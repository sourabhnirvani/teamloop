"""Desk's tools: apps, windows, keyboard, any app's controls, screenshots and laptop settings.

Only one bot drives the screen at a time (the desktop lease). Anything that acts as the person goes
through risk.py and an approval card.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import time
from typing import AsyncIterator

from teamloop.computer import apps, com, risk, system, uia, winapi
from teamloop.computer.operator import OPERATOR
from teamloop.tools.registry import ToolResult, tool

WINDOW_WAIT = 12.0
_leases: dict[int, asyncio.Lock] = {}


class LeaseBusy(Exception):
    pass


@contextlib.asynccontextmanager
async def lease(timeout: float = 60) -> AsyncIterator[None]:
    lock = _leases.setdefault(id(asyncio.get_running_loop()), asyncio.Lock())
    try:
        await asyncio.wait_for(lock.acquire(), timeout)
    except asyncio.TimeoutError:
        raise LeaseBusy() from None
    try:
        await OPERATOR.wait_until_quiet()  # never fight the person for the mouse and keyboard
        yield
    finally:
        OPERATOR.mark_ours()
        lock.release()


def _busy() -> ToolResult:
    return ToolResult(False, "Another bot is using the screen right now; try again in a moment.")


async def _window(name: str | None) -> winapi.Win | None:
    if name and name.strip():
        found = await asyncio.to_thread(winapi.find, name)
        return found[0] if found else None
    fg = await asyncio.to_thread(winapi.foreground)
    return next((w for w in await asyncio.to_thread(winapi.windows) if w.hwnd == fg), None)


def _where(win: winapi.Win) -> str:
    """How risk.py sees a window: its title plus the program, e.g. 'Windows PowerShell [powershell.exe]'."""
    return f"{win.title} [{win.process}]"


def _shot_url(hwnd: int | None) -> str | None:
    try:
        return f"/api/shots/{uia.screenshot(hwnd).name}"
    except Exception:
        return None


async def _wait_for_window(app_name: str, before: set[int]) -> winapi.Win | None:
    deadline = time.monotonic() + WINDOW_WAIT
    words = [w for w in app_name.lower().split() if len(w) > 2] or [app_name.lower()]
    while time.monotonic() < deadline:
        await asyncio.sleep(0.4)
        current = await asyncio.to_thread(winapi.windows)
        new = [w for w in current if w.hwnd not in before]
        if new:
            return new[0]
        if time.monotonic() > deadline - WINDOW_WAIT + 3:  # single-instance apps reuse their window
            for w in current:
                if any(word in w.title.lower() or word in w.process.lower() for word in words):
                    return w
    return None


# ---- windows and apps --------------------------------------------------------------------------
@tool("list_windows", "List the open windows (title, app, minimized or not).", {}, kit="computer")
async def list_windows(args: dict, ctx) -> ToolResult:
    wins = await asyncio.to_thread(winapi.windows)
    return ToolResult(True, f"{len(wins)} windows are open.", {"windows": [w.brief() for w in wins]})


@tool("open_app", "Open an installed app by name (Calculator, Notepad, Chrome, Settings, Spotify...).",
      {"name": {"type": "string"}, "required": ["name"]}, kit="computer")
async def open_app(args: dict, ctx) -> ToolResult:
    name = str(args.get("name", "")).strip()
    if not name or len(name) > 80:
        return ToolResult(False, "Tell me which app to open.")
    app = await asyncio.to_thread(apps.match, name)
    if app is None:
        return ToolResult(False, f"There is no app called {name!r} in the Start menu.")
    try:
        async with lease():
            before = {w.hwnd for w in await asyncio.to_thread(winapi.windows)}
            await asyncio.to_thread(apps.launch, app["appid"])
            win = await _wait_for_window(app["name"], before)
            if win is None:
                return ToolResult(False, f"Started {app['name']}, but no window showed up in {WINDOW_WAIT:.0f} seconds.")
            front = await asyncio.to_thread(winapi.focus, win.hwnd)
    except LeaseBusy:
        return _busy()
    where = "in front" if front else "open (Windows kept another window in front)"
    return ToolResult(True, f"Opened {app['name']}; its window \"{win.title}\" is {where}.",
                      {"app": app["name"], "window": win.title})


HOST_PROCESSES = {"applicationframehost.exe", "explorer.exe"}
RUNNABLE = {".exe", ".bat", ".cmd", ".com", ".ps1", ".psm1", ".vbs", ".vbe", ".js", ".jse", ".wsf", ".wsh", ".msi",
            ".msp", ".scr", ".lnk", ".url", ".reg", ".hta", ".cpl", ".jar", ".py", ".pyw", ".appref-ms"}


@tool("open_file", "Open a file (a report, PDF, picture...) in its usual app. Desktop, Documents, Downloads or "
                   "workspace only; asks the person first.",
      {"path": {"type": "string", "description": "e.g. Desktop/report.md"}, "required": ["path"]}, kit="computer")
async def open_file(args: dict, ctx) -> ToolResult:
    from teamloop.tools.files import resolve, where

    try:
        path = resolve(str(args.get("path", "")))
    except ValueError as e:
        return ToolResult(False, f"Refused: {e}")
    if not path.is_file():
        return ToolResult(False, f"There is no file at {path}.")
    if path.suffix.lower() in RUNNABLE:
        return ToolResult(False, "Refused: that file is a program or script, so opening it would run it.")
    if not await ctx.approve("Open a file", f"Open {path.name} ({where(path)}) with its usual app."):
        return ToolResult(False, f"The person said no, so {path.name} stays closed.")
    try:
        async with lease():
            before = {w.hwnd for w in await asyncio.to_thread(winapi.windows)}
            await asyncio.to_thread(os.startfile, str(path))
            win = await _wait_for_window(path.name, before)
    except LeaseBusy:
        return _busy()
    except OSError as e:
        return ToolResult(False, f"Windows couldn't open {path.name}: {e.strerror or e}.")
    if win is None:
        return ToolResult(True, f"Asked Windows to open {path.name}; no new window showed up yet.", {"path": str(path)})
    return ToolResult(True, f"Opened {path.name}; its window \"{win.title}\" is in front.",
                      {"path": str(path), "window": win.title})


@tool("close_app", "Close an app's windows (asks the person first; unsaved work could be lost).",
      {"name": {"type": "string", "description": "app or window name"}, "required": ["name"]}, kit="computer")
async def close_app(args: dict, ctx) -> ToolResult:
    name = str(args.get("name", "")).strip()
    found = await asyncio.to_thread(winapi.find, name) if name else []
    if not found:
        return ToolResult(False, f"No open window matches {name!r}.")
    target = [w for w in found if w.process == found[0].process]
    titles = "; ".join(w.title for w in target[:5])
    # Store apps all run under one host program; their window title is the name people know.
    label = found[0].title if found[0].process.lower() in HOST_PROCESSES else found[0].process.removesuffix(".exe")
    if not await ctx.approve(f"Close {label}",
                             f"Close {len(target)} window(s): {titles}. Unsaved work in them could be lost.",
                             _shot_url(target[0].hwnd)):
        return ToolResult(False, "The person said no, so nothing was closed.")
    try:
        async with lease():
            for w in target:
                await asyncio.to_thread(winapi.close, w.hwnd)
            await asyncio.sleep(2.5)
            left = [w for w in target if await asyncio.to_thread(winapi.exists, w.hwnd)]
    except LeaseBusy:
        return _busy()
    if left:
        return ToolResult(False, f"{left[0].title} is still open; it may be asking to save. I left it for the person.")
    return ToolResult(True, f"Closed {len(target)} window{'s' if len(target) != 1 else ''} of {label}.")


@tool("focus_window", "Bring a window to the front.", {"name": {"type": "string"}, "required": ["name"]},
      kit="computer")
async def focus_window(args: dict, ctx) -> ToolResult:
    win = await _window(str(args.get("name", "")))
    if win is None:
        return ToolResult(False, f"No open window matches {args.get('name')!r}.")
    ok = await asyncio.to_thread(winapi.focus, win.hwnd)
    return ToolResult(ok, f"\"{win.title}\" is {'in front now' if ok else 'still behind another window'}.")


@tool("window_state", "Minimize, maximize or restore a window.",
      {"name": {"type": "string"}, "state": {"type": "string", "enum": ["minimize", "maximize", "restore"]},
       "required": ["name", "state"]}, kit="computer")
async def window_state(args: dict, ctx) -> ToolResult:
    state = str(args.get("state", ""))
    if state not in ("minimize", "maximize", "restore"):
        return ToolResult(False, "State must be minimize, maximize or restore.")
    win = await _window(str(args.get("name", "")))
    if win is None:
        return ToolResult(False, f"No open window matches {args.get('name')!r}.")
    await asyncio.to_thread(winapi.set_state, win.hwnd, state)
    await asyncio.sleep(0.3)
    return ToolResult(True, f"\"{win.title}\" is {state}d.")


# ---- keyboard and controls -----------------------------------------------------------------------
@tool("type_text", "Type text into a window (the one named, or the front window).",
      {"text": {"type": "string"}, "window": {"type": "string"}, "required": ["text"]}, kit="computer")
async def type_text(args: dict, ctx) -> ToolResult:
    text = str(args.get("text", ""))
    if not text:
        return ToolResult(False, "Nothing to type.")
    win = await _window(args.get("window"))
    if win is None:
        return ToolResult(False, "I can't find that window.")
    level = risk.type_risk(text, _where(win))
    if level == risk.NEVER:
        return ToolResult(False, risk.refusal("type", text, _where(win)))
    if level == risk.ASK and not await ctx.approve("Type and send", f"Type into {win.title}:\n{text[:400]}",
                                                   _shot_url(win.hwnd)):
        return ToolResult(False, "The person said no, so nothing was typed.")
    try:
        async with lease():
            if not await asyncio.to_thread(winapi.focus, win.hwnd):
                return ToolResult(False, f"Couldn't bring \"{win.title}\" to the front, so I didn't type.")
            await com.run(uia.send_text, text)  # pywinauto needs COM set up on the thread that types
    except LeaseBusy:
        return _busy()
    return ToolResult(True, f"Typed {len(text)} characters into \"{win.title}\".")


@tool("press_keys", "Press a key or shortcut, like ctrl+s, alt+tab, enter (Windows-key shortcuts are refused).",
      {"keys": {"type": "string"}, "window": {"type": "string"}, "required": ["keys"]}, kit="computer")
async def press_keys(args: dict, ctx) -> ToolResult:
    keys = str(args.get("keys", "")).strip()
    if not keys:
        return ToolResult(False, "Which keys?")
    win = await _window(args.get("window"))
    title = win.title if win else ""
    level = risk.keys_risk(keys, _where(win) if win else "")
    if level == risk.NEVER:
        return ToolResult(False, risk.refusal("keys", keys, _where(win) if win else ""))
    if level == risk.ASK and not await ctx.approve(
            f"Press {keys}", f"Press {keys} in {title or 'the front window'}.", _shot_url(win.hwnd if win else None)):
        return ToolResult(False, "The person said no, so no keys were pressed.")
    try:
        async with lease():
            if win and not await asyncio.to_thread(winapi.focus, win.hwnd):
                return ToolResult(False, f"Couldn't bring \"{title}\" to the front.")
            await com.run(uia.send_keys_combo, keys)
    except LeaseBusy:
        return _busy()
    return ToolResult(True, f"Pressed {risk.normalize_keys(keys)}" + (f" in \"{title}\"." if title else "."))


@tool("ui_snapshot", "List the buttons, fields and text inside a window, numbered. To click something, use "
      "click_on with its name instead; use this only to see everything a window offers.",
      {"window": {"type": "string"}, "required": ["window"]}, kit="computer")
async def ui_snapshot(args: dict, ctx) -> ToolResult:
    win = await _window(args.get("window"))
    if win is None:
        return ToolResult(False, f"No open window matches {args.get('window')!r}.")
    try:
        items = await asyncio.wait_for(uia.snapshot(win.hwnd), 20)
    except asyncio.TimeoutError:
        return ToolResult(False, f"\"{win.title}\" took too long to describe itself.")
    return ToolResult(True, f"\"{win.title}\" shows {len(items)} controls.", {"window": win.title, "controls": items})


@tool("ui_act", "Click, type into or select a control from the last ui_snapshot of that window.",
      {"window": {"type": "string"}, "index": {"type": "integer"},
       "action": {"type": "string", "enum": ["click", "type", "select"]}, "text": {"type": "string"},
       "required": ["window", "index", "action"]}, kit="computer")
async def ui_act(args: dict, ctx) -> ToolResult:
    win = await _window(args.get("window"))
    if win is None:
        return ToolResult(False, f"No open window matches {args.get('window')!r}.")
    index, action, text = int(args.get("index", -1)), str(args.get("action", "")), str(args.get("text", ""))
    info = await uia.describe(win.hwnd, index)
    if info is None:
        return ToolResult(False, "That number isn't in the last snapshot of this window; take a new ui_snapshot.")
    where = _where(win)
    if action == "type":
        level = risk.type_risk(text, where, info["password"], field=info["name"])
        if level == risk.NEVER:
            return ToolResult(False, risk.refusal("type", text, where, info["password"], info["name"]))
        if level == risk.ASK and not await ctx.approve(
                "Type and send", f"Type into {info['name'] or win.title}:\n{text[:400]}", _shot_url(win.hwnd)):
            return ToolResult(False, "The person said no, so nothing was typed.")
    if action == "click":
        level = risk.click_risk(info["name"], where)
        if level == risk.NEVER:
            return ToolResult(False, risk.refusal("click", window_title=where))
        if level == risk.ASK and not await ctx.approve(
                f"Click \"{info['name']}\"", f"Click \"{info['name']}\" in {win.title}.", _shot_url(win.hwnd)):
            return ToolResult(False, f"The person said no, so \"{info['name']}\" was not clicked.")
    try:
        async with lease():
            await uia.act(win.hwnd, index, action, text)
    except LeaseBusy:
        return _busy()
    except (LookupError, ValueError) as e:
        return ToolResult(False, str(e))
    done = {"click": "Clicked", "type": "Typed into", "select": "Selected"}[action]
    return ToolResult(True, f"{done} {info['type']} \"{info['name'] or index}\" in \"{win.title}\".")


@tool("screen_read", "Read the text a window is showing (names and values of its controls).",
      {"window": {"type": "string"}}, kit="computer")
async def screen_read(args: dict, ctx) -> ToolResult:
    win = await _window(args.get("window"))
    if win is None:
        return ToolResult(False, "I can't find that window.")
    try:
        items = await asyncio.wait_for(uia.snapshot(win.hwnd, 150), 20)
    except asyncio.TimeoutError:
        return ToolResult(False, f"\"{win.title}\" took too long to read.")
    lines = [f"{i['name']}: {i['value']}" if i["value"] else i["name"] for i in items if i["name"] or i["value"]]
    return ToolResult(True, f"Read {len(lines)} lines from \"{win.title}\".", {"window": win.title, "text": "\n".join(lines)})


@tool("screenshot", "Take a screenshot of a window (or the whole screen) to show the person.",
      {"window": {"type": "string"}}, kit="computer")
async def screenshot(args: dict, ctx) -> ToolResult:
    win = await _window(args.get("window")) if args.get("window") else None
    url = await asyncio.to_thread(_shot_url, win.hwnd if win else None)
    if not url:
        return ToolResult(False, "The screenshot failed.")
    await ctx.emit("screenshot", bot=ctx.bot_id, url=url)
    return ToolResult(True, f"Took a screenshot of {win.title if win else 'the screen'}.", {"url": url})


# ---- laptop settings -------------------------------------------------------------------------------
@tool("system_status", "Read volume, brightness, battery and Wi-Fi.", {}, kit="computer")
async def system_status(args: dict, ctx) -> ToolResult:
    volume, muted = await system.get_volume()
    brightness = await asyncio.to_thread(system.get_brightness)
    battery = await asyncio.to_thread(system.battery)
    wifi = await asyncio.to_thread(system.wifi)
    parts = [f"volume {volume}%" + (" (muted)" if muted else "")]
    if brightness is not None:
        parts.append(f"brightness {brightness}%")
    if battery:
        parts.append(f"battery {battery['percent']}%" + (" charging" if battery["plugged_in"] else ""))
    else:
        parts.append("no battery found (a desktop, or Windows can't read it)")
    parts.append(f"Wi-Fi {wifi['state']}" + (f" on {wifi['network']}" if wifi.get("network") else ""))
    return ToolResult(True, "Right now: " + ", ".join(parts) + ".",
                      {"volume": volume, "muted": muted, "brightness": brightness, "battery": battery, "wifi": wifi})


@tool("set_volume", "Set the volume (level 0-100), change it (+10 / -10), or mute/unmute.",
      {"level": {"type": "integer"}, "change": {"type": "integer"}, "mute": {"type": "boolean"}}, kit="computer")
async def set_volume(args: dict, ctx) -> ToolResult:
    level = args.get("level")
    if level is None and args.get("change") is not None:
        current, _ = await system.get_volume()
        level = current + int(args["change"])
    mute = args.get("mute")
    if level is None and mute is None:
        return ToolResult(False, "Give a level, a change, or mute.")
    volume, muted = await system.set_volume(None if level is None else int(level), mute)
    return ToolResult(True, f"Volume is now {volume}%" + (" and muted." if muted else "."), {"volume": volume, "muted": muted})


@tool("set_brightness", "Set screen brightness (level 0-100) or change it (+10 / -10).",
      {"level": {"type": "integer"}, "change": {"type": "integer"}}, kit="computer")
async def set_brightness(args: dict, ctx) -> ToolResult:
    level = args.get("level")
    if level is None and args.get("change") is not None:
        current = await asyncio.to_thread(system.get_brightness)
        if current is None:
            return ToolResult(False, "This screen doesn't let Windows change its brightness.")
        level = current + int(args["change"])
    if level is None:
        return ToolResult(False, "Give a level or a change.")
    now = await asyncio.to_thread(system.set_brightness, int(level))
    if now is None:
        return ToolResult(False, "This screen doesn't let Windows change its brightness.")
    return ToolResult(True, f"Brightness is now {now}%.", {"brightness": now})


@tool("set_wifi", "Turn Wi-Fi on or off. Off asks first: it cuts the crew off the internet too.",
      {"on": {"type": "boolean"}, "required": ["on"]}, kit="computer")
async def set_wifi(args: dict, ctx) -> ToolResult:
    on = bool(args.get("on"))
    if not on and not await ctx.approve("Turn Wi-Fi off",
                                        "Wi-Fi goes off. The crew can't reach models or the web until it's back on."):
        return ToolResult(False, "The person said no, so Wi-Fi stays on.")
    state = await asyncio.to_thread(system.set_wifi, on)
    if state == "none":
        return ToolResult(False, "This laptop has no Wi-Fi radio Windows can switch.")
    if state.lower() != ("on" if on else "off"):
        return ToolResult(False, f"Tried to turn Wi-Fi {'on' if on else 'off'}, but it reads {state}.")
    return ToolResult(True, f"Wi-Fi is now {'on' if on else 'off'}.", {"wifi": state})


@tool("power", "Lock, sleep, restart or shut down the laptop (always asks the person first).",
      {"action": {"type": "string", "enum": ["lock", "sleep", "restart", "shutdown"]}, "required": ["action"]},
      kit="computer")
async def power(args: dict, ctx) -> ToolResult:
    action = str(args.get("action", ""))
    if risk.power_risk(action) == risk.NEVER:
        return ToolResult(False, "Action must be lock, sleep, restart or shutdown.")
    details = {"lock": "Lock the laptop now.", "sleep": "Put the laptop to sleep now.",
               "restart": "Restart the laptop in 60 seconds (can be cancelled).",
               "shutdown": "Shut the laptop down in 60 seconds (can be cancelled)."}[action]
    if not await ctx.approve(action.capitalize(), details):
        return ToolResult(False, f"The person said no, so the laptop was not told to {action}.")
    if action == "lock":
        await asyncio.to_thread(system.lock)
        return ToolResult(True, "Locked the laptop.")
    if action == "sleep":
        await asyncio.to_thread(system.sleep)
        return ToolResult(True, "The laptop is going to sleep.")
    await asyncio.to_thread(system.shutdown, action == "restart")
    return ToolResult(True, f"The laptop will {action} in 60 seconds. Say \"cancel shutdown\" to stop it.")


@tool("cancel_shutdown", "Cancel a restart or shutdown that is counting down.", {}, kit="computer")
async def cancel_shutdown(args: dict, ctx) -> ToolResult:
    ok = await asyncio.to_thread(system.cancel_shutdown)
    return ToolResult(ok, "Cancelled the shutdown." if ok else "There was no shutdown counting down.")
