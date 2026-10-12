# N: Advanced computer use, design (jrkrishh, Mon 12 Oct ~07:30 IST)

Goal (Sourabh): Desk controls any app like a person. That means clicking, getting to any point, scrolling, dragging,
and working menus and dialogs, and it checks its own work.

## 1. What exists today, tried on this laptop
`evidence/runs/computer-use-baseline-yang.py` is read-only (nothing clicked); its output is in `computer-use-baseline-yang.out.txt`.

| App | `ui_snapshot` | What it means |
|---|---|---|
| Calculator | 40 controls in 1.0 s; "Seven", "Plus", "Equals", "Display is 0" all present by name | The accessibility (UIA) tree is enough. The model must still do two steps (snapshot, then act by index) and has no "click Seven" |
| Paint | 67 controls: ribbon buttons (Pencil, Brushes…) yes, **the canvas no** | Drawing needs real mouse coordinates, which we don't have |
| Notepad | 18 controls; File/Edit menus, "Text Editor" | Menus work through UIA; Save As then opens a **new dialog window** that the snapshot of the old window never sees |

Where it fails:
1. **No mouse at all.** There's no move, click at a point, right/double click, scroll or drag. `ui_act` uses
   `click_input()` on a tree element, and when an app has no tree (canvas, games, many Electron/web views), Desk is stuck.
2. **No find by meaning.** The model must snapshot, read up to 150 numbered lines, and pick an index. That costs tokens,
   and it's fragile: indexes shift once anything changes.
3. **No check that an action worked.** `ui_act` says "Clicked X" even when nothing happened, and a dialog that pops up
   (Save As, "Do you want to save?") isn't noticed.
4. **Mixed coordinate systems (measured).** This process starts DPI-unaware: `GetSystemMetrics` = **1536x864**. But the
   screen is 1920x1080 at 125% (a full-screen capture is 1920x1080), and window rects come back **physical** (Paint maximised:
   `(-9,-9,1929,1039)`). Which one you get depends on whether pywinauto has been imported yet. A click computed in one space
   and sent in the other misses by 25%.

## 2. Options researched
**Finding a control**
- **UIA tree (pywinauto, already a dependency).** It gives name, control type and automation id, plus patterns:
  - **Invoke:** buttons and menu items, with no mouse involved
  - **Value:** set the text of a field directly
  - **Toggle:** checkboxes
  - **ExpandCollapse:** menus and combo boxes
  - **SelectionItem:** list and tab items
  - **ScrollItem:** bring an item into view
  
  It's exact, fast (0.1-1 s) and works when the window is covered. It fails on canvas, games, and many Chromium/Electron
  surfaces unless their accessibility is on.
- **Windows OCR (`Windows.Media.Ocr`).** It's built into Windows and free. **Available here: en-US, en-GB, max image
  10000 px.** Python's WinRT projection isn't installed, but Windows PowerShell 5.1 can load the type, so it needs no new
  pip package. It returns words with pixel boxes, which gives exact click points for visible text. It's blind to icons with
  no text.
- **Free vision model (Gemini free tier, or a local Ollama vision model).** It finds "the gear icon"-type targets with no
  text. It's slower (2-6 s), needs a key or a local model, and its coordinates need checking. It's the last fallback only.

**Sending input**
- **`SendInput`** with `MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK`: absolute positions over the whole virtual desktop,
  normalised to 0..65535. It works across monitors, including negative coordinates. Its input looks real to apps, unlike
  `PostMessage`, which many apps ignore.
- **DPI:** set **per-monitor-aware v2** (`SetProcessDpiAwarenessContext(-4)`) once at import. From then on, every rect,
  screenshot pixel and cursor position is in **physical pixels**, which closes failure 4. Screenshots come from PIL
  `ImageGrab.grab(all_screens=True)`, which uses physical pixels once the process is aware, offset by the virtual-screen
  origin (`SM_XVIRTUALSCREEN`).

## 3. Chosen approach
**Tree first, OCR second, vision last.** Act through UIA patterns when a control exists. Use real mouse input at exact
physical coordinates when it doesn't. **Every action is checked:** look, act, look again, confirm, retry once, and stop
on surprises.

New files:
- `computer/mouse.py`: DPI awareness, the virtual screen, `SendInput` move/click/double/right/scroll/drag, and
  `element_at(x, y)` (UIA `ElementFromPoint`, to name what is under a point for the risk check).
- `computer/ground.py`: find a target in a window:
  1. UIA fuzzy match on name, automation id or control type ("Save button" → role Button, name ~ "Save"), scored
     exact > starts-with > contains > token overlap
  2. OCR words or lines on a window screenshot
  3. vision, if a free key or model is set
  
  It returns `{x, y, box, how, name}`.
- `computer/verify.py`: a window "fingerprint" (title, focused element, the names of visible controls, a hash of the
  OCR text, the list of top-level windows). `changed(before, after)`, `wait_for(text)`, and `new_dialog(before, after)`.

New tools, in the computer kit (contract in PLAN.md §4):
| Tool | Args | Does |
|---|---|---|
| `click_on` | `window`, `target` ("Save button", "Seven", "Documents"), `action` = click / double_click / right_click / focus (default click), `expect`? (text that should appear afterwards) | Finds the target (tree, then OCR, then vision); uses the Invoke pattern if it has one, else a real click at its centre; then verifies: `expect` shows up, or the window visibly changed. If not, it re-finds once and retries; then it fails and says what it sees. Reports a new dialog by name and stops |
| `mouse` | `action` = move / click / double_click / right_click / scroll / drag, `x`, `y` (inside `window` if given, else the screen), `to_x`, `to_y` (drag), `amount` (scroll notches, + up / − down), `window`? | Raw input at exact physical pixels, for canvases and games. Says what was under the point (UIA name) and whether the window changed |
| `find_on_screen` | `window`?, `text` | Look only: where the text or control is (box, how it was found) and the window's visible text (OCR, keys redacted). Nothing is clicked |

The plan, act, look, verify loop: the model plans (Desk's persona gets a short "how to drive an app" block), and each tool
does the act/look/verify for its own step with **one retry**. The crew's existing step limit bounds the whole plan. B's
pause and Stop/Ctrl+Alt+Q stop it between and inside steps, since every tool takes the desktop lease.

`tools.py` gets **no edits**: the new tools register from their own module, `computer/pointer.py`, which is imported by
the kit loader. One line in the Desk persona (crew/bots.py, Sourabh's) says when to use them. I'll ask first.

## 4. Safety
- **Every action takes the desktop lease**, so B's pause applies, and Stop/Ctrl+Alt+Q cancel it, mid-plan included.
- **Clicks go through `risk.click_risk(name, where)` + `gate`:**
  - The name is the UIA name of the target or of what is under the point.
  - For OCR hits it is the OCR text.
  - **A raw point with no name inside a mail, chat, browser or shop window → an approval card (ASK).**
  - Send, Buy, Pay, Delete, Post and the other existing risky words get a card as today.
- **Drag inside File Explorer** (moves files) → card. Scroll is safe.
- **Typing stays in `type_text` / `ui_act`**, which keep `type_risk`: no passwords or keys.
- **OCR text is redacted** (`keys.redact`) before it reaches the model. Screenshots stay local.
- **Free models only.** Vision is used only if a free key (Gemini) or a local Ollama vision model is present; otherwise it is skipped.

Risks:
- **OCR misreads small text.** Mitigation: OCR at 2x scale for small windows, line-level fuzzy match, and verify after the click.
- **Electron apps without accessibility.** OCR handles text buttons; icon-only buttons need vision (step 5, if there's time).
- **Clicking the wrong place.** Mitigation: physical-pixel maths everywhere, `element_at` before clicking, verify after.
- **PowerShell OCR latency (~1-2 s a call).** It's only used when the tree has nothing.

## 5. Build order and tests (Sourabh's order)
1. `mouse.py` + tests (coordinate maths, normalisation, multi-monitor offsets with fake metrics).
2. `ground.py` UIA find + `click_on`, with tests on fake trees.
3. `verify.py` + `expect`/retry/dialog detection.
4. OCR fallback (PowerShell WinRT), with tests on a rendered image.
5. Vision fallback, only if time is left.

**Live tests in `computer-use-yang.md`, a screenshot and log for each:**
- Calculator 12+30 by name
- Notepad Save As through the menus and the dialog
- Settings > System > Display
- Explorer > Documents
- Paint: click and drag
- an app with a weak tree, via OCR
- the safety trio: card, mouse pause, Ctrl+Alt+Q
