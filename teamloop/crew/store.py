"""SQLite storage: chats, messages, approvals, usage, settings, routines, board tasks."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from datetime import date
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS chats (
    id TEXT PRIMARY KEY, title TEXT NOT NULL, members TEXT NOT NULL, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT NOT NULL, sender TEXT NOT NULL,
    text TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'chat', ts REAL NOT NULL);
CREATE INDEX IF NOT EXISTS messages_chat ON messages(chat_id, id);
CREATE TABLE IF NOT EXISTS approvals (
    id TEXT PRIMARY KEY, chat_id TEXT NOT NULL, bot TEXT NOT NULL, title TEXT NOT NULL,
    details TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', ts REAL NOT NULL);
CREATE TABLE IF NOT EXISTS usage (
    day TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL,
    requests INTEGER NOT NULL DEFAULT 0, tokens_in INTEGER NOT NULL DEFAULT 0,
    tokens_out INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (day, provider, model));
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS routines (
    id TEXT PRIMARY KEY, chat_id TEXT NOT NULL, text TEXT NOT NULL, schedule TEXT NOT NULL,
    next_run REAL NOT NULL, enabled INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'todo',
    bot TEXT, by TEXT, chat_id TEXT, note TEXT NOT NULL DEFAULT '', source TEXT NOT NULL DEFAULT 'manual',
    created REAL NOT NULL, updated REAL NOT NULL);
"""

TASK_STATES = ("todo", "doing", "blocked", "done")


class Store:
    def __init__(self, path: Path | str):
        self.path = str(path)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        with self._lock:
            self._db.executescript(SCHEMA)
            self._db.commit()

    def _run(self, sql: str, args: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._db.execute(sql, args)
            self._db.commit()
            return cur

    def _all(self, sql: str, args: tuple = ()) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self._db.execute(sql, args).fetchall()]

    # ---- chats ----------------------------------------------------------------------------
    def create_chat(self, title: str, members: list[str], chat_id: str | None = None) -> dict:
        chat = {"id": chat_id or uuid.uuid4().hex[:12], "title": title, "members": members, "created": time.time()}
        self._run("INSERT INTO chats VALUES (?,?,?,?)",
                  (chat["id"], title, json.dumps(members), chat["created"]))
        return chat

    def get_chat(self, chat_id: str) -> dict | None:
        rows = self._all("SELECT * FROM chats WHERE id=?", (chat_id,))
        return _chat(rows[0]) if rows else None

    def chats(self) -> list[dict]:
        out = [_chat(r) for r in self._all("SELECT * FROM chats ORDER BY created")]
        last = {r["chat_id"]: {"sender": r["sender"], "text": r["text"][:160], "kind": r["kind"], "ts": r["ts"]}
                for r in self._all("SELECT m.chat_id, m.sender, m.text, m.kind, m.ts FROM messages m JOIN "
                                   "(SELECT chat_id, MAX(id) AS id FROM messages GROUP BY chat_id) l ON m.id = l.id")}
        for chat in out:
            chat["last"] = last.get(chat["id"])
        return out

    def delete_chat(self, chat_id: str) -> None:
        self._run("DELETE FROM messages WHERE chat_id=?", (chat_id,))
        self._run("DELETE FROM chats WHERE id=?", (chat_id,))

    def update_members(self, chat_id: str, members: list[str]) -> None:
        self._run("UPDATE chats SET members=? WHERE id=?", (json.dumps(members), chat_id))

    # ---- messages -------------------------------------------------------------------------
    def add_message(self, chat_id: str, sender: str, text: str, kind: str = "chat") -> dict:
        ts = time.time()
        cur = self._run("INSERT INTO messages (chat_id, sender, text, kind, ts) VALUES (?,?,?,?,?)",
                        (chat_id, sender, text, kind, ts))
        return {"id": cur.lastrowid, "chat_id": chat_id, "sender": sender, "text": text, "kind": kind, "ts": ts}

    def messages(self, chat_id: str, limit: int = 200) -> list[dict]:
        rows = self._all("SELECT * FROM messages WHERE chat_id=? ORDER BY id DESC LIMIT ?", (chat_id, limit))
        return list(reversed(rows))

    # ---- approvals ------------------------------------------------------------------------
    def add_approval(self, chat_id: str, bot: str, title: str, details: str) -> dict:
        row = {"id": uuid.uuid4().hex[:12], "chat_id": chat_id, "bot": bot, "title": title,
               "details": details, "status": "pending", "ts": time.time()}
        self._run("INSERT INTO approvals VALUES (:id,:chat_id,:bot,:title,:details,:status,:ts)", row)
        return row

    def set_approval(self, approval_id: str, status: str) -> None:
        self._run("UPDATE approvals SET status=? WHERE id=?", (status, approval_id))

    def pending_approvals(self, chat_id: str | None = None) -> list[dict]:
        if chat_id:
            return self._all("SELECT * FROM approvals WHERE status='pending' AND chat_id=?", (chat_id,))
        return self._all("SELECT * FROM approvals WHERE status='pending'")

    # ---- usage ----------------------------------------------------------------------------
    def add_usage(self, provider: str, model: str, tokens_in: int, tokens_out: int, purpose: str = "") -> None:
        self._run(
            "INSERT INTO usage VALUES (?,?,?,1,?,?) ON CONFLICT(day, provider, model) DO UPDATE SET "
            "requests=requests+1, tokens_in=tokens_in+excluded.tokens_in, tokens_out=tokens_out+excluded.tokens_out",
            (date.today().isoformat(), provider, model, tokens_in, tokens_out))

    def usage(self, day: str | None = None) -> list[dict]:
        return self._all("SELECT * FROM usage WHERE day=? ORDER BY provider, model",
                         (day or date.today().isoformat(),))

    # ---- board ----------------------------------------------------------------------------
    def add_task(self, title: str, status: str = "todo", bot: str | None = None, by: str | None = None,
                 chat_id: str | None = None, source: str = "manual", note: str = "") -> dict:
        now = time.time()
        cur = self._run("INSERT INTO tasks (title, status, bot, by, chat_id, note, source, created, updated) "
                        "VALUES (?,?,?,?,?,?,?,?,?)", (title, status, bot, by, chat_id, note, source, now, now))
        return self.get_task(cur.lastrowid)

    def get_task(self, task_id: int) -> dict | None:
        rows = self._all("SELECT * FROM tasks WHERE id=?", (task_id,))
        return rows[0] if rows else None

    def update_task(self, task_id: int, **fields: Any) -> dict | None:
        allowed = {k: v for k, v in fields.items() if k in ("title", "status", "note", "bot") and v is not None}
        if allowed:
            sets = ", ".join(f"{k}=?" for k in allowed)
            self._run(f"UPDATE tasks SET {sets}, updated=? WHERE id=?", (*allowed.values(), time.time(), task_id))
        return self.get_task(task_id)

    def tasks(self, limit: int = 300) -> list[dict]:
        return self._all("SELECT * FROM tasks ORDER BY id DESC LIMIT ?", (limit,))

    def delete_task(self, task_id: int) -> bool:
        return self._run("DELETE FROM tasks WHERE id=?", (task_id,)).rowcount > 0

    # ---- settings -------------------------------------------------------------------------
    def get_setting(self, key: str, default: Any = None) -> Any:
        rows = self._all("SELECT value FROM settings WHERE key=?", (key,))
        return json.loads(rows[0]["value"]) if rows else default

    def set_setting(self, key: str, value: Any) -> None:
        self._run("INSERT INTO settings VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                  (key, json.dumps(value)))

    def close(self) -> None:
        with self._lock:
            self._db.close()


def _chat(row: dict) -> dict:
    return {**row, "members": json.loads(row["members"])}
