"""Build L probe: try to break pairing, the phone guard, approvals and the hub hop on this machine.

    .venv\\Scripts\\python.exe evidence\\runs\\security-probe-yang.py

Runs the real app in-process (fake model, temp workspace). "Remote" requests carry cf-connecting-ip, as every
request through a quick tunnel or the hub does. Prints one line per attempt: verdict, request, what came back.
Fake keys only; nothing leaves the machine.
"""

from __future__ import annotations

import asyncio
import base64
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
ws = Path(tempfile.mkdtemp(prefix="tl-sec-"))
os.environ.update(TEAMLOOP_WORKSPACE=str(ws), TEAMLOOP_DB=str(ws / "t.db"), TEAMLOOP_VAULT=str(ws / "keys.vault"),
                  TEAMLOOP_TRACE="0")

from fakes import FakeRouter  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from teamloop.server import hub, phones  # noqa: E402
from teamloop.server.app import build_crew, create_app  # noqa: E402

REMOTE = {"cf-connecting-ip": "203.0.113.7"}
rows: list[tuple[str, str, str, str]] = []


def note(verdict: str, attempt: str, request: str, got: str) -> None:
    rows.append((verdict, attempt, request, got))
    print(f"{verdict:4} | {attempt} | {request} | {got}")


crew = build_crew(ws / "t.db", router=FakeRouter([]))
app = create_app(crew)
P = app.state.phones

with TestClient(app) as c:
    # ---- pairing ------------------------------------------------------------------------------------------
    code = P.new_code()
    r = c.post("/pair", content=f"code={code}", headers={**REMOTE, "content-type": "application/x-www-form-urlencoded"},
               follow_redirects=False)
    cookie = r.cookies.get(phones.COOKIE)
    set_cookie = r.headers.get("set-cookie", "")
    note("PASS" if r.status_code == 303 and cookie else "FAIL", "pair with a fresh code", "POST /pair code=<fresh>",
         f"{r.status_code}, cookie flags: {'; '.join(p.strip() for p in set_cookie.split(';')[1:])}")
    r = c.post("/pair", content=f"code={code}", headers={**REMOTE, "content-type": "application/x-www-form-urlencoded"})
    note("PASS" if r.status_code == 400 else "FAIL", "reuse a used code", "POST /pair code=<same code again>",
         str(r.status_code))
    old = P.new_code()
    P.codes[old] = time.time() - 1
    r = c.post("/pair", content=f"code={old}", headers={**REMOTE, "content-type": "application/x-www-form-urlencoded"})
    note("PASS" if r.status_code == 400 else "FAIL", "use an expired code", "POST /pair code=<expired 1 s ago>",
         str(r.status_code))
    live = P.new_code()
    tries = 0
    for i in range(12):
        tries += 1
        c.post("/pair", content="code=AAAAAAAA", headers={**REMOTE, "content-type": "application/x-www-form-urlencoded"})
        if live not in P.codes:
            break
    note("PASS" if live not in P.codes else "FAIL", "brute-force codes",
         "12 x POST /pair code=AAAAAAAA (wrong) while a real code is open",
         f"after {tries} wrong tries every open code was wiped (24^8 = 1.1e11 codes, 10 tries per wipe)")
    note("NOTE", "brute-force side effect", "same as above",
         "the fail counter is global and never resets on success: anyone who can reach /pair can wipe a code the "
         "person is about to type (annoyance, not a bypass)")

    # ---- the phone guard (requests that arrive through the tunnel / hub) ------------------------------------
    r = c.get("/api/chats", headers=REMOTE)
    note("PASS" if r.status_code == 401 else "FAIL", "API without a cookie", "GET /api/chats (remote, no cookie)",
         str(r.status_code))
    r = c.get("/api/chats", headers={"x-forwarded-for": "127.0.0.1"})
    note("PASS" if r.status_code == 401 else "FAIL", "spoof x-forwarded-for: 127.0.0.1", "GET /api/chats",
         f"{r.status_code} (any proxy header counts as remote, whatever its value)")
    tricks = ["//api/chats", "/API/chats", "/api/../api/chats", "/%61pi/chats", "/api%2Fchats", "/api/chats/",
              "/docs", "/DOCS", "/docs/", "/console", "/c%6Fnsole", "//console", "/openapi.json", "/redoc",
              "/api/phones", "/api/events"]
    for path in tricks:
        r = c.get(path, headers=REMOTE, follow_redirects=False)
        body = r.text[:60].replace("\n", " ")
        leaked = r.status_code == 200 and ("openapi" in r.text[:200].lower() or r.text.lstrip().startswith(("[", "{"))
                                           or "<title>TeamLoop console" in r.text)
        note("FAIL" if leaked else "PASS", "reach a laptop-only path, no cookie", f"GET {path}",
             f"{r.status_code} {body!r}")

    c.cookies.set(phones.COOKIE, cookie)
    r = c.get("/api/chats", headers=REMOTE)
    note("PASS" if r.status_code == 200 else "FAIL", "paired phone reaches the API", "GET /api/chats (cookie)",
         str(r.status_code))
    r = c.get("/api/phones", headers=REMOTE)
    note("PASS" if r.status_code == 403 else "FAIL", "paired phone manages phones", "GET /api/phones (cookie)",
         str(r.status_code))
    for path in ["/docs", "/console", "/openapi.json"]:
        r = c.get(path, headers=REMOTE)
        note("PASS" if r.status_code == 404 else "FAIL", "paired phone opens a laptop-only page", f"GET {path} (cookie)",
             str(r.status_code))

    # ---- approvals -------------------------------------------------------------------------------------------
    async def card():
        return await crew.gate.ask("dm-s", "desk", "Open an app", "Open Calculator.")
    import threading
    answered: dict = {}

    def ask_in_thread():
        answered["ok"] = asyncio.run(card())
    t = threading.Thread(target=ask_in_thread)
    t.start()
    for _ in range(50):
        waiting = crew.gate.waiting_cards()
        if waiting:
            break
        time.sleep(0.05)
    aid = waiting[0]["id"] if waiting else "none"
    c.cookies.clear()
    r = c.post(f"/api/approvals/{aid}", json={"ok": True}, headers=REMOTE)
    note("PASS" if r.status_code == 401 else "FAIL", "answer a card from an unpaired phone",
         "POST /api/approvals/<id> {ok:true} (remote, no cookie)", str(r.status_code))
    phone_id = P.list()[0]["id"]
    P.remove(phone_id)
    c.cookies.set(phones.COOKIE, cookie)
    r = c.post(f"/api/approvals/{aid}", json={"ok": True}, headers=REMOTE)
    note("PASS" if r.status_code == 401 else "FAIL", "answer a card with a removed phone's cookie",
         "POST /api/approvals/<id> {ok:true} (remote, removed phone's cookie)", str(r.status_code))
    c.cookies.clear()

    # ---- CSRF against the laptop itself (no cookie needed there) ------------------------------------------------
    evil = {"origin": "https://evil.example", "content-type": "text/plain"}
    r = c.post(f"/api/approvals/{aid}", content='{"ok": true}', headers=evil)
    note("FAIL" if r.status_code == 200 else "PASS", "CSRF: another website approves a card",
         "POST /api/approvals/<id> from Origin https://evil.example, text/plain body {\"ok\": true}",
         f"{r.status_code} {r.text[:80]!r}")
    crew.gate.answer(aid, False)
    t.join(5)
    r = c.post("/api/chats/dm-s/messages", content='{"text": "hello from another website"}', headers=evil)
    note("FAIL" if r.status_code == 200 else "PASS", "CSRF: another website posts into a chat",
         "POST /api/chats/dm-s/messages from Origin https://evil.example, text/plain", f"{r.status_code} {r.text[:80]!r}")
    r = c.post("/api/keys/cleanup", headers={"origin": "https://evil.example"})
    note("FAIL" if r.status_code == 200 else "PASS", "CSRF: another website triggers a body-less POST",
         "POST /api/keys/cleanup from Origin https://evil.example (a plain form post can do this)",
         f"{r.status_code} {r.text[:80]!r}")
    r = c.post("/api/stop-all" if False else "/api/chats/dm-s/stop", headers={"origin": "https://evil.example"})
    note("FAIL" if r.status_code == 200 else "PASS", "CSRF: another website stops a chat",
         "POST /api/chats/dm-s/stop from Origin https://evil.example", f"{r.status_code} {r.text[:80]!r}")
    started: list[str] = []

    async def fake_tunnel():
        started.append("tunnel")
        return "https://fake.trycloudflare.com"

    async def fake_setup(store):
        started.append("hub setup")
    P.tunnel = fake_tunnel                       # stand-ins: record the call, open nothing
    hub.setup_in_background = fake_setup
    r = c.post("/api/phones/pair", headers={"origin": "https://evil.example"})
    note("FAIL" if "tunnel" in started else "PASS", "CSRF: another website opens a public tunnel",
         "POST /api/phones/pair from Origin https://evil.example (cloudflared stubbed)",
         f"{r.status_code}; tunnel started: {'tunnel' in started} (a pairing code is minted too; the site can't "
         "read it, but the laptop is now reachable from the internet)")
    r = c.post("/api/hub/setup", headers={"origin": "https://evil.example"})
    note("FAIL" if "hub setup" in started else "PASS", "CSRF: another website starts the Cloudflare hub setup",
         "POST /api/hub/setup from Origin https://evil.example (setup stubbed)",
         f"{r.status_code}; setup started: {'hub setup' in started} (real one opens a Cloudflare sign-in and deploys)")
    r = c.get("/api/keys", headers={"host": "evil.example"})
    note("FAIL" if r.status_code == 200 else "PASS", "DNS rebinding: Host is not checked",
         "GET /api/keys with Host: evil.example (what a rebinding page on the laptop sends)",
         f"{r.status_code} (a rebinding page could read every laptop API answer)")
    r = c.post("/api/chats/dm-s/messages", json={"text": "sent by a rebinding page"},
               headers={"host": "evil.example:8790", "origin": "http://evil.example:8790"})
    note("FAIL" if r.status_code in (200, 202) else "PASS", "DNS rebinding: a page drives the crew",
         "POST /api/chats/dm-s/messages, JSON, Host and Origin http://evil.example:8790 (same-origin after rebinding)",
         f"{r.status_code} {r.text[:60]!r}")
    r = c.post("/pair", content="code=AAAAAAAA", headers={**REMOTE, "origin": "https://evil.example",
                                                          "content-type": "application/x-www-form-urlencoded"})
    note("PASS", "CSRF on /pair", "POST /pair from Origin https://evil.example",
         f"{r.status_code}: needs a live code from this laptop; the cookie is HttpOnly, Secure, SameSite=Strict, so "
         "a cross-site post can't ride an existing pairing")


# ---- the hub hop: what hub.answer does with what the Worker sends ------------------------------------------------
async def through_hub(path: str, headers: dict, method: str = "GET", body: bytes = b"") -> dict:
    msg = {"id": "x", "method": method, "path": path, "headers": headers, "body": base64.b64encode(body).decode()}
    return await asyncio.wait_for(hub.answer(app, msg), 10)


async def hub_attempts():
    for path, hdrs, label in [
        ("/api/chats", {}, "no proxy headers at all (local wrangler dev adds none)"),
        ("//127.0.0.1:8790/api/chats", {}, "pathname starting with // (host-like)"),
        ("//x/console", {}, "// path to a laptop-only page the Worker doesn't block"),
        ("/api/chats", {"X-Forwarded-For": "127.0.0.1"}, "phone sends its own X-Forwarded-For"),
    ]:
        res = await through_hub(path, hdrs)
        body = base64.b64decode(res["body"])[:60]
        ok = res["status"] in (401, 404)
        note("PASS" if ok else "FAIL", f"hub hop: {label}", f"GET {path}", f"{res['status']} {body!r}")
    code = P.new_code()
    res = await through_hub("/pair", {"content-type": "application/x-www-form-urlencoded"}, "POST",
                            f"code={code}".encode())
    tok = next((v.split("=", 1)[1].split(";")[0] for k, v in res["headers"] if k == "set-cookie"), "")
    try:
        res = await through_hub("/api/events", {"cookie": f"{phones.COOKIE}={tok}"})
        note("PASS", "hub hop: SSE stream with a cookie", "GET /api/events (cookie) via hub.answer",
             f"{res['status']} came back")
    except asyncio.TimeoutError:
        note("FAIL", "hub hop: SSE stream with a cookie",
             "GET /api/events (paired cookie) via hub.answer, path the Worker blocks but //x/api/events or "
             "/api/%65vents would pass it",
             "hub.answer never returns (waited 10 s): the stream never ends, so each such request leaves a task "
             "and an open stream on the laptop for good")

asyncio.run(hub_attempts())

fails = [r for r in rows if r[0] == "FAIL"]
print(f"\n{len(rows)} attempts, {len(fails)} FAIL")
