"""Files kit: read, list and save text files in the person's Desktop, Documents, Downloads or workspace.

Paths may start with a folder name ("Desktop/report.md"). Anything outside those folders is refused.
Overwriting an existing file asks the person first.
"""

from __future__ import annotations

import os
from pathlib import Path

from teamloop import config
from teamloop.tools.registry import ToolResult, tool

READ_CHARS = 8000


def known_folder(name: str) -> Path:
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


def resolve(raw: str) -> Path:
    text = raw.strip().strip('"').replace("\\", "/")
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
    return path


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
        if not await ctx.approve("Replace a file", f"Overwrite {path} ({path.stat().st_size} bytes) with new text."):
            return ToolResult(False, f"The person said no, so {path.name} was left as it was.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
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
