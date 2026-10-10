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
from urllib.parse import parse_qs

import segno
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from teamloop import config

COOKIE = "teamloop_phone"
CODE_SECONDS = 600
MAX_FAILS = 10
LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ"  # no I or O, so a typed code can't be misread
PROXY_HEADERS = ("cf-connecting-ip", "x-forwarded-for", "forwarded")
API_PAGES = {"/docs", "/docs/oauth2-redirect", "/redoc", "/openapi.json"}
LOCAL_HOSTS = {"127.0.0.1", "::1", "testclient"}  # the server only listens on loopback
TUNNEL_URL = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
mimetypes.add_type("application/manifest+json", ".webmanifest")


def is_remote(request: Request) -> bool:
    host = request.client.host if request.client else ""
    return host not in LOCAL_HOSTS or any(h in request.headers for h in PROXY_HEADERS)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class Phones:
    def __init__(self, store):
        self.store = store
        self.codes: dict[str, float] = {}
        self.fails = 0
        self.url: str | None = None
        self._proc: subprocess.Popen | None = None
        self._seen: dict[str, float] = {}

    # ---- pairing ------------------------------------------------------------------------------
    def new_code(self) -> str:
        code = "".join(secrets.choice(LETTERS) for _ in range(8))
        self.codes[code] = time.time() + CODE_SECONDS
        return code

    def redeem(self, code: str, name: str) -> str | None:
        code = re.sub(r"[^A-Z]", "", code.upper())
        self.codes = {c: t for c, t in self.codes.items() if t > time.time()}
        if self.codes.pop(code, None) is None:
            self.fails += 1
            if self.fails >= MAX_FAILS:  # someone is guessing: every open code dies
                self.codes.clear()
                self.fails = 0
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
            return {"seq": log.seq, "events": cards}
        events = await log.after(after, min(wait, 25))
        return {"seq": log.seq, "events": events}

    @app.post("/api/phones/pair")
    async def pair() -> dict:
        try:
            url = await phones.tunnel()
        except RuntimeError as e:
            raise HTTPException(503, str(e)) from None
        code = phones.new_code()
        link = f"{url}/pair?code={code}"
        return {"code": f"{code[:4]}-{code[4:]}", "link": link, "expires": time.time() + CODE_SECONDS,
                "qr": segno.make(link, error="m").svg_inline(scale=5, border=2, light="white")}

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
        token = phones.redeem(form.get("code", [""])[0], _device(request.headers.get("user-agent", "")))
        if token is None:
            return HTMLResponse(_page(error="That code is wrong or expired. Make a new one on the laptop."), 400)
        res = RedirectResponse("/", status_code=303)
        res.set_cookie(COOKIE, token, max_age=365 * 86400, httponly=True, secure=True, samesite="strict")
        return res


def _device(agent: str) -> str:
    for name in ("iPhone", "iPad", "Android", "Windows", "Mac"):
        if name in agent:
            return f"{name} phone" if name in ("iPhone", "Android") else name
    return "Phone"
