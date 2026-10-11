"""Phones: reach TeamLoop from your phone over a free Cloudflare quick tunnel.

The laptop shows a QR code / 8-letter code (one use, 10 minutes). Redeeming it gives that phone its own
token in a cookie; a phone can be removed at any time. Anything that arrives through the tunnel must carry
a paired phone's token to reach /api, because the API can drive the laptop."""

from __future__ import annotations

import asyncio
import hashlib
import html
import mimetypes
import re
import secrets
import shutil
import subprocess
import threading
import time
import uuid
from collections import deque
from urllib.parse import parse_qs, urlsplit

import segno
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from teamloop import config

COOKIE = "teamloop_phone"
CODE_SECONDS = 600
MAX_FAILS = 10
LOCKOUT_SECONDS = 600  # wrong codes are counted per sender over this long
LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ"  # no I or O, so a typed code can't be misread
PROXY_HEADERS = ("cf-connecting-ip", "x-forwarded-for", "forwarded")
API_PAGES = {"/docs", "/docs/oauth2-redirect", "/redoc", "/openapi.json", "/console"}
LOCAL_HOSTS = {"127.0.0.1", "::1", "testclient"}  # the server only listens on loopback
TUNNEL_URL = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
mimetypes.add_type("application/manifest+json", ".webmanifest")


def is_remote(request: Request) -> bool:
    host = request.client.host if request.client else ""
    return host not in LOCAL_HOSTS or any(h in request.headers for h in PROXY_HEADERS)


# ---- other websites ----------------------------------------------------------------------------------------
# The app listens on loopback, but a web page in the person's browser can still reach it: by re-pointing its own
# name at 127.0.0.1 (DNS rebinding: the Host header is then the attacker's name), or by posting a form straight to
# 127.0.0.1:8790 (CSRF: the Origin is the attacker's site). Both are refused here, before anything else runs.
LOOPBACK_NAMES = {"localhost", "127.0.0.1", "::1"}
TEST_NAMES = {"testserver", "testclient"}  # FastAPI's TestClient
HUB_HOST = "hub"  # what hub.answer() calls the app
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def hostname(value: str) -> str:
    """'Evil.Example:8790' -> 'evil.example'; '[::1]:8790' -> '::1'; 'https://x.y.dev' -> 'x.y.dev'."""
    v = (value or "").strip().lower()
    if "://" in v:
        v = urlsplit(v).netloc
    if v.startswith("["):
        return v[1:v.index("]")] if "]" in v else v
    return v.rsplit(":", 1)[0] if v.count(":") == 1 else v


def _hub_name(store) -> str:
    from teamloop.server import hub

    return hostname(store.get_setting(hub.SETTING) or "")


def trusted_host(request: Request, store) -> bool:
    """Requests addressed to this laptop by a name it answers to: loopback, the hub relay, a quick tunnel
    (Cloudflare owns those names, so they can't be re-pointed at the laptop), or the person's own hub."""
    name = hostname(request.headers.get("host", ""))
    hub_name = _hub_name(store)
    return (name in LOOPBACK_NAMES or name in TEST_NAMES or name == HUB_HOST
            or name.endswith(".trycloudflare.com") or (bool(hub_name) and name == hub_name))


def from_this_app(request: Request, store) -> bool:
    """Anything that changes something must come from TeamLoop's own pages, not from another site's page."""
    if request.method in SAFE_METHODS:
        return True
    if request.headers.get("sec-fetch-site") == "cross-site":
        return False
    origin = request.headers.get("origin")
    if origin is None:  # not sent by a page in a browser (scripts, the Telegram bridge, tests)
        return True
    name = hostname(origin) if origin != "null" else ""  # "null": a file:// page or a sandboxed frame
    host = hostname(request.headers.get("host", ""))
    if not name:
        return False
    if name in LOOPBACK_NAMES:  # the app on the laptop: Electron, a browser tab, the Vite dev server
        return host in LOOPBACK_NAMES or host in TEST_NAMES
    if host == HUB_HOST:  # a phone through the hub: its page lives at the hub's own address
        return name == _hub_name(store)
    return name == host  # a phone through the quick tunnel: same name both ways


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class Phones:
    def __init__(self, store):
        self.store = store
        self.codes: dict[str, float] = {}
        self.fails: dict[str, list[float]] = {}  # sender -> when it typed a wrong code
        self.url: str | None = None
        self._proc: subprocess.Popen | None = None
        self._seen: dict[str, float] = {}

    # ---- pairing ------------------------------------------------------------------------------
    def new_code(self) -> str:
        code = "".join(secrets.choice(LETTERS) for _ in range(8))
        self.codes[code] = time.time() + CODE_SECONDS
        return code

    def redeem(self, code: str, name: str, who: str = "") -> str | None:
        """A phone's token for a right code. A sender with MAX_FAILS wrong codes is shut out for a while; the
        person's own code keeps working (before, anyone could wipe it by typing 10 wrong codes at the hub)."""
        now = time.time()
        tries = [t for t in self.fails.get(who, []) if now - t < LOCKOUT_SECONDS]
        if len(tries) >= MAX_FAILS:
            self.fails[who] = tries
            return None
        code = re.sub(r"[^A-Z]", "", code.upper())
        self.codes = {c: t for c, t in self.codes.items() if t > now}
        if self.codes.pop(code, None) is None:
            self.fails[who] = [*tries, now]
            return None
        token = secrets.token_urlsafe(32)
        phone = {"id": uuid.uuid4().hex[:8], "name": name[:80] or "Phone", "hash": _hash(token),
                 "paired": time.time(), "last_seen": time.time()}
        self.store.set_setting("phones", self._all() + [phone])
        return token

    def check(self, token: str) -> dict | None:
        if not token:
            return None
        digest = _hash(token)
        phones = self._all()
        phone = next((p for p in phones if secrets.compare_digest(p["hash"], digest)), None)
        if phone and time.time() - self._seen.get(phone["id"], 0) > 60:  # one write a minute, not per request
            self._seen[phone["id"]] = phone["last_seen"] = time.time()
            self.store.set_setting("phones", phones)
        return phone

    def list(self) -> list[dict]:
        return [{k: v for k, v in p.items() if k != "hash"} for p in self._all()]

    def remove(self, phone_id: str) -> bool:
        phones = self._all()
        kept = [p for p in phones if p["id"] != phone_id]
        self.store.set_setting("phones", kept)
        return len(kept) < len(phones)

    def _all(self) -> list[dict]:
        return list(self.store.get_setting("phones", []) or [])

    # ---- tunnel -------------------------------------------------------------------------------
    async def tunnel(self) -> str:
        if self.url and self._proc and self._proc.poll() is None:
            return self.url
        exe = shutil.which("cloudflared")
        if not exe:
            raise RuntimeError("cloudflared is not installed. Run: winget install Cloudflare.cloudflared")
        found = threading.Event()
        self._proc = subprocess.Popen([exe, "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{config.port()}"],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
                                      creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

        def read(proc: subprocess.Popen) -> None:  # keeps draining the log so cloudflared never blocks
            for line in proc.stderr:
                match = TUNNEL_URL.search(line)
                if match and not found.is_set():
                    self.url = match.group(0)
                    found.set()

        threading.Thread(target=read, args=(self._proc,), daemon=True).start()
        if not await asyncio.to_thread(found.wait, 30):
            self.stop()
            raise RuntimeError("The tunnel did not start within 30 seconds. Check the internet connection.")
        return self.url

    def stop(self) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
        self._proc, self.url = None, None


class EventLog:
    """Recent crew events with numbers, for phones: Cloudflare quick tunnels don't carry SSE, so phones long-poll."""

    def __init__(self, bus, size: int = 300):
        self.bus, self.seq = bus, 0
        self.events: deque[tuple[int, dict]] = deque(maxlen=size)
        self._new = asyncio.Event()
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._record())

    async def _record(self) -> None:
        with self.bus.subscribe() as queue:
            while True:
                event = await queue.get()
                self.seq += 1
                self.events.append((self.seq, event))
                self._new.set()
                self._new = asyncio.Event()

    def oldest(self) -> int:
        return self.events[0][0] if self.events else self.seq + 1

    async def after(self, seq: int, wait: float) -> list[dict]:
        if not any(n > seq for n, _ in self.events):
            try:
                await asyncio.wait_for(self._new.wait(), wait)
            except asyncio.TimeoutError:
                return []
        return [e for n, e in self.events if n > seq]


PAIR_PAGE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Pair phone · TeamLoop</title>
<style>body{{font-family:system-ui,sans-serif;max-width:22rem;margin:3rem auto;padding:0 1rem;text-align:center}}
input,button{{font-size:1.3rem;padding:.6rem;width:100%;box-sizing:border-box;margin-top:.8rem;border-radius:.5rem}}
input{{letter-spacing:.2em;text-transform:uppercase;text-align:center;border:1px solid #999}}
button{{background:#3b6cf6;color:#fff;border:0}}.err{{color:#c0392b}}</style></head><body>
<h2>Pair this phone</h2><p>Enter the 8-letter code shown on the laptop under Settings → Phone.</p>
{error}<form method="post" action="/pair"><input name="code" value="{code}" maxlength="9" autocomplete="off" required>
<button>Pair</button></form></body></html>"""


def _page(code: str = "", error: str = "") -> str:
    note = f'<p class="err">{html.escape(error)}</p>' if error else ""
    return PAIR_PAGE.format(code=html.escape(code), error=note)


def install(app: FastAPI, phones: Phones) -> None:
    log = EventLog(app.state.crew.bus)

    @app.middleware("http")
    async def guard(request: Request, call_next):
        log.start()  # needs the running loop, so it starts with the first request
        path = request.url.path
        store = app.state.crew.store
        if not trusted_host(request, store):  # DNS rebinding: another site's name pointed at this laptop
            return JSONResponse({"detail": "This address isn't TeamLoop's."}, 400)
        if not from_this_app(request, store):  # another site's page posting here
            return JSONResponse({"detail": "Only TeamLoop's own pages can do that."}, 403)
        if path == "/api/events" and is_remote(request):  # an endless stream: a hub request would never end
            return JSONResponse({"detail": "Phones get live updates from /api/events/poll."}, 404)
        if path in API_PAGES and is_remote(request):  # the API's shape stays on the laptop
            return JSONResponse({"detail": "Not Found"}, 404)
        if path.startswith("/api") and is_remote(request):
            if path.startswith("/api/phones"):
                return JSONResponse({"detail": "Phones are managed on the laptop."}, 403)
            if phones.check(request.cookies.get(COOKIE, "")) is None:
                return JSONResponse({"detail": "Pair this phone first."}, 401)
        return await call_next(request)

    @app.get("/api/events/poll")
    async def poll(after: int = -1, wait: float = 20) -> dict:
        """Long-poll version of /api/events. after=-1 starts now and returns the cards still waiting for an answer."""
        if after > log.seq:  # the server restarted since the last poll: start over from now
            after = -1
        if after < 0:
            crew = app.state.crew
            waiting = {aid for chat in crew.store.chats() for aid in crew.gate.pending_in(chat["id"])}
            cards = [e for _, e in log.events if e["type"] == "approval" and e.get("id") in waiting]
            return {"seq": log.seq, "oldest": log.oldest(), "events": cards}
        events = await log.after(after, min(wait, 25))
        # `oldest` > after+1 means events were dropped from the buffer: the app reloads its chats and /api/state
        return {"seq": log.seq, "oldest": log.oldest(), "events": events}

    @app.post("/api/phones/pair")
    async def pair() -> dict:
        from teamloop.server import hub

        url = hub.link(app.state.crew.store)  # the fixed address, once the hub is set up and connected
        if not url:
            try:
                url = await phones.tunnel()
            except RuntimeError as e:
                raise HTTPException(503, str(e)) from None
        code = phones.new_code()
        link = f"{url}/pair?code={code}"
        return {"code": f"{code[:4]}-{code[4:]}", "link": link, "expires": time.time() + CODE_SECONDS,
                # a viewBox (no fixed size) so CSS can scale it without cropping; 4 modules of quiet zone so
                # phone cameras find it
                "qr": segno.make(link, error="m").svg_inline(border=4, light="white", omitsize=True)}

    @app.get("/api/phones")
    def list_phones() -> list[dict]:
        return phones.list()

    @app.delete("/api/phones/{phone_id}")
    def remove_phone(phone_id: str) -> dict:
        if not phones.remove(phone_id):
            raise HTTPException(404, "No such phone.")
        return {"ok": True}

    @app.get("/pair", response_class=HTMLResponse)
    def pair_page(code: str = "") -> str:
        return _page(code)

    @app.post("/pair")
    async def pair_phone(request: Request):
        form = parse_qs((await request.body()).decode("utf-8", "replace"))
        token = phones.redeem(form.get("code", [""])[0], _device(request.headers.get("user-agent", "")), _sender(request))
        if token is None:
            return HTMLResponse(_page(error="That code is wrong or expired. Make a new one on the laptop."), 400)
        res = RedirectResponse("/", status_code=303)
        res.set_cookie(COOKIE, token, max_age=365 * 86400, httponly=True, secure=True, samesite="strict")
        return res


def _sender(request: Request) -> str:
    """Who is typing codes: Cloudflare's own record of the visitor (it can't be faked through the tunnel or the
    hub), else the forwarded or direct address."""
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    return request.headers.get("cf-connecting-ip") or forwarded or (request.client.host if request.client else "")


def _device(agent: str) -> str:
    for name in ("iPhone", "iPad", "Android", "Windows", "Mac"):
        if name in agent:
            return f"{name} phone" if name in ("iPhone", "Android") else name
    return "Phone"
