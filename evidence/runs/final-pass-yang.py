"""Final regression pass: HANDOFF section 6 debug rows against the REAL app (desktop app's server on :8790, real free
model keys), through its HTTP API. Each row posts a message, answers approval cards as the row needs, waits for the
crew to finish, and prints PASS/FAIL with what came back.

    .venv\\Scripts\\python.exe evidence\\runs\\final-pass-yang.py [row ...]     rows: 6 9 10 11 14 15
"""

import json
import os
import sys
import time
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8790"
c = httpx.Client(base_url=BASE, timeout=60)
ROOT = Path(__file__).resolve().parents[2]
TMP = Path(os.environ.get("TEMP", "C:/Windows/Temp")) / "teamloop-final-pass"
RESULTS = []


def say(chat, text):
    before = len(c.get(f"/api/chats/{chat}/messages").json())
    c.post(f"/api/chats/{chat}/messages", json={"text": text})
    return before


def wait_done(chat, since, seconds=150, answer=None):
    """Wait until the crew is idle in `chat`; answer=callable(card)->bool|None answers cards (None leaves them)."""
    cards = []
    end = time.time() + seconds
    while time.time() < end:
        for card in c.get("/api/approvals").json():
            if card["chat_id"] == chat and card["id"] not in [x["id"] for x in cards]:
                cards.append(card)
                verdict = answer(card) if answer else None
                if verdict is not None:
                    c.post(f"/api/approvals/{card['id']}", json={"ok": verdict})
        state = c.get("/api/state").json()
        busy = state.get("typing", {}).get(chat) or any(a["chat_id"] == chat for a in state.get("approvals", []))
        msgs = c.get(f"/api/chats/{chat}/messages").json()[since:]
        if msgs and not busy and msgs[-1]["sender"] != "user":
            time.sleep(2)
            state = c.get("/api/state").json()
            if not state.get("typing", {}).get(chat):
                return msgs, cards
        time.sleep(1)
    return c.get(f"/api/chats/{chat}/messages").json()[since:], cards


def note(row, ok, what, msgs, cards):
    lines = [f"{m['sender']}[{m['kind']}]: {m['text'][:160]}".replace("\n", " ") for m in msgs]
    RESULTS.append({"row": row, "ok": ok, "what": what, "messages": lines, "cards": [x["title"] for x in cards]})
    print(f"\n== row {row}: {'PASS' if ok else 'FAIL'}: {what}")
    for line in lines:
        print("   ", line)
    print("    cards:", [x["title"] for x in cards])


def row6():
    since = say("dm-scout", "open notepad")
    msgs, cards = wait_done("dm-scout", since, 90)
    bots = {b["name"].lower() for b in c.get("/api/bots").json()}
    text = " ".join(m["text"] for m in msgs)
    invented = "operator" in text.lower() and "operator" not in bots
    ok = not invented and ("desk" in text.lower() or any(m["sender"] == "desk" for m in msgs))
    note(6, ok, "a worker that can't do it names a real teammate (Desk), never an invented one", msgs, cards)
    for w in c.get("/api/bots").json():
        pass


def make_victim(name):
    TMP.mkdir(exist_ok=True)
    f = TMP / name
    f.write_text("final pass test file", encoding="utf-8")
    return f


def row9_10():
    victim = make_victim("row9.txt")
    since = say("dm-desk", f"delete the file {victim}")
    msgs1, cards1 = wait_done("dm-desk", since, 120, answer=lambda card: False)
    reply = msgs1[-1]["text"] if msgs1 else ""
    ok10 = bool(cards1) and not reply.startswith("Failed") and victim.exists()
    note(10, ok10, "after a deny the reply is plain ('You said no…'), not 'Failed:'; the file is still there", msgs1, cards1)
    since = say("dm-desk", f"please remove {victim} from that folder")
    msgs2, cards2 = wait_done("dm-desk", since, 120, answer=lambda card: False)
    ok9 = not cards2 and victim.exists()
    note(9, ok9, "a rephrased retry of something just denied doesn't raise a new card", msgs2, cards2)


def row11():
    victim = make_victim("row11.txt")
    since = say("dm-desk", f"delete the file {victim}")
    t0 = time.time()
    msgs, cards = wait_done("dm-desk", since, 220, answer=lambda card: None)   # nobody answers
    text = " ".join(m["text"] for m in msgs)
    ok = len(cards) == 1 and victim.exists() and "{username}" not in text
    note(11, ok, f"an unanswered card expires (~2 min) and counts as a no: one card only, no retry "
                 f"({time.time() - t0:.0f} s)", msgs, cards)


def notepad_text():
    from pywinauto import Desktop
    for w in Desktop(backend="uia").windows():
        if w.window_text().endswith("Notepad"):
            try:  # Notepad's edit box gives its text through LegacyIAccessible's Value
                edit = w.descendants(control_type="Edit")[0]
                return edit.legacy_properties().get("Value", ""), w
            except Exception:
                return "", w
    return None, None


def row14_15():
    since = say("dm-desk", "open notepad and type hello from the final pass")
    msgs, cards = wait_done("dm-desk", since, 150, answer=lambda card: True)
    text, win = notepad_text()
    ok14 = text is not None and "hello from the final pass" in (text or "").lower()
    note(14, ok14, f"Notepad opened and the text is really in it (read back: {text!r})", msgs, cards)
    since = say("dm-desk", "close notepad without saving")
    msgs, cards = wait_done("dm-desk", since, 150, answer=lambda card: True)
    time.sleep(1.5)
    still, _ = notepad_text()
    ok15 = still is None and not any("No open window matches" in m["text"] for m in msgs)
    note(15, ok15, "'close notepad without saving' is understood (not read as an app called 'notepad without "
                   "saving'), asks first, and Notepad is gone", msgs, cards)


ROWS = {"6": row6, "9": row9_10, "10": row9_10, "11": row11, "14": row14_15, "15": row14_15}

if __name__ == "__main__":
    picked, done = sys.argv[1:] or ["6", "9", "11", "14"], set()
    for r in picked:
        fn = ROWS[r]
        if fn in done:
            continue
        done.add(fn)
        fn()
    out = ROOT / "evidence" / "runs" / "final-pass-yang.json"
    old = json.loads(out.read_text(encoding="utf-8")) if out.exists() else []
    out.write_text(json.dumps(old + RESULTS, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\nSUMMARY:", ", ".join(f"row {x['row']} {'PASS' if x['ok'] else 'FAIL'}" for x in RESULTS))
