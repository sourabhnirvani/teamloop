"""A rehearsal TeamLoop on port 8791: the real server and UI, but a scripted model, so checking the UI costs no tokens.

    .venv\\Scripts\\python.exe scripts\\rehearse.py        then open http://127.0.0.1:8791

In the Team chat any message runs the demo job: S hands research to Scout, the report to Writer (whose first
save fails once, like the recovery demo), opening it to Desk (an approval card you answer), then sets a Monday
routine and reports. 1:1 chats answer with one line. Fast-path commands ("battery?", "volume 30") are real.
Files land in a temp folder, nothing opens on screen, and Telegram, the model doctor and tracing are off.
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from teamloop import config, trace  # noqa: E402
from teamloop.computer import tools as desk_tools  # noqa: E402
from teamloop.computer import winapi  # noqa: E402
from teamloop.models import doctor  # noqa: E402
from teamloop.models.router import Reply, ToolCall  # noqa: E402
from teamloop.server import app as server  # noqa: E402
from teamloop.server import telegram  # noqa: E402
from teamloop.tools import files, registry  # noqa: E402
from teamloop.tools.registry import ToolResult  # noqa: E402

PORT = 8791
PACE = 0.7  # seconds per "model call", so the UI has time to show each state
REPORT = "# Free LLM APIs for students\n1. Gemini (https://ai.google.dev)\n2. Groq (https://console.groq.com)\n" \
         "3. OpenRouter (https://openrouter.ai)\n"


def _call(name: str, **args) -> Reply:
    return Reply("", [ToolCall(f"r-{name}-{os.urandom(3).hex()}", name, args)], "rehearsal", "scripted", 120, 40)


def _say(text: str) -> Reply:
    return Reply(text, [], "rehearsal", "scripted", 120, 40)


def _since_person(messages: list[dict]) -> list[dict]:
    """The messages after the newest one from the person (or from the bot handing work over)."""
    last = max((i for i, m in enumerate(messages) if m["role"] == "user"), default=0)
    return messages[last + 1:]


class ScriptRouter:
    """Answers like a model would, from a fixed plan per bot. Each call reports usage like a real one."""

    def __init__(self) -> None:
        self.dead_models: set = set()
        self.last_doctor: list = []
        self.on_usage = None
        self.runs = 0
        self.report = "Desktop/llm-report.md"  # a new name each job, so a second run doesn't hit "already exists"

    async def chat(self, messages, tools=None, prefer=None, purpose="", max_tokens=None, only=False):
        await asyncio.sleep(PACE)
        reply = self._next(messages, purpose)
        if self.on_usage:
            self.on_usage("rehearsal", "scripted", reply.tokens_in, reply.tokens_out, purpose)
        return reply

    def _next(self, messages: list[dict], purpose: str) -> Reply:
        bot = purpose.split(":", 1)[-1]
        done = [m for m in _since_person(messages) if m["role"] == "tool"]
        if purpose.startswith("wrapup"):
            return _say("Done.")
        if bot == "s":
            person = next((str(m["content"]) for m in reversed(messages) if m["role"] == "user"), "")
            if not done and len(person) < 25:  # "hi", "thanks": a one-line answer
                return _say("Hi! I'm S. In this rehearsal, send a longer request to watch the whole crew work.")
            if not done:
                self.runs += 1
                self.report = f"Desktop/llm-report-{self.runs}.md"
            plan = [
                lambda: _call("delegate", bot="scout", instruction="Find the top 3 free LLM APIs for students, with links."),
                lambda: _call("delegate", bot="writer", instruction=f"Save {self.report} with:\n{REPORT}"),
                lambda: _call("delegate", bot="desk", instruction=f"Open {self.report}."),
                lambda: _call("schedule_routine", task="Remind me about the LLM report on my Desktop",
                              schedule="every monday at 9am"),
                lambda: _say("Done: Scout found Gemini, Groq and OpenRouter, Writer saved llm-report.md on your Desktop, "
                             "Desk opened it, and I'll remind you every Monday at 9am."),
            ]
            return plan[min(len(done), len(plan) - 1)]()
        if bot == "scout":
            return _call("web_search", query="free LLM APIs for students") if not done else \
                _say("Top 3: Gemini (https://ai.google.dev), Groq (https://console.groq.com), OpenRouter (https://openrouter.ai).")
        if bot == "writer":
            if len(done) < 2 and not any(str(m["content"]).startswith("OK:") for m in done):
                return _call("write_file", path=self.report, content=REPORT)
            return _say(f"Saved {self.report}.")
        if bot == "desk":
            if not done:
                return _call("open_file", path=self.report)
            result = str(done[-1]["content"])
            return _say("Opened llm-report.md." if result.startswith("OK:") else
                        "No answer on the card, so I left it. Ask me again when you're back."
                        if "No one answered" in result else "You said no, so I left it.")
        return _say(f"Hi! I'm {bot.title()}. (Rehearsal: this chat answers with one line.)")


def install_fakes(home: Path) -> None:
    from teamloop import kits

    kits.load_all()  # tools register when their kit loads
    for name in ("Desktop", "Documents", "Downloads"):
        (home / name).mkdir(parents=True, exist_ok=True)
    files.known_folder = lambda name: home / name

    async def search(args, ctx):
        return ToolResult(True, "Found 3 results.", {"results": [
            {"title": "Gemini API", "url": "https://ai.google.dev"},
            {"title": "Groq", "url": "https://console.groq.com"},
            {"title": "OpenRouter", "url": "https://openrouter.ai"}]})

    registry.REGISTRY["web_search"].handler = search
    desk_tools.os.startfile = lambda path: None  # nothing opens on screen
    async def window(name, before):
        return winapi.Win(1, f"{name} - Notepad", 1, "notepad.exe", False)

    desk_tools._wait_for_window = window
    winapi.windows = lambda: []  # Desk sees no real windows
    os.environ["TEAMLOOP_FAIL_ONCE"] = "write_file"  # Writer's first save fails, then it retries

    async def nothing(*_a, **_k):
        return None

    telegram.run = nothing          # never answer the real Telegram bot
    doctor.keep_checking = nothing  # no model checks
    trace.init = lambda *a, **k: False


def main() -> None:
    import uvicorn

    home = Path(tempfile.mkdtemp(prefix="teamloop-rehearsal-"))
    os.environ["TEAMLOOP_WORKSPACE"] = str(home / "workspace")
    install_fakes(home)
    router = ScriptRouter()
    crew = server.build_crew(home / "rehearsal.db", router=router)
    router.on_usage = server.usage_hook(crew.store, crew.bus)
    app = server.create_app(crew)
    print(f"Rehearsal TeamLoop: http://127.0.0.1:{PORT}  (files in {home}; workspace {config.workspace()})")
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
