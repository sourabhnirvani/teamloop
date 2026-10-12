"""Row 15 of the final pass: "close notepad without saving" left Notepad at its save prompt. With discard, close_app
asks its own card (never covered by an always-allow rule) and presses "Don't Save" by name, never Save or Enter."""

from types import SimpleNamespace

import pytest

from teamloop.computer import gate, tools
from teamloop.crew import bots


class Ctx(SimpleNamespace):
    async def approve(self, title, details, screenshot=None, key=None):
        self.cards.append((title, details))
        return self.answer


class FakeButton:
    def __init__(self, name, pressed):
        self.name, self.pressed = name, pressed

    def window_text(self):
        return self.name

    def invoke(self):
        self.pressed.append(self.name)


@pytest.fixture
def notepad(monkeypatch):
    """One Notepad window that a plain close leaves open (it asks to save) until a prompt button is pressed."""
    state = {"open": True, "pressed": [], "buttons": ["Save", "Don't Save", "Cancel"]}
    win = SimpleNamespace(hwnd=7, title="*notes.txt - Notepad", process="notepad.exe")
    monkeypatch.setattr(tools.winapi, "find", lambda name: [win])
    monkeypatch.setattr(tools.winapi, "close", lambda hwnd: None)
    monkeypatch.setattr(tools.winapi, "exists", lambda hwnd: state["open"])
    monkeypatch.setattr(tools, "_shot_url", lambda hwnd: None)

    async def no_wait(seconds):
        return None
    monkeypatch.setattr(tools.asyncio, "sleep", no_wait)

    def press(hwnd):
        for label in tools.DONT_SAVE:
            if label in state["buttons"]:
                state["pressed"].append(label)
                state["open"] = label in ("Save",)  # only Save would keep it (we must never press it)
                return True
        return False

    async def run(fn, *args):
        return press(*args) if fn is tools._press_dont_save else fn(*args)
    monkeypatch.setattr(tools.com, "run", run)
    return state


async def test_discard_asks_its_own_card_and_presses_dont_save(notepad):
    ctx = Ctx(answer=True, cards=[])
    result = await tools.close_app({"name": "notepad", "discard": True}, ctx)
    assert result.ok and result.text == "Closed 1 window of notepad without saving."
    assert ctx.cards[0][0] == "Close notepad WITHOUT saving" and "will be lost" in ctx.cards[0][1]
    assert notepad["pressed"] == ["Don't Save"]


def test_a_discard_card_never_offers_always_allow():
    assert not gate.can_always("Close notepad WITHOUT saving", "x")
    assert gate.can_always("Close notepad", "x")


async def test_no_dont_save_button_leaves_the_prompt_alone(notepad):
    notepad["buttons"] = ["Save", "Cancel"]
    result = await tools.close_app({"name": "notepad", "discard": True}, Ctx(answer=True, cards=[]))
    assert not result.ok and result.text == "The save prompt for *notes.txt - Notepad is still open; I didn't touch it."
    assert notepad["pressed"] == []


async def test_older_apps_use_no(notepad):
    notepad["buttons"] = ["Yes", "No", "Cancel"]
    result = await tools.close_app({"name": "notepad", "discard": True}, Ctx(answer=True, cards=[]))
    assert result.ok and notepad["pressed"] == ["No"]


async def test_without_discard_nothing_is_pressed(notepad):
    result = await tools.close_app({"name": "notepad"}, Ctx(answer=True, cards=[]))
    assert not result.ok and "I left it for the person" in result.text and notepad["pressed"] == []


def test_the_rules_say_an_earlier_no_is_not_a_failure():
    assert "You said no earlier, so I left it." in bots.RULES and "don't start with Failed:" in bots.RULES
