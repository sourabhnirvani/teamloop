"""Other websites can't use TeamLoop on the laptop: DNS rebinding (a foreign Host) and cross-site requests (a foreign
Origin) are refused, and the phone's ways in (tunnel, hub) still work. Found by jrkrishh's security review
(evidence/runs/security-review-yang.md)."""

import asyncio

from fakes import FakeRouter
from fastapi.testclient import TestClient

from teamloop.server import hub, phones
from teamloop.server.app import build_crew, create_app


def client_for(tmp_path, base_url="http://127.0.0.1:8790"):
    app = create_app(build_crew(tmp_path / "w.db", router=FakeRouter(["ok"] * 5)))
    return app, TestClient(app, base_url=base_url)


def test_a_rebinding_page_cant_read_or_drive_the_app(tmp_path):
    # the browser connects to 127.0.0.1 but says Host: evil.example (the attacker's name, re-pointed at the laptop)
    app, client = client_for(tmp_path, "http://evil.example:8790")
    with client:
        assert client.get("/api/keys").status_code == 400
        assert client.get("/api/chats").status_code == 400
        sent = client.post("/api/chats/dm-s/messages", json={"text": "run something"},
                           headers={"origin": "http://evil.example:8790"})
        assert sent.status_code == 400
    assert app.state.crew.store.messages("dm-s") == []  # the crew never saw it


def test_other_sites_cant_post_to_the_laptop(tmp_path, monkeypatch):
    app, client = client_for(tmp_path)

    async def never(*a, **kw):  # if a refusal ever regressed, this test must not start a real tunnel or deploy
        raise AssertionError("reached a real side effect")

    monkeypatch.setattr(hub, "setup_in_background", never)
    monkeypatch.setattr(app.state.phones, "tunnel", never)
    with client:
        for path in ("/api/keys/cleanup", "/api/keys/test", "/api/models/check", "/api/chats/team/stop",
                     "/api/hub/setup", "/api/phones/pair"):
            for headers in ({"origin": "https://evil.example"}, {"origin": "null"},
                            {"sec-fetch-site": "cross-site"}, {"origin": "https://attacker.trycloudflare.com"}):
                assert client.post(path, headers=headers).status_code == 403, (path, headers)


def test_the_app_itself_and_its_phone_ways_in_still_work(tmp_path, monkeypatch):
    app, client = client_for(tmp_path)
    with client:  # the laptop app (Electron, the browser at 127.0.0.1 or localhost, the Vite dev server)
        for origin in ("http://127.0.0.1:8790", "http://localhost:8790", "http://localhost:5173"):
            res = client.post("/api/chats/team/stop", headers={"origin": origin, "sec-fetch-site": "same-origin"})
            assert res.status_code == 200, origin
        assert client.post("/api/chats/team/stop").status_code == 200  # no Origin: not a browser page
    # a phone through the quick tunnel: Host and Origin are the tunnel's own name
    tunnel = "https://bright-words-here.trycloudflare.com"
    (tmp_path / "t").mkdir()
    app, client = client_for(tmp_path / "t", tunnel)
    token = app.state.phones.redeem(app.state.phones.new_code(), "Phone")
    with client:
        res = client.post("/api/chats/team/stop", headers={"origin": tunnel, "x-forwarded-for": "1.2.3.4",
                                                           "cookie": f"{phones.COOKIE}={token}"})
        assert res.status_code == 200
    # a phone through the fixed hub: Host is "hub", Origin is the hub's workers.dev address
    (tmp_path / "h").mkdir()
    app, _ = client_for(tmp_path / "h")
    app.state.crew.store.set_setting(hub.SETTING, "https://teamloop-hub.me.workers.dev")
    token = app.state.phones.redeem(app.state.phones.new_code(), "Phone")
    msg = {"id": "1", "method": "POST", "path": "/api/chats/team/stop", "body": "",
           "headers": {"origin": "https://teamloop-hub.me.workers.dev", "sec-fetch-site": "same-origin",
                       "cookie": f"{phones.COOKIE}={token}"}}
    with TestClient(app):
        assert asyncio.run(hub.answer(app, msg))["status"] == 200
        evil = {**msg, "headers": {**msg["headers"], "origin": "https://evil.example", "sec-fetch-site": "cross-site"}}
        assert asyncio.run(hub.answer(app, evil))["status"] == 403


def test_a_phone_cant_open_the_laptops_endless_event_stream(tmp_path):
    # through the hub, /api/events (SSE) never ends, so each such request would hang on the laptop forever
    app, _ = client_for(tmp_path)
    token = app.state.phones.redeem(app.state.phones.new_code(), "Phone")
    msg = {"id": "1", "method": "GET", "path": "/api/events", "body": "", "headers": {"cookie": f"{phones.COOKIE}={token}"}}
    with TestClient(app):
        out = asyncio.run(asyncio.wait_for(hub.answer(app, msg), 10))
    assert out["status"] == 404  # phones long-poll /api/events/poll instead


def test_a_paired_phone_sees_telegram_but_cant_change_who_may_use_it(tmp_path):
    # a stolen phone mustn't add its own Telegram id (the bot drives this laptop) and keep control after removal
    app, client = client_for(tmp_path, "https://bright-words-here.trycloudflare.com")
    token = app.state.phones.redeem(app.state.phones.new_code(), "Phone")
    phone = {"x-forwarded-for": "1.2.3.4", "cookie": f"{phones.COOKIE}={token}",
             "origin": "https://bright-words-here.trycloudflare.com"}
    with client:
        assert client.get("/api/integrations", headers=phone).status_code == 200
        assert client.post("/api/integrations/telegram", json={"allowed_ids": "42"}, headers=phone).status_code == 403
        assert client.delete("/api/integrations/telegram", headers=phone).status_code == 403
