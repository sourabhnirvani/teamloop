"""Fixes from jrkrishh's UI audit (evidence/runs/ui-audit-yang.md) that live on the server side."""

import asyncio

from fakes import call, make_crew

from teamloop.crew.team import _task_title
from teamloop.tools import registry
from teamloop.tools.files import roots, where
from teamloop.tools.registry import ToolResult


def test_board_titles_read_like_to_dos():  # row 8
    assert _task_title("Open Desktop/llm-report-1.md.") == "Open Desktop/llm-report-1.md"
    assert _task_title("Save Desktop/llm-report-1.md with:\n# Report") == "Save Desktop/llm-report-1.md"
    assert _task_title(r"open C:\Users\me\AppData\Local\Temp\x\Desktop\report.md now.") == "Open …\\Desktop\\report.md now"


def test_cards_name_folders_the_way_the_person_knows_them():  # row 3
    folders = roots()
    assert where(folders["desktop"] / "report.md") == "on your Desktop"
    assert where(folders["documents"] / "Work" / "q3.md") == "in Documents\\Work"


async def test_a_step_you_said_no_to_is_finished_not_blocked(tmp_path, monkeypatch):  # row 6
    async def risky(args, ctx):
        if not await ctx.approve("Run a command", "Remove-Item x.txt"):
            return ToolResult(False, "The person said no, so I didn't run it.")
        return ToolResult(True, "Deleted.")

    monkeypatch.setitem(registry.REGISTRY, "risky", registry.Tool("risky", "", {"type": "object"}, "memory", risky))
    crew = make_crew(tmp_path, [call("delegate", bot="desk", instruction="Delete x.txt."), call("risky"),
                                "You said no, so I left it.", "Okay, left it."])

    async def say_no():
        with crew.bus.subscribe() as queue:
            while True:
                e = await queue.get()
                if e["type"] == "approval":
                    crew.gate.answer(e["id"], False)

    answering = asyncio.create_task(say_no())
    await crew.post("team", "delete x.txt")
    await crew.wait_idle("team")
    answering.cancel()
    [task] = crew.store.tasks()
    assert task["status"] == "done" and task["note"].startswith("Skipped: you said no.")
    assert task["title"] == "Delete x.txt"


def test_a_routine_reads_without_its_internal_id(tmp_path):  # row 2
    from teamloop.crew import routines

    crew = make_crew(tmp_path, [])
    ctx = type("Ctx", (), {"crew": crew, "chat_id": "team", "bot_id": "s"})()
    out = asyncio.run(routines.schedule_routine({"task": "Remind me about the report", "schedule": "every monday at 9am"}, ctx))
    assert out.ok and out.text.startswith('Routine set: "Remind me about the report"'), out.text
    assert out.data.get("id") or out.data.get("routine")  # the id is still there for the model to use


def test_folders_are_where_windows_says_not_a_guess(monkeypatch):  # found by jrkrishh during N's live tests
    import subprocess
    import sys

    from teamloop.tools import files

    if sys.platform == "win32":
        real = subprocess.run(["powershell", "-NoProfile", "-Command", "[Environment]::GetFolderPath('MyDocuments')"],
                              capture_output=True, text=True, timeout=60).stdout.strip()
        assert str(files.known_folder("Documents")) == real  # not OneDrive\Documents just because it exists
    monkeypatch.setattr(files, "_windows_folder", lambda name: None)  # off Windows, or if the call fails: the old guess
    assert files.known_folder("Documents").name == "Documents"
