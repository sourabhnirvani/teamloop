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
