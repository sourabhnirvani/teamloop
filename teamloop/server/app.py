"""The HTTP API the UI, phone and Telegram use (contract: PLAN.md section 4)."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from teamloop import config, kits, trace
from teamloop.crew import routines
from teamloop.crew import bots as crew_bots
from teamloop.crew.bots import BOTS, ROSTER
from teamloop.tools import registry
from teamloop.crew.events import Bus
from teamloop.computer import terminal
from teamloop.computer.operator import OPERATOR
from teamloop.crew.store import TASK_STATES, Store
from teamloop.crew.team import Crew
from teamloop.keys import entries as key_rows
from teamloop.keys import vault, wallet
from teamloop.models import doctor
from teamloop.models import providers as P
from teamloop.models.router import Router
from teamloop.server import hub, phones, telegram

PING_SECONDS = 15
VERSION_CHECK_SECONDS = 5


def ui_version() -> str:
    """Which UI bundle the laptop serves (index-xxxx.js); an open app with another bundle offers Update."""
    page = config.ROOT / "ui" / "dist" / "index.html"
    if not page.is_file():
        return "dev"
    html = page.read_text(encoding="utf-8", errors="replace")
    bundle = re.search(r"assets/(index-[\w-]+\.js)", html)
    return bundle.group(1) if bundle else hashlib.sha1(html.encode()).hexdigest()[:10]


async def watch_version(bus: Bus, every: float = VERSION_CHECK_SECONDS) -> None:
    """A new UI build lands: tell every open app (the phone too) right away, so it can ask to update."""
    last = ui_version()
    while True:
        await asyncio.sleep(every)
        now = ui_version()
        if now != last:
            last = now
            await bus.emit("version", chat_id=None, version=now)


class NewChat(BaseModel):
    title: str
    members: list[str]


class NewMessage(BaseModel):
    text: str


class Answer(BaseModel):
    ok: bool
    always: bool = False


class KeyText(BaseModel):
    text: str


LOOK_KEYS = ("body", "accessory", "eyes", "colour")


class NewBot(BaseModel):
    name: str
    role: str = ""
    persona: str = ""
    look: dict = {}
    personality: str = "cheerful"


class BotPatch(BaseModel):
    name: str | None = None
    role: str | None = None
    persona: str | None = None  # "" puts a built-in bot's own job & rules back
    muted: bool | None = None
    look: dict | None = None
    personality: str | None = None  # "" puts a built-in bot's own personality back


class NewRoutine(BaseModel):
    chat_id: str
    text: str
    schedule: str


def _look(look: dict | None) -> dict:
    return {k: str(v)[:24] for k, v in (look or {}).items() if k in LOOK_KEYS}


class NewTask(BaseModel):
    title: str
    bot: str | None = None


class TaskPatch(BaseModel):
    title: str | None = None
    status: str | None = None
    note: str | None = None


SIGN_IN_URL = "https://accounts.google.com"


class SignIn(BaseModel):
    url: str = SIGN_IN_URL


def build_crew(db_path: Path | str | None = None, router: Any = None) -> Crew:
    store = Store(db_path or config.db_path())
    bus = Bus()
    crew = Crew(store, router or Router(on_usage=usage_hook(store, bus)), bus)
    crew.ensure_default_chats()
    return crew


def usage_hook(store: Store, bus: Bus):
    """Count each model call, and tell the UI live (a "usage" event) so its counter needn't refetch."""
    def hook(provider: str, model: str, tokens_in: int, tokens_out: int, purpose: str = "") -> None:
        store.add_usage(provider, model, tokens_in, tokens_out, purpose)
        try:
            asyncio.get_running_loop().create_task(
                bus.emit("usage", chat_id=None, provider=provider, model=model,
                         tokens_in=tokens_in, tokens_out=tokens_out))
        except RuntimeError:  # no running loop (scripts): counting is enough
            pass
    return hook


def _mask(key: str) -> str:
    return f"{key[:4]}…{key[-4:]}" if len(key) > 12 else "…"


def create_app(crew: Crew | None = None) -> FastAPI:
    kits.load_all()
    try:
        vault.export_to_env()
    except (OSError, ValueError) as e:
        logging.getLogger(__name__).warning("key vault not loaded: %s", e)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        trace.init()
        ticker = asyncio.create_task(routines.scheduler(app.state.crew))
        phone = asyncio.create_task(telegram.run(app.state.crew))
        checker = asyncio.create_task(doctor.keep_checking(app.state.crew.router))
        link = asyncio.create_task(hub.run(app))  # the phone hub, once it's set up
        versions = asyncio.create_task(watch_version(app.state.crew.bus))
        yield
        link.cancel()
        versions.cancel()
        ticker.cancel()
        phone.cancel()
        app.state.phones.stop()
        checker.cancel()
        trace.flush()

    app = FastAPI(title="TeamLoop", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
                       allow_methods=["*"], allow_headers=["*"])
    app.state.crew = crew or build_crew()
    app.state.phones = phones.Phones(app.state.crew.store)
    phones.install(app, app.state.phones)

    def get_crew() -> Crew:
        return app.state.crew

    @app.get("/api/bots")
    def bots() -> list[dict]:
        c = get_crew()
        over = c.store.get_setting(crew_bots.OVERRIDES, {}) or {}
        custom = {b["id"]: b for b in c.store.get_setting(crew_bots.CUSTOM, []) or []}
        builtin = {b.id: b for b in ROSTER}
        out = []
        for b in crew_bots.crew():
            look = (over.get(b.id) or {}).get("look") or (custom.get(b.id) or {}).get("look") or None
            out.append({"id": b.id, "name": b.name, "role": b.role, "emoji": b.emoji,
                        "model": c.model_for(b.id) or "auto", "only": c.only_for(b.id),
                        "custom": b.custom, "muted": b.muted, "persona": b.persona, "look": look,
                        "default_persona": builtin[b.id].persona if b.id in builtin else None,
                        "personality": b.personality,
                        "default_personality": builtin[b.id].personality if b.id in builtin else None,
                        "tools": [t.name for t in registry.tools_for_kits(list(b.kits))]})
        return out

    @app.get("/api/personalities")
    def personalities() -> list[dict]:
        """The personalities a bot can have: how it talks, and how it moves in the app."""
        return [{"id": k, "label": p.label, "emoji": p.emoji, "blurb": p.blurb}
                for k, p in crew_bots.PERSONALITIES.items()]

    def check_personality(key: str) -> str:
        if key not in crew_bots.PERSONALITIES:
            raise HTTPException(400, "Pick one of the listed personalities.")
        return key

    async def bots_changed() -> None:
        crew = get_crew()
        crew_bots.load(crew.store)
        await crew.bus.emit("settings", chat_id=None, **settings())  # open apps reload the crew

    @app.post("/api/bots")
    async def new_bot(body: NewBot) -> dict:
        crew = get_crew()
        name = body.name.strip()[:24]
        if not name:
            raise HTTPException(400, "Give the bot a name.")
        if crew_bots.find_bot(name):
            raise HTTPException(409, f"There's already a bot called {name}.")
        bot_id, n = crew_bots.slug(name), 2
        while bot_id in BOTS or crew.store.get_chat(f"dm-{bot_id}"):
            bot_id, n = f"{crew_bots.slug(name)}-{n}", n + 1
        row = {"id": bot_id, "name": name, "role": body.role.strip()[:40] or "Helper",
               "persona": body.persona.strip()[:2000] or crew_bots.DEFAULT_PERSONA, "look": _look(body.look),
               "kits": list(crew_bots.CUSTOM_KITS), "personality": check_personality(body.personality)}
        crew.store.set_setting(crew_bots.CUSTOM, [*(crew.store.get_setting(crew_bots.CUSTOM, []) or []), row])
        crew.store.create_chat(name, [bot_id], chat_id=f"dm-{bot_id}")
        team = crew.store.get_chat("team")
        if team and bot_id not in team["members"]:
            crew.store.update_members("team", [*team["members"], bot_id])
        await bots_changed()
        return next(b for b in bots() if b["id"] == bot_id)

    @app.patch("/api/bots/{bot_id}")
    async def edit_bot(bot_id: str, body: BotPatch) -> dict:
        crew = get_crew()
        if bot_id not in BOTS:
            raise HTTPException(404, "No such bot.")
        over = dict(crew.store.get_setting(crew_bots.OVERRIDES, {}) or {})
        mine = dict(over.get(bot_id) or {})
        if body.persona is not None:
            if body.persona.strip():
                mine["persona"] = body.persona.strip()[:2000]
            else:
                mine.pop("persona", None)
        if body.muted is not None:
            mine["muted"] = body.muted
        if body.look is not None:
            mine["look"] = _look(body.look)
        if body.personality is not None:
            if body.personality:
                mine["personality"] = check_personality(body.personality)
            else:
                mine.pop("personality", None)
        over[bot_id] = mine
        crew.store.set_setting(crew_bots.OVERRIDES, over)
        if BOTS[bot_id].custom and (body.name or body.role):
            rows = crew.store.get_setting(crew_bots.CUSTOM, []) or []
            for row in rows:
                if row["id"] == bot_id:
                    row["name"] = (body.name or row["name"]).strip()[:24]
                    row["role"] = (body.role or row["role"]).strip()[:40]
            crew.store.set_setting(crew_bots.CUSTOM, rows)
        await bots_changed()
        return next(b for b in bots() if b["id"] == bot_id)

    @app.delete("/api/bots/{bot_id}")
    async def delete_bot(bot_id: str) -> dict:
        crew = get_crew()
        if bot_id not in BOTS:
            raise HTTPException(404, "No such bot.")
        if not BOTS[bot_id].custom:
            raise HTTPException(400, "The built-in crew can't be removed (you can mute a bot instead).")
        crew.store.set_setting(crew_bots.CUSTOM, [r for r in crew.store.get_setting(crew_bots.CUSTOM, []) or []
                                                  if r["id"] != bot_id])
        for chat in crew.store.chats():
            if chat["members"] == [bot_id]:
                crew.store.delete_chat(chat["id"])
            elif bot_id in chat["members"]:
                crew.store.update_members(chat["id"], [m for m in chat["members"] if m != bot_id])
        await bots_changed()
        return {"ok": True}

    @app.get("/api/chats")
    def chats() -> list[dict]:
        return get_crew().store.chats()

    @app.post("/api/chats")
    def new_chat(body: NewChat) -> dict:
        members = [m for m in body.members if m in BOTS]
        if not members:
            raise HTTPException(400, "Pick at least one bot.")
        return get_crew().store.create_chat(body.title.strip() or "New chat", members)

    @app.get("/api/chats/{chat_id}/messages")
    def messages(chat_id: str) -> list[dict]:
        c = get_crew()
        if c.store.get_chat(chat_id) is None:
            raise HTTPException(404, "No such chat.")
        return c.store.messages(chat_id)

    @app.post("/api/chats/{chat_id}/messages", status_code=202)
    async def post_message(chat_id: str, body: NewMessage) -> dict:
        if not body.text.strip():
            raise HTTPException(400, "Empty message.")
        try:
            return await get_crew().post(chat_id, body.text)
        except KeyError:
            raise HTTPException(404, "No such chat.") from None

    @app.post("/api/chats/{chat_id}/stop")
    async def stop(chat_id: str) -> dict:
        return {"stopped": await get_crew().stop(chat_id)}

    @app.post("/api/approvals/{approval_id}")
    def answer(approval_id: str, body: Answer) -> dict:
        result = get_crew().gate.answer(approval_id, body.ok, body.always)
        if not result:
            raise HTTPException(404, "That approval is no longer waiting.")
        return {"ok": True, "rule": result if isinstance(result, dict) else None}

    @app.get("/api/allowed")
    def allowed() -> list[dict]:
        return get_crew().gate.rules()

    @app.delete("/api/allowed/{rule_id}")
    def forget_allowed(rule_id: str) -> dict:
        if not get_crew().gate.forget_rule(rule_id):
            raise HTTPException(404, "No such rule.")
        return {"ok": True}

    @app.get("/api/events")
    async def events() -> StreamingResponse:
        bus = get_crew().bus

        async def stream():
            with bus.subscribe() as queue:
                yield ": connected\n\n"
                while True:
                    try:
                        event = await asyncio.wait_for(queue.get(), PING_SECONDS)
                    except asyncio.TimeoutError:
                        yield ": ping\n\n"
                        continue
                    yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"

        return StreamingResponse(stream(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.post("/api/stop-all")
    async def stop_all() -> dict:
        """Ctrl+Alt+Q from anywhere: stop every chat (and so every screen action and approval card)."""
        crew = get_crew()
        stopped = [chat["id"] for chat in crew.store.chats() if await crew.stop(chat["id"])]
        return {"stopped": stopped, "chats": len(crew.store.chats())}

    @app.get("/api/operator")
    def operator_state() -> dict:
        return OPERATOR.state()

    @app.get("/api/security")
    def security() -> dict:
        """Names only: how many keys the vault locks, and the tool calls refused for carrying one."""
        try:
            names = sorted(vault.load())
        except (OSError, ValueError):
            names = []
        return {"locked": len(names), "names": names,
                "blocked": get_crew().store.get_setting(registry.BLOCKED, []) or []}

    @app.get("/api/keys/entries")
    def key_entries() -> list[dict]:
        return key_rows.entries(get_crew().store)

    @app.post("/api/keys/test")
    async def test_keys() -> list[dict]:
        return await key_rows.test_all(get_crew().store)

    @app.post("/api/keys/cleanup")
    def clean_up_keys() -> dict:
        return key_rows.cleanup(get_crew().store)

    @app.delete("/api/keys/{env}")
    def remove_key(env: str) -> dict:
        try:
            if not key_rows.remove(get_crew().store, env):
                raise HTTPException(404, f"No saved key is called {env}.")
        except key_rows.FromEnv as e:
            raise HTTPException(409, str(e))
        return {"removed": env}

    @app.get("/api/keys")
    def keys() -> list[dict]:
        return [{"id": p.id, "name": p.name, "needs_key": p.needs_key,
                 "keys": [_mask(k) for k in P.keys_for(p) if k]} for p in P.PROVIDERS.values()]

    @app.post("/api/keys")
    async def add_keys(body: KeyText) -> list[dict]:
        # Service keys (neatlogs, Telegram) first, the same way pasting them in a chat does.
        services = wallet.service_keys(body.text)
        out = [{"provider": label.lower(), "status": "saved", "text": sentence}
               for (_, label, _), sentence in zip(services, wallet.add_services(body.text))]
        for item in out:
            if item["provider"] == "neatlogs":
                item["text"] += " Tracing is on." if trace.init() else " Tracing will start after a restart."
        found = await wallet.add_from_text(body.text)
        if not (found or out):
            raise HTTPException(400, "No API key found in that text.")
        get_crew().router.dead_models.clear()
        return out + [{"provider": a.provider, "status": a.status, "text": a.sentence()} for a in found]

    @app.post("/api/models/check")
    async def check_models() -> dict:
        router = get_crew().router
        results = await doctor.check_all(router)
        router.last_doctor = results
        return {"results": results, "summary": doctor.summary(results)}

    @app.get("/api/models")
    def models() -> list[dict]:
        router = get_crew().router
        dead = getattr(router, "dead_models", set())
        checked = {(r["provider"], r["model"]): r["ok"] for r in getattr(router, "last_doctor", [])}
        out = []
        for p in P.chain():
            local = p.id == "ollama"
            base = P.base_url_for(p)
            running = P.ollama_running(base) if local else None
            names = P.models_for(p) if not local or running else []  # Ollama off: no made-up model names
            rows = []
            for m in names:
                row = {"id": m, "dead": (p.id, m) in dead, "ok": checked.get((p.id, m))}
                if local:  # what Ollama says the model can do: tools natively, or written into its prompt
                    info = P.ollama_model_info(base, m)
                    row.update(tools=info.get("tools"), thinking=bool(info.get("thinking")), ctx=info.get("ctx"))
                rows.append(row)
            out.append({"provider": p.id, "name": p.name, "has_key": bool(P.keys_for(p)), "local": local,
                        "running": running, "models": rows})
        return out

    @app.get("/api/settings")
    def settings() -> dict:
        s = get_crew().store
        return {"save_tokens": bool(s.get_setting("save_tokens", False)),
                "crew_model": s.get_setting("crew_model"),
                "bot_models": s.get_setting("bot_models", {}) or {},
                "bot_only": s.get_setting("bot_only", {}) or {}}

    @app.post("/api/settings")
    async def set_settings(body: dict) -> dict:
        s = get_crew().store
        for key in ("save_tokens", "crew_model", "bot_models", "bot_only"):
            if key in body:
                s.set_setting(key, body[key])
        now = settings()
        await get_crew().bus.emit("settings", chat_id=None, **now)  # other open apps (the phone) update at once
        return now

    @app.get("/api/state")
    def state() -> dict:
        """What an app that (re)connects needs: who is working where, cards still waiting, asleep, save tokens."""
        return get_crew().state()

    @app.get("/api/approvals")
    def approvals() -> list[dict]:
        return get_crew().gate.waiting_cards()

    @app.get("/api/usage")
    def usage() -> list[dict]:
        return get_crew().store.usage()

    @app.get("/api/routines")
    def list_routines() -> list[dict]:
        return routines.listing(get_crew())

    @app.post("/api/routines")
    def add_routine(body: NewRoutine) -> dict:
        crew = get_crew()
        if crew.store.get_chat(body.chat_id) is None:
            raise HTTPException(404, "No such chat.")
        if not body.text.strip():
            raise HTTPException(400, "Say what the routine should do.")
        try:
            return routines.add(crew, body.chat_id, body.text.strip(), body.schedule.strip())
        except ValueError as e:
            raise HTTPException(400, str(e)) from None

    @app.delete("/api/routines/{routine_id}")
    def cancel_routine(routine_id: str) -> dict:
        if not routines.cancel(get_crew(), routine_id):
            raise HTTPException(404, "No such routine.")
        return {"ok": True}

    @app.post("/api/browser/signin")
    async def browser_signin(body: SignIn) -> dict:
        """Open a tab in the crew's Chrome on a sign-in page; the person signs in there once, the bots use it."""
        from teamloop.browser import kit as browser_kit

        url = body.url.strip() or SIGN_IN_URL
        if not url.startswith("https://"):
            raise HTTPException(400, "Only https:// sign-in pages.")
        browser = browser_kit.host()
        if browser.headless:
            raise HTTPException(409, "The crew's Chrome runs hidden (TEAMLOOP_BROWSER_HEADLESS=1), so there's nothing to sign in to.")
        try:
            await browser.start()
            page = await browser.context.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.bring_to_front()
        except Exception as e:
            raise HTTPException(503, f"Couldn't open the crew's Chrome: {str(e).splitlines()[0][:160]}") from None
        return {"ok": True, "url": page.url,
                "text": "The crew's Chrome is open on the sign-in page. Sign in there yourself; the bots use it after."}

    @app.get("/api/tasks")
    def list_tasks() -> list[dict]:
        return get_crew().store.tasks()

    @app.post("/api/tasks")
    async def add_task(body: NewTask) -> dict:
        title = body.title.strip()
        if not title:
            raise HTTPException(400, "Give the task a title.")
        return await get_crew().board_add(title[:200], bot=body.bot if body.bot in BOTS else None, by="user")

    @app.patch("/api/tasks/{task_id}")
    async def patch_task(task_id: int, body: TaskPatch) -> dict:
        if body.status is not None and body.status not in TASK_STATES:
            raise HTTPException(400, f"Status is one of: {', '.join(TASK_STATES)}.")
        task = await get_crew().board_update(task_id, title=body.title, status=body.status, note=body.note)
        if task is None:
            raise HTTPException(404, "No such task.")
        return task

    @app.delete("/api/tasks/{task_id}")
    async def delete_task(task_id: int) -> dict:
        crew = get_crew()
        if not crew.store.delete_task(task_id):
            raise HTTPException(404, "No such task.")
        await crew.bus.emit("task", chat_id=None, task={"id": task_id, "deleted": True})
        return {"ok": True}

    @app.get("/api/jobs")
    def list_jobs() -> list[dict]:
        return terminal.jobs()

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str) -> dict:
        job = terminal.job_detail(job_id)
        if job is None:
            raise HTTPException(404, "No such job.")
        return job

    @app.post("/api/jobs/{job_id}/stop")
    async def stop_job(job_id: str) -> dict:
        if not await terminal.stop(job_id):
            raise HTTPException(404, "No such job.")
        return terminal.job_detail(job_id) or {"ok": True}

    @app.get("/api/hub")
    def hub_status() -> dict:
        url, secret = hub.target(get_crew().store)
        return {"configured": bool(url and secret), "url": url, "connected": hub.state["connected"],
                "since": hub.state["since"], "error": hub.state["error"], "setup": hub.state["setup"]}

    @app.post("/api/hub/setup")
    async def hub_setup(request: Request) -> dict:
        if phones.is_remote(request):
            raise HTTPException(403, "Set up the phone link on the laptop.")
        if hub.state["setup"] and not hub.state["setup"].startswith(("Done", "Failed")):
            raise HTTPException(409, "Setup is already running.")
        hub.state["setup"] = "Starting…"
        asyncio.create_task(hub.setup_in_background(get_crew().store))
        return hub_status()

    @app.get("/api/version")
    def version() -> dict:
        """Which UI build the laptop serves; an open app (the phone's above all) compares it with its own to offer Update."""
        return {"version": ui_version()}

    @app.get("/api/shots/{name}")
    def shot(name: str) -> FileResponse:
        if not re.fullmatch(r"[0-9a-f]{12}\.png", name):
            raise HTTPException(404, "No such screenshot.")
        path = config.workspace() / "shots" / name
        if not path.is_file():
            raise HTTPException(404, "No such screenshot.")
        return FileResponse(path, media_type="image/png")

    @app.get("/console", response_class=HTMLResponse)
    def console() -> str:
        """A plain test page for the API (the real app is ui/)."""
        return (Path(__file__).parent / "console.html").read_text(encoding="utf-8")

    ui = config.ROOT / "ui" / "dist"
    if ui.is_dir():
        app.mount("/", StaticFiles(directory=ui, html=True), name="ui")

    return app
