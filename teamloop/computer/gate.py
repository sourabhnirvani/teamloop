"""Approval cards: a bot that wants to act as the person waits for Approve/Deny. No answer = no.

A "no" is remembered for a while: the same request in the same chat is refused without asking again,
so a later, unrelated message can't bring a denied delete back (until the person says "ask me again").

"Always allow" turns a card into a rule, so the same action goes ahead without asking next time. It's only
offered for actions that don't send, post, buy, delete, replace files or touch power; a command rule
matches that exact command only.
"""

from __future__ import annotations

import asyncio
import re
import time
import uuid

from teamloop.crew.events import Bus
from teamloop.crew.store import Store

DEFAULT_TIMEOUT = 120.0
DENY_MEMORY = 600.0  # seconds a "no" holds for the same request in the same chat
RULES = "always_allowed"  # setting: [{id, title, key, label, bot, added}]

# cards that can never become "always allow": anything that sends, posts, submits, buys, replaces or powers off
_NEVER_ALWAYS = re.compile(r"^(Type and send|Type |Press |Click |Select |Fill |Submit|Open a checkout page|Replace a file|"
                           r"Lock|Sleep|Restart|Shutdown)", re.I)
_RISKY_COMMANDS = {"delete", "power", "registry", "run-code"}
_BY_TITLE = re.compile(r"^(Close |Turn Wi-Fi off)")  # "always allow closing Notepad", whatever windows are open


def can_always(title: str, key: str) -> bool:
    if _NEVER_ALWAYS.match(title) or "without saving" in title.lower():  # discarding work is asked every time
        return False
    if title == "Run a command":
        acts = key.removeprefix("cmd:").split(":", 1)[0].split("+")
        return key.startswith("cmd:") and not (set(acts) & _RISKY_COMMANDS)
    return True


def rule_key(title: str, key: str) -> str:
    return "" if _BY_TITLE.match(title) else key


class Gate:
    def __init__(self, store: Store, bus: Bus, timeout: float = DEFAULT_TIMEOUT):
        self.store, self.bus, self.timeout = store, bus, timeout
        self._waiting: dict[str, tuple[str, asyncio.Future]] = {}
        self._denied: dict[tuple[str, str, str], float] = {}
        self._stopped: set[str] = set()
        self.last: dict[str, str] = {}  # chat id -> how the latest card there ended
        self.cards: dict[str, dict] = {}  # approval id -> its event, while it waits (for apps that reconnect)
        self._keys: dict[str, str] = {}  # approval id -> what it really is, for "always allow"

    async def ask(self, chat_id: str, bot: str, title: str, details: str, screenshot: str | None = None,
                  key: str | None = None) -> bool:
        # `key` says what the request really is (e.g. "delete:notes.txt"), so a re-worded repeat is still a no
        what = key or details
        rule = self.rule_for(title, what)
        if rule:  # the person said "always allow" for exactly this: go ahead, and say so in the chat
            row = self.store.add_approval(chat_id, bot, title, details)
            self.store.set_approval(row["id"], "allowed")
            self.last[chat_id] = "approved"
            await self.bus.emit("allowed", chat_id=chat_id, bot=bot, title=title, details=details, rule=rule["id"])
            return True
        key = (chat_id, title, what)
        said_no = self._denied.get(key)
        if said_no is not None and time.monotonic() - said_no < DENY_MEMORY:
            self.last[chat_id] = "denied_before"
            return False
        row = self.store.add_approval(chat_id, bot, title, details)
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._waiting[row["id"]] = (chat_id, future)
        card = {"type": "approval", "id": row["id"], "chat_id": chat_id, "bot": bot, "title": title,
                "details": details, "screenshot": screenshot, "can_always": can_always(title, what)}
        self.cards[row["id"]] = card
        self._keys[row["id"]] = what
        await self.bus.emit("approval", **{k: v for k, v in card.items() if k != "type"})
        try:
            ok = bool(await asyncio.wait_for(future, self.timeout))
            status = "approved" if ok else "denied"
        except asyncio.TimeoutError:
            ok, status = False, "expired"
        finally:
            self._waiting.pop(row["id"], None)
            self.cards.pop(row["id"], None)
            self._keys.pop(row["id"], None)
        if row["id"] in self._stopped:  # Stop pressed: not a "no" to remember
            self._stopped.discard(row["id"])
            status = "stopped"
        if status == "denied":
            self._denied[key] = time.monotonic()
        self.last[chat_id] = status
        self.store.set_approval(row["id"], status)
        await self.bus.emit("approval_done", id=row["id"], chat_id=chat_id, status=status)
        return ok

    def answer(self, approval_id: str, ok: bool, always: bool = False) -> dict | bool:
        """True when the card was waiting; with always=True and an allowable card, the new rule instead."""
        waiting = self._waiting.get(approval_id)
        if not waiting or waiting[1].done():
            return False
        card = self.cards.get(approval_id)
        rule = None
        if ok and always and card and card.get("can_always"):
            rule = self.allow(card["title"], self._keys.get(approval_id, card["details"]), card["bot"], card["details"])
        waiting[1].set_result(bool(ok))
        return rule or True

    # ---- always-allow rules ---------------------------------------------------------------------
    def rules(self) -> list[dict]:
        return list(self.store.get_setting(RULES, []) or [])

    def rule_for(self, title: str, key: str) -> dict | None:
        if not can_always(title, key):
            return None
        want = rule_key(title, key)
        return next((r for r in self.rules() if r["title"] == title and r["key"] == want), None)

    def allow(self, title: str, key: str, bot: str, details: str = "") -> dict:
        existing = self.rule_for(title, key)
        if existing:
            return existing
        first = (details or key).splitlines()[0] if (details or key) else ""
        label = title if _BY_TITLE.match(title) else f"{title}: {first[:120]}"
        rule = {"id": uuid.uuid4().hex[:10], "title": title, "key": rule_key(title, key), "label": label,
                "bot": bot, "added": time.time()}
        self.store.set_setting(RULES, [*self.rules(), rule])
        return rule

    def forget_rule(self, rule_id: str) -> bool:
        rules = self.rules()
        kept = [r for r in rules if r["id"] != rule_id]
        self.store.set_setting(RULES, kept)
        return len(kept) != len(rules)

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
