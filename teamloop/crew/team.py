"""The crew at work: who answers a message, group rounds, handoffs between bots, Stop, default chats."""

from __future__ import annotations

import asyncio
import dataclasses
import logging
import re
from typing import Any

from teamloop import trace
from teamloop.computer.gate import Gate
from teamloop.crew import commands, fastpath
from teamloop.crew.bots import BOTS, LEAD, ROSTER, Bot, find_bot
from teamloop.crew.context import Stopped, TurnCtx
from teamloop.crew.events import Bus
from teamloop.crew.runner import MAX_STEPS, run_bot_turn
from teamloop.crew.store import Store
from teamloop.keys import wallet
from teamloop.keys.redact import add_secret, redact
from teamloop.models.providers import detect_keys
from teamloop.models.router import AllModelsBusy
from teamloop.tools.registry import ToolResult, tool

log = logging.getLogger(__name__)

HISTORY_LIMIT, SAVE_HISTORY_LIMIT = 20, 8
SAVE_MAX_STEPS = 5
MAX_HANDOFF_DEPTH = 2
STOP_WORDS = {"stop", "stop it", "cancel", "stop now"}
_MENTION = re.compile(r"@(\w+)|\bask (\w+) to\b", re.IGNORECASE)
_TEAM_WORDS = re.compile(r"\b(everyone|everybody|team|all of you|guys|you all|y'all)\b", re.IGNORECASE)
ROUND_NOTE = ("(Group round: the person asked the whole team. Add only something new and useful from your role, "
              "in one or two sentences. If you have nothing new, reply exactly SKIP.)")
WORKER_KITS = ("computer", "terminal", "files", "web", "browser", "memory")
_YES_NO = {**{w: True for w in ("yes", "y", "ok", "okay", "approve", "approved", "go ahead", "do it", "haan", "ha")},
           **{w: False for w in ("no", "n", "deny", "denied", "don't", "dont", "nahi", "na", "cancel it")}}


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

    def saving(self) -> bool:
        return bool(self.store.get_setting("save_tokens", False))

    # ---- messages -------------------------------------------------------------------------
    async def post(self, chat_id: str, text: str) -> dict:
        chat = self.store.get_chat(chat_id)
        if chat is None:
            raise KeyError(chat_id)
        for _, key in detect_keys(text):
            add_secret(key)  # a pasted key is never stored, shown or sent to a model
        for _, _, key in wallet.service_keys(text):
            add_secret(key)
        msg = self.store.add_message(chat_id, "user", redact(text))
        await self.bus.emit("message", chat_id=chat_id, message=msg)
        if text.strip().lower().rstrip("!.") in STOP_WORDS:
            await self.stop(chat_id)
            return msg
        waiting = self.gate.pending_in(chat_id)
        answer = _YES_NO.get(text.strip().lower().rstrip("!."))
        if waiting and answer is not None:  # typed answer to the newest approval card
            self.gate.answer(waiting[-1], answer)
            return msg
        previous = self._tasks.get(chat_id)
        self._tasks[chat_id] = asyncio.create_task(self._handle(chat, text, previous))
        return msg

    async def wait_idle(self, chat_id: str) -> None:
        task = self._tasks.get(chat_id)
        if task:
            await asyncio.gather(task, return_exceptions=True)

    def mentioned(self, chat: dict, text: str) -> list[Bot]:
        members = [m for m in chat["members"] if m in BOTS]
        found: list[Bot] = []
        for at_name, ask_name in _MENTION.findall(text):
            bot = find_bot(at_name or ask_name)
            if bot and bot.id in members and bot not in found:
                found.append(bot)
        return found

    def lead_of(self, chat: dict) -> Bot:
        return BOTS[LEAD] if LEAD in chat["members"] else BOTS[chat["members"][0]]

    def responders(self, chat: dict, text: str) -> list[Bot]:
        mentioned = self.mentioned(chat, text)
        if mentioned:
            return mentioned
        return [self.lead_of(chat)]

    def history(self, chat_id: str, bot_id: str, limit: int = HISTORY_LIMIT) -> list[dict]:
        """Recent chat as the model sees it: its own lines as assistant, everyone else's as user."""
        rows = self.store.messages(chat_id, limit + 1)[:-1]  # the newest is the message being answered
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
        lead = self.lead_of(chat)
        try:
            with trace.span("chat message", "workflow", session_id=chat["id"], chat=chat["id"]) as sp:
                sp.set("input.value", text)
                quick = await commands.handle(self, chat, text)
                if quick is not None:
                    await self.say(chat["id"], lead.id, quick)
                    return
                if self.store.get_setting("asleep", False):
                    await self.say(chat["id"], lead.id, commands.ASLEEP_NOTE)
                    return
                if await fastpath.handle(self, chat, text, stop):
                    return
                order = self.responders(chat, text)
                is_round = (not self.mentioned(chat, text) and len(chat["members"]) > 1
                            and _TEAM_WORDS.search(text) and not self.saving())
                if is_round:
                    order = [lead] + [BOTS[m] for m in chat["members"] if m in BOTS and m != lead.id]
                for i, bot in enumerate(order):
                    reply = await self._turn(bot, chat, text, TurnCtx(chat["id"], bot.id, self, stop),
                                             note=ROUND_NOTE if is_round and i > 0 else None)
                    if reply is not None and len(chat["members"]) > 1:
                        await self._follow_up(chat, bot, reply, text, stop)
        except (Stopped, asyncio.CancelledError):
            await self.say(chat["id"], lead.id, "Stopped.")

    async def _turn(self, bot: Bot, chat: dict, text: str, ctx: TurnCtx, note: str | None = None) -> str | None:
        saving = self.saving()
        if bot.id == LEAD and self.store.get_setting("solo", False):
            bot = dataclasses.replace(bot, kits=WORKER_KITS)  # "one bot" mode for before/after numbers
        prompt = f"{text}\n\n{note}" if note else text
        await self.bus.emit("typing", chat_id=chat["id"], bot=bot.id, on=True)
        try:
            reply = await run_bot_turn(bot, self.router,
                                       self.history(chat["id"], bot.id, SAVE_HISTORY_LIMIT if saving else HISTORY_LIMIT),
                                       prompt, ctx, prefer=self.model_for(bot.id), members=chat["members"],
                                       max_steps=SAVE_MAX_STEPS if saving else MAX_STEPS)
        except AllModelsBusy as e:
            reply = f"Failed: {e}"
        finally:
            await self.bus.emit("typing", chat_id=chat["id"], bot=bot.id, on=False)
        if note and reply.strip().upper().startswith("SKIP"):
            return None
        await self.say(chat["id"], bot.id, reply)
        return reply

    async def _follow_up(self, chat: dict, bot: Bot, reply: str, original: str, stop: asyncio.Event) -> None:
        """One visible handoff in group chats: a bot @mentions a teammate, or says the job isn't theirs."""
        if reply.lower().startswith("not mine:") and bot.id != LEAD and LEAD in chat["members"]:
            ask = (f"The person asked: {original}\n{bot.name} said it isn't theirs: {reply}\n"
                   f"Hand the job to the right teammate.")
            await self._turn(BOTS[LEAD], chat, ask, TurnCtx(chat["id"], LEAD, self, stop))
            return
        for target in self.mentioned(chat, reply):
            if target.id != bot.id:
                ask = f"{bot.name} asked you in the group: {reply}\n(The person's message was: {original})"
                await self._turn(target, chat, ask, TurnCtx(chat["id"], target.id, self, stop))
                return

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
            reply = await run_bot_turn(bot, self.router, [], instruction, sub, prefer=self.model_for(bot.id),
                                       max_steps=SAVE_MAX_STEPS if self.saving() else MAX_STEPS)
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
