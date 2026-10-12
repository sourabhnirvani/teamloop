# N: Advanced computer use, live results (jrkrishh, Mon 12 Oct ~07:40 IST)

Design: `computer-use-design-yang.md`.

- **What was built:**
  - `teamloop/computer/__init__.py` (per-monitor-v2 DPI, set once, read back)
  - `mouse.py` (SendInput on the virtual desktop)
  - `ground.py` (UIA find by meaning, plus Windows OCR)
  - `verify.py` (before/after looks)
  - `pointer.py` (the tools `click_on`, `mouse`, `find_on_screen`)
- **Wiring:** registered in the computer kit (`kits.py`), with a 4-line "how to drive an app" block in Desk's persona.
  `ui_snapshot`'s description now points at `click_on`.

**Tests:** `tests/test_pointer.py`, 9 tests:
- coordinates with a monitor left of the primary
- drag path
- target parsing
- score order (exact > starts with > contains > fuzzy, the right role, case-exact)
- OCR word runs
- risk on raw points including the label around them
- a retitle vs a new dialog
- the ring on the card
- Stop during a `click_on` retry

Full suite: 292 passed, 1 skipped.

**Live:** run on this laptop with `evidence/runs/computer-use-live-yang.py`. It goes through the real tool path
(`registry.run` → risk → card → desktop lease and operator pause → act → verify). The full log is in
`computer-use-live-yang.out.txt`; folder names are hidden in the log, and the Explorer picture's pinned folders are
blurred. Screenshots are of the app window only, never the desktop.

| # | Test | Result | Tries | What happened | Picture |
|---|---|---|---|---|---|
| 1 | Calculator 12+30 by clicking buttons by name, read the result | **PASS** | 8 | One, Two, Plus, Three, Zero via the Invoke pattern; Equals with `expect="Display is 42"` → shown. 8 tool tries for 7 clicks: "Clear" on an already-0 display honestly reported "nothing changed" and retried once | `evidence/ui/cu-calc-yang.png` |
| 2 | Notepad: type, File > Save As through the menus and the dialog | **PASS** | 4 | File (menu) → "Save As..." (`expect="File name"`) → the dialog's File name box (focus) → path typed → "Save". The file is on disk, 40 bytes | `cu-notepad-yang.png` |
| 3 | Settings: System > Display | **PASS** | 2 | System (`expect="Display"`), Display (`expect="Scale"`, via Select) | `cu-settings-yang.png` |
| 4 | File Explorer: Documents, open a folder | **PASS** on the 3rd run | 3 | Documents (nav tree) → the window is retitled "Documents" → double-click "TeamLoop live test" → retitled to it. **The first two runs failed and found 2 real bugs, both fixed:** (a) the search took in every window of the program, and explorer.exe also runs the taskbar and desktop, so it clicked a **desktop icon** named "documents". Now it searches the window plus windows it owns and popup menus. (b) A tree item got Expand instead of Select. A third finding is for Sourabh: `files.known_folder("Documents")` prefers OneDrive\Documents, but Explorer's Documents here is `C:\Users\BCE\Documents` | `cu-explorer-yang.png` |
| 5 | Paint: click at a point, drag a line (no tree on the canvas) | **PASS** | 2 | Pencil (by name), then `mouse` click at (300,350) and drag (320,380)→(620,480) in window coordinates. Pixels changed; the dot and line are visible, and the line stops at the canvas's right edge | `cu-paint-yang.png` |
| 6 | Low-accessibility app: a page drawn on a `<canvas>` in Edge (the button doesn't exist in the tree) | **PASS** | 1 | `find_on_screen` and `click_on` found "Start game" **by OCR**, clicked with the real mouse, and `expect="Game started"` was confirmed by OCR | `cu-ocr-yang.png` |
| 7a | Safety: an unnamed "Delete all" icon (canvas) gets a card with a ring | **PASS** | 1 | UIA had no name at the point; OCR of the 220x44 box around it read "Delete all" → `click_risk` = ask → card "Mouse: click at (534, 357) on "Delete all"", with a red ring with a white halo on the card's picture. Deny → not clicked; the canvas still says "Delete all" | `cu-safety-card-ring-yang.png` |
| 7b | Safety: the person moving the mouse pauses a click | **PASS** | 1 | A second process moved the real mouse for 4 s; `click_on "Five"` waited and finished after 8.4 s (3 quiet seconds after the mouse stopped). The display shows 5 | - |
| 7c | Safety: Stop mid-plan | **PASS 3/3** after a harness fix (1 FAIL in the full run, explained) | 1 | A real crew run (Desk's model asked for `click_on "Nine"`) was paused by the moving mouse; `POST /api/stop-all` (what Ctrl+Alt+Q calls; the hotkey itself was proven live in B) stopped `dm-desk`, and after the quiet seconds the display was still 0. **In the full run it FAILED once:** the scripted model answers instantly, so the click started before the second process had moved the mouse, the pause never began, and 9 was pressed. The harness now starts the "person" 0.7 s before the job. This shows a real limit: the pause is checked **when each screen action starts**, not continuously during one. 3 reruns: PASS, PASS, PASS (`computer-use-live-yang.safety-c-reruns.txt`) | - |
| 8 | The existing tools under per-monitor DPI | **PASS** | 1 | `screenshot`, `window_state` minimize/restore, `ui_snapshot` + `ui_act` click "Eight", and the card picture is 418x675, exactly the physical window rect | - |

## Not done (time)
- **Vision-model fallback** (step 5 of the build order). OCR covered test 6. Icon-only buttons with no text still need
  it, or a coordinate from the person.
- **The pause is checked per action.** A person who starts using the mouse in the middle of a long drag isn't detected
  until the next action.
