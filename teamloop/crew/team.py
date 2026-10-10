"""The crew at work: who answers a message, handoffs between bots, Stop, and the default chats."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from teamloop import trace
from teamloop.computer.gate import Gate
from teamloop.crew.bots import BOTS, LEAD, ROSTER, Bot, find_bot
from teamloop.crew.context import Stopped, TurnCtx
from teamloop.crew.events import Bus
from teamloop.crew.runner import run_bot_turn
from teamloop.crew.store import Store
from teamloop.models.router import AllModelsBusy
from teamloop.tools.registry import ToolResult, tool

log = logging.getLogger(__name__)

HISTORY_LIMIT = 20
MAX_HANDOFF_DEPTH = 2
STOP_WORDS = {"stop", "stop it", "cancel", "stop now"}
_MENTION = re.compile(r"@(\w+)|\bask (\w+) to\b", re.IGNORECASE)


class Crew:
    def __init__(self, store: Store, router: Any, bus: Bus, gate: Gate | None = None):
        self.store, self.router, self.bus = store, router, bus
        self.gate = gate or Gate(store, bus)
        self._tasks: dict[str, asyncio.Task] = {}
        self._stops: dict[str, asyncio.Event] = {}

    # ---- setup ----------------------------------------------------------------------------
    def ensure_default_chats(self) -> None:
        if self.store.chats():
            return
        for bot in ROSTER:
            self.store.create_chat(bot.name, [bot.id], chat_id=f"dm-{bot.id}")
        self.store.create_chat("Team", [b.id for b in ROSTER], chat_id="team")

    def model_for(self, bot_id: str) -> str | None:
        per_bot = self.store.get_setting("bot_models", {}) or {}
        return per_bot.get(bot_id) or self.store.get_setting("crew_model")

    # ---- messages -------------------------------------------------------------------------
    async def post(self, chat_id: str, text: str) -> dict:
        chat = self.store.get_chat(chat_id)
        if chat is None:
            raise KeyError(chat_id)
        msg = self.store.add_message(chat_id, "user", text)
        await self.bus.emit("message", chat_id=chat_id, message=msg)
        if text.strip().lower().rstrip("!.") in STOP_WORDS:
            await self.stop(chat_id)
            return msg
        previous = self._tasks.get(chat_id)
        self._tasks[chat_id] = asyncio.create_task(self._handle(chat, text, previous))
        return msg

    async def wait_idle(self, chat_id: str) -> None:
        task = self._tasks.get(chat_id)
        if task:
            await asyncio.gather(task, return_exceptions=True)

    def responders(self, chat: dict, text: str) -> list[Bot]:
        members = [m for m in chat["members"] if m in BOTS]
        mentioned: list[Bot] = []
        for at_name, ask_name in _MENTION.findall(text):
            bot = find_bot(at_name or ask_name)
            if bot and bot.id in members and bot not in mentioned:
                mentioned.append(bot)
        if mentioned:
            return mentioned
        if len(members) == 1:
            return [BOTS[members[0]]]
        return [BOTS[LEAD] if LEAD in members else BOTS[members[0]]]

    def history(self, chat_id: str, bot_id: str) -> list[dict]:
        """Recent chat as the model sees it: its own lines as assistant, everyone else's as user."""
        rows = self.store.messages(chat_id, HISTORY_LIMIT + 1)[:-1]  # the newest is the message being answered
        out = []
        for m in rows:
            if m["sender"] == bot_id:
                out.append({"role": "assistant", "content": m["text"]})
            elif m["sender"] == "user":
                out.append({"role": "user", "content": m["text"]})
            else:
                name = BOTS[m["sender"]].name if m["sender"] in BOTS else m["sender"]
                out.append({"role": "user", "content": f"[{name}] {m['text']}"})
        return out

    async def _handle(self, chat: dict, text: str, previous: asyncio.Task | None) -> None:
        if previous and not previous.done():
            await asyncio.gather(previous, return_exceptions=True)  # replies stay in order
        stop = self._stops.setdefault(chat["id"], asyncio.Event())
        stop.clear()
        try:
            with trace.span("chat message", "workflow", session_id=chat["id"], chat=chat["id"]):
                for bot in self.responders(chat, text):
                    ctx = TurnCtx(chat["id"], bot.id, self, stop)
                    await self._turn(bot, chat, text, ctx)
        except (Stopped, asyncio.CancelledError):
            await self.say(chat["id"], LEAD if LEAD in chat["members"] else chat["members"][0], "Stopped.")

    async def _turn(self, bot: Bot, chat: dict, text: str, ctx: TurnCtx) -> str:
        await self.bus.emit("typing", chat_id=chat["id"], bot=bot.id, on=True)
        try:
            reply = await run_bot_turn(bot, self.router, self.history(chat["id"], bot.id), text, ctx,
                                       prefer=self.model_for(bot.id), members=chat["members"])
        except AllModelsBusy as e:
            reply = f"Failed: {e}"
        finally:
            await self.bus.emit("typing", chat_id=chat["id"], bot=bot.id, on=False)
        await self.say(chat["id"], bot.id, reply)
        return reply

    async def say(self, chat_id: str, sender: str, text: str, kind: str = "chat") -> dict:
        msg = self.store.add_message(chat_id, sender, text, kind)
        await self.bus.emit("message", chat_id=chat_id, message=msg)
        return msg

    # ---- handoffs -------------------------------------------------------------------------
    async def delegate(self, ctx: TurnCtx, bot_name: str, instruction: str) -> ToolResult:
        bot = find_bot(bot_name)
        if bot is None or bot.id == LEAD:
            names = ", ".join(b.id for b in ROSTER if b.id != LEAD)
            return ToolResult(False, f"There is no teammate called {bot_name!r}. Teammates: {names}.")
        if not instruction.strip():
            return ToolResult(False, "Give the teammate a clear instruction.")
        if ctx.depth >= MAX_HANDOFF_DEPTH:
            return ToolResult(False, "Too many handoffs in a row. Do this step yourself or ask the person.")
        await self.say(ctx.chat_id, ctx.bot_id, f"@{bot.name} {instruction}", kind="handoff")
        sub = ctx.for_bot(bot.id, depth=ctx.depth + 1)
        await self.bus.emit("typing", chat_id=ctx.chat_id, bot=bot.id, on=True)
        try:
            reply = await run_bot_turn(bot, self.router, [], instruction, sub, prefer=self.model_for(bot.id))
        except AllModelsBusy as e:
            reply = f"Failed: {e}"
        finally:
            await self.bus.emit("typing", chat_id=ctx.chat_id, bot=bot.id, on=False)
        await self.say(ctx.chat_id, bot.id, reply)
        ok = not reply.lower().startswith(("failed:", "not mine:"))
        return ToolResult(ok, f"{bot.name} replied: {reply}")

    # ---- stop -----------------------------------------------------------------------------
    async def stop(self, chat_id: str) -> bool:
        self._stops.setdefault(chat_id, asyncio.Event()).set()
        self.gate.deny_all(chat_id)
        task = self._tasks.get(chat_id)
        if task and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            return True
        return False


@tool("delegate",
      "Hand one step of the job to a teammate and get their result back. The teammate does not see the "
      "chat, so the instruction must be complete (names, paths, links, exact wording).",
      {"bot": {"type": "string", "description": "teammate id: desk, web, scout, inbox or writer"},
       "instruction": {"type": "string", "description": "one clear, complete instruction"},
       "required": ["bot", "instruction"]},
      kit="lead")
async def delegate(args: dict, ctx: TurnCtx) -> ToolResult:
    return await ctx.crew.delegate(ctx, str(args.get("bot", "")), str(args.get("instruction", "")))
