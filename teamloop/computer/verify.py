"""Did that action do anything? Before/after looks at a program's windows, waiting for expected text, new dialogs.

A look is the program's window titles plus the names of its visible controls (UI Automation). `changes` turns two
looks into plain sentences; `wait_for` polls until some text shows (tree first, OCR as a last look).
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from teamloop.computer import ground


@dataclass(frozen=True)
class Look:
    windows: tuple[str, ...]
    names: frozenset[str]


def look(hwnd: int) -> Look:
    """Runs on the COM thread."""
    try:
        names = ground.visible_names(hwnd)
    except Exception:
        names = []
    windows = tuple(n[len("[window] "):] for n in names if n.startswith("[window] "))
    return Look(windows, frozenset(n for n in names if not n.startswith("[window] ")))


def changes(before: Look, after: Look) -> list[str]:
    out = []
    # the first entry is the window itself (it may just be retitled); the rest are its menus and dialogs
    main_b, main_a = before.windows[:1], after.windows[:1]
    new = [w for w in after.windows[1:] if w and w not in before.windows[1:]]
    gone = [w for w in before.windows[1:] if w and w not in after.windows[1:]]
    if main_a and main_b and main_a != main_b:
        out.append(f"the window is now titled \"{main_a[0]}\"")
    if new:
        out.append("a new window opened: " + ", ".join(f"\"{w}\"" for w in new))
    if gone:
        out.append("closed: " + ", ".join(f"\"{w}\"" for w in gone))
    added, removed = after.names - before.names, before.names - after.names
    if added or removed:
        sample = sorted(added, key=len)[:4]
        out.append(f"{len(added)} things appeared" + (f" (e.g. {', '.join(repr(s) for s in sample)})" if sample else "")
                   + (f", {len(removed)} went away" if removed else ""))
    return out


def shows(hwnd: int, text: str) -> bool:
    want = ground.norm(text)
    return any(want and want in ground.norm(n) for n in look(hwnd).names)


def wait_for(hwnd: int, text: str, seconds: float = 3.0) -> str | None:
    """'uia' or 'ocr' when the text shows within the time, else None. Runs on the COM thread."""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if shows(hwnd, text):
            return "uia"
        time.sleep(0.3)
    try:
        from teamloop.computer import winapi
        lines = ground.read_box(winapi.rect(hwnd))
        if ground.find_in_lines(lines, text, min_score=60):
            return "ocr"
    except Exception:
        pass
    return None
