"""Routines: "every Monday at 9am, ..." jobs. Due routines are posted into their chat as the person's message.

Schedules S understands (plain words, local time):
  "every day at 9am" · "every weekday at 18:30" · "every monday at 9" · "every 2 hours" · "every 30 minutes"
  "in 10 minutes" · "tomorrow at 8am" (one-off)
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from teamloop.tools.registry import ToolResult, tool

if TYPE_CHECKING:
    from teamloop.crew.team import Crew

log = logging.getLogger(__name__)

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_TIME = r"(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?"
_EVERY_N = re.compile(r"^every\s+(\d+)\s*(minute|minutes|min|mins|hour|hours|hr|hrs)$")
_IN_N = re.compile(r"^in\s+(\d+)\s*(minute|minutes|min|mins|hour|hours|hr|hrs)$")
_DAILY = re.compile(rf"^every\s+(day|weekday|{'|'.join(DAYS)})\s*{_TIME}$")
_TOMORROW = re.compile(rf"^(today|tomorrow)\s*{_TIME}$")
TICK_SECONDS = 20


def _hm(hour: str, minute: str | None, ampm: str | None) -> tuple[int, int]:
    h, m = int(hour), int(minute or 0)
    if ampm == "pm" and h < 12:
        h += 12
    if ampm == "am" and h == 12:
        h = 0
    if not (0 <= h < 24 and 0 <= m < 60):
        raise ValueError("That time doesn't exist.")
    return h, m


def _minutes(n: str, unit: str) -> int:
    return int(n) * (60 if unit.startswith("h") else 1)


def next_run(schedule: str, now: datetime | None = None) -> datetime | None:
    """When a schedule fires next after `now`; None for a one-off that has passed. Raises ValueError if unclear."""
    now = now or datetime.now()
    s = re.sub(r"\s+", " ", schedule.strip().lower())
    if m := _EVERY_N.match(s):
        return now + timedelta(minutes=max(1, _minutes(*m.groups())))
    if m := _IN_N.match(s):
        return now + timedelta(minutes=max(1, _minutes(*m.groups())))
    if m := _TOMORROW.match(s):
        h, mi = _hm(*m.groups()[1:])
        day = now + timedelta(days=1 if m.group(1) == "tomorrow" else 0)
        at = day.replace(hour=h, minute=mi, second=0, microsecond=0)
        return at if at > now else None
    if m := _DAILY.match(s):
        which = m.group(1)
        h, mi = _hm(*m.groups()[1:])
        for add in range(0, 8):
            day = now + timedelta(days=add)
            at = day.replace(hour=h, minute=mi, second=0, microsecond=0)
            if at <= now:
                continue
            if which == "day" or (which == "weekday" and day.weekday() < 5) or \
                    (which in DAYS and day.weekday() == DAYS.index(which)):
                return at
    raise ValueError(f"I don't understand the schedule {schedule!r}. Try 'every monday at 9am' or 'in 10 minutes'.")


def is_repeating(schedule: str) -> bool:
    return schedule.strip().lower().startswith("every")


# ---- storage helpers on the crew's store --------------------------------------------------------
def add(crew: "Crew", chat_id: str, text: str, schedule: str) -> dict:
    for row in listing(crew, chat_id):  # the same job twice (a model repeating itself) stays one routine
        if row["text"].strip().lower() == text.strip().lower() and row["schedule"].strip().lower() == schedule.strip().lower():
            return {**row, "existing": True}
    when = next_run(schedule)
    if when is None:
        raise ValueError("That time has already passed.")
    row = {"id": uuid.uuid4().hex[:8], "chat_id": chat_id, "text": text, "schedule": schedule,
           "next_run": when.timestamp(), "enabled": 1}
    crew.store._run("INSERT INTO routines VALUES (:id,:chat_id,:text,:schedule,:next_run,:enabled)", row)
    return row


def listing(crew: "Crew", chat_id: str | None = None) -> list[dict]:
    if chat_id:
        return crew.store._all("SELECT * FROM routines WHERE enabled=1 AND chat_id=? ORDER BY next_run", (chat_id,))
    return crew.store._all("SELECT * FROM routines WHERE enabled=1 ORDER BY next_run")


def cancel(crew: "Crew", routine_id: str) -> bool:
    return crew.store._run("UPDATE routines SET enabled=0 WHERE id=? AND enabled=1", (routine_id,)).rowcount > 0


async def run_due(crew: "Crew", now: float | None = None) -> int:
    now = now or time.time()
    if crew.store.get_setting("asleep", False):
        return 0  # due routines run once the crew wakes up
    due = crew.store._all("SELECT * FROM routines WHERE enabled=1 AND next_run<=?", (now,))
    for r in due:
        if is_repeating(r["schedule"]):
            nxt = next_run(r["schedule"], datetime.fromtimestamp(now))
            crew.store._run("UPDATE routines SET next_run=? WHERE id=?", (nxt.timestamp(), r["id"]))
        else:
            crew.store._run("UPDATE routines SET enabled=0 WHERE id=?", (r["id"],))
        if crew.store.get_chat(r["chat_id"]) is None:
            continue
        await crew.say(r["chat_id"], "s" if "s" in crew.store.get_chat(r["chat_id"])["members"] else
                       crew.store.get_chat(r["chat_id"])["members"][0], f"⏰ Routine: {r['text']}", kind="routine")
        await crew.post(r["chat_id"], r["text"])
    return len(due)


async def scheduler(crew: "Crew") -> None:
    while True:
        try:
            await run_due(crew)
        except Exception:
            log.exception("routine tick failed")
        await asyncio.sleep(TICK_SECONDS)


def _when(row: dict) -> str:
    return datetime.fromtimestamp(row["next_run"]).strftime("%a %d %b %H:%M")


# ---- tools for S ---------------------------------------------------------------------------------
@tool("schedule_routine", "Set up a job that runs later or repeats, e.g. every monday at 9am.",
      {"task": {"type": "string", "description": "what to do, written as the person's request"},
       "schedule": {"type": "string", "description": "every day at 9am / every monday at 18:30 / every 2 hours / "
                                                     "in 10 minutes / tomorrow at 8am"},
       "required": ["task", "schedule"]}, kit="lead")
async def schedule_routine(args: dict, ctx) -> ToolResult:
    try:
        row = add(ctx.crew, ctx.chat_id, str(args.get("task", "")).strip(), str(args.get("schedule", "")))
    except ValueError as e:
        return ToolResult(False, str(e))
    if row.get("existing"):
        return ToolResult(True, f"That routine already exists ({row['id']}): \"{row['text']}\" ({row['schedule']}); "
                                f"next run {_when(row)}.", {"id": row["id"]})
    return ToolResult(True, f"Routine set: \"{row['text']}\" ({row['schedule']}); first run {_when(row)}.",
                      {"id": row["id"]})


@tool("list_routines", "List this chat's routines.", {}, kit="lead")
async def list_routines(args: dict, ctx) -> ToolResult:
    rows = listing(ctx.crew, ctx.chat_id)
    if not rows:
        return ToolResult(True, "There are no routines in this chat.")
    return ToolResult(True, f"{len(rows)} routines.",
                      {"routines": [{"id": r["id"], "task": r["text"], "schedule": r["schedule"], "next": _when(r)}
                                    for r in rows]})


@tool("cancel_routine", "Cancel a routine by its id.", {"id": {"type": "string"}, "required": ["id"]}, kit="lead")
async def cancel_routine(args: dict, ctx) -> ToolResult:
    rid = str(args.get("id", "")).strip()
    return ToolResult(True, f"Cancelled routine {rid}.") if cancel(ctx.crew, rid) else \
        ToolResult(False, f"There is no active routine {rid}.")
