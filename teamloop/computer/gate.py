"""Approval cards: a bot that wants to act as the person waits for Approve/Deny. No answer = no."""

from __future__ import annotations

import asyncio

from teamloop.crew.events import Bus
from teamloop.crew.store import Store

DEFAULT_TIMEOUT = 120.0


class Gate:
    def __init__(self, store: Store, bus: Bus, timeout: float = DEFAULT_TIMEOUT):
        self.store, self.bus, self.timeout = store, bus, timeout
        self._waiting: dict[str, tuple[str, asyncio.Future]] = {}

    async def ask(self, chat_id: str, bot: str, title: str, details: str, screenshot: str | None = None) -> bool:
        row = self.store.add_approval(chat_id, bot, title, details)
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._waiting[row["id"]] = (chat_id, future)
        await self.bus.emit("approval", id=row["id"], chat_id=chat_id, bot=bot, title=title,
                            details=details, screenshot=screenshot)
        try:
            ok = bool(await asyncio.wait_for(future, self.timeout))
            status = "approved" if ok else "denied"
        except asyncio.TimeoutError:
            ok, status = False, "expired"
        finally:
            self._waiting.pop(row["id"], None)
        self.store.set_approval(row["id"], status)
        await self.bus.emit("approval_done", id=row["id"], chat_id=chat_id, status=status)
        return ok

    def answer(self, approval_id: str, ok: bool) -> bool:
        waiting = self._waiting.get(approval_id)
        if not waiting or waiting[1].done():
            return False
        waiting[1].set_result(bool(ok))
        return True

    def pending_in(self, chat_id: str) -> list[str]:
        return [aid for aid, (cid, fut) in self._waiting.items() if cid == chat_id and not fut.done()]

    def deny_all(self, chat_id: str) -> int:
        ids = self.pending_in(chat_id)
        for aid in ids:
            self.answer(aid, False)
        return len(ids)
