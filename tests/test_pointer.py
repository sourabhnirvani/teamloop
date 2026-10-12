"""N, advanced computer use: coordinate maths, finding by meaning, risk on raw points, Stop mid-retry, ringed cards."""

import asyncio
from types import SimpleNamespace

import pytest
from PIL import Image

from teamloop.computer import ground, mouse, pointer, risk, tools, verify


def test_absolute_coordinates_cover_every_monitor_including_one_left_of_the_primary():
    s = mouse.Screen(left=-1920, top=0, width=3840, height=1080)   # second monitor to the left
    assert s.absolute(-1920, 0) == (0, 0)
    assert s.absolute(1919, 1079) == (65535, 65535)
    x, _ = s.absolute(0, 0)                                         # the primary's top-left: just past half way
    assert 32760 <= x <= 32780
    assert s.contains(-5, 10) and not s.contains(1920, 10) and not s.contains(-1921, 10)


def test_drag_path_ends_on_the_target():
    path = mouse.drag_path(0, 0, 100, 50, steps=10)
    assert len(path) == 10 and path[-1] == (100, 50) and path[0] == (10, 5)


def test_targets_parse_into_words_and_a_role():
    assert ground.parse_target("the Save button") == ("save", "Button")
    assert ground.parse_target("Seven") == ("seven", None)
    assert ground.parse_target("search box") == ("search", "Edit")
    assert ground.parse_target("&File") == ("file", None)


def test_score_order_exact_beats_starts_with_beats_contains_beats_fuzzy():
    want, role = ground.parse_target("Save")
    exact = ground.score("Save", "", "Button", want, role)
    starts = ground.score("Save As...", "", "Button", want, role)
    contains = ground.score("Quick Save", "", "Button", want, role)
    fuzzy = ground.score("Sav", "", "Button", want, role)
    unrelated = ground.score("Open", "", "Button", want, role)
    assert exact > starts > contains > fuzzy >= 0 and unrelated == 0
    # the right role wins over the same words on a label
    assert ground.score("Save", "", "Button", "save", "Button") > ground.score("Save", "", "Text", "save", "Button")
    # and "Documents" beats "documents" when the person typed it that way
    assert ground.score("Documents", "", "TreeItem", "documents", None, "Documents") > \
        ground.score("documents", "", "TreeItem", "documents", None, "Documents")


def test_ocr_words_are_matched_as_a_run():
    lines = [{"text": "Start game now", "words": [{"t": "Start", "x": 10, "y": 5, "w": 40, "h": 12},
                                                  {"t": "game", "x": 55, "y": 5, "w": 35, "h": 12},
                                                  {"t": "now", "x": 95, "y": 5, "w": 25, "h": 12}]}]
    hit = ground.find_in_lines(lines, "Start game")
    assert hit.how == "ocr" and hit.box == (10, 5, 90, 17) and (hit.x, hit.y) == (50, 11)


def test_raw_point_risk_reads_the_label_around_it():
    # an unnamed icon whose printed label says Delete gets a card in any app, not only mail or shops
    assert pointer.point_risk("", "Photos [Photos.exe]", "click", nearby="Delete") == risk.ASK
    assert pointer.point_risk("", "Paint [mspaint.exe]", "click", nearby="Brushes") == risk.SAFE
    assert pointer.point_risk("", "Inbox - Outlook [OUTLOOK.EXE]", "click") == risk.ASK      # unnamed, in mail
    assert pointer.point_risk("Send", "Notepad [notepad.exe]", "click") == risk.ASK
    assert pointer.point_risk("", "Documents [explorer.exe]", "drag") == risk.ASK             # moves files


def test_changes_tell_a_retitle_from_a_new_dialog():
    before = verify.Look(("File Explorer",), frozenset({"a"}))
    retitled = verify.Look(("Documents",), frozenset({"a", "b"}))
    dialog = verify.Look(("Untitled - Notepad", "Save As"), frozenset({"a"}))
    assert verify.changes(before, retitled)[0] == 'the window is now titled "Documents"'
    assert not any("new window" in c for c in verify.changes(before, retitled))
    assert verify.changes(verify.Look(("Untitled - Notepad",), frozenset({"a"})), dialog) == \
        ['a new window opened: "Save As"']


def test_the_card_shows_a_red_ring_on_the_target(tmp_path, monkeypatch):
    shot = tmp_path / "card.png"
    Image.new("RGB", (400, 300), "white").save(shot)
    monkeypatch.setattr(pointer.uia, "screenshot", lambda hwnd: shot)
    monkeypatch.setattr(pointer.winapi, "rect", lambda hwnd: (100, 50, 500, 350))   # 400 px wide: scale 1
    url = pointer.ringed_shot(123, [(300, 200)])                                    # (200, 150) in the picture
    assert url == "/api/shots/card.png"
    image = Image.open(shot)
    r = 22
    assert image.getpixel((200 + r, 150))[:3] == (230, 30, 30) or image.getpixel((200 + r - 1, 150))[:3] == (230, 30, 30)
    assert image.getpixel((200, 150))[:3] == (230, 30, 30)            # the dot in the middle
    assert image.getpixel((10, 10))[:3] == (255, 255, 255)           # the rest is untouched


async def test_stop_during_a_click_on_retry_stops_at_once(monkeypatch):
    acted, second = [], asyncio.Event()
    hit = ground.Hit("Equals", 10, 10, (0, 0, 20, 20), "uia", "Button", 115)

    def fake_act(h, action, hwnd):
        acted.append(action)
        return "invoke"

    async def run(fn, *args):
        if fn is fake_act and len(acted) == 1:   # the retry's click: the app hangs while it happens
            fn(*args)
            second.set()
            await asyncio.sleep(30)
        return fn(*args)

    win = SimpleNamespace(hwnd=1, title="Calculator", process="CalculatorApp.exe")

    async def fake_window(name):
        return win
    monkeypatch.setattr(pointer, "_window", fake_window)
    monkeypatch.setattr(pointer.com, "run", run)
    monkeypatch.setattr(pointer, "_find", lambda hwnd, target: hit)
    monkeypatch.setattr(pointer, "_act", fake_act)
    monkeypatch.setattr(pointer.verify, "look", lambda hwnd: verify.Look(("Calculator",), frozenset()))
    monkeypatch.setattr(pointer.verify, "wait_for", lambda hwnd, text, seconds: None)  # never shows: it retries

    task = asyncio.create_task(pointer.click_on({"window": "Calculator", "target": "Equals", "expect": "42"},
                                                SimpleNamespace(approve=None)))
    await asyncio.wait_for(second.wait(), 5)
    task.cancel()                         # what Stop / Ctrl+Alt+Q does to the chat's task
    with pytest.raises(asyncio.CancelledError):
        await task
    assert acted == ["click", "click"]    # the first try and the retry, nothing after the stop
    async with tools.lease(timeout=1):    # and the desktop lease was let go
        pass
