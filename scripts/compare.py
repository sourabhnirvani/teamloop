"""Before/after evidence: run the same goal with one bot (S alone, all tools) and with the crew.

    python scripts/compare.py "Check my battery and Wi-Fi, then save a one-line status to workspace/status.txt"

Each run uses a fresh database. Prints and saves time, model requests, tokens, tool calls and failures to
evidence/before_after.json. Real models are used (whatever keys and TEAMLOOP_CHAIN say).
"""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from teamloop import kits, trace  # noqa: E402
from teamloop.crew.events import Bus  # noqa: E402
from teamloop.crew.store import Store  # noqa: E402
from teamloop.crew.team import Crew  # noqa: E402
from teamloop.keys import vault  # noqa: E402
from teamloop.models.router import Router  # noqa: E402


async def run_once(goal: str, solo: bool, folder: Path) -> dict:
    store = Store(folder / ("solo.db" if solo else "crew.db"))
    crew = Crew(store, Router(on_usage=store.add_usage), Bus())
    crew.ensure_default_chats()
    store.set_setting("solo", solo)
    steps = {"calls": 0, "fails": 0}

    async def count() -> None:
        with crew.bus.subscribe() as queue:
            while True:
                event = await queue.get()
                if event["type"] == "step" and event.get("status") in ("done", "fail"):
                    steps["calls"] += 1
                    steps["fails"] += event["status"] == "fail"
                if event["type"] == "approval":  # the comparison never waits on a person
                    crew.gate.answer(event["id"], True)

    counter = asyncio.create_task(count())
    await asyncio.sleep(0)
    started = time.monotonic()
    await crew.post("team", goal)
    await crew.wait_idle("team")
    seconds = time.monotonic() - started
    counter.cancel()
    usage = store.usage()
    messages = store.messages("team")
    store.close()
    return {
        "mode": "one bot" if solo else "crew",
        "seconds": round(seconds, 1),
        "model_requests": sum(u["requests"] for u in usage),
        "tokens": sum(u["tokens_in"] + u["tokens_out"] for u in usage),
        "tool_calls": steps["calls"],
        "tool_failures": steps["fails"],
        "bots_involved": sorted({m["sender"] for m in messages if m["sender"] != "user"}),
        "final_reply": messages[-1]["text"] if messages else "",
    }


async def main(goal: str) -> None:
    kits.load_all()
    vault.export_to_env()
    trace.init("teamloop-compare")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        results = [await run_once(goal, True, Path(tmp)), await run_once(goal, False, Path(tmp))]
    out = ROOT / "evidence" / "before_after.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"goal": goal, "runs": results}, indent=2, ensure_ascii=False), encoding="utf-8")
    for r in results:
        print(f"{r['mode']:>8}: {r['seconds']}s, {r['model_requests']} requests, {r['tokens']} tokens, "
              f"{r['tool_calls']} tool calls ({r['tool_failures']} failed), bots: {', '.join(r['bots_involved'])}")
    print(f"saved {out}")
    trace.flush()


if __name__ == "__main__":
    asyncio.run(main(" ".join(sys.argv[1:]) or
                     "Check my battery and Wi-Fi, then save a one-line status note to workspace/status.txt"))
