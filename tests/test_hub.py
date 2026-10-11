"""The phone hub's laptop side: requests from the hub get the same checks as the tunnel, and pairing uses the fixed link."""

import asyncio
import base64
import json

from fakes import FakeRouter
from fastapi.testclient import TestClient

from teamloop.server import hub, phones
from teamloop.server.app import build_crew, create_app

TUNNEL = {"cf-connecting-ip": "203.0.113.9"}


def make_app(tmp_path):
    return create_app(build_crew(tmp_path / "h.db", router=FakeRouter([])))


def request(path, method="GET", headers=None, body=b""):
    return {"id": "r1", "method": method, "path": path, "headers": headers or {}, "body": base64.b64encode(body).decode()}


async def test_hub_requests_need_a_paired_phone_like_the_tunnel(tmp_path):
    app = make_app(tmp_path)
    out = await hub.answer(app, request("/api/chats"))
    assert (out["id"], out["status"]) == ("r1", 401)  # remote: no cookie, no API
    code = app.state.phones.new_code()
    paired = await hub.answer(app, request("/pair", "POST", {"content-type": "application/x-www-form-urlencoded",
                                                               "user-agent": "Mozilla (Linux; Android 14)"},
                                           f"code={code}".encode()))
    assert paired["status"] == 303
    cookie = next(v for k, v in paired["headers"] if k == "set-cookie").split(";")[0]
    ok = await hub.answer(app, request("/api/chats", headers={"cookie": cookie}))
    assert ok["status"] == 200 and any(c["id"] == "team" for c in json.loads(base64.b64decode(ok["body"])))
    assert (await hub.answer(app, request("/console", headers={"cookie": cookie})))["status"] == 404  # laptop only


async def test_laptop_dials_out_and_answers_through_the_hub(tmp_path, monkeypatch):
    from websockets.asyncio.server import serve

    app = make_app(tmp_path)
    got = {}

    async def fake_hub(ws):  # what the Durable Object does: send a phone request, wait for the answer
        got["secret"] = ws.request.headers.get("x-link-secret")
        await ws.send(json.dumps(request("/api/version")))
        got["answer"] = json.loads(await ws.recv())

    async with serve(fake_hub, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        app.state.crew.store.set_setting(hub.SETTING, f"http://127.0.0.1:{port}")
        monkeypatch.setenv(hub.SECRET, "s3cret-value-for-test")
        task = asyncio.create_task(hub.run(app))
        for _ in range(100):
            if "answer" in got:
                break
            await asyncio.sleep(0.05)
        task.cancel()
    assert got["secret"] == "s3cret-value-for-test"
    assert got["answer"]["id"] == "r1" and got["answer"]["status"] == 401  # remote without a cookie, as it should be


def test_pairing_uses_the_fixed_link_when_the_hub_is_connected(tmp_path, monkeypatch):
    app = make_app(tmp_path)
    app.state.crew.store.set_setting(hub.SETTING, "https://teamloop-hub.me.workers.dev")
    monkeypatch.setenv(hub.SECRET, "s3cret-value-for-test")
    monkeypatch.setitem(hub.state, "connected", True)

    async def no_tunnel():
        raise AssertionError("no quick tunnel when the hub is there")

    monkeypatch.setattr(app.state.phones, "tunnel", no_tunnel)
    with TestClient(app) as client:
        link = client.post("/api/phones/pair").json()["link"]
        status = client.get("/api/hub").json()
    assert link.startswith("https://teamloop-hub.me.workers.dev/pair?code=")
    assert status["configured"] and status["connected"] and status["url"].endswith("workers.dev")


def test_hub_setup_is_laptop_only(tmp_path):
    app = make_app(tmp_path)
    token = app.state.phones.redeem(app.state.phones.new_code(), "Phone")
    with TestClient(app, base_url="https://x.trycloudflare.com") as client:
        res = client.post("/api/hub/setup", headers={**TUNNEL, "cookie": f"{phones.COOKIE}={token}"})
    assert res.status_code == 403
