"""Approval cards: a bot that wants to act as the person waits for Approve/Deny. No answer = no.

A "no" is remembered for a while: the same request in the same chat is refused without asking again,
so a later, unrelated message can't bring a denied delete back (until the person says "ask me again").
"""

from __future__ import annotations

import asyncio
import time

from teamloop.crew.events import Bus
from teamloop.crew.store import Store

DEFAULT_TIMEOUT = 120.0
DENY_MEMORY = 600.0  # seconds a "no" holds for the same request in the same chat


class Gate:
    def __init__(self, store: Store, bus: Bus, timeout: float = DEFAULT_TIMEOUT):
        self.store, self.bus, self.timeout = store, bus, timeout
        self._waiting: dict[str, tuple[str, asyncio.Future]] = {}
        self._denied: dict[tuple[str, str, str], float] = {}
        self._stopped: set[str] = set()
        self.last: dict[str, str] = {}  # chat id -> how the latest card there ended
        self.cards: dict[str, dict] = {}  # approval id -> its event, while it waits (for apps that reconnect)

    async def ask(self, chat_id: str, bot: str, title: str, details: str, screenshot: str | None = None,
                  key: str | None = None) -> bool:
        # `key` says what the request really is (e.g. "delete:notes.txt"), so a re-worded repeat is still a no
        key = (chat_id, title, key or details)
        said_no = self._denied.get(key)
        if said_no is not None and time.monotonic() - said_no < DENY_MEMORY:
            self.last[chat_id] = "denied_before"
            return False
        row = self.store.add_approval(chat_id, bot, title, details)
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._waiting[row["id"]] = (chat_id, future)
        card = {"type": "approval", "id": row["id"], "chat_id": chat_id, "bot": bot, "title": title,
                "details": details, "screenshot": screenshot}
        self.cards[row["id"]] = card
        await self.bus.emit("approval", **{k: v for k, v in card.items() if k != "type"})
        try:
            ok = bool(await asyncio.wait_for(future, self.timeout))
            status = "approved" if ok else "denied"
        except asyncio.TimeoutError:
            ok, status = False, "expired"
        finally:
            self._waiting.pop(row["id"], None)
            self.cards.pop(row["id"], None)
        if row["id"] in self._stopped:  # Stop pressed: not a "no" to remember
            self._stopped.discard(row["id"])
            status = "stopped"
        if status == "denied":
            self._denied[key] = time.monotonic()
        self.last[chat_id] = status
        self.store.set_approval(row["id"], status)
        await self.bus.emit("approval_done", id=row["id"], chat_id=chat_id, status=status)
        return ok

    def answer(self, approval_id: str, ok: bool) -> bool:
        waiting = self._waiting.get(approval_id)
        if not waiting or waiting[1].done():
            return False
        waiting[1].set_result(bool(ok))
        return True

    def waiting_cards(self) -> list[dict]:
        return [dict(c) for aid, c in self.cards.items() if aid in self._waiting and not self._waiting[aid][1].done()]

    def pending_in(self, chat_id: str) -> list[str]:
        return [aid for aid, (cid, fut) in self._waiting.items() if cid == chat_id and not fut.done()]

    def deny_all(self, chat_id: str) -> int:
        ids = self.pending_in(chat_id)
        for aid in ids:
            self._stopped.add(aid)
            self.answer(aid, False)
        return len(ids)

    def forget_denials(self, chat_id: str) -> int:
        """The person said "ask me again": earlier "no"s in this chat stop blocking."""
        keys = [k for k in self._denied if k[0] == chat_id]
        for k in keys:
            del self._denied[k]
        return len(keys)
