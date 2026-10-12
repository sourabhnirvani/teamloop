"""N live tests on this laptop, through the real tool path (registry.run -> risk -> lease -> act -> verify).

    .venv\\Scripts\\python.exe evidence\\runs\\computer-use-live-yang.py [test ...]   (calc notepad settings explorer paint ocr)

Each test prints every tool call and its answer, and saves a screenshot of just that app's window in
evidence/ui/cu-<test>-yang.png (never the whole desktop). Approval cards are answered by this script and logged.
"""

import asyncio
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from PIL import Image, ImageGrab  # noqa: E402

from teamloop import kits  # noqa: E402
from teamloop.computer import pointer, winapi  # noqa: E402
from teamloop.tools import registry  # noqa: E402

kits.load_all()
import teamloop.computer.pointer  # noqa: E402,F401  (until kits.py lists it)

RESULTS = []


class Ctx:
    bot_id, chat_id, last_answer = "desk", "live", ""

    def __init__(self, answer=True):
        self.answer, self.cards = answer, []

    async def emit(self, type_, **data):      # tools that post a picture into the chat
        print(f"      [chat event] {type_}: {', '.join(data)}")

    async def approve(self, title, details, screenshot=None, key=None):
        self.cards.append(title)
        print(f"      [approval card] {title}: {details[:90]} -> {'Approve' if self.answer else 'Deny'}")
        return self.answer


async def call(name, ctx=None, **args):
    t = time.time()
    r = await registry.run(name, args, ctx or Ctx())
    print(f"   {name}({', '.join(f'{k}={v!r}' for k, v in args.items())}) -> {'OK' if r.ok else 'FAIL'} "
          f"in {time.time() - t:.1f}s: {r.text[:220]}")
    return r


def wait_window(match, seconds=15):
    end = time.time() + seconds
    while time.time() < end:
        for w in winapi.windows():
            if match(w.title):
                return w
        time.sleep(0.4)
    return None


def shot(win, name):
    path = ROOT / "evidence" / "ui" / f"cu-{name}-yang.png"
    time.sleep(0.5)
    ImageGrab.grab(bbox=pointer.visible_rect(win.hwnd), all_screens=True).save(path)
    return path.name


def verdict(test, ok, tries, note, image):
    RESULTS.append((test, ok, tries, note, image))
    print(f"==> {test}: {'PASS' if ok else 'FAIL'} ({tries} tr{'y' if tries == 1 else 'ies'}) {note} [{image}]\n")


async def calc():
    print("1. Calculator: 12+30 by clicking buttons by name, then read the result")
    subprocess.Popen("start calc", shell=True)
    win = wait_window(lambda t: t == "Calculator")
    await asyncio.sleep(1.5)
    tries = 0
    for target in ["Clear", "One", "Two", "Plus", "Three", "Zero"]:
        r = await call("click_on", window="Calculator", target=target)
        tries += r.data.get("tries", 1)
    r = await call("click_on", window="Calculator", target="Equals", expect="Display is 42")
    tries += r.data.get("tries", 1)
    read = await call("find_on_screen", window="Calculator", text="Display is")
    image = shot(win, "calc")
    ok = r.ok and "42" in (read.data.get("found") or {}).get("name", "")
    verdict("Calculator 12+30", ok, tries, f"display: {(read.data.get('found') or {}).get('name')}", image)
    winapi.close(win.hwnd)


async def notepad():
    print("2. Notepad: type text, then File > Save As through the menus and the dialog")
    target = Path(__import__("tempfile").gettempdir()) / f"teamloop-live-{int(time.time())}.txt"
    subprocess.Popen("start notepad", shell=True)
    win = wait_window(lambda t: t.endswith("- Notepad"))
    await asyncio.sleep(1.0)
    tries = 0
    await call("type_text", window="Notepad", text="Typed by TeamLoop's Desk in a live test.")
    r = await call("click_on", window="Notepad", target="File menu", expect="Save As")
    tries += r.data.get("tries", 1)
    r = await call("click_on", window="Notepad", target="Save As", expect="File name")
    tries += r.data.get("tries", 1)
    dialog = wait_window(lambda t: t == "Save As", 8)
    r = await call("click_on", window="Save As", target="File name box", action="focus")
    tries += r.data.get("tries", 1)
    await call("press_keys", window="Save As", keys="ctrl+a")
    await call("type_text", window="Save As", text=str(target))
    r = await call("click_on", window="Save As", target="Save button")
    tries += r.data.get("tries", 1)
    await asyncio.sleep(1.0)
    win = wait_window(lambda t: target.name in t, 8) or win
    image = shot(win, "notepad")
    saved = target.exists() and "live test" in target.read_text(encoding="utf-8", errors="replace")
    verdict("Notepad Save As", saved and dialog is not None, tries,
            f"file on disk: {target.name} ({target.stat().st_size if target.exists() else 0} bytes), "
            f"title now \"{win.title}\"", image)
    winapi.close(win.hwnd)


async def settings():
    print("3. Settings: System > Display")
    subprocess.Popen("start ms-settings:", shell=True)
    win = wait_window(lambda t: t == "Settings")
    await asyncio.sleep(2.5)
    tries = 0
    r1 = await call("click_on", window="Settings", target="System", expect="Display")
    tries += r1.data.get("tries", 1)
    r2 = await call("click_on", window="Settings", target="Display", expect="Scale")
    tries += r2.data.get("tries", 1)
    image = shot(win, "settings")
    verdict("Settings > System > Display", r1.ok and r2.ok, tries, r2.text[:120], image)
    winapi.close(win.hwnd)


async def explorer():
    import os
    from teamloop.tools.files import known_folder
    print("4. File Explorer: go to Documents and open a folder")
    docs = Path(subprocess.run(["powershell.exe", "-NoProfile", "-Command", "[Environment]::GetFolderPath('MyDocuments')"],
                               capture_output=True, text=True).stdout.strip())   # where Explorer's Documents points
    folder = "TeamLoop live test"          # a throwaway folder, so no real folder names land in the evidence
    (docs / folder).mkdir(exist_ok=True)
    subprocess.Popen("explorer.exe", shell=True)
    win = wait_window(lambda t: t in ("File Explorer", "Home", "Quick access", "This PC"))
    await asyncio.sleep(2.0)
    tries = 0
    r1 = await call("click_on", window=win.title, target="Documents")
    tries += r1.data.get("tries", 1)
    await asyncio.sleep(1.0)
    win = wait_window(lambda t: t == "Documents", 6) or win
    r2 = await call("click_on", window="Documents", target=folder, action="double_click") if folder else None
    tries += r2.data.get("tries", 1) if r2 else 0
    await asyncio.sleep(1.0)
    opened = wait_window(lambda t: t == folder, 6) if folder else None
    image = shot(opened or win, "explorer")
    verdict("Explorer > Documents > a folder", bool(r1.ok and opened), tries,
            f"opened \"{folder}\" -> window \"{(opened or win).title}\"", image)
    winapi.close((opened or win).hwnd)
    await asyncio.sleep(1.0)
    (docs / folder).rmdir()


async def paint():
    from PIL import ImageChops
    print("5. Paint: click at a point, then drag a line (canvas: no accessibility tree, coordinates only)")
    subprocess.Popen("start mspaint", shell=True)
    win = wait_window(lambda t: t.endswith("- Paint"))
    await asyncio.sleep(2.5)
    await call("click_on", window="Paint", target="Pencil")
    box = pointer.visible_rect(win.hwnd)
    before = ImageGrab.grab(bbox=box, all_screens=True)
    r1 = await call("mouse", window="Paint", action="click", x=300, y=350)
    r2 = await call("mouse", window="Paint", action="drag", x=320, y=380, to_x=620, to_y=480)
    after = ImageGrab.grab(bbox=box, all_screens=True)
    diff = ImageChops.difference(before.convert("RGB"), after.convert("RGB")).getbbox()
    image = shot(win, "paint")
    verdict("Paint click + drag", bool(r1.ok and r2.ok and diff), 2,
            f"pixels changed inside window box {diff} (dot at 300,350, line 320,380 -> 620,480)", image)
    subprocess.run(["taskkill", "/IM", "mspaint.exe", "/F"], capture_output=True)  # skip "save changes?"


CANVAS_PAGE = """<!doctype html><title>Canvas only</title><body style="margin:0;background:#fff">
<canvas id=c width=900 height=500></canvas><script>
const c=document.getElementById('c'),g=c.getContext('2d');
function draw(t,bg){g.fillStyle='#fff';g.fillRect(0,0,900,500);g.fillStyle=bg;g.fillRect(300,200,300,90);
g.fillStyle='#fff';g.font='bold 36px Segoe UI';g.fillText(t,330,258);}
draw('Start game','#2b6cf6');
c.onclick=e=>{if(e.offsetX>300&&e.offsetX<600&&e.offsetY>200&&e.offsetY<290)draw('Game started','#1a9b4b');};
</script>"""


async def ocr():
    print("6. Low-accessibility app: a page drawn on a <canvas> in Edge (no button in the tree). Find it by OCR")
    page = Path(__import__("tempfile").gettempdir()) / "teamloop-canvas.html"
    page.write_text(CANVAS_PAGE, encoding="utf-8")
    subprocess.Popen(["cmd", "/c", "start", "msedge", "--new-window", f"--app={page.as_uri()}"])
    win = wait_window(lambda t: t.startswith("Canvas only"))
    await asyncio.sleep(2.5)
    tree = await call("find_on_screen", window="Canvas only", text="Start game")
    r = await call("click_on", window="Canvas only", target="Start game", expect="Game started")
    image = shot(win, "ocr")
    found_by = (r.data.get("found") or {}).get("how")
    verdict("Canvas button via OCR", r.ok and found_by == "ocr", r.data.get("tries", 1),
            f"found by {found_by}; {r.text[:100]}", image)
    winapi.close(win.hwnd)


DELETE_PAGE = CANVAS_PAGE.replace("Canvas only", "Canvas delete").replace("'Start game','#2b6cf6'", "'Delete all','#c62828'") \
    .replace("draw('Game started','#1a9b4b')", "draw('Deleted!','#555')")
JIGGLE = ("import ctypes,time\nu=ctypes.windll.user32\nend=time.time()+{s}\nwhile time.time()<end:\n"
          " u.mouse_event(1,1,0,0,0);time.sleep(0.1);u.mouse_event(1,-1,0,0,0);time.sleep(0.1)\n")


async def calc_display():
    from teamloop.computer import com, ground   # UI Automation only on the COM thread
    w = wait_window(lambda t: t == "Calculator", 2)
    h = await com.run(ground.find_uia, w.hwnd, "Display is") if w else None
    return h.name if h else "?"


async def safety():
    import shutil
    from teamloop.computer import uia
    print("7. Safety: (a) a card with a red ring for an unnamed 'Delete all' icon, (b) moving the mouse pauses a "
          "click, (c) Stop mid-plan through /api/stop-all")
    # (a) card + ring, denied
    page = Path(__import__("tempfile").gettempdir()) / "teamloop-canvas-delete.html"
    page.write_text(DELETE_PAGE, encoding="utf-8")
    subprocess.Popen(["cmd", "/c", "start", "msedge", "--new-window", f"--app={page.as_uri()}"])
    win = wait_window(lambda t: t.startswith("Canvas delete"))
    await asyncio.sleep(2.5)
    found = await call("find_on_screen", window="Canvas delete", text="Delete all")
    f = found.data["found"]
    left, top = pointer.visible_rect(win.hwnd)[:2]
    ctx = Ctx(answer=False)
    shots_before = set(uia.shots_dir().glob("*.png"))
    r = await call("mouse", ctx, window="Canvas delete", action="click", x=f["x"] - left, y=f["y"] - top)
    card = sorted(set(uia.shots_dir().glob("*.png")) - shots_before, key=lambda p: p.stat().st_mtime)
    if card:
        shutil.copy(card[-1], ROOT / "evidence" / "ui" / "cu-safety-card-ring-yang.png")
    still = await call("find_on_screen", window="Canvas delete", text="Delete all")
    ok_a = bool(ctx.cards) and not r.ok and still.ok
    verdict("Safety (a): card with ring, denied, nothing clicked", ok_a, 1,
            f"card: {ctx.cards}; canvas still says 'Delete all': {still.ok}", "cu-safety-card-ring-yang.png")
    winapi.close(win.hwnd)

    # (b) the person moves the mouse: the click waits, then goes ahead by itself
    subprocess.Popen("start calc", shell=True)
    wait_window(lambda t: t == "Calculator")
    await asyncio.sleep(1.5)
    await call("click_on", window="Calculator", target="Clear")
    person = subprocess.Popen([sys.executable, "-c", JIGGLE.format(s=4)])
    t0 = time.time()
    await asyncio.sleep(0.7)               # the person is really moving the mouse before the click is asked for
    r = await call("click_on", window="Calculator", target="Five", expect="Display is 5")
    waited = time.time() - t0
    person.wait()
    ok_b = r.ok and waited >= 5.5
    verdict("Safety (b): mouse moving pauses the click", ok_b, r.data.get("tries", 1),
            f"the person moved the mouse for 4 s; the click finished after {waited:.1f} s; display {await calc_display()}", "-")

    # (c) a real crew run: Desk's model asks for click_on; Stop arrives (POST /api/stop-all, what Ctrl+Alt+Q calls)
    sys.path.insert(0, str(ROOT / "tests"))
    from fakes import FakeRouter, call as tool_call
    from fastapi.testclient import TestClient
    from teamloop.server.app import build_crew, create_app
    await call("click_on", window="Calculator", target="Clear")
    crew = build_crew(Path(__import__("tempfile").mkdtemp()) / "c.db",
                      router=FakeRouter([tool_call("click_on", window="Calculator", target="Nine"), "Done."]))
    person = subprocess.Popen([sys.executable, "-c", JIGGLE.format(s=5)])
    await asyncio.sleep(0.7)               # the person is already moving the mouse when the job starts
    with TestClient(create_app(crew)) as client:
        client.post("/api/chats/dm-desk/messages", json={"text": "press nine on the calculator"})
        await asyncio.sleep(1.5)
        paused = client.get("/api/operator").json()["paused"]
        stop = client.post("/api/stop-all").json()
        person.wait()
        await asyncio.sleep(4.5)       # the 3 quiet seconds pass: a click that survived the stop would land now
    display = await calc_display()
    ok_c = paused and "dm-desk" in stop["stopped"] and display == "Display is 0"
    verdict("Safety (c): Stop mid-plan (while paused)", ok_c, 1,
            f"paused before Stop: {paused}; stop-all: {stop['stopped']}; display after: {display}", "-")
    image = shot(wait_window(lambda t: t == "Calculator"), "safety-calc")
    winapi.close(wait_window(lambda t: t == "Calculator").hwnd)


async def existing():
    print("8. The existing tools still behave with per-monitor DPI (screenshot, window_state, ui_act, card picture)")
    from teamloop.computer import tools as desk
    subprocess.Popen("start calc", shell=True)
    win = wait_window(lambda t: t == "Calculator")
    await asyncio.sleep(1.5)
    s = await call("screenshot", window="Calculator")
    m1 = await call("window_state", window="Calculator", state="minimize")
    m2 = await call("window_state", window="Calculator", state="restore")
    snap = await call("ui_snapshot", window="Calculator")
    eight = next(c["i"] for c in snap.data["controls"] if c["name"] == "Eight")
    a = await call("ui_act", window="Calculator", index=eight, action="click")
    url = desk._shot_url(win.hwnd)
    from teamloop.computer import uia
    card = Image.open(uia.shots_dir() / url.rsplit("/", 1)[1]) if url else None
    x0, y0, x1, y1 = winapi.rect(win.hwnd)
    print(f"   card picture {card.size if card else None} vs window rect {x1 - x0}x{y1 - y0} (physical)")
    ok = s.ok and m1.ok and m2.ok and a.ok and "8" in await calc_display() and card is not None and \
        abs(card.size[0] - (x1 - x0)) <= 2
    verdict("Existing tools under per-monitor DPI", ok, 1, f"display {await calc_display()}", "-")
    winapi.close(win.hwnd)


TESTS = {"calc": calc, "notepad": notepad, "settings": settings, "explorer": explorer, "paint": paint, "ocr": ocr,
         "safety": safety, "existing": existing}

if __name__ == "__main__":
    wanted = sys.argv[1:] or list(TESTS)
    for name in wanted:
        asyncio.run(TESTS[name]())
    print("SUMMARY")
    for test, ok, tries, note, image in RESULTS:
        print(f"  {'PASS' if ok else 'FAIL'} | {test} | tries {tries} | {note} | {image}")
