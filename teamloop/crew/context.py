"""What a tool sees while a bot works: which chat, which bot, how to emit events, ask, or stop."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from teamloop.crew.team import Crew


class Stopped(Exception):
    """The person pressed Stop (or typed "stop")."""


@dataclass
class TurnCtx:
    chat_id: str
    bot_id: str
    crew: "Crew"
    stop: asyncio.Event
    depth: int = 0  # how many handoffs deep this turn is
    last_answer: str = ""  # how this turn's latest card ended: approved, denied, expired, denied_before, expired_before
    # Cards nobody answered in this job (shared with teammates' sub-turns): no answer counts as a no, so the same
    # request isn't asked again until the person sends a new message.
    unanswered: set = field(default_factory=set)

    async def emit(self, type: str, **data: Any) -> None:
        await self.crew.bus.emit(type, chat_id=self.chat_id, **data)

    async def approve(self, title: str, details: str, screenshot: str | None = None, key: str | None = None) -> bool:
        self.check_stop()
        what = (title, key or details)
        if what in self.unanswered:
            self.last_answer = "expired_before"
            return False
        ok = await self.crew.gate.ask(self.chat_id, self.bot_id, title, details, screenshot, key=key)
        self.last_answer = self.crew.gate.last.get(self.chat_id, "")
        if self.last_answer == "expired":
            self.unanswered.add(what)
        self.check_stop()
        return ok

    def check_stop(self) -> None:
        if self.stop.is_set():
            raise Stopped()

    def for_bot(self, bot_id: str, depth: int | None = None) -> "TurnCtx":
        return replace(self, bot_id=bot_id, depth=self.depth if depth is None else depth)
