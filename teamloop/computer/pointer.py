"""Desk's advanced computer use: click on things by what they are, raw mouse input, and looking at the screen.

click_on    find a control by meaning (UI Automation, then OCR), act (Invoke pattern or a real click), then check that
            something happened (the expected text shows, or the window changed); one retry; reports new dialogs.
mouse       move / click / double / right / scroll / drag at exact physical pixels, for canvases and games.
find_on_screen   look only: where a control or text is, and what the window shows.

Every action takes the desktop lease (operator safety: pause while the person works, Stop, Ctrl+Alt+Q) and goes
through risk.py and an approval card like every other tool that acts as the person.
"""

from __future__ import annotations

import asyncio
import ctypes
import re
from ctypes import wintypes

from teamloop.computer import com, ground, mouse, risk, uia, verify, winapi
from teamloop.computer.tools import LeaseBusy, _busy, _shot_url, _where, _window, lease
from teamloop.keys.redact import redact
from teamloop.tools.registry import ToolResult, tool

UNNAMED_ASK = re.compile(r"mail|outlook|whatsapp|telegram|slack|teams|discord|signal|messenger|amazon|flipkart|"
                         r"paypal|bank|checkout|cart|chrome|edge|firefox|brave|opera", re.IGNORECASE)


def visible_rect(hwnd: int) -> tuple[int, int, int, int]:
    """The window as you see it (without Windows 10/11's invisible resize borders), physical pixels."""
    r = wintypes.RECT()
    if ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(r), ctypes.sizeof(r)) == 0:  # EXTENDED_FRAME
        return r.left, r.top, r.right, r.bottom
    return winapi.rect(hwnd)


def near_text(x: int, y: int) -> str:
    """OCR of a small box around a point (about 220x44 px): the label of an icon button with no UIA name."""
    s = mouse.screen()
    box = (max(s.left, x - 110), max(s.top, y - 22), min(s.left + s.width, x + 110), min(s.top + s.height, y + 22))
    try:
        return " ".join(line["text"] for line in ground.read_box(box))[:120]
    except Exception:
        return ""


def point_risk(name: str, where: str, action: str, nearby: str = "") -> str:
    """A raw point is judged by what is under it: its UIA name, else the text printed around it (an unnamed icon
    labelled Delete or Send gets a card in any app). Nothing named at all in a mail/chat/shop/browser window: ask."""
    level = risk.click_risk(name, where)
    if level == risk.SAFE and not name and nearby:
        level = risk.click_risk(nearby, where)
    if level == risk.SAFE and action == "drag" and risk.EXPLORER.search(where):
        return risk.ASK                  # dragging in File Explorer moves files
    if level == risk.SAFE and not name and action in ("click", "double_click") and UNNAMED_ASK.search(where):
        return risk.ASK
    return level


def ringed_shot(hwnd: int | None, points: list[tuple[int, int]]) -> str | None:
    """The card's screenshot with a red ring on each target point (and a line for a drag), so the person sees
    exactly where the crew will click before saying yes."""
    try:
        from PIL import Image, ImageDraw

        path = uia.screenshot(hwnd)
        if hwnd:
            left, top, right, _ = winapi.rect(hwnd)
            width = right - left
        else:
            s = mouse.screen()
            left, top, width = s.left, s.top, s.width
        image = Image.open(path).convert("RGB")
        scale = image.width / max(width, 1)
        draw = ImageDraw.Draw(image)
        marks = [((x - left) * scale, (y - top) * scale) for x, y in points]
        if len(marks) == 2:
            draw.line(marks, fill=(255, 255, 255), width=7)
            draw.line(marks, fill=(230, 30, 30), width=3)
        for cx, cy in marks:  # red inside a white halo, so it shows on a red button or a dark app too
            r = max(14.0, 22 * scale)
            for pad, colour, width in ((4, (255, 255, 255), 4), (0, (230, 30, 30), 4)):
                draw.ellipse((cx - r - pad, cy - r - pad, cx + r + pad, cy + r + pad), outline=colour, width=width)
            draw.ellipse((cx - 5, cy - 5, cx + 5, cy + 5), fill=(255, 255, 255))
            draw.ellipse((cx - 3, cy - 3, cx + 3, cy + 3), fill=(230, 30, 30))
        image.save(path, "PNG")
        return f"/api/shots/{path.name}"
    except Exception:
        return _shot_url(hwnd)


def _act(hit: ground.Hit, action: str, hwnd: int) -> str:
    """Do it; returns how. Runs on the COM thread."""
    winapi.focus(hwnd)
    el = hit.element
    if el is not None and action == "click":
        # a tree/list/tab item is "clicked" by selecting it (Explorer's Documents navigates; Expand only unfolds it)
        order = ("select", "invoke", "expand") if hit.role in ("TreeItem", "ListItem", "TabItem", "DataItem") \
            else ("invoke", "expand", "select")
        for how in order:
            call = how
            try:
                getattr(el, call)()
                return how
            except Exception:
                continue
    if el is not None and action == "focus":
        try:
            el.set_focus()
            return "focus"
        except Exception:
            pass
    button, count = {"right_click": ("right", 1), "double_click": ("left", 2)}.get(action, ("left", 1))
    mouse.click(hit.x, hit.y, button, count)
    return "mouse"


def _find(hwnd: int, target: str) -> ground.Hit | None:
    hit = ground.find_uia(hwnd, target)
    if hit is None or hit.score < 60:
        try:
            ocr_hit = ground.find_in_lines(ground.read_box(visible_rect(hwnd)), target)
        except Exception:
            ocr_hit = None
        if ocr_hit and (hit is None or ocr_hit.score > hit.score):
            hit = ocr_hit
    return hit


@tool("click_on",
      "Click a control by what it is, e.g. target 'Seven', 'the Save button', 'Documents', 'File'. Finds it through "
      "the app's controls (or by reading the screen), clicks, and checks it worked. Set expect to text that should "
      "appear afterwards (e.g. 'Display is 42'). Use this before mouse or ui_act.",
      {"window": {"type": "string"}, "target": {"type": "string"},
       "action": {"type": "string", "enum": ["click", "double_click", "right_click", "focus"]},
       "expect": {"type": "string", "description": "text that should show after the click"},
       "required": ["window", "target"]}, kit="computer")
async def click_on(args: dict, ctx) -> ToolResult:
    target, action = str(args.get("target", "")).strip(), str(args.get("action") or "click")
    expect = str(args.get("expect") or "").strip()
    win = await _window(args.get("window"))
    if win is None:
        return ToolResult(False, f"No open window matches {args.get('window')!r}.")
    if not target:
        return ToolResult(False, "What should I click?")
    hit = await com.run(_find, win.hwnd, target)
    if hit is None:
        names = await com.run(ground.visible_names, win.hwnd, 40)
        shown = ", ".join(n for n in names if not n.startswith("[window]"))[:400]
        return ToolResult(False, f"I couldn't find \"{target}\" in \"{win.title}\". It shows: {redact(shown)}",
                          {"window": win.title})
    where = _where(win)
    level = risk.click_risk(hit.name, where)
    if level == risk.NEVER:
        return ToolResult(False, risk.refusal("click", window_title=where))
    if level == risk.ASK and not await ctx.approve(f"Click \"{hit.name}\"", f"Click \"{hit.name}\" in {win.title}.",
                                                   ringed_shot(win.hwnd, [(hit.x, hit.y)])):
        return ToolResult(False, f"The person said no, so \"{hit.name}\" was not clicked.")
    tries, how, seen = 0, "", ""
    try:
        async with lease():
            before = await com.run(verify.look, win.hwnd)
            for tries in (1, 2):
                how = await com.run(_act, hit, action, win.hwnd)
                await asyncio.sleep(0.4)
                if expect:
                    seen = await com.run(verify.wait_for, win.hwnd, expect, 3.0) or ""
                    if seen:
                        break
                else:
                    after = await com.run(verify.look, win.hwnd)
                    if verify.changes(before, after) or action == "focus":
                        break
                # nothing happened: find it again (it may have moved) and use a real click this time
                again = await com.run(_find, win.hwnd, target)
                if again is None:
                    break
                hit, hit.element = again, None
            after = await com.run(verify.look, win.hwnd)
    except LeaseBusy:
        return _busy()
    changed = verify.changes(before, after)
    data = {"window": win.title, "found": hit.public(), "how": how, "tries": tries, "changed": changed}
    did = f"{'Clicked' if action == 'click' else action.replace('_', '-').capitalize() + 'ed'} \"{hit.name}\" in " \
          f"\"{win.title}\" (found by {hit.how}, {how})"
    dialogs = [c for c in changed if c.startswith("a new window opened")]
    if expect and not seen:
        return ToolResult(False, f"{did}, but \"{expect}\" didn't show after {tries} tries. "
                                 + (f"What changed: {'; '.join(changed)}." if changed else "Nothing changed."), data)
    if not expect and not changed and action != "focus":
        return ToolResult(False, f"{did}, but nothing changed after {tries} tries.", data)
    tail = f" {dialogs[0].capitalize()}: deal with it before going on." if dialogs else \
        (f" Now: {'; '.join(changed)}." if changed else "")
    return ToolResult(True, f"{did}." + (f" \"{expect}\" shows." if expect else "") + tail, data)


@tool("mouse",
      "Real mouse at exact pixels, for things with no named controls (canvases, games, maps): move, click, "
      "double_click, right_click, scroll (amount: + up, - down) or drag (to_x, to_y). x/y are inside the window "
      "if given (0,0 = its top-left corner), else on the screen.",
      {"action": {"type": "string", "enum": ["move", "click", "double_click", "right_click", "scroll", "drag"]},
       "x": {"type": "integer"}, "y": {"type": "integer"}, "to_x": {"type": "integer"}, "to_y": {"type": "integer"},
       "amount": {"type": "integer"}, "window": {"type": "string"},
       "required": ["action", "x", "y"]}, kit="computer")
async def mouse_tool(args: dict, ctx) -> ToolResult:
    action = str(args.get("action", ""))
    win = await _window(args.get("window")) if args.get("window") else None
    if args.get("window") and win is None:
        return ToolResult(False, f"No open window matches {args.get('window')!r}.")
    ox, oy = visible_rect(win.hwnd)[:2] if win else (0, 0)
    try:
        x, y = ox + int(args["x"]), oy + int(args["y"])
        tx = ox + int(args["to_x"]) if action == "drag" else x
        ty = oy + int(args["to_y"]) if action == "drag" else y
        mouse.check_point(x, y)
        mouse.check_point(tx, ty)
    except (KeyError, TypeError, ValueError) as e:
        return ToolResult(False, f"Bad point: {e}" if isinstance(e, ValueError) else "A drag needs to_x and to_y.")
    under = await com.run(mouse.element_at, x, y)
    where = f"{under['window'] or (win.title if win else '')}"
    if win:
        where = _where(win)
    nearby = ""
    if action not in ("move", "scroll") and not under["name"]:
        nearby = await asyncio.to_thread(near_text, x, y)
    level = point_risk(under["name"], where, action, nearby) if action not in ("move", "scroll") else risk.SAFE
    if level == risk.NEVER:
        return ToolResult(False, risk.refusal("click", window_title=where))
    on = under["name"] or nearby
    label = f"{action.replace('_', ' ')} at ({x}, {y})" + (f" on \"{on}\"" if on else "")
    marks = [(x, y), (tx, ty)] if action == "drag" else [(x, y)]
    if level == risk.ASK and not await ctx.approve(f"Mouse: {label}", f"{label} in {where} (red ring on the picture).",
                                                   ringed_shot(win.hwnd if win else None, marks)):
        return ToolResult(False, f"The person said no, so I didn't {action.replace('_', ' ')} there.")
    try:
        async with lease():
            before = await com.run(verify.look, win.hwnd) if win else None
            if win:
                await asyncio.to_thread(winapi.focus, win.hwnd)
            if action == "move":
                await asyncio.to_thread(mouse.move, x, y)
            elif action == "scroll":
                await asyncio.to_thread(mouse.scroll, x, y, int(args.get("amount") or -3))
            elif action == "drag":
                await asyncio.to_thread(mouse.drag, x, y, tx, ty)
            else:
                button, count = {"right_click": ("right", 1), "double_click": ("left", 2)}.get(action, ("left", 1))
                await asyncio.to_thread(mouse.click, x, y, button, count)
            after = await com.run(verify.look, win.hwnd) if win else None
    except LeaseBusy:
        return _busy()
    changed = verify.changes(before, after) if win else []
    what = f" over \"{under['name']}\" ({under['type']})" if under["name"] else ""
    text = (f"Dragged from ({x}, {y}) to ({tx}, {ty})" if action == "drag" else
            f"{action.replace('_', ' ').capitalize()} at ({x}, {y})") + what + "."
    if win:
        text += f" {'; '.join(changed).capitalize()}." if changed else " The window's controls look the same " \
                                                                      "(normal for drawing on a canvas)."
    return ToolResult(True, text, {"x": x, "y": y, "under": under, "changed": changed})


@tool("find_on_screen",
      "Look without touching: where a control or text is in a window (its box and centre), and the text the window "
      "shows. Use it to check the result of a step or to plan clicks.",
      {"window": {"type": "string"}, "text": {"type": "string"}, "required": ["text"]}, kit="computer")
async def find_on_screen(args: dict, ctx) -> ToolResult:
    win = await _window(args.get("window"))
    if win is None:
        return ToolResult(False, f"No open window matches {args.get('window')!r}.")
    text = str(args.get("text", "")).strip()
    hit = await com.run(_find, win.hwnd, text) if text else None
    try:
        lines = await asyncio.to_thread(ground.read_box, visible_rect(win.hwnd))
        shown = redact(" | ".join(line["text"] for line in lines))[:1500]
    except Exception as e:
        shown = f"(couldn't read the screen: {e})"
    data = {"window": win.title, "found": hit.public() if hit else None, "screen_text": shown}
    if hit is None:
        return ToolResult(False, f"\"{text}\" isn't visible in \"{win.title}\". It shows: {shown[:300]}", data)
    return ToolResult(True, f"\"{hit.name}\" is at ({hit.x}, {hit.y}) in \"{win.title}\" (found by {hit.how}).", data)
