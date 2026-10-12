"""N baseline: what the existing computer kit sees in real apps before any change (read-only, nothing is clicked).

    .venv\\Scripts\\python.exe evidence\\runs\\computer-use-baseline-yang.py
"""

import asyncio
import ctypes
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from teamloop.computer import uia, winapi  # noqa: E402


def wait_window(words, seconds=12):
    end = time.time() + seconds
    while time.time() < end:
        for w in winapi.windows():
            if any(word.lower() in w.title.lower() for word in words):
                return w
        time.sleep(0.4)
    return None


async def look(label, launch, words, wanted):
    subprocess.Popen(launch, shell=True)
    win = wait_window(words)
    if not win:
        print(f"{label}: window never appeared")
        return
    time.sleep(1.5)
    t = time.time()
    items = await uia.snapshot(win.hwnd)
    took = time.time() - t
    names = [f"{i.get('type')}:{i.get('name')}" for i in items]
    found = {w: any(w.lower() == (i.get("name") or "").lower() for i in items) for w in wanted}
    print(f"\n{label}: \"{win.title}\" rect={winapi.rect(win.hwnd)} -> {len(items)} controls in {took:.1f}s")
    print("  wanted by name:", found)
    print("  first 25:", names[:25])
    winapi.close(win.hwnd)


async def main():
    aware = ctypes.windll.user32.GetAwarenessFromDpiAwarenessContext(ctypes.windll.user32.GetThreadDpiAwarenessContext())
    print("this process DPI awareness (0 unaware, 1 system, 2 per-monitor):", aware)
    print("GetSystemMetrics screen:", ctypes.windll.user32.GetSystemMetrics(0), "x", ctypes.windll.user32.GetSystemMetrics(1))
    await look("Calculator", "start calc", ["Calculator"], ["Seven", "Plus", "Equals", "Display is 0"])
    await look("Paint", "start mspaint", ["Paint"], ["File", "Pencil", "Brushes"])
    await look("Notepad", "start notepad", ["Notepad"], ["File", "Edit", "Text editor"])

asyncio.run(main())
