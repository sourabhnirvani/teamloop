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


def screenshot(hwnd: int | None = None) -> Path:
    from PIL import ImageGrab

    bbox = winapi.rect(hwnd) if hwnd else None
    image = ImageGrab.grab(bbox=bbox, all_screens=bbox is None)
    image.thumbnail((1600, 1600))
    path = shots_dir() / f"{uuid.uuid4().hex[:12]}.png"
    image.save(path, "PNG")
    return path
