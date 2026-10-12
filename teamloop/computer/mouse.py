"""Real mouse input at exact physical pixels, on any monitor.

The package import (computer/__init__.py) makes the process per-monitor DPI aware (v2), so window rects, screenshots and the cursor all speak
physical pixels; without it this laptop (125%) reports a 1536x864 screen while window rects come back physical,
and a click lands 25% off. Input goes through SendInput with absolute coordinates over the whole virtual desktop
(every monitor, negative coordinates included), which apps treat as a real mouse.
"""

from __future__ import annotations

import ctypes
import time
from ctypes import wintypes
from dataclasses import dataclass

MOVE, LEFTDOWN, LEFTUP, RIGHTDOWN, RIGHTUP = 0x0001, 0x0002, 0x0004, 0x0008, 0x0010
WHEEL, VIRTUALDESK, ABSOLUTE = 0x0800, 0x4000, 0x8000
WHEEL_DELTA = 120
INPUT_MOUSE = 0


@dataclass(frozen=True)
class Screen:
    """The virtual desktop: every monitor together, in physical pixels."""
    left: int
    top: int
    width: int
    height: int

    def contains(self, x: int, y: int) -> bool:
        return self.left <= x < self.left + self.width and self.top <= y < self.top + self.height

    def absolute(self, x: int, y: int) -> tuple[int, int]:
        """SendInput's 0..65535 scale for a physical point on this virtual desktop."""
        nx = round((x - self.left) * 65535 / max(self.width - 1, 1))
        ny = round((y - self.top) * 65535 / max(self.height - 1, 1))
        return max(0, min(65535, nx)), max(0, min(65535, ny))


def screen() -> Screen:
    m = ctypes.windll.user32.GetSystemMetrics
    return Screen(m(76), m(77), m(78), m(79))  # SM_X/YVIRTUALSCREEN, SM_CX/CYVIRTUALSCREEN


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class _INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("mi", _MOUSEINPUT), ("pad", ctypes.c_byte * 32)]  # pad: the union's real size (keyboard/hw)
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]


def _send(flags: int, x: int | None = None, y: int | None = None, data: int = 0) -> None:
    dx = dy = 0
    if x is not None and y is not None:
        dx, dy = screen().absolute(x, y)
        flags |= ABSOLUTE | VIRTUALDESK | MOVE
    item = _INPUT(type=INPUT_MOUSE)
    item.mi = _MOUSEINPUT(dx, dy, ctypes.c_uint32(data).value, flags, 0, 0)
    if ctypes.windll.user32.SendInput(1, ctypes.byref(item), ctypes.sizeof(_INPUT)) != 1:
        raise OSError("Windows refused the mouse input (another program may be blocking it).")


def check_point(x: int, y: int) -> None:
    if not screen().contains(x, y):
        s = screen()
        raise ValueError(f"({x}, {y}) is off the screen; the screen spans x {s.left}..{s.left + s.width - 1}, "
                         f"y {s.top}..{s.top + s.height - 1}.")


def cursor() -> tuple[int, int]:
    p = wintypes.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(p))
    return p.x, p.y


def move(x: int, y: int) -> None:
    check_point(x, y)
    _send(0, x, y)
    time.sleep(0.05)


def click(x: int, y: int, button: str = "left", count: int = 1) -> None:
    move(x, y)
    down, up = (RIGHTDOWN, RIGHTUP) if button == "right" else (LEFTDOWN, LEFTUP)
    for i in range(count):
        _send(down)
        _send(up)
        if i + 1 < count:
            time.sleep(0.06)  # well inside the double-click time (500 ms by default)
    time.sleep(0.15)


def scroll(x: int, y: int, notches: int) -> None:
    """Positive scrolls up (away from you), negative down."""
    move(x, y)
    _send(WHEEL, data=int(notches) * WHEEL_DELTA)
    time.sleep(0.2)


def drag_path(x1: int, y1: int, x2: int, y2: int, steps: int = 20) -> list[tuple[int, int]]:
    return [(round(x1 + (x2 - x1) * i / steps), round(y1 + (y2 - y1) * i / steps)) for i in range(1, steps + 1)]


def drag(x1: int, y1: int, x2: int, y2: int) -> None:
    check_point(x2, y2)
    move(x1, y1)
    _send(LEFTDOWN)
    time.sleep(0.08)
    try:
        for x, y in drag_path(x1, y1, x2, y2):  # apps draw and track drags only when the mouse really travels
            _send(0, x, y)
            time.sleep(0.015)
    finally:
        _send(LEFTUP)
    time.sleep(0.15)


def element_at(x: int, y: int) -> dict:
    """What UI Automation says is under a physical point: name, type and its window. Run it on the COM thread."""
    from pywinauto import Desktop

    try:
        el = Desktop(backend="uia").from_point(x, y)
        info = el.element_info
        return {"name": (info.name or "").strip()[:80], "type": info.control_type or "",
                "window": (el.top_level_parent().window_text() or "")[:80]}
    except Exception:
        return {"name": "", "type": "", "window": ""}
