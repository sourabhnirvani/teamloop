"""Evals that check real outcomes on this laptop, not just what a bot said.

    python -m evals.run                  deterministic tasks (no model calls)
    python -m evals.run --live           + tasks where the crew's models decide what to do
    python -m evals.run --only battery   one task

Each task gets its own chat, so it is its own neatlogs session. Approval cards are answered by the task
("yes" or "no") and the check looks at the machine: the file exists with the right content, the battery
number matches, a delete nobody approved didn't happen. Results go to evidence/evals/.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

from teamloop import config, kits, trace

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "evidence" / "evals"


@dataclass
class Task:
    name: str
    about: str
    run: Callable[["Eval"], Awaitable[str]]  # returns a detail line; raises AssertionError on a wrong outcome
    live: bool = False
    desktop: bool = False  # opens windows on screen


class Eval:
    """One task's world: a fresh chat with every bot, approvals answered with `approve`."""

    def __init__(self, crew: Any, name: str, approve: bool = True):
        self.crew, self.approve = crew, approve
        self.chat_id = f"eval-{name}-{int(time.time())}"
        crew.store.create_chat(f"Eval: {name}", ["s", "desk", "web", "scout", "inbox", "writer"], chat_id=self.chat_id)
        self.folder = config.workspace() / "evals"
        self.folder.mkdir(parents=True, exist_ok=True)
        self.asked: list[str] = []

    async def say(self, text: str, timeout: float = 240) -> str:
        """Post like the person would and return the last bot reply."""
        with self.crew.bus.subscribe() as queue:
            answering = asyncio.create_task(self._answer(queue))
            try:
                await self.crew.post(self.chat_id, text)
                await asyncio.wait_for(self.crew.wait_idle(self.chat_id), timeout)
            finally:
                answering.cancel()
        bots = [m for m in self.crew.store.messages(self.chat_id) if m["sender"] != "user"]
        return bots[-1]["text"] if bots else ""

    async def tool(self, name: str, args: dict, bot: str = "desk") -> Any:
        from teamloop.crew.context import TurnCtx
        from teamloop.tools import registry

        with self.crew.bus.subscribe() as queue:
            answering = asyncio.create_task(self._answer(queue))
            try:
                ctx = TurnCtx(self.chat_id, bot, self.crew, asyncio.Event())
                return await registry.run(name, args, ctx)
            finally:
                answering.cancel()

    async def _answer(self, queue: asyncio.Queue) -> None:
        while True:
            e = await queue.get()
            if e["type"] == "approval" and e.get("chat_id") == self.chat_id:
                self.asked.append(e["title"])
                self.crew.gate.answer(e["id"], self.approve)


# ---- deterministic tasks (no model) ------------------------------------------------------------
async def battery(ev: Eval) -> str:
    from teamloop.computer import system

    reply = await ev.say("what's my battery?")
    real = system.battery()
    if real is None:
        assert "battery" not in reply.lower() or "Right now" in reply, reply
        return "no battery on this machine; status read back"
    said = re.search(r"battery (\d+)%", reply)
    assert said, f"no battery number in: {reply}"
    assert abs(int(said.group(1)) - real["percent"]) <= 1, f"said {said.group(1)}%, machine says {real['percent']}%"
    return f"said {said.group(1)}%, machine {real['percent']}%"


async def write_file(ev: Eval) -> str:
    from teamloop.tools.files import resolve

    path = f"workspace/evals/note-{int(time.time() * 1000)}.txt"
    result = await ev.tool("write_file", {"path": path, "content": "TeamLoop eval: hello"}, bot="writer")
    real = resolve(path)
    assert result.ok, result.text
    assert real.read_text(encoding="utf-8") == "TeamLoop eval: hello", "content differs"
    return f"{real.name} has the exact text"


async def unapproved_delete(ev: Eval) -> str:
    target = ev.folder / f"keep-{int(time.time() * 1000)}.txt"
    target.write_text("do not delete", encoding="utf-8")
    ev.approve = False
    result = await ev.tool("run_command", {"command": f"Remove-Item '{target}'"})
    assert ev.asked == ["Run a command"], f"approval asked: {ev.asked}"
    assert not result.ok and target.exists(), "the file was deleted without approval"
    return "asked first; the answer was no and the file is still there"


async def terminal(ev: Eval) -> str:
    await ev.tool("run_command", {"command": f"Set-Location '{ev.folder}'"})
    where = await ev.tool("run_command", {"command": "(Get-Location).Path"})
    assert where.data["stdout"].strip().lower() == str(ev.folder).lower(), where.data
    code = await ev.tool("run_command", {"command": "cmd /c exit 7"})
    assert code.data["exit_code"] == 7 and not code.ok, code.data
    return "cd stuck between runs; exit code 7 read back"


async def secrets_hidden(ev: Eval) -> str:
    fake = "gsk_" + "e" * 52
    await ev.say(f"here is my key {fake}")
    stored = json.dumps(ev.crew.store.messages(ev.chat_id))
    assert fake not in stored, "a pasted key was stored in the chat"
    return "the pasted key never reached the chat log"


async def fast_path_volume(ev: Eval) -> str:
    from teamloop.computer import system

    level, _ = await system.get_volume()
    reply = await ev.say(f"volume {level}")  # same level: nothing audible changes
    now, _ = await system.get_volume()
    assert now == level and f"{level}%" in reply, reply
    return f"volume read back {level}% with no model call"


async def notepad(ev: Eval) -> str:
    from teamloop.computer import winapi

    assert not winapi.find("Notepad"), "skipped: a Notepad window is already open (it could hold unsaved work)"
    opened = await ev.tool("open_app", {"name": "Notepad"})
    assert opened.ok, opened.text
    assert winapi.find("Notepad"), "no Notepad window"
    closed = await ev.tool("close_app", {"name": "Notepad"})
    await asyncio.sleep(1.5)
    assert closed.ok and not winapi.find("Notepad"), closed.text
    return "opened, seen on screen, closed after approval"


# ---- live tasks (the crew's models decide) -----------------------------------------------------
async def live_writer(ev: Eval) -> str:
    from teamloop.tools.files import resolve

    name = f"live-{int(time.time())}.txt"
    reply = await ev.say(f"Ask Writer to save a file at workspace/evals/{name} with exactly this text: crew eval ok")
    real = resolve(f"workspace/evals/{name}")
    assert real.exists(), f"no file; S said: {reply}"
    assert "crew eval ok" in real.read_text(encoding="utf-8").lower(), "wrong content"
    return f"{name} written through S -> Writer"


async def live_desk(ev: Eval) -> str:
    from teamloop.computer import winapi

    assert not winapi.find("Notepad"), "skipped: a Notepad window is already open (it could hold unsaved work)"
    reply = await ev.say("Ask Desk to open Notepad.")
    found = winapi.find("Notepad")
    with contextlib.suppress(Exception):
        await ev.tool("close_app", {"name": "Notepad"})
    assert found, f"no Notepad window; S said: {reply}"
    return "S handed it to Desk and Notepad really opened"


async def live_recovery(ev: Eval) -> str:
    import os

    name = f"recover-{int(time.time())}.txt"
    os.environ["TEAMLOOP_FAIL_ONCE"] = "write_file"
    try:
        reply = await ev.say(f"Save a file at workspace/evals/{name} with the text: recovered")
    finally:
        os.environ.pop("TEAMLOOP_FAIL_ONCE", None)
    from teamloop.tools.files import resolve

    assert resolve(f"workspace/evals/{name}").exists(), f"didn't recover; reply: {reply}"
    return "write_file failed once (simulated) and the crew retried until the file existed"


TASKS = [
    Task("battery", "the battery number matches the machine", battery),
    Task("write_file", "a file exists with the exact content", write_file),
    Task("unapproved_delete", "a delete nobody approved doesn't happen", unapproved_delete),
    Task("terminal", "cd sticks and exit codes are real", terminal),
    Task("secrets_hidden", "a pasted key never reaches the chat log", secrets_hidden),
    Task("fast_path_volume", "a plain command runs with no model", fast_path_volume),
    Task("notepad", "an app really opens and closes", notepad, desktop=True),
    Task("live_writer", "S hands a file job to Writer", live_writer, live=True),
    Task("live_desk", "S hands an app job to Desk", live_desk, live=True, desktop=True),
    Task("live_recovery", "a failed step is retried until the outcome is real", live_recovery, live=True),
]


async def run(live: bool = False, only: list[str] | None = None, desktop: bool = True,
              crew: Any = None, save: bool = True, out: Callable = print) -> list[dict]:
    if crew is None:
        from teamloop.keys import vault
        from teamloop.server.app import build_crew

        kits.load_all()
        with contextlib.suppress(OSError, ValueError):
            vault.export_to_env()
        trace.init()
        (config.workspace() / "evals").mkdir(parents=True, exist_ok=True)
        crew = build_crew(config.workspace() / "evals" / "evals.db")
    picked = [t for t in TASKS if (only and t.name in only) or
              (not only and (live or not t.live) and (desktop or not t.desktop))]
    results = []
    for task in picked:
        started = time.monotonic()
        try:
            detail, ok = await task.run(Eval(crew, task.name)), True
        except AssertionError as e:
            detail, ok = str(e) or "wrong outcome", False
        except Exception as e:  # a crash is a failed eval, not a crashed run
            detail, ok = f"{type(e).__name__}: {e}", False
        row = {"task": task.name, "checks": task.about, "ok": ok, "seconds": round(time.monotonic() - started, 1),
               "detail": detail, "live": task.live}
        results.append(row)
        out(f"{'PASS' if ok else 'FAIL'}  {task.name:<18} {row['seconds']:>5}s  {detail}")
    passed = sum(r["ok"] for r in results)
    out(f"{passed}/{len(results)} passed")
    if save and results:
        RESULTS.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        body = json.dumps({"when": stamp, "passed": passed, "total": len(results), "results": results}, indent=2)
        (RESULTS / f"evals-{stamp}.json").write_text(body, encoding="utf-8")
        (RESULTS / "latest.json").write_text(body, encoding="utf-8")
    trace.flush()
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m evals.run")
    parser.add_argument("--live", action="store_true", help="also run tasks that call models")
    parser.add_argument("--no-desktop", action="store_true", help="skip tasks that open windows")
    parser.add_argument("--only", nargs="*", help="task names")
    args = parser.parse_args(argv)
    with contextlib.suppress(AttributeError):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    results = asyncio.run(run(args.live, args.only, not args.no_desktop))
    return 0 if results and all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
