"""What a tool sees while a bot works: which chat, which bot, how to emit events, ask, or stop."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
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

    async def emit(self, type: str, **data: Any) -> None:
        await self.crew.bus.emit(type, chat_id=self.chat_id, **data)

    async def approve(self, title: str, details: str, screenshot: str | None = None) -> bool:
        self.check_stop()
        ok = await self.crew.gate.ask(self.chat_id, self.bot_id, title, details, screenshot)
        self.check_stop()
        return ok

    def check_stop(self) -> None:
        if self.stop.is_set():
            raise Stopped()

    def for_bot(self, bot_id: str, depth: int | None = None) -> "TurnCtx":
        return replace(self, bot_id=bot_id, depth=self.depth if depth is None else depth)
