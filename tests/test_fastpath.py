from types import SimpleNamespace

import pytest
from fakes import make_crew

from teamloop import kits
from teamloop.computer import system
from teamloop.crew import commands, fastpath, routines
from teamloop.tools import registry
from teamloop.tools.registry import ToolResult

kits.load_all()


@pytest.mark.parametrize("text, hit", [
    ("open calculator", ("open_app", {"name": "calculator"})),
    ("Please open Notepad app.", ("open_app", {"name": "Notepad"})),
    ("open youtube.com", ("browser_open", {"url": "youtube.com"})),
    ("calculator kholo", ("open_app", {"name": "calculator"})),
    ("close spotify", ("close_app", {"name": "spotify"})),
    ("Volume 30%", ("set_volume", {"level": 30})),
    ("set the volume to 45", ("set_volume", {"level": 45})),
    ("volume up", ("set_volume", {"change": 10})),
    ("mute", ("set_volume", {"mute": True})),
    ("brightness down", ("set_brightness", {"change": -10})),
    ("set brightness to 70 percent", ("set_brightness", {"level": 70})),
    ("wifi off", ("set_wifi", {"on": False})),
    ("turn on the wi-fi", ("set_wifi", {"on": True})),
    ("what's my battery?", ("system_status", {})),
    ("brightness?", ("system_status", {})),
    ("is wifi on?", ("system_status", {})),
    ("volume?", ("system_status", {})),
    ("what apps are open", ("list_windows", {})),
    ("take a screenshot", ("screenshot", {})),
    ("lock the laptop", ("power", {"action": "lock"})),
    ("search free llm apis for students", ("web_search", {"query": "free llm apis for students"})),
    ("hey S, can you open calculator please", ("open_app", {"name": "calculator"})),
])
def test_plain_commands_match(text, hit):
    assert fastpath.match(text) == hit


@pytest.mark.parametrize("text", [
    "open calculator and set volume to 30",
    "research the top 3 free LLM APIs for students, write a short report",
    "@desk open calculator",
    "how are you",
    "open the report I wrote yesterday on the desktop",
    "search the web then summarize it",
])
def test_anything_else_goes_to_the_bots(text):
    assert fastpath.match(text) is None


@pytest.fixture
def fake_volume(monkeypatch):
    calls = []

    async def handler(args, ctx):
        calls.append((args, ctx.bot_id))
        return ToolResult(True, f"Volume is now {args.get('level')}%.")

    monkeypatch.setattr(registry.REGISTRY["set_volume"], "handler", handler)
    return calls


async def test_fast_path_runs_one_tool_with_no_model_call(tmp_path, fake_volume):
    crew = make_crew(tmp_path, [])
    await crew.post("team", "volume 30")
    await crew.wait_idle("team")
    last = crew.store.messages("team")[-1]
    assert (last["sender"], last["text"], last["kind"]) == ("desk", "Volume is now 30%.", "fast")
    assert fake_volume == [({"level": 30}, "desk")] and crew.router.calls == []


async def test_fast_path_skips_chats_without_the_right_bot(tmp_path, fake_volume):
    crew = make_crew(tmp_path, ["Not mine: Desk does volume.", "Volume is 30%."])
    await crew.post("dm-writer", "volume 30")
    await crew.wait_idle("dm-writer")
    # no fast path in Writer's chat: Writer answers, says it's Desk's job, and Desk takes it from there
    assert fake_volume == [] and [c["purpose"] for c in crew.router.calls] == ["turn:writer", "turn:desk"]


async def test_a_plain_failure_goes_back_to_the_bots(tmp_path, monkeypatch):
    async def no_such_app(args, ctx):
        return ToolResult(False, "There is no app called 'everything' in the Start menu.")

    monkeypatch.setattr(registry.REGISTRY["open_app"], "handler", no_such_app)
    crew = make_crew(tmp_path, ["Which app do you mean?"])
    await crew.post("dm-desk", "open everything")
    await crew.wait_idle("dm-desk")
    assert crew.store.messages("dm-desk")[-1]["text"] == "Which app do you mean?"
    assert len(crew.router.calls) == 1


async def test_fast_path_can_be_switched_off(tmp_path, fake_volume):
    crew = make_crew(tmp_path, ["ok"])
    crew.store.set_setting("fast_path", False)
    await crew.post("team", "volume 30")
    await crew.wait_idle("team")
    assert fake_volume == [] and len(crew.router.calls) == 1


async def test_sleep_and_wake_up(tmp_path, fake_volume):
    crew = make_crew(tmp_path, [])
    await crew.post("dm-s", "S its time to sleep")
    await crew.wait_idle("dm-s")
    assert crew.store.messages("dm-s")[-1]["text"].startswith("Going to sleep")

    await crew.post("team", "volume 30")
    await crew.wait_idle("team")
    assert crew.store.messages("team")[-1]["text"] == commands.ASLEEP_NOTE and fake_volume == []
    routines.add(crew, "dm-s", "check mail", "in 1 minute")
    assert await routines.run_due(crew, now=10**11) == 0

    await crew.post("dm-s", "S wake up")
    await crew.wait_idle("dm-s")
    assert crew.store.messages("dm-s")[-1]["text"] == "Awake and ready."
    await crew.post("team", "volume 30")
    await crew.wait_idle("team")
    assert fake_volume and crew.router.calls == []


class Ctx(SimpleNamespace):
    async def approve(self, title, details, screenshot=None, key=None):
        self.asked = title
        return self.answer


async def test_wifi_off_asks_first(monkeypatch):
    switched = []
    monkeypatch.setattr(system, "set_wifi", lambda on: switched.append(on) or ("On" if on else "Off"))
    tool = registry.REGISTRY["set_wifi"].handler

    denied = await tool({"on": False}, Ctx(answer=False))
    assert not denied.ok and switched == []
    off = await tool({"on": False}, Ctx(answer=True))
    assert off.ok and off.text == "Wi-Fi is now off." and switched == [False]
    on = await tool({"on": True}, Ctx(answer=False))  # turning it on never asks
    assert on.ok and switched == [False, True]


async def test_window_list_names_the_windows(tmp_path, monkeypatch):
    async def windows(args, ctx):
        return ToolResult(True, "2 windows are open.", {"windows": ["Calculator [ApplicationFrameHost.exe]",
                                                                    "notes.txt - Notepad [notepad.exe]"]})

    monkeypatch.setattr(registry.REGISTRY["list_windows"], "handler", windows)
    crew = make_crew(tmp_path, [])
    await crew.post("dm-desk", "what apps are open")
    await crew.wait_idle("dm-desk")
    text = crew.store.messages("dm-desk")[-1]["text"]
    assert text == "2 windows are open.\n- Calculator [ApplicationFrameHost.exe]\n- notes.txt - Notepad [notepad.exe]"
