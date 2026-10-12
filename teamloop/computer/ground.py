"""Find a control by what it is ("the Save button", "Seven", "Documents"): UI Automation first, OCR second.

UIA searches the window and every other window of the same program (menus and dialogs like Save As open as
their own windows). OCR (Windows.Media.Ocr, built in and free, run through Windows PowerShell 5.1 because it
can load WinRT) reads a screenshot of the window when the tree has nothing, e.g. canvases and many Electron apps.
Coordinates are physical pixels (mouse.py makes the process DPI aware).
"""

from __future__ import annotations

import difflib
import json
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from teamloop.computer import mouse  # noqa: F401  (DPI awareness before any rect is read)

ROLES = {"button": "Button", "btn": "Button", "box": "Edit", "field": "Edit", "textbox": "Edit", "input": "Edit",
         "link": "Hyperlink", "tab": "TabItem", "menu": "MenuItem", "checkbox": "CheckBox", "check": "CheckBox",
         "radio": "RadioButton", "dropdown": "ComboBox", "combo": "ComboBox", "list": "List", "folder": "ListItem",
         "file": "ListItem", "item": None, "option": None}
FILLER = {"the", "a", "an", "on", "in", "named", "called", "labelled", "labeled", "icon"}
DEPTH = 14


@dataclass
class Hit:
    name: str
    x: int                       # centre, physical pixels
    y: int
    box: tuple[int, int, int, int]
    how: str                     # "uia" or "ocr"
    role: str = ""
    score: float = 0.0
    element: object = field(default=None, repr=False)   # the pywinauto wrapper when found through UIA

    def public(self) -> dict:
        return {"name": self.name, "x": self.x, "y": self.y, "box": list(self.box), "how": self.how,
                "role": self.role}


def norm(text: str) -> str:
    text = re.sub(r"&(?=\w)", "", text or "")            # menu accelerators: "&File" -> "File"
    return re.sub(r"[^\w+%.=\-]+", " ", text.lower()).strip()


def parse_target(target: str) -> tuple[str, str | None]:
    """'the Save button' -> ('save', 'Button'); 'Seven' -> ('seven', None)."""
    words = norm(target).split()
    role = None
    if len(words) > 1 and words[-1] in ROLES:
        role = ROLES[words.pop()]
    elif len(words) > 1 and words[0] in ROLES and ROLES[words[0]]:
        role = ROLES[words.pop(0)]
    words = [w for w in words if w not in FILLER] or words
    return " ".join(words), role


def _raw_words(target: str) -> str:
    """The target as typed, minus filler and a trailing role word: 'the Documents folder' -> 'Documents'."""
    words = [w for w in re.sub(r"[^\w+%.=\- ]", " ", target).split() if w.lower() not in FILLER]
    if len(words) > 1 and words[-1].lower() in ROLES:
        words.pop()
    return " ".join(words)


def score(name: str, auto_id: str, role_of: str, want: str, role: str | None, want_raw: str = "") -> float:
    n, a = norm(name), norm(auto_id)
    if not want or not (n or a):
        return 0.0
    if n == want:
        s = 100.0
    elif a == want or a.replace(" ", "") == want.replace(" ", ""):
        s = 90.0
    elif n.startswith(want + " ") or n.startswith(want):
        s = 75.0 if len(want) >= 3 else 0.0
    elif re.search(rf"\b{re.escape(want)}\b", n):
        s = 60.0
    elif all(w in n.split() for w in want.split()):
        s = 50.0
    else:
        ratio = difflib.SequenceMatcher(None, n, want).ratio()
        s = 45.0 * ratio if ratio >= 0.8 else 0.0
    if s and role:
        s += 15 if role_of == role else -30
    if s and want_raw and (name or "").strip() == want_raw:
        s += 3                           # "Documents" beats "documents"
    if s and role_of in ACTIONABLE:
        s += 2                           # a button or item beats a label with the same words
    return max(s, 0.0)


ACTIONABLE = {"Button", "MenuItem", "TreeItem", "ListItem", "TabItem", "Hyperlink", "CheckBox", "RadioButton",
              "SplitButton", "ComboBox", "DataItem", "Edit"}


# ---- UI Automation ---------------------------------------------------------------------------------
MENU_OR_DIALOG = {"#32768", "#32770"}  # popup menus, standard dialogs (Save As, message boxes)


def _owner(handle: int) -> int:
    import ctypes
    return ctypes.windll.user32.GetWindow(handle, 4) or 0  # GW_OWNER


def _windows_of_program(hwnd: int):
    """The window plus the menus and dialogs it opened: windows it owns, or popup menus of the same program.
    Never the program's other windows: File Explorer's process also runs the taskbar and the desktop icons."""
    from pywinauto import Desktop

    desk = Desktop(backend="uia")
    first = desk.window(handle=hwnd).wrapper_object()
    pid = first.process_id()
    others = []
    for w in desk.windows(process=pid, visible_only=True):
        if w.handle == hwnd:
            continue
        try:
            if _owner(w.handle) == hwnd or w.class_name() == "#32768":
                others.append(w)
        except Exception:
            continue
    return [first, *others]


def find_uia(hwnd: int, target: str, min_score: float = 50) -> Hit | None:
    """Best match in the window and the program's other windows (menus, dialogs). Runs on the COM thread."""
    want, role = parse_target(target)
    raw = _raw_words(target)
    best: Hit | None = None
    for top in _windows_of_program(hwnd):
        for el in [top, *top.descendants(depth=DEPTH)]:
            info = el.element_info
            s = score(info.name or "", getattr(info, "automation_id", "") or "", info.control_type or "", want, role,
                      raw)
            if s < min_score or (best and s <= best.score):
                continue
            try:
                if not el.is_visible():
                    continue
                r = el.rectangle()
            except Exception:
                continue
            if r.width() <= 0 or r.height() <= 0:
                continue
            best = Hit((info.name or "").strip(), (r.left + r.right) // 2, (r.top + r.bottom) // 2,
                       (r.left, r.top, r.right, r.bottom), "uia", info.control_type or "", s, el)
            if s >= 115:   # exact name and the right role: nothing beats it
                return best
    return best


def visible_names(hwnd: int, limit: int = 150) -> list[str]:
    """Names of the visible controls in the window and its program's other windows (for before/after checks)."""
    out: list[str] = []
    for top in _windows_of_program(hwnd):
        out.append(f"[window] {top.window_text()}")
        for el in top.descendants(depth=DEPTH):
            name = (el.element_info.name or "").strip()
            if name and len(out) < limit:
                try:
                    if el.is_visible():
                        out.append(name[:80])
                except Exception:
                    continue
    return out


# ---- OCR ---------------------------------------------------------------------------------------------
OCR_SCRIPT = r"""
param([string]$Path)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
  $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($op, [Type]$t) { $task = $asTask.MakeGenericMethod($t).Invoke($null, @($op)); $task.Wait(-1) | Out-Null; $task.Result }
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics, ContentType = WindowsRuntime]
$file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($Path)) ([Windows.Storage.StorageFile])
$stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
$decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
$bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
$result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
$lines = foreach ($line in $result.Lines) {
  $words = foreach ($w in $line.Words) { @{ t = $w.Text; x = [int]$w.BoundingRect.X; y = [int]$w.BoundingRect.Y; w = [int]$w.BoundingRect.Width; h = [int]$w.BoundingRect.Height } }
  @{ text = $line.Text; words = @($words) }
}
$stream.Dispose()
ConvertTo-Json -InputObject @($lines) -Depth 5 -Compress
"""


def _ocr_script() -> Path:
    path = Path(tempfile.gettempdir()) / "teamloop-ocr.ps1"
    if not path.exists() or path.read_text(encoding="utf-8") != OCR_SCRIPT:
        path.write_text(OCR_SCRIPT, encoding="utf-8")
    return path


def ocr_image(path: Path) -> list[dict]:
    """[{text, words: [{t, x, y, w, h}]}] in the image's pixels."""
    done = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(_ocr_script()),
                           "-Path", str(path)], capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=30, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if done.returncode != 0:
        raise RuntimeError("Windows OCR failed: " + (done.stderr or done.stdout).strip()[-300:])
    out = (done.stdout or "").strip()
    return json.loads(out) if out else []


def grab(box: tuple[int, int, int, int]) -> tuple[Path, float]:
    """Screenshot of a physical-pixel box; small ones are doubled so OCR reads small text. Returns (png, scale)."""
    from PIL import ImageGrab

    img = ImageGrab.grab(bbox=box, all_screens=True)
    scale = 2.0 if img.height < 700 else 1.0
    if scale != 1.0:
        img = img.resize((int(img.width * scale), int(img.height * scale)))
    path = Path(tempfile.gettempdir()) / "teamloop-ocr.png"
    img.save(path)
    return path, scale


def read_box(box: tuple[int, int, int, int]) -> list[dict]:
    """OCR lines in a screen box, with word boxes in screen pixels."""
    path, scale = grab(box)
    lines = ocr_image(path)
    for line in lines:
        for w in line.get("words") or []:
            w["x"] = box[0] + round(w["x"] / scale)
            w["y"] = box[1] + round(w["y"] / scale)
            w["w"], w["h"] = round(w["w"] / scale), round(w["h"] / scale)
    return lines


def find_in_lines(lines: list[dict], target: str, min_score: float = 50) -> Hit | None:
    """The best run of consecutive OCR words matching the target."""
    want, _ = parse_target(target)
    n = len(want.split()) or 1
    best: Hit | None = None
    for line in lines:
        words = line.get("words") or []
        for size in {n, n + 1}:
            for i in range(0, max(len(words) - size + 1, 0)):
                run = words[i:i + size]
                text = " ".join(w["t"] for w in run)
                s = score(text, "", "", want, None)
                if s >= min_score and (best is None or s > best.score):
                    left, top = min(w["x"] for w in run), min(w["y"] for w in run)
                    right = max(w["x"] + w["w"] for w in run)
                    bottom = max(w["y"] + w["h"] for w in run)
                    best = Hit(text, (left + right) // 2, (top + bottom) // 2, (left, top, right, bottom), "ocr",
                               "", s)
    return best
