"""Find and start installed apps by name, the way the Start menu does.

App names never go through a shell: the Start menu list comes from Get-StartApps once, and an app is
started with explorer.exe shell:AppsFolder\\<AppID> passed as a single argument.
"""

from __future__ import annotations

import difflib
import json
import subprocess
import time

CACHE_SECONDS = 600
ALIASES = {
    "calc": "calculator", "explorer": "file explorer", "files": "file explorer", "chrome": "google chrome",
    "edge": "microsoft edge", "word": "word", "excel": "excel", "vs code": "visual studio code",
    "vscode": "visual studio code", "code": "visual studio code", "cmd": "command prompt",
    "terminal": "terminal", "settings": "settings", "store": "microsoft store", "paint": "paint",
}

_cache: tuple[float, list[dict]] = (0.0, [])


def start_apps(refresh: bool = False) -> list[dict]:
    global _cache
    if not refresh and _cache[1] and time.time() - _cache[0] < CACHE_SECONDS:
        return _cache[1]
    out = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command",
         "[Console]::OutputEncoding=[Text.Encoding]::UTF8; Get-StartApps | Select-Object Name,AppID | ConvertTo-Json -Compress"],
        capture_output=True, text=True, encoding="utf-8", timeout=30)
    try:
        data = json.loads(out.stdout or "[]")
    except json.JSONDecodeError:
        data = []
    apps = [{"name": a["Name"], "appid": a["AppID"]} for a in (data if isinstance(data, list) else [data])
            if a.get("Name") and a.get("AppID")]
    _cache = (time.time(), apps)
    return apps


def match(name: str, apps: list[dict] | None = None) -> dict | None:
    apps = apps if apps is not None else start_apps()
    q = name.strip().lower()
    q = ALIASES.get(q, q)
    if not q:
        return None
    by_name = {a["name"].lower(): a for a in apps}
    if q in by_name:
        return by_name[q]
    starts = [a for a in apps if a["name"].lower().startswith(q)]
    if starts:
        return min(starts, key=lambda a: len(a["name"]))
    contains = [a for a in apps if q in a["name"].lower()]
    if contains:
        return min(contains, key=lambda a: len(a["name"]))
    close = difflib.get_close_matches(q, list(by_name), n=1, cutoff=0.75)
    return by_name[close[0]] if close else None


def launch(appid: str) -> None:
    subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{appid}"])
