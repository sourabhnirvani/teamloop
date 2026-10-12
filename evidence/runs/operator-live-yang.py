"""Build B live check: the real GetLastInputInfo, a simulated person, the real desktop lease.

    .venv\\Scripts\\python.exe evidence\\runs\\operator-live-yang.py

A separate process plays "the person": it nudges the real mouse 1 px back and forth for 4 seconds (to Windows
that's user input; the operator didn't send it). Meanwhile a screen action takes the desktop lease. It must wait
while the mouse moves, then go ahead by itself QUIET seconds after the mouse stops. Prints a timeline.
"""

import asyncio
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from teamloop.computer import operator, tools  # noqa: E402

PERSON = r"""
import ctypes, time
u = ctypes.windll.user32
end = time.time() + 4
while time.time() < end:
    u.mouse_event(0x0001, 1, 0, 0, 0); time.sleep(0.1)   # MOUSEEVENTF_MOVE, 1 px right
    u.mouse_event(0x0001, -1, 0, 0, 0); time.sleep(0.1)  # and back
"""


async def main():
    t0 = time.monotonic()
    log = lambda what: print(f"{time.monotonic() - t0:5.1f}s  {what}")  # noqa: E731
    person = subprocess.Popen([sys.executable, "-c", PERSON])
    log("person starts moving the mouse (for 4 s)")
    await asyncio.sleep(0.5)

    async def watch():
        last = None
        while True:
            paused = operator.OPERATOR.state()["paused"]
            if paused != last:
                log(f"GET /api/operator would say paused={paused}")
                last = paused
            await asyncio.sleep(0.1)
    watcher = asyncio.create_task(watch())
    log("a screen action asks for the desktop lease")
    async with tools.lease():
        log("lease granted: the screen action runs now")
    person.wait()
    watcher.cancel()
    waited = time.monotonic() - t0
    ok = waited >= 4 + operator.QUIET - 0.6
    print(f"\n{'PASS' if ok else 'FAIL'}: the action waited for the person and went ahead {operator.QUIET:.0f} s after "
          f"the mouse stopped (total {waited:.1f} s)")

asyncio.run(main())
