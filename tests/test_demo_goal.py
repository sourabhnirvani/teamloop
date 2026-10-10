"""The demo goal end to end with scripted models: S plans, Scout researches, Writer writes the report on the
Desktop, Desk opens it behind an approval card, S sets the Monday routine and reports. Nothing real opens."""

import asyncio

from fakes import call, make_crew

from teamloop import kits
from teamloop.computer import tools as desk_tools
from teamloop.computer import winapi
from teamloop.tools import files, registry
from teamloop.tools.registry import ToolResult

GOAL = ("Research the top 3 free LLM APIs for students, write a short report on the Desktop, open it, "
        "and remind me about it every Monday.")
kits.load_all()

REPORT = "# Free LLM APIs for students\n1. Gemini\n2. Groq\n3. OpenRouter\n"


async def test_demo_goal_runs_through_the_crew(tmp_path, monkeypatch):
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    monkeypatch.setattr(files, "known_folder", lambda name: tmp_path / name)

    async def search(args, ctx):
        return ToolResult(True, "Found 3 results.", {"results": [{"title": "Gemini API", "url": "https://ai.google.dev"}]})

    monkeypatch.setattr(registry.REGISTRY["web_search"], "handler", search)
    opened = []
    monkeypatch.setattr(desk_tools.os, "startfile", lambda path: opened.append(path), raising=False)
    monkeypatch.setattr(winapi, "windows", lambda: [])

    async def window(name, before):
        return winapi.Win(1, f"{name} - Notepad", 1, "notepad.exe", False)

    monkeypatch.setattr(desk_tools, "_wait_for_window", window)

    crew = make_crew(tmp_path, [
        call("delegate", bot="scout", instruction="Find the top 3 free LLM APIs for students, with links."),
        call("web_search", query="free LLM APIs for students"),
        "Top 3: Gemini, Groq, OpenRouter.",
        call("delegate", bot="writer", instruction=f"Save Desktop/llm-report.md with this text:\n{REPORT}"),
        call("write_file", path="Desktop/llm-report.md", content=REPORT),
        "Saved Desktop/llm-report.md.",
        call("delegate", bot="desk", instruction="Open Desktop/llm-report.md."),
        call("open_file", path="Desktop/llm-report.md"),
        "Opened llm-report.md.",
        call("schedule_routine", task="Remind me about the LLM report on my Desktop", schedule="every monday at 9am"),
        "Done: Scout found Gemini, Groq and OpenRouter, Writer saved llm-report.md on your Desktop, Desk opened it, "
        "and I'll remind you every Monday at 9am.",
    ])
    asked = []

    async def answer_cards():
        with crew.bus.subscribe() as queue:
            while True:
                e = await queue.get()
                if e["type"] == "approval":
                    asked.append(e["title"])
                    crew.gate.answer(e["id"], True)

    answering = asyncio.create_task(answer_cards())
    await asyncio.sleep(0)
    await crew.post("team", GOAL)
    await asyncio.wait_for(crew.wait_idle("team"), 20)
    answering.cancel()

    assert (desktop / "llm-report.md").read_text(encoding="utf-8") == REPORT
    assert opened == [str((desktop / "llm-report.md").resolve())] and asked == ["Open a file"]
    routines = crew.store._all("SELECT * FROM routines")
    assert len(routines) == 1 and "monday" in routines[0]["schedule"].lower()
    said = [(m["sender"], m["kind"]) for m in crew.store.messages("team")]
    assert ("scout", "chat") in said and ("writer", "chat") in said and ("desk", "chat") in said
    assert crew.store.messages("team")[-1]["sender"] == "s"
    assert crew.store.messages("team")[-1]["text"].startswith("Done:")
    assert crew.router.script == []  # every scripted step was used, in order


async def test_open_file_refuses_programs_and_outside_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(files, "known_folder", lambda name: tmp_path / name)
    (tmp_path / "Desktop").mkdir()
    (tmp_path / "Desktop" / "setup.exe").write_bytes(b"MZ")

    class Ctx:
        chat_id = "t"

        async def approve(self, *a, **k):
            raise AssertionError("should not ask")

    out = await registry.REGISTRY["open_file"].handler({"path": "Desktop/setup.exe"}, Ctx())
    assert out.text.startswith("Refused: that file is a program")
    out = await registry.REGISTRY["open_file"].handler({"path": "C:/Windows/win.ini"}, Ctx())
    assert out.text.startswith("Refused:")
