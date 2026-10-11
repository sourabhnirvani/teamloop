import asyncio

from fakes import FakeRouter
from fastapi.testclient import TestClient

from teamloop.server import phones
from teamloop.server.app import build_crew, create_app

TUNNEL = {"cf-connecting-ip": "203.0.113.9"}  # what cloudflared adds to every request


def app_and_client(tmp_path):
    app = create_app(build_crew(tmp_path / "p.db", router=FakeRouter([])))
    return app, TestClient(app, base_url="https://x.trycloudflare.com")


def test_tunnel_requests_need_a_paired_phone(tmp_path):
    app, client = app_and_client(tmp_path)
    with client:
        assert client.get("/api/chats").status_code == 200  # on the laptop itself
        assert client.get("/api/chats", headers=TUNNEL).status_code == 401
        assert client.get("/api/chats", headers={**TUNNEL, "cookie": f"{phones.COOKIE}=guess"}).status_code == 401
        assert client.get("/pair", headers=TUNNEL).status_code == 200  # the pairing page itself is open
        for page in ("/docs", "/redoc", "/openapi.json"):
            assert client.get(page, headers=TUNNEL).status_code == 404
            assert client.get(page).status_code == 200  # still there on the laptop


def test_pair_with_code_then_remove(tmp_path):
    app, client = app_and_client(tmp_path)
    with client:
        code = app.state.phones.new_code()
        res = client.post("/pair", content=f"code={code[:4]}-{code[4:].lower()}", follow_redirects=False,
                          headers={**TUNNEL, "content-type": "application/x-www-form-urlencoded",
                                   "user-agent": "Mozilla (Linux; Android 14)"})
        assert res.status_code == 303
        token = res.cookies[phones.COOKIE]
        paired = {**TUNNEL, "cookie": f"{phones.COOKIE}={token}"}
        assert client.get("/api/chats", headers=paired).status_code == 200
        assert client.get("/api/phones", headers=paired).status_code == 403  # phones are managed on the laptop

        [phone] = client.get("/api/phones").json()
        assert phone["name"] == "Android phone" and "hash" not in phone
        assert client.delete(f"/api/phones/{phone['id']}").json() == {"ok": True}
        assert client.get("/api/chats", headers=paired).status_code == 401


def test_codes_work_once_and_guessing_kills_them(tmp_path):
    app, client = app_and_client(tmp_path)
    store = app.state.phones
    code = store.new_code()
    assert store.redeem(code, "Phone")
    assert store.redeem(code, "Phone") is None
    fresh = store.new_code()
    for _ in range(phones.MAX_FAILS):
        store.redeem("WRONGONE", "Phone")
    assert store.redeem(fresh, "Phone") is None


def test_bad_code_shows_the_page_again(tmp_path):
    app, client = app_and_client(tmp_path)
    with client:
        res = client.post("/pair", content="code=<b>", headers={**TUNNEL, "content-type": "application/x-www-form-urlencoded"})
        assert res.status_code == 400 and "wrong or expired" in res.text and "<b>" not in res.text


async def test_event_log_long_poll_returns_new_events():
    from teamloop.crew.events import Bus

    bus = Bus()
    log = phones.EventLog(bus)
    log.start()
    await asyncio.sleep(0)
    assert await log.after(0, 0.05) == []  # nothing new: the poll just times out
    waiting = asyncio.create_task(log.after(0, 5))
    await asyncio.sleep(0)
    await bus.emit("typing", chat_id="team", bot="s", on=True)
    [event] = await waiting
    assert event["type"] == "typing" and log.seq == 1


async def test_first_poll_brings_cards_still_waiting(tmp_path):
    import httpx

    crew = build_crew(tmp_path / "p.db", router=FakeRouter([]))
    app = create_app(crew)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1") as client:
        assert (await client.get("/api/events/poll", params={"after": -1})).json() == {"seq": 0, "events": []}
        asked = asyncio.create_task(crew.gate.ask("team", "desk", "Lock", "Lock the laptop now."))
        await asyncio.sleep(0.05)
        first = (await client.get("/api/events/poll", params={"after": -1})).json()
        assert [e["title"] for e in first["events"]] == ["Lock"]
        later = (await client.get("/api/events/poll", params={"after": 99, "wait": 0.05})).json()
        assert later["seq"] == first["seq"]  # a stale number from before a restart starts over
        crew.gate.answer(first["events"][0]["id"], False)
        assert await asked is False


def test_pairing_qr_scales_without_cropping(tmp_path, monkeypatch):
    app, client = app_and_client(tmp_path)

    async def fake_tunnel():
        return "https://colours-birthday-spies-app.trycloudflare.com"

    monkeypatch.setattr(app.state.phones, "tunnel", fake_tunnel)
    with client:
        qr = client.post("/api/phones/pair").json()["qr"]
    head = qr[:qr.index(">")]
    assert "viewBox" in head and "width=" not in head and "height=" not in head  # CSS sizes it, nothing cut off
    size = int(head.split('viewBox="0 0 ')[1].split()[0])
    assert size in {21 + 4 * v + 8 for v in range(1, 41)}  # a whole QR symbol plus 4 modules of quiet zone each side
