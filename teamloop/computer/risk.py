"""Shared safety rules for anything that acts as the person. Pure functions, table-tested.

"safe" runs at once, "ask" shows an approval card first, "never" is refused.
"""

from __future__ import annotations

import re

SAFE, ASK, NEVER = "safe", "ask", "never"

MESSAGING = re.compile(
    r"whatsapp|telegram|signal|discord|slack|teams|outlook|gmail|\bmail\b|messenger|instagram|linkedin|"
    r"twitter|\bx\.com\b|facebook|reddit", re.IGNORECASE)
COMMIT_WORDS = re.compile(
    r"^\W*(send|post|reply( all)?|tweet|publish|submit|share|comment|buy|pay|place order|checkout|"
    r"confirm|delete|remove|uninstall|format|empty recycle bin|sign out|log out)\b", re.IGNORECASE)
DESTRUCTIVE_KEYS = {"shift+delete", "ctrl+shift+delete", "alt+f4"}
SEND_KEYS = {"enter", "ctrl+enter", "alt+s"}

POWER_ACTIONS = {"lock", "sleep", "restart", "shutdown"}


def normalize_keys(keys: str) -> str:
    parts = [p.strip().lower() for p in re.split(r"\s*\+\s*", keys.strip()) if p.strip()]
    aliases = {"control": "ctrl", "return": "enter", "del": "delete", "escape": "esc", "windows": "win"}
    parts = [aliases.get(p, p) for p in parts]
    mods = [m for m in ("ctrl", "shift", "alt", "win") if m in parts]
    rest = [p for p in parts if p not in ("ctrl", "shift", "alt", "win")]
    return "+".join(mods + rest)


def click_risk(control_name: str, window_title: str = "") -> str:
    if COMMIT_WORDS.search(control_name or ""):
        return ASK
    return SAFE


def keys_risk(keys: str, window_title: str = "") -> str:
    k = normalize_keys(keys)
    if k in DESTRUCTIVE_KEYS:
        return ASK
    if k in SEND_KEYS and MESSAGING.search(window_title or ""):
        return ASK
    return SAFE


def type_risk(text: str, window_title: str = "", is_password: bool = False) -> str:
    if is_password:
        return NEVER
    if "\n" in text.rstrip(" ") and MESSAGING.search(window_title or ""):
        return ASK
    return SAFE


def power_risk(action: str) -> str:
    return ASK if action in POWER_ACTIONS else NEVER
