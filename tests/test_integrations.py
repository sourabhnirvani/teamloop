"""Build A/H: Telegram from Settings (save a token, allowed people, restart without a server restart, turn off) and the
new Telegram commands (/sleep, /wake, /crew). A fake Telegram API; never the network, never a real token."""

import asyncio
import os

import httpx
import pytest
from fakes import FakeRouter, make_crew
from fastapi.testclient import TestClient

from teamloop.keys import vault
from teamloop.keys.redact import redact
from teamloop.server import telegram
from teamloop.server.app import build_crew, create_app

GOOD = "123456789:" + "AAfakeTokenForTestsOnly_abcdefghijklmn"
BAD = "987654321:" + "AAthisTokenIsRejectedByFakeTelegram_xyz"


async def fake_telegram(request: httpx.Request) -> httpx.Response:
    method = request.url.path.rsplit("/", 1)[-1]
    token = request.url.path.split("/bot", 1)[1].split("/", 1)[0]
    if method == "getMe":
        if token == GOOD:
            return httpx.Response(200, json={"ok": True, "result": {"username": "teamloop_test_bot"}})
        return httpx.Response(401, json={"ok": False, "description": "Unauthorized"})
    if method == "getUpdates":
        await asyncio.sleep(0.2)  # a long poll with nothing new
        return httpx.Response(200, json={"ok": True, "result": []})
    return httpx.Response(200, json={"ok": True, "result": True})


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(telegram, "client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(fake_telegram)))
    for name in ("TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID"):
        os.environ.pop(name, None)
    yield
    telegram.stop()


def app_client(tmp_path):
    return TestClient(create_app(build_crew(tmp_path / "i.db", router=FakeRouter([]))))


def test_saving_a_token_starts_the_bridge_and_hides_the_token(tmp_path):
    with app_client(tmp_path) as c:
        assert c.get("/api/integrations").json()["telegram"]["on"] is False
        r = c.post("/api/integrations/telegram", json={"token": GOOD, "allowed_ids": "555, 777"})
        assert r.status_code == 200, r.text
        assert GOOD not in r.text
        state = c.get("/api/integrations").json()
    assert state["telegram"] == {"on": True, "bot_name": "@teamloop_test_bot", "allowed_ids_count": 2, "error": ""}
    assert vault.load()["TELEGRAM_TOKEN"] == GOOD and vault.load()["TELEGRAM_CHAT_ID"] == "555,777"
    assert redact(f"token {GOOD}") == "token [hidden key]"


def test_a_new_token_restarts_the_bridge_without_a_server_restart(tmp_path):
    with app_client(tmp_path) as c:
        c.post("/api/integrations/telegram", json={"token": GOOD})
        first = telegram.STATE["task"]
        c.post("/api/integrations/telegram", json={"allowed_ids": ["555"]})
        second = telegram.STATE["task"]
        assert first is not second and first.cancelled() or first.done()
        assert c.get("/api/integrations").json()["telegram"]["allowed_ids_count"] == 1


def test_bad_tokens_and_ids_get_a_clear_error(tmp_path):
    with app_client(tmp_path) as c:
        rejected = c.post("/api/integrations/telegram", json={"token": BAD})
        shape = c.post("/api/integrations/telegram", json={"token": "not-a-token"})
        ids = c.post("/api/integrations/telegram", json={"allowed_ids": "555, @someone"})
        empty = c.post("/api/integrations/telegram", json={})
    assert rejected.status_code == 400 and "isn't valid" in rejected.json()["detail"]
    assert shape.status_code == 400 and "@BotFather" in shape.json()["detail"]
    assert ids.status_code == 400 and "@someone" in ids.json()["detail"]
    assert empty.status_code == 400
    assert "TELEGRAM_TOKEN" not in vault.load()


def test_turning_it_off(tmp_path):
    with app_client(tmp_path) as c:
        c.post("/api/integrations/telegram", json={"token": GOOD, "allowed_ids": "555"})
        off = c.delete("/api/integrations/telegram").json()
    assert off["on"] is False and "TELEGRAM_TOKEN" not in vault.load() and not os.environ.get("TELEGRAM_TOKEN")


def test_a_token_from_env_cannot_be_removed_here(tmp_path):
    os.environ["TELEGRAM_TOKEN"] = GOOD
    with app_client(tmp_path) as c:
        r = c.delete("/api/integrations/telegram")
    assert r.status_code == 409 and ".env" in r.json()["detail"]


class FakeTG:
    def __init__(self):
        self.sent = []

    async def post(self, url, json=None, data=None, files=None):
        self.sent.append((url.rsplit("/", 1)[-1], json or data))
        return type("R", (), {"json": lambda self: {"ok": True, "result": True}})()


async def test_sleep_wake_and_crew_commands(tmp_path):
    crew = make_crew(tmp_path, [])
    tg = FakeTG()
    bridge = telegram.Bridge(crew, "TOKEN", ["555"], tg)
    await bridge.command("/sleep", "555")
    await crew.wait_idle("team")
    assert crew.store.get_setting("asleep") is True
    await bridge.command("/wake", "555")
    await crew.wait_idle("team")
    assert crew.store.get_setting("asleep") is False
    await bridge.command("/crew", "555")
    text = tg.sent[-1][1]["text"]
    assert text.startswith("The crew:") and "Desk: Computer" in text and "(tinkerer)" in text.lower()
