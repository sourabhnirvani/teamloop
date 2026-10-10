"""Read and act inside any app through UI Automation (pywinauto), plus keyboard input and screenshots.

`snapshot` numbers the controls it sees; `act` uses those numbers. Everything runs on the COM thread.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path

from teamloop import config
from teamloop.computer import com, winapi

MAX_ITEMS = 80
DEPTH = 12
INTERESTING = {"Button", "Edit", "Document", "Hyperlink", "MenuItem", "ListItem", "TabItem", "CheckBox",
               "RadioButton", "ComboBox", "Text", "TreeItem", "DataItem", "SplitButton"}

_last: dict[int, list] = {}  # hwnd -> wrappers from the last snapshot


def _snapshot(hwnd: int, max_items: int) -> list[dict]:
    from pywinauto import Desktop

    window = Desktop(backend="uia").window(handle=hwnd).wrapper_object()
    items, wrappers = [], []
    for el in window.descendants(depth=DEPTH):
        info = el.element_info
        ctype = info.control_type or ""
        name = (info.name or "").strip()
        if ctype not in INTERESTING or (not name and ctype not in ("Edit", "Document")):
            continue
        if ctype == "Text" and len(items) >= max_items // 2:
            continue
        try:
            if not el.is_visible():
                continue
        except Exception:
            continue
        value = ""
        if ctype in ("Edit", "Document", "ComboBox"):
            try:
                value = (el.get_value() if hasattr(el, "get_value") else el.window_text()) or ""
            except Exception:
                value = ""
        items.append({"i": len(items), "type": ctype, "name": name[:80], "value": str(value)[:120]})
        wrappers.append(el)
        if len(items) >= max_items:
            break
    _last[hwnd] = wrappers
    return items


async def snapshot(hwnd: int, max_items: int = MAX_ITEMS) -> list[dict]:
    return await com.run(_snapshot, hwnd, max_items)


def _is_password(el) -> bool:
    try:
        return bool(el.element_info.element.CurrentIsPassword)
    except Exception:
        return False


def control(hwnd: int, index: int):
    wrappers = _last.get(hwnd) or []
    if not 0 <= index < len(wrappers):
        return None
    return wrappers[index]


def _describe(hwnd: int, index: int) -> dict | None:
    el = control(hwnd, index)
    if el is None:
        return None
    info = el.element_info
    return {"name": (info.name or "").strip(), "type": info.control_type, "password": _is_password(el)}


async def describe(hwnd: int, index: int) -> dict | None:
    return await com.run(_describe, hwnd, index)


def _act(hwnd: int, index: int, action: str, text: str) -> str:
    el = control(hwnd, index)
    if el is None:
        raise LookupError("That control number is not in the last snapshot; take a new snapshot.")
    winapi.focus(hwnd)
    if action == "click":
        try:
            el.invoke()
        except Exception:
            el.click_input()
    elif action == "type":
        try:
            el.set_edit_text(text)
        except Exception:
            el.click_input()
            send_text(text)
    elif action == "select":
        el.select()
    else:
        raise ValueError(f"Unknown action {action}.")
    time.sleep(0.3)
    return action


async def act(hwnd: int, index: int, action: str, text: str = "") -> str:
    return await com.run(_act, hwnd, index, action, text)


# ---- keyboard ------------------------------------------------------------------------------------
_SPECIAL = set("{}+^%~()")
_NAMED = {"enter": "{ENTER}", "tab": "{TAB}", "esc": "{ESC}", "up": "{UP}", "down": "{DOWN}", "left": "{LEFT}",
          "right": "{RIGHT}", "delete": "{DELETE}", "backspace": "{BACKSPACE}", "home": "{HOME}", "end": "{END}",
          "pgup": "{PGUP}", "pageup": "{PGUP}", "pgdn": "{PGDN}", "pagedown": "{PGDN}", "space": "{SPACE}",
          **{f"f{i}": f"{{F{i}}}" for i in range(1, 13)}}
_MODS = {"ctrl": "^", "shift": "+", "alt": "%"}


def escape_text(text: str) -> str:
    out = []
    for ch in text:
        if ch in _SPECIAL:
            out.append("{" + ch + "}")
        elif ch == "\n":
            out.append("{ENTER}")
        elif ch == "\t":
            out.append("{TAB}")
        else:
            out.append(ch)
    return "".join(out)


def keys_to_sendkeys(keys: str) -> str:
    from teamloop.computer.risk import normalize_keys

    parts = normalize_keys(keys).split("+")
    mods = [p for p in parts if p in _MODS or p == "win"]
    rest = [p for p in parts if p not in _MODS and p != "win"]
    key = "".join(_NAMED.get(r, escape_text(r) if len(r) == 1 else "{" + r.upper() + "}") for r in rest)
    combo = "".join(_MODS[m] for m in mods if m in _MODS) + (f"({key})" if len(rest) > 1 else key)
    if "win" in mods:
        return "{VK_LWIN down}" + combo + "{VK_LWIN up}"
    return combo


def send_text(text: str) -> None:
    from pywinauto.keyboard import send_keys

    send_keys(escape_text(text), with_spaces=True, with_tabs=True, with_newlines=True, pause=0.01)


def send_keys_combo(keys: str) -> None:
    from pywinauto.keyboard import send_keys

    send_keys(keys_to_sendkeys(keys), pause=0.02)


# ---- screenshots -----------------------------------------------------------------------------------
def shots_dir() -> Path:
    path = config.workspace() / "shots"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _window_image(hwnd: int):
    """The window's own pixels via PrintWindow, even when other windows cover it. None if it can't."""
    import ctypes
    from ctypes import wintypes

    from PIL import Image

    left, top, right, bottom = winapi.rect(hwnd)
    width, height = right - left, bottom - top
    if width <= 0 or height <= 0:
        return None
    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    user32.GetWindowDC.restype = gdi32.CreateCompatibleDC.restype = ctypes.c_void_p
    gdi32.CreateCompatibleBitmap.restype = gdi32.SelectObject.restype = ctypes.c_void_p
    user32.GetWindowDC.argtypes = [wintypes.HWND]
    user32.PrintWindow.argtypes = [wintypes.HWND, ctypes.c_void_p, wintypes.UINT]
    user32.ReleaseDC.argtypes = [wintypes.HWND, ctypes.c_void_p]
    gdi32.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
    gdi32.CreateCompatibleBitmap.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
    gdi32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    gdi32.GetDIBits.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT, wintypes.UINT, ctypes.c_void_p,
                                ctypes.c_void_p, wintypes.UINT]
    gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
    gdi32.DeleteDC.argtypes = [ctypes.c_void_p]

    class Header(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                    ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                    ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]

    window_dc = user32.GetWindowDC(hwnd)
    memory_dc = gdi32.CreateCompatibleDC(window_dc)
    bitmap = gdi32.CreateCompatibleBitmap(window_dc, width, height)
    gdi32.SelectObject(memory_dc, bitmap)
    try:
        if not user32.PrintWindow(hwnd, memory_dc, 2):  # 2 = PW_RENDERFULLCONTENT (works for GPU-drawn apps)
            return None
        header = Header(ctypes.sizeof(Header), width, -height, 1, 32, 0, 0, 0, 0, 0, 0)
        buffer = ctypes.create_string_buffer(width * height * 4)
        if not gdi32.GetDIBits(memory_dc, bitmap, 0, height, buffer, ctypes.byref(header), 0):
            return None
        return Image.frombuffer("RGB", (width, height), buffer, "raw", "BGRX", 0, 1)
    finally:
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(memory_dc)
        user32.ReleaseDC(hwnd, window_dc)


def screenshot(hwnd: int | None = None) -> Path:
    from PIL import ImageGrab

    if hwnd:
        # Never fall back to grabbing the screen area: whatever covers the window would leak into the card.
        image = _window_image(hwnd)
        if image is None:
            raise RuntimeError("could not capture that window")
    else:
        image = ImageGrab.grab(all_screens=True)
    image.thumbnail((1600, 1600))
    path = shots_dir() / f"{uuid.uuid4().hex[:12]}.png"
    image.save(path, "PNG")
    return path
