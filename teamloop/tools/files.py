"""Files kit: read, list and save text files in the person's Desktop, Documents, Downloads or workspace.

Paths may start with a folder name ("Desktop/report.md"). Anything outside those folders is refused.
Overwriting an existing file asks the person first.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from teamloop import config
from teamloop.keys import vault
from teamloop.tools.registry import ToolResult, tool

READ_CHARS = 8000


# Windows' own ids for the person's folders: asking Windows beats guessing. A OneDrive\Documents folder can exist while
# Explorer's Documents is C:\Users\me\Documents, and saved files then landed where the person never looks
# (found by jrkrishh on his laptop, and true on Sourabh's too).
_FOLDER_IDS = {"Desktop": "B4BFCC3A-DB2C-424C-B029-7FE99A87C641", "Documents": "FDD39AD0-238F-46AF-ADB4-6C85480369C7",
               "Downloads": "374DE290-123F-4565-9164-39C4925E467B"}


def _windows_folder(name: str) -> Path | None:
    """Where Windows itself says the folder is (SHGetKnownFolderPath), or None off Windows or on failure."""
    if sys.platform != "win32" or name not in _FOLDER_IDS:
        return None
    import ctypes
    import uuid

    class GUID(ctypes.Structure):
        _fields_ = [("Data1", ctypes.c_uint32), ("Data2", ctypes.c_uint16), ("Data3", ctypes.c_uint16),
                    ("Data4", ctypes.c_ubyte * 8)]

    u = uuid.UUID(_FOLDER_IDS[name])
    guid = GUID(u.time_low, u.time_mid, u.time_hi_version, (ctypes.c_ubyte * 8).from_buffer_copy(u.bytes[8:]))
    out = ctypes.c_wchar_p()
    try:
        if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(out)) != 0:
            return None
        return Path(out.value) if out.value else None
    except OSError:
        return None
    finally:
        if out:
            ctypes.windll.ole32.CoTaskMemFree(out)


def known_folder(name: str) -> Path:
    found = _windows_folder(name)
    if found:
        return found
    home = Path.home()
    for base in (Path(os.environ["OneDrive"]) if os.environ.get("OneDrive") else None, home / "OneDrive", home):
        if base and (base / name).is_dir():
            return base / name
    return home / name


def roots() -> dict[str, Path]:
    files = config.workspace() / "files"
    files.mkdir(parents=True, exist_ok=True)
    return {"desktop": known_folder("Desktop"), "documents": known_folder("Documents"),
            "downloads": known_folder("Downloads"), "workspace": files}


_URL = re.compile(r"https?://[^\s)\]>]+")
_LIST_ITEM = re.compile(r"^\s*([-*•]|\d+[.)])\s+|^\s*(\[[^\]]*\]\()?https?://")


def dedupe_link_lines(text: str) -> str:
    """Drop a list line that only repeats a link already listed (S and Writer both adding the same sources).
    Sentences in the text are never touched."""
    seen: set[str] = set()
    out = []
    for line in text.split("\n"):
        urls = _URL.findall(line)
        if len(urls) == 1 and _LIST_ITEM.match(line) and len(line.strip()) < 300:
            url = urls[0].rstrip(".,;").rstrip("/").lower()
            if url in seen:
                continue
            seen.add(url)
        out.append(line)
    return "\n".join(out)


_PS_VAR = re.compile(r"\$env:(\w+)", re.IGNORECASE)
_PCT_VAR = re.compile(r"%(\w+)%")
_DOLLAR_VAR = re.compile(r"\$\{?(\w+)\}?")
# Only folder-ish variables. Anything else stays literal: "Documents/$env:GROQ_API_KEY.txt" must never become a file
# whose name is the key (the key guard only sees "$env:GROQ_API_KEY" in the args, and the file could sync to OneDrive).
PATH_VARS = {"USERPROFILE", "HOME", "HOMEDRIVE", "HOMEPATH", "ONEDRIVE", "ONEDRIVECONSUMER", "PUBLIC", "USERNAME",
             "APPDATA", "LOCALAPPDATA", "TEMP", "TMP"}


def _var(match: re.Match) -> str:
    name = match.group(1)
    if name.upper() not in PATH_VARS:
        return match.group(0)
    return os.environ.get(name) or os.environ.get(name.upper()) or match.group(0)


def expand(text: str) -> str:
    """$env:USERPROFILE (PowerShell), %USERPROFILE% and $HOME, the way a model often writes paths, for the
    folder variables in PATH_VARS only. resolve() still checks the expanded path against the allowed folders."""
    for pattern in (_PS_VAR, _PCT_VAR, _DOLLAR_VAR):
        text = pattern.sub(_var, text)
    return text


def resolve(raw: str) -> Path:
    text = expand(raw.strip().strip('"')).replace("\\", "/")
    if not text:
        raise ValueError("Give a file path.")
    folders = roots()
    first, _, rest = text.partition("/")
    alias = first.lower().lstrip("~")
    if alias in folders:
        path = folders[alias] / rest
    elif text.startswith("~/"):
        path = Path.home() / text[2:]
    elif Path(text).is_absolute():
        path = Path(text)
    else:
        path = folders["workspace"] / text
    path = path.resolve()
    if not any(path == r.resolve() or path.is_relative_to(r.resolve()) for r in folders.values()):
        raise ValueError(f"{raw} is outside Desktop, Documents, Downloads and the workspace.")
    if _holds_secrets(path):
        raise ValueError(f"{path.name} holds keys or app data, so bots can't open it.")
    return path


def where(path: Path) -> str:
    """Where a file is, as the person knows it: "on your Desktop", "in Documents\\Reports"; a full path elsewhere."""
    names = {"desktop": "on your Desktop", "documents": "in Documents", "downloads": "in Downloads",
             "workspace": "in TeamLoop's workspace"}
    folder = path.parent.resolve()
    for key, base in roots().items():
        base = base.resolve()
        if folder == base:
            return names.get(key, f"in {base}")
        if folder.is_relative_to(base):
            label = names.get(key, f"in {base}").replace("on your Desktop", "in Desktop")
            return f"{label}\\{folder.relative_to(base)}"
    return f"in {folder}"


def _holds_secrets(path: Path) -> bool:
    """The key vault, .env files (not .env.example) and databases."""
    name = path.name.lower()
    if path == vault.path().resolve() or name == "keys.vault":
        return True
    if name == ".env" or (name.startswith(".env.") and name != ".env.example"):
        return True
    return name.endswith((".db", ".db-wal", ".db-shm", ".sqlite"))


@tool("write_file", "Save text to a file. Paths can start with Desktop, Documents, Downloads or workspace.",
      {"path": {"type": "string"}, "content": {"type": "string"},
       "overwrite": {"type": "boolean", "description": "replace the file if it exists (asks the person)"},
       "required": ["path", "content"]}, kit="files")
async def write_file(args: dict, ctx) -> ToolResult:
    try:
        path = resolve(str(args.get("path", "")))
    except ValueError as e:
        return ToolResult(False, f"Refused: {e}")
    content = str(args.get("content", ""))
    if path.exists():
        if not args.get("overwrite"):
            return ToolResult(False, f"{path} already exists. Pick another name or set overwrite.")
        if not await ctx.approve("Replace a file", f"Overwrite {path.name} ({where(path)}, {path.stat().st_size} bytes) "
                                                   "with new text."):
            return ToolResult(False, f"The person said no, so {path.name} was left as it was.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedupe_link_lines(content), encoding="utf-8")
    size = path.stat().st_size
    return ToolResult(True, f"Saved {path} ({size} bytes).", {"path": str(path), "bytes": size})


@tool("read_file", "Read a text file.", {"path": {"type": "string"}, "required": ["path"]}, kit="files")
async def read_file(args: dict, ctx) -> ToolResult:
    try:
        path = resolve(str(args.get("path", "")))
    except ValueError as e:
        return ToolResult(False, f"Refused: {e}")
    if not path.is_file():
        return ToolResult(False, f"There is no file at {path}.")
    text = path.read_text(encoding="utf-8", errors="replace")
    return ToolResult(True, f"Read {path} ({len(text)} characters).", {"path": str(path), "text": text[:READ_CHARS]})


@tool("list_files", "List what is in a folder (Desktop, Documents, Downloads, workspace or a folder inside them).",
      {"path": {"type": "string"}, "required": ["path"]}, kit="files")
async def list_files(args: dict, ctx) -> ToolResult:
    try:
        path = resolve(str(args.get("path", "")) or "workspace")
    except ValueError as e:
        return ToolResult(False, f"Refused: {e}")
    if not path.is_dir():
        return ToolResult(False, f"There is no folder at {path}.")
    entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))[:100]
    items = [{"name": p.name, "folder": p.is_dir()} for p in entries]
    return ToolResult(True, f"{path} has {len(items)} items.", {"path": str(path), "items": items})
