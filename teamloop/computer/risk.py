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


# TeamLoop's own window (its app, or its UI in a browser tab): a bot must never press Approve for itself.
# Desktop titles come as "title [process.exe]". Enter in a terminal or the Run box runs a command: that's
# what Desk's run_command (with its own rules) is for. Explorer's address bar can run commands too.
TERMINAL_WINDOWS = re.compile(
    r"\[(cmd|powershell|pwsh|windowsterminal|wt|conhost|bash|mintty|wsl)(\.exe)?\]|windows powershell|"
    r"command prompt|^run\s*\[explorer\.exe\]", re.IGNORECASE)
EXPLORER = re.compile(r"\[explorer\.exe\]", re.IGNORECASE)
CODE_FIELD = re.compile(r"\b(otp|one[- ]?time|verification|security code|2fa|two[- ]factor|passcode|"
                        r"auth(?:entication)? code|pin)\b", re.IGNORECASE)
_CARD = re.compile(r"(?<!\d)\d(?:[ -]?\d){12,18}(?!\d)")


_PROCESS = re.compile(r"\s*\[[^\]]*\]\s*$")
_BROWSER = re.compile(r"\s+[-–—]\s+((google\s+)?chrome|microsoft\W{0,3}edge|chromium|brave|opera|(mozilla\s+)?firefox)\s*$",
                      re.IGNORECASE)


def own_window(window_title: str) -> bool:
    """TeamLoop's own app window or browser tab: titled exactly "TeamLoop", or showing its local address.
    Not any title that merely contains the word, like "teamloop-notes.txt - Notepad"."""
    title = _PROCESS.sub("", window_title or "")
    from teamloop import config

    if re.search(rf"(localhost|127\.0\.0\.1):{config.port()}\b", title):
        return True
    title = _BROWSER.sub("", title).split(" http", 1)[0].strip()
    return title.lower() == "teamloop"


def _luhn(digits: str) -> bool:
    total = 0
    for i, d in enumerate(reversed(digits)):
        n = int(d) * (2 if i % 2 else 1)
        total += n - 9 if n > 9 else n
    return total % 10 == 0


def secret_kind(text: str, field: str = "") -> str | None:
    """What secret this text is (an API key, a card number, a one-time code), or None."""
    from teamloop.keys.redact import redact

    if text and redact(text) != text:
        return "an API key or token"
    for m in _CARD.finditer(text or ""):
        if _luhn(re.sub(r"\D", "", m.group(0))):
            return "a card number"
    if CODE_FIELD.search(field or "") and re.fullmatch(r"\s*\d{4,8}\s*", text or ""):
        return "a one-time code"
    return None


def click_risk(control_name: str, window_title: str = "") -> str:
    if own_window(window_title):
        return NEVER
    if COMMIT_WORDS.search(control_name or ""):
        return ASK
    return SAFE


def keys_risk(keys: str, window_title: str = "") -> str:
    k = normalize_keys(keys)
    if own_window(window_title) or "win" in k.split("+"):
        return NEVER
    if k in SEND_KEYS and TERMINAL_WINDOWS.search(window_title or ""):
        return NEVER
    if k in DESTRUCTIVE_KEYS:
        return ASK
    if k in SEND_KEYS and (MESSAGING.search(window_title or "") or EXPLORER.search(window_title or "")):
        return ASK
    return SAFE


def type_risk(text: str, window_title: str = "", is_password: bool = False, field: str = "") -> str:
    if is_password or own_window(window_title) or secret_kind(text, field):
        return NEVER
    if "\n" in text.rstrip(" ") and TERMINAL_WINDOWS.search(window_title or ""):
        return NEVER
    if "\n" in text.rstrip(" ") and MESSAGING.search(window_title or ""):
        return ASK
    return SAFE


def refusal(action: str, text: str = "", window_title: str = "", is_password: bool = False, field: str = "") -> str:
    """The one plain sentence a tool returns when a rule above says NEVER."""
    if own_window(window_title):
        return "Refused: that's TeamLoop's own window; bots never act on it (approvals are the person's)."
    if action == "type":
        kind = "a password" if is_password else secret_kind(text, field)
        if kind:
            return f"Refused: that looks like {kind}. The person types those themselves."
        return "Refused: typing a new line into a terminal runs it; use Desk's run_command instead."
    if action == "keys" and "win" in normalize_keys(text).split("+"):
        return "Refused: Windows-key shortcuts can open anything (Win+R runs commands), so bots don't press them."
    return "Refused: pressing Enter in a terminal or the Run box runs a command; use Desk's run_command instead."


def power_risk(action: str) -> str:
    return ASK if action in POWER_ACTIONS else NEVER


# Terminal: deleting, killing processes, registry, services, power, running downloaded code and touching
# TeamLoop's own secrets ask first. Wiping disks or boot settings is refused.
COMMAND_ASK = re.compile(
    r"\b(remove-item|rm|rmdir|rd|del|erase|ri|clear-recyclebin|clear-content)\b"
    r"|\b(stop-process|spps|kill|taskkill|pskill)\b"
    r"|\breg(\.exe)?\s+(add|delete|import|load|unload|restore|copy)\b"
    r"|\b(set|new|remove|rename)-itemproperty\b|\bhk(lm|cu|cr|u|cc):"
    r"|\b(stop|start|restart|set|new|remove|suspend)-service\b|\bsc(\.exe)?\s+(stop|start|config|delete|create)\b"
    r"|\b(stop|restart)-computer\b|\bshutdown(\.exe)?\b|\blogoff\b"
    r"|\b(set-executionpolicy|invoke-expression|iex|start-process\s+.*-verb\s+runas)\b"
    r"|\.env\b|keys\.vault|teamloop\.db",
    re.IGNORECASE)
COMMAND_NEVER = re.compile(
    r"\bformat-volume\b|\bformat(\.com)?\s+[a-z]:|\bdiskpart\b|\bbcdedit\b|\bvssadmin\s+delete\b"
    r"|\bcipher\s+/w\b|\bclear-disk\b|\binitialize-disk\b",
    re.IGNORECASE)


def command_risk(command: str) -> str:
    if COMMAND_NEVER.search(command or ""):
        return NEVER
    if COMMAND_ASK.search(command or ""):
        return ASK
    return SAFE


_ACTS = [
    ("delete", r"\b(remove-item|rm|rmdir|rd|del|erase|ri|clear-content|clear-recyclebin)\b"),
    ("kill", r"\b(stop-process|spps|kill|taskkill|pskill)\b"),
    ("registry", r"\breg(\.exe)?\s|itemproperty|\bhk(lm|cu|cr|u|cc):"),
    ("service", r"-service\b|\bsc(\.exe)?\s"),
    ("power", r"\b(stop|restart)-computer\b|\bshutdown\b|\blogoff\b"),
    ("run-code", r"\b(iex|invoke-expression|set-executionpolicy)\b"),
]
_NAMEISH = re.compile(r"[\w.~-]+\.\w{1,8}\b|\b[\w-]+\.exe\b")
_PROCNAME = re.compile(r"(?:-name|-processname|/im)\s+['\"]?([\w.-]+)")


def command_key(command: str) -> str:
    """What a risky command does and to which files, so a "no" still holds when the bot re-words it:
    "Remove-Item 'C:\\x\\a.txt' -Force" and "del a.txt -ErrorAction SilentlyContinue" are the same request."""
    low = (command or "").lower()
    acts = [name for name, pattern in _ACTS if re.search(pattern, low)] or ["other"]
    names = set(_NAMEISH.findall(low))
    names |= {n.removesuffix(".exe") + ".exe" for n in _PROCNAME.findall(low)}
    return "+".join(acts) + ":" + ",".join(sorted(names))
