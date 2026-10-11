import time
from types import SimpleNamespace

from fakes import FakeRouter
from fastapi.testclient import TestClient

from teamloop.keys import vault
from teamloop.server.app import build_crew, create_app
from teamloop.tools import files


def test_api_roundtrip(tmp_path):
    crew = build_crew(tmp_path / "api.db", router=FakeRouter(["Hello from S"]))
    with TestClient(create_app(crew)) as client:
        bots = client.get("/api/bots").json()
        assert [b["id"] for b in bots] == ["s", "desk", "web", "scout", "inbox", "writer"]
        assert {c["id"] for c in client.get("/api/chats").json()} >= {"team", "dm-s"}

        assert client.post("/api/chats/dm-s/messages", json={"text": "hi"}).status_code == 202
        deadline = time.time() + 3
        while time.time() < deadline and len(client.get("/api/chats/dm-s/messages").json()) < 2:
            time.sleep(0.02)
        assert client.get("/api/chats/dm-s/messages").json()[-1]["text"] == "Hello from S"

        duo = client.post("/api/chats", json={"title": "Duo", "members": ["web", "scout", "nobody"]}).json()
        assert duo["members"] == ["web", "scout"]
        assert client.post("/api/chats/nope/messages", json={"text": "x"}).status_code == 404
        assert client.post("/api/approvals/nope", json={"ok": True}).status_code == 404
        assert client.post("/api/settings", json={"save_tokens": True}).json()["save_tokens"] is True
        assert isinstance(client.get("/api/keys").json(), list)


def test_settings_key_box_saves_telegram_and_neatlogs_keys(tmp_path):
    crew = build_crew(tmp_path / "api.db", router=FakeRouter([]))
    neat, tg = "nl_" + "k" * 30, "1234567890:" + "A" * 35
    with TestClient(create_app(crew)) as client:
        out = client.post("/api/keys", json={"text": f"neatlogs key: {neat}\n{tg}"}).json()
        assert [o["provider"] for o in out] == ["neatlogs", "telegram"]
        assert out[0]["text"].startswith("Saved your neatlogs key.") and out[1]["text"] == "Saved your Telegram key."
        assert vault.load() == {"NEATLOGS_API_KEY": neat, "TELEGRAM_TOKEN": tg}
        assert client.post("/api/keys", json={"text": "no key here"}).status_code == 400


class Ctx(SimpleNamespace):
    async def approve(self, title, details, screenshot=None):
        self.asked = title
        return self.answer


async def test_files_write_read_and_refuse_outside(workspace):
    ctx = Ctx(answer=True)
    saved = await files.write_file({"path": "workspace/notes/a.md", "content": "hello"}, ctx)
    assert saved.ok and saved.data["bytes"] == 5
    assert (await files.read_file({"path": "workspace/notes/a.md"}, ctx)).data["text"] == "hello"

    again = await files.write_file({"path": "workspace/notes/a.md", "content": "x"}, ctx)
    assert not again.ok and "already exists" in again.text

    ctx.answer = False
    denied = await files.write_file({"path": "workspace/notes/a.md", "content": "x", "overwrite": True}, ctx)
    assert not denied.ok and ctx.asked == "Replace a file"

    outside = await files.write_file({"path": "C:/Windows/evil.txt", "content": "x"}, ctx)
    assert not outside.ok and outside.text.startswith("Refused:")
    sneaky = await files.write_file({"path": "workspace/../../escape.txt", "content": "x"}, ctx)
    assert not sneaky.ok


def test_sign_in_opens_a_tab_in_the_crews_chrome(tmp_path):
    from teamloop.browser import kit as browser_kit

    opened = []

    class Page:
        url = ""

        async def goto(self, url, **kw):
            self.url = url
            opened.append(url)

        async def bring_to_front(self):
            pass

    class Context:
        async def new_page(self):
            return Page()

    class Host:
        headless = False
        context = Context()

        async def start(self):
            pass

    browser_kit.set_host(Host())
    try:
        crew = build_crew(tmp_path / "api.db", router=FakeRouter([]))
        with TestClient(create_app(crew)) as client:
            out = client.post("/api/browser/signin", json={}).json()
            assert out["ok"] and opened == ["https://accounts.google.com"]
            assert client.post("/api/browser/signin", json={"url": "http://evil.example"}).status_code == 400
    finally:
        browser_kit.set_host(None)


async def test_each_model_call_is_counted_and_announced(tmp_path):
    import asyncio

    from teamloop.server.app import usage_hook

    crew = build_crew(tmp_path / "api.db", router=FakeRouter([]))
    with crew.bus.subscribe() as queue:
        usage_hook(crew.store, crew.bus)("nvidia", "nemotron", 120, 30, "turn:s")
        event = await asyncio.wait_for(queue.get(), 2)
    assert event["type"] == "usage" and event["provider"] == "nvidia" and event["tokens_in"] == 120
    assert crew.store.usage()[0]["requests"] == 1
