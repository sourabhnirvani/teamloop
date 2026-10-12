"""The lead does every step the person asked for, and only reports what teammates really returned.

Yang's live debug pass (rows 22-23, Groq gpt-oss-120b): S ran research, the report and the Monday
routine but dropped "open it" ("the file will be opened automatically"). And early on S answered
"Scout says: ..." without ever asking Scout.
"""

import asyncio

from fakes import call, make_crew

from teamloop import kits
from teamloop.computer import tools as desk_tools
from teamloop.computer import winapi
from teamloop.crew import coverage
from teamloop.tools import files, registry
from teamloop.tools.registry import ToolResult

kits.load_all()
GOAL = ("Research the top 3 free LLM APIs for students, write a short report on the Desktop, open it, "
        "and remind me about it every Monday.")
REPORT = "# Free LLM APIs for students\n1. Gemini\n2. Groq\n3. OpenRouter\n"


def desk_and_search(tmp_path, monkeypatch):
    (tmp_path / "Desktop").mkdir()
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
    return opened


async def run(crew, chat, text):
    asked = []

    async def approve_all():
        with crew.bus.subscribe() as queue:
            while True:
                e = await queue.get()
                if e["type"] == "approval":
                    asked.append(e["title"])
                    crew.gate.answer(e["id"], True)

    answering = asyncio.create_task(approve_all())
    await asyncio.sleep(0)
    await crew.post(chat, text)
    await asyncio.wait_for(crew.wait_idle(chat), 20)
    answering.cancel()
    return asked


def nudges(crew):
    return [m["content"] for c in crew.router.calls for m in c["messages"]
            if m["role"] == "user" and "Never say a teammate did something" in str(m["content"])]


async def test_lead_is_sent_back_when_open_it_was_skipped(tmp_path, monkeypatch):
    opened = desk_and_search(tmp_path, monkeypatch)
    crew = make_crew(tmp_path, [
        call("delegate", bot="scout", instruction="Find the top 3 free LLM APIs for students, with links."),
        call("web_search", query="free LLM APIs for students"),
        "Top 3: Gemini, Groq, OpenRouter.",
        call("delegate", bot="writer", instruction=f"Save Desktop/llm-report.md with this text:\n{REPORT}"),
        call("write_file", path="Desktop/llm-report.md", content=REPORT),
        "Saved Desktop/llm-report.md.",
        call("schedule_routine", task="Open the LLM report on my Desktop", schedule="every monday at 9am"),
        "Done: the report is saved and every Monday the file will be opened automatically.",  # "open it" dropped
        # sent back once: the missing step now happens
        call("delegate", bot="desk", instruction="Open Desktop/llm-report.md."),
        call("open_file", path="Desktop/llm-report.md"),
        "Opened llm-report.md.",
        "Done: Scout found the top 3, Writer saved llm-report.md, Desk opened it, and I'll remind you every Monday.",
    ])
    asked = await run(crew, "team", GOAL)
    assert [n.startswith("Not done yet: open it.") for n in nudges(crew)][:1] == [True]
    assert opened == [str((tmp_path / "Desktop" / "llm-report.md").resolve())] and asked == ["Open a file"]
    assert crew.store.messages("team")[-1]["text"].startswith("Done: Scout found the top 3")
    assert crew.router.script == []


async def test_lead_claiming_a_teammate_without_delegate_is_corrected(tmp_path, monkeypatch):
    desk_and_search(tmp_path, monkeypatch)
    crew = make_crew(tmp_path, [
        "Scout says: neatlogs is a Windows utility.",  # invented: Scout never ran
        call("delegate", bot="scout", instruction="Search the web for what neatlogs is; one sentence with the link."),
        call("web_search", query="neatlogs"),
        "neatlogs traces AI agents (https://ai.google.dev).",
        "Scout found: neatlogs traces AI agents (https://ai.google.dev).",
    ])
    await run(crew, "team", "Find out what neatlogs is, then tell me in one sentence.")
    assert "didn't work on this job" in nudges(crew)[0]
    said = [(m["sender"], m["kind"]) for m in crew.store.messages("team")]
    assert ("s", "handoff") in said and ("scout", "chat") in said
    assert crew.store.messages("team")[-1]["text"].startswith("Scout found:")
    assert not any("Windows utility" in m["text"] for m in crew.store.messages("team"))  # never posted


async def test_no_nudge_when_everything_was_done(tmp_path, monkeypatch):
    desk_and_search(tmp_path, monkeypatch)
    monkeypatch.setattr(winapi, "windows", lambda: [winapi.Win(1, "Untitled - Notepad", 1, "notepad.exe", False)])
    crew = make_crew(tmp_path, [
        call("delegate", bot="desk", instruction="List the open windows."),
        call("list_windows"),
        "Notepad is open.",
        "Desk says only Notepad is open.",
    ])
    await run(crew, "team", "Which apps are open right now?")
    assert crew.router.calls[0]["purpose"] == "turn:s"  # S handled it (no direct address)
    assert nudges(crew) == [] and len(crew.router.calls) == 4


async def test_nudge_happens_once(tmp_path, monkeypatch):
    desk_and_search(tmp_path, monkeypatch)
    crew = make_crew(tmp_path, [
        call("delegate", bot="writer", instruction="Save Desktop/x.md with: hi"),
        call("write_file", path="Desktop/x.md", content="hi"),
        "Saved Desktop/x.md.",
        "Saved it.",            # skipped "open it": sent back once
        "Saved it, really.",    # still skipped: no second nudge, this is the reply
    ])
    await run(crew, "team", "Write a note called x on the Desktop and open it")
    assert len(nudges(crew)) == 1
    final = crew.store.messages("team")[-1]["text"]
    assert final.startswith("Saved it, really.")   # no second nudge; the runner adds the honest line instead
    assert 'Not done: open it (no tool ran for it). Say "try again"' in final


def test_open_as_a_verb_only():
    assert coverage.missing("open the report", set()) == ["open it"]
    for text in ("what apps are open", "is chrome still open?", "find open-source models", "list open windows"):
        assert "open it" not in coverage.missing(text, set()), text
