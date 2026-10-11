"""The laptop's side of the phone hub: a fixed, free phone address that survives restarts.

The hub (phone-hub/, a Cloudflare Worker + Durable Object on the person's own free account) is the phone app's
one permanent address. This laptop dials OUT to it over a websocket and answers each phone request with the
running app, so the pairing cookie, approvals and every other check happen here exactly as before. Nothing at
home is opened, and no quick tunnel is needed once the hub is set up.

    python -m teamloop.server.hub setup      # one time: free Cloudflare sign-in in the browser, then deploy
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
from typing import Any

import httpx

from teamloop import config
from teamloop.keys import vault
from teamloop.keys.redact import add_secret

log = logging.getLogger(__name__)

SETTING = "hub_url"
SECRET = "TEAMLOOP_HUB_SECRET"  # in the key vault; the _SECRET suffix keeps it out of every log and chat
WRANGLER = ["npx", "--yes", "wrangler@4"]
CONFIG = config.ROOT / "phone-hub" / "wrangler.jsonc"
WORKERS_URL = re.compile(r"https://[a-z0-9-]+\.[a-z0-9-]+\.workers\.dev")

state: dict[str, Any] = {"connected": False, "since": None, "error": "", "setup": ""}


def target(store) -> tuple[str | None, str | None]:
    return store.get_setting(SETTING), os.environ.get(SECRET)


def link(store) -> str | None:
    """The phone app's fixed address, when the hub is set up and this laptop is connected to it."""
    url, _ = target(store)
    return url if url and state["connected"] else None


async def answer(app, msg: dict) -> dict:
    """One phone request, answered by the running app as if it came through the tunnel."""
    headers = {k: v for k, v in (msg.get("headers") or {}).items() if k.lower() not in ("host", "content-length")}
    headers.setdefault("x-forwarded-for", "phone-hub")  # it's a remote request: the pairing cookie is required
    body = base64.b64decode(msg.get("body") or "")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://hub") as client:
        try:
            res = await client.request(msg.get("method", "GET"), msg.get("path", "/"), headers=headers, content=body,
                                       timeout=60)
        except Exception as e:  # never leave the phone hanging
            log.warning("hub request failed: %s", e)
            data = json.dumps({"detail": "TeamLoop on the laptop hit an error."}).encode()
            return {"id": msg.get("id"), "status": 502, "headers": [["content-type", "application/json"]],
                    "body": base64.b64encode(data).decode()}
    return {"id": msg.get("id"), "status": res.status_code, "headers": [list(h) for h in res.headers.multi_items()],
            "body": base64.b64encode(res.content).decode()}


async def run(app) -> None:
    """Stay connected to the hub while it's set up; reconnect with a growing pause when it drops."""
    from websockets.asyncio.client import connect

    pause = 2.0
    while True:
        url, secret = target(app.state.crew.store)
        if not url or not secret:
            state["connected"] = False
            await asyncio.sleep(15)
            continue
        ws_url = re.sub(r"^http", "ws", url.rstrip("/")) + "/__laptop"
        try:
            async with connect(ws_url, additional_headers={"x-link-secret": secret}, max_size=32 * 1024 * 1024,
                               ping_interval=20, open_timeout=20) as ws:
                state.update(connected=True, since=time.time(), error="")
                pause = 2.0
                async for raw in ws:
                    msg = json.loads(raw)
                    if msg.get("type") == "pong":
                        continue
                    asyncio.create_task(_reply(ws, app, msg))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            state["error"] = str(e).splitlines()[0][:200] if str(e) else type(e).__name__
            log.info("phone hub not connected: %s", state["error"])
        state["connected"] = False
        await asyncio.sleep(pause)
        pause = min(pause * 2, 60)


async def _reply(ws, app, msg: dict) -> None:
    try:
        await ws.send(json.dumps(await answer(app, msg)))
    except Exception as e:  # the socket closed meanwhile: the hub tells the phone the laptop didn't answer
        log.info("hub reply dropped: %s", e)


# ---- one-time setup ------------------------------------------------------------------------------------------
def _wrangler(*args: str, input: str | None = None, timeout: int = 300) -> subprocess.CompletedProcess:
    exe = shutil.which("npx") or "npx"
    return subprocess.run([exe, *WRANGLER[1:], *args], input=input, capture_output=True, text=True, timeout=timeout,
                          cwd=CONFIG.parent, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def setup(store, say=print) -> str:
    """Sign in (the browser opens; the person clicks Allow), deploy the hub, give it the secret, remember its URL."""
    if not shutil.which("npx"):
        raise RuntimeError("Node.js is needed for the one-time setup (npx). Install Node, then try again.")
    say("Checking the Cloudflare sign-in…")
    who = _wrangler("whoami", timeout=120)
    if "not authenticated" in (who.stdout + who.stderr).lower() or who.returncode != 0:
        say("A browser window opens: sign in to your free Cloudflare account (or make one, no card needed) and press Allow.")
        login = _wrangler("login", timeout=600)
        if login.returncode != 0:
            raise RuntimeError("The Cloudflare sign-in didn't finish: " + (login.stderr or login.stdout).strip()[-300:])
    secret = os.environ.get(SECRET) or secrets.token_urlsafe(32)
    vault.put(SECRET, secret)
    os.environ[SECRET] = secret
    add_secret(secret)
    say("Putting the hub on your account (free plan)…")
    deploy = _wrangler("deploy", "--config", str(CONFIG), timeout=600)
    out = deploy.stdout + deploy.stderr
    found = WORKERS_URL.search(out)
    if deploy.returncode != 0 or not found:
        tail = out.strip()[-400:]
        if "workers.dev" in out and "subdomain" in out.lower():
            raise RuntimeError("Your Cloudflare account needs a workers.dev subdomain first: open dash.cloudflare.com → "
                               "Workers & Pages once (it asks for one), then try again.")
        raise RuntimeError("Deploying the hub failed: " + tail)
    say("Giving the hub its secret…")
    put = _wrangler("secret", "put", "LINK_SECRET", "--config", str(CONFIG), input=secret + "\n", timeout=300)
    if put.returncode != 0:
        raise RuntimeError("Setting the hub's secret failed: " + (put.stderr or put.stdout).strip()[-300:])
    url = found.group(0)
    store.set_setting(SETTING, url)
    say(f"Done. The phone app's fixed address is {url}")
    return url


async def setup_in_background(store) -> None:
    def say(text: str) -> None:
        state["setup"] = text

    try:
        await asyncio.to_thread(setup, store, say)
    except Exception as e:
        state["setup"] = f"Failed: {e}"


if __name__ == "__main__":  # pragma: no cover - one-time CLI
    if sys.argv[1:] != ["setup"]:
        print(__doc__)
        sys.exit(1)
    from teamloop.crew.store import Store

    vault.export_to_env()
    print(setup(Store(config.db_path())))
