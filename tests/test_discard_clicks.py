"""Live repro (final pass): a model replayed "close notepad without saving" through click_on (the title-bar Close,
then "Don't Save") and skipped close_app's discard card. Every click path now asks first for those."""

from types import SimpleNamespace

import pytest

from teamloop.computer import ground, pointer, risk


@pytest.mark.parametrize("name", ["Close", "Close Notepad", "Don't Save", "Don’t save", "Do not save",
                                  "Discard changes", "Exit", "Quit"])
def test_discarding_controls_need_a_card(name):
    assert risk.click_risk(name, "Notepad [notepad.exe]") == risk.ASK


@pytest.mark.parametrize("name", ["Seven", "File", "Save As...", "Display", "Closet organiser"])
def test_ordinary_controls_stay_safe(name):
    assert risk.click_risk(name, "Notepad [notepad.exe]") == risk.SAFE


async def test_click_on_dont_save_raises_a_card(monkeypatch):
    hit = ground.Hit("Don't Save", 10, 10, (0, 0, 20, 20), "uia", "Button", 115)
    win = SimpleNamespace(hwnd=1, title="Notepad", process="notepad.exe")

    async def fake_window(name):
        return win

    async def run(fn, *args):
        return fn(*args)
    monkeypatch.setattr(pointer, "_window", fake_window)
    monkeypatch.setattr(pointer.com, "run", run)
    monkeypatch.setattr(pointer, "_find", lambda hwnd, target: hit)
    monkeypatch.setattr(pointer, "ringed_shot", lambda hwnd, points: None)
    asked = []

    async def approve(title, details, screenshot=None, key=None):
        asked.append(title)
        return False
    result = await pointer.click_on({"window": "Notepad", "target": "Don't Save"}, SimpleNamespace(approve=approve))
    assert asked == ['Click "Don\'t Save"'] and not result.ok and "said no" in result.text


async def test_ui_act_click_on_dont_save_raises_a_card(monkeypatch):
    from teamloop.computer import tools
    win = SimpleNamespace(hwnd=1, title="Notepad", process="notepad.exe")

    async def fake_window(name):
        return win

    async def describe(hwnd, index):
        return {"name": "Don't Save", "type": "Button", "password": False}
    monkeypatch.setattr(tools, "_window", fake_window)
    monkeypatch.setattr(tools.uia, "describe", describe)
    monkeypatch.setattr(tools, "_shot_url", lambda hwnd: None)
    asked = []

    async def approve(title, details, screenshot=None, key=None):
        asked.append(title)
        return False
    result = await tools.ui_act({"window": "Notepad", "index": 3, "action": "click"}, SimpleNamespace(approve=approve))
    assert asked == ['Click "Don\'t Save"'] and not result.ok


def test_the_mouse_path_judges_the_label_too():
    assert pointer.point_risk("", "Notepad [notepad.exe]", "click", nearby="Don’t Save") == risk.ASK
    assert pointer.point_risk("Close", "Notepad [notepad.exe]", "click") == risk.ASK


def test_no_always_allow_for_clicks_or_mouse_cards():
    from teamloop.computer import gate
    assert not gate.can_always('Click "Don\'t Save"', "x")
    assert not gate.can_always("Mouse: click at (10, 10) on \"Close\"", "x")
