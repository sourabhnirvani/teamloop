"""Crew memory: facts the person asks the bots to remember, shared by every bot and every chat."""

from __future__ import annotations

import re
import time

from teamloop.tools.registry import ToolResult, tool

SCHEMA = """CREATE TABLE IF NOT EXISTS memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT, fact TEXT NOT NULL, by TEXT NOT NULL, ts REAL NOT NULL)"""
MAX_FACT = 500


def _ensure(store) -> None:
    store._run(SCHEMA)


def remember_fact(store, fact: str, by: str) -> int:
    _ensure(store)
    return store._run("INSERT INTO memory (fact, by, ts) VALUES (?,?,?)", (fact[:MAX_FACT], by, time.time())).lastrowid


def recall_facts(store, query: str = "", limit: int = 10) -> list[dict]:
    _ensure(store)
    rows = store._all("SELECT id, fact FROM memory ORDER BY id DESC LIMIT 500")
    words = [w for w in re.findall(r"\w+", query.lower()) if len(w) > 2]
    if words:
        scored = [(sum(w in r["fact"].lower() for w in words), r) for r in rows]
        rows = [r for s, r in sorted(scored, key=lambda x: -x[0]) if s > 0]
    return rows[:limit]


def forget_fact(store, fact_id: int) -> bool:
    _ensure(store)
    return store._run("DELETE FROM memory WHERE id=?", (fact_id,)).rowcount > 0


INSTRUCTION = re.compile(r"^\s*(?:please\s+|can you\s+|could you\s+)?(?:save|open|create|delete|send|write|remind|"
                         r"close)\b", re.I)
ASKED_TO_REMEMBER = re.compile(r"\bremember\b|\bnote\b|\bdon'?t forget\b|\bkeep in mind\b", re.I)


def _flat(text: str) -> str:
    return re.sub(r"\W+", " ", text or "").strip().lower()


def is_task(fact: str, person_said: str) -> bool:
    """A "fact" that is really the request (seen live: S stored "Save a file at workspace/evals/..." and a later
    turn offered to save that old file again). Fine when the person's own words asked to remember it."""
    if ASKED_TO_REMEMBER.search(person_said or ""):
        return False
    return bool(INSTRUCTION.match(fact)) or (bool(person_said) and _flat(fact) == _flat(person_said))


def _person_said(ctx) -> str:
    """The person's latest message in this chat."""
    try:
        said = [m for m in ctx.crew.store.messages(ctx.chat_id, limit=20) if m["sender"] == "user"]
        return said[-1]["text"] if said else ""
    except Exception:  # no store (a bare test ctx): judge the fact alone
        return ""


@tool("remember", "Save a fact the person wants the crew to remember (preferences, names, details).",
      {"fact": {"type": "string"}, "required": ["fact"]}, kit="memory")
async def remember(args: dict, ctx) -> ToolResult:
    fact = str(args.get("fact", "")).strip()
    if not fact:
        return ToolResult(False, "What should I remember?")
    if is_task(fact, _person_said(ctx)):
        return ToolResult(False, "That's a task, not a fact about the person, so I didn't store it: do the task "
                                 "instead. remember is for preferences, names and details.")
    fid = remember_fact(ctx.crew.store, fact, ctx.bot_id)
    return ToolResult(True, f"Remembered (#{fid}): {fact}")


@tool("recall", "Look up facts the crew remembered. Empty query lists the newest.",
      {"query": {"type": "string"}}, kit="memory")
async def recall(args: dict, ctx) -> ToolResult:
    rows = recall_facts(ctx.crew.store, str(args.get("query", "")))
    if not rows:
        return ToolResult(True, "Nothing remembered about that.")
    return ToolResult(True, f"Found {len(rows)} remembered facts.", {"facts": [f"#{r['id']}: {r['fact']}" for r in rows]})


@tool("forget", "Forget a remembered fact by its number.", {"id": {"type": "integer"}, "required": ["id"]},
      kit="memory")
async def forget(args: dict, ctx) -> ToolResult:
    fid = int(args.get("id", 0))
    return ToolResult(True, f"Forgot #{fid}.") if forget_fact(ctx.crew.store, fid) else \
        ToolResult(False, f"There is no fact #{fid}.")
