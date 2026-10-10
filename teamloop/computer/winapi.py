"""Small ctypes layer over user32/dwmapi: list, find, focus, resize and close top-level windows."""

from __future__ import annotations

import ctypes
import sys
import time
from ctypes import wintypes
from dataclasses import dataclass

if sys.platform != "win32":  # pragma: no cover - the computer kit is Windows-only
    raise ModuleNotFoundError("teamloop.computer.winapi needs Windows", name="teamloop.computer.winapi")

user32 = ctypes.WinDLL("user32", use_last_error=True)
dwmapi = ctypes.WinDLL("dwmapi")
kernel32 = ctypes.WinDLL("kernel32")

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsIconic.argtypes = [wintypes.HWND]
user32.IsZoomed.argtypes = [wintypes.HWND]
user32.IsWindow.argtypes = [wintypes.HWND]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetForegroundWindow.restype = wintypes.HWND
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.BringWindowToTop.argtypes = [wintypes.HWND]
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
dwmapi.DwmGetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]

SW_MINIMIZE, SW_MAXIMIZE, SW_RESTORE = 6, 3, 9
WM_CLOSE = 0x0010
GWL_EXSTYLE, WS_EX_TOOLWINDOW = -20, 0x00000080
DWMWA_CLOAKED = 14
SKIP_TITLES = {"Program Manager", "Windows Input Experience"}


@dataclass
class Win:
    hwnd: int
    title: str
    pid: int
    process: str
    minimized: bool

    def brief(self) -> str:
        state = " (minimized)" if self.minimized else ""
        return f"{self.title} [{self.process}]{state}"


def _process_name(pid: int) -> str:
    try:
        import psutil

        return psutil.Process(pid).name()
    except Exception:
        return "?"


def _cloaked(hwnd: int) -> bool:
    value = ctypes.c_int(0)
    dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED, ctypes.byref(value), ctypes.sizeof(value))
    return value.value != 0


def title_of(hwnd: int) -> str:
    n = user32.GetWindowTextLengthW(hwnd)
    if n <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def pid_of(hwnd: int) -> int:
    pid = wintypes.DWORD(0)
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def windows() -> list[Win]:
    """Visible, real top-level windows (no hidden UWP shells, no tool windows)."""
    found: list[int] = []

    def collect(hwnd, _):
        if user32.IsWindowVisible(hwnd) and not (user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE) & WS_EX_TOOLWINDOW):
            found.append(int(hwnd))
        return True

    user32.EnumWindows(WNDENUMPROC(collect), 0)
    out = []
    for hwnd in found:
        title = title_of(hwnd)
        if not title or title in SKIP_TITLES or _cloaked(hwnd):
            continue
        pid = pid_of(hwnd)
        out.append(Win(hwnd, title, pid, _process_name(pid), bool(user32.IsIconic(hwnd))))
    return out


def find(query: str) -> list[Win]:
    """Windows whose title or process name matches, best first."""
    q = query.strip().lower()
    if not q:
        return []
    scored = []
    for w in windows():
        title, proc = w.title.lower(), w.process.lower().removesuffix(".exe")
        if q == title or q == proc:
            score = 0
        elif title.startswith(q) or proc.startswith(q):
            score = 1
        elif q in title or q in proc:
            score = 2
        else:
            continue
        scored.append((score, w))
    return [w for _, w in sorted(scored, key=lambda s: s[0])]


def foreground() -> int:
    return int(user32.GetForegroundWindow() or 0)


def exists(hwnd: int) -> bool:
    return bool(user32.IsWindow(hwnd)) and bool(user32.IsWindowVisible(hwnd))


def focus(hwnd: int) -> bool:
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    fg = foreground()
    me = kernel32.GetCurrentThreadId()
    fg_thread = user32.GetWindowThreadProcessId(fg, None) if fg else 0
    attached = bool(fg_thread and fg_thread != me and user32.AttachThreadInput(me, fg_thread, True))
    try:
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
    finally:
        if attached:
            user32.AttachThreadInput(me, fg_thread, False)
    for _ in range(10):
        if foreground() == hwnd:
            return True
        time.sleep(0.05)
    return False


def set_state(hwnd: int, state: str) -> None:
    user32.ShowWindow(hwnd, {"minimize": SW_MINIMIZE, "maximize": SW_MAXIMIZE, "restore": SW_RESTORE}[state])


def is_maximized(hwnd: int) -> bool:
    return bool(user32.IsZoomed(hwnd))


def close(hwnd: int) -> None:
    user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)


def rect(hwnd: int) -> tuple[int, int, int, int]:
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom
