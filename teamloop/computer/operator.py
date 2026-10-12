"""Operator safety: the crew never fights the person for the mouse and keyboard.

Before any screen action (everything that takes the desktop lease in tools.py), wait until the person has not
touched the mouse or keyboard for QUIET seconds, then carry on by itself. Input the crew itself sent doesn't count:
Windows reports injected input as input too, so each action marks when it ended and anything up to then is ours.
Stopping a chat (or Ctrl+Alt+Q, which stops every chat) cancels a wait in the middle.

It also keeps the last few screen steps (time, bot, tool, ok, text) for Settings > Operator safety.
"""

from __future__ import annotations

import asyncio
import ctypes
import sys
import time
from collections import deque
from typing import Callable

QUIET = 3.0          # seconds without the person's input before the crew may act
OURS_SLACK = 0.5     # injected input can register a little after the call that sent it returns
MAX_WAIT = 120.0     # someone working the whole time: give up rather than wait forever
KEEP = 20


def _idle_seconds() -> float:
    """Seconds since the last mouse or keyboard input anywhere on this PC (GetLastInputInfo)."""
    if sys.platform != "win32":
        return 1e9

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

    info = LASTINPUTINFO(ctypes.sizeof(LASTINPUTINFO), 0)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        return 1e9
    return ((ctypes.windll.kernel32.GetTickCount() - info.dwTime) & 0xFFFFFFFF) / 1000


class UserBusy(Exception):
    """The person kept using the computer for MAX_WAIT seconds."""


class Operator:
    def __init__(self, idle: Callable[[], float] = _idle_seconds, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], object] = asyncio.sleep):
        self.idle, self.clock, self.sleep = idle, clock, sleep
        self.ours_until = 0.0
        self.paused_since: float | None = None   # clock time the current wait began
        self.paused_wall: float | None = None    # same, as wall time for the API
        self.recent: deque[dict] = deque(maxlen=KEEP)

    def person_active(self) -> bool:
        """The person (not the crew) used the mouse or keyboard in the last QUIET seconds."""
        idle = self.idle()
        last_input = self.clock() - idle
        return idle < QUIET and last_input > self.ours_until

    async def wait_until_quiet(self) -> float:
        """Wait while the person is using the computer; returns how long it waited."""
        start = self.clock()
        while self.person_active():
            if self.paused_since is None:
                self.paused_since, self.paused_wall = start, time.time()
            if self.clock() - start > MAX_WAIT:
                self._resume()
                raise UserBusy("You kept using the computer for two minutes, so I didn't take over the mouse "
                               "and keyboard. Ask again when you're free.")
            try:
                await self.sleep(0.25)
            except BaseException:
                self._resume()
                raise
        self._resume()
        return self.clock() - start

    def _resume(self) -> None:
        self.paused_since = self.paused_wall = None

    def mark_ours(self) -> None:
        """Called when a screen action finishes: input up to now (plus a little) was the crew's."""
        self.ours_until = self.clock() + OURS_SLACK

    def record(self, bot: str, tool: str, ok: bool, text: str) -> None:
        self.recent.append({"ts": time.time(), "bot": bot, "tool": tool, "ok": ok, "text": text[:200]})

    def state(self) -> dict:
        return {"paused": self.paused_since is not None, "paused_since": self.paused_wall,
                "quiet_seconds": QUIET, "recent": list(reversed(self.recent))}


OPERATOR = Operator()
