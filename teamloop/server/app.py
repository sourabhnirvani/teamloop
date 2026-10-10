"""The HTTP API the UI, phone and Telegram use (contract: PLAN.md section 4)."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from teamloop import config, kits, trace
from teamloop.crew import routines
from teamloop.crew.bots import BOTS, ROSTER
from teamloop.crew.events import Bus
from teamloop.crew.store import Store
from teamloop.crew.team import Crew
from teamloop.keys import vault, wallet
from teamloop.models import doctor
from teamloop.models import providers as P
from teamloop.models.router import Router
from teamloop.server import phones, telegram

PING_SECONDS = 15


class NewChat(BaseModel):
    title: str
    members: list[str]


class NewMessage(BaseModel):
    text: str


class Answer(BaseModel):
    ok: bool


class KeyText(BaseModel):
    text: str


def build_crew(db_path: Path | str | None = None, router: Any = None) -> Crew:
    store = Store(db_path or config.db_path())
    crew = Crew(store, router or Router(on_usage=store.add_usage), Bus())
    crew.ensure_default_chats()
    return crew


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
        yield
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
        return [{"id": b.id, "name": b.name, "role": b.role, "emoji": b.emoji,
                 "model": c.model_for(b.id) or "auto"} for b in ROSTER]

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
        if not get_crew().gate.answer(approval_id, body.ok):
            raise HTTPException(404, "That approval is no longer waiting.")
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
        return [{"provider": p.id, "name": p.name, "has_key": bool(P.keys_for(p)),
                 "models": [{"id": m, "dead": (p.id, m) in dead, "ok": checked.get((p.id, m))}
                            for m in P.models_for(p)]}
                for p in P.chain()]

    @app.get("/api/settings")
    def settings() -> dict:
        s = get_crew().store
        return {"save_tokens": bool(s.get_setting("save_tokens", False)),
                "crew_model": s.get_setting("crew_model"),
                "bot_models": s.get_setting("bot_models", {}) or {}}

    @app.post("/api/settings")
    def set_settings(body: dict) -> dict:
        s = get_crew().store
        for key in ("save_tokens", "crew_model", "bot_models"):
            if key in body:
                s.set_setting(key, body[key])
        return settings()

    @app.get("/api/usage")
    def usage() -> list[dict]:
        return get_crew().store.usage()

    @app.get("/api/routines")
    def list_routines() -> list[dict]:
        return routines.listing(get_crew())

    @app.delete("/api/routines/{routine_id}")
    def cancel_routine(routine_id: str) -> dict:
        if not routines.cancel(get_crew(), routine_id):
            raise HTTPException(404, "No such routine.")
        return {"ok": True}

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
