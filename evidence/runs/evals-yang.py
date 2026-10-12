"""I (evals) for the judges: the live crew tasks, 3 rounds, on a free model, with steps, tokens and seconds per run.

    set TEAMLOOP_CHAIN=groq   (free tier only)
    .venv\\Scripts\\python.exe evidence\\runs\\evals-yang.py

Uses evals/run.py's own live tasks (S -> Writer saves a file; S -> Desk opens Notepad; a save that fails once on
purpose via TEAMLOOP_FAIL_ONCE=write_file and must be recovered). Outcomes are checked on the machine, not from
what a bot said. Tokens and model calls come from the crew's own usage table; steps are the chat's tool/hand-off
lines plus every tool call (recorded around registry.run). Writes evidence/runs/evals-yang.json.
"""

import asyncio
import contextlib
import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from evals import run as evals  # noqa: E402
from teamloop import config, kits, trace  # noqa: E402
from teamloop.tools import registry  # noqa: E402

CALLS: list[dict] = []          # every tool call of the current task: neatlogs' TOOL spans, kept locally too
_real_run = registry.run


async def _recorded_run(name, args, ctx):
    result = await _real_run(name, args, ctx)
    CALLS.append({"bot": getattr(ctx, "bot_id", ""), "tool": name, "ok": result.ok, "text": result.text[:160]})
    return result
registry.run = _recorded_run

ROUNDS = 3
PICK = ["live_writer", "live_desk", "live_recovery"]


def totals(store) -> tuple[int, int]:
    rows = store.usage()
    return sum(r["requests"] for r in rows), sum(r["tokens_in"] + r["tokens_out"] for r in rows)


async def main():
    from teamloop.keys import vault
    from teamloop.server.app import build_crew

    kits.load_all()
    with contextlib.suppress(OSError, ValueError):
        vault.export_to_env()
    tracing = trace.init()
    (config.workspace() / "evals").mkdir(parents=True, exist_ok=True)
    crew = build_crew(config.workspace() / "evals" / f"evals-yang-{int(time.time())}.db")
    tasks = {t.name: t for t in evals.TASKS}
    rows = []
    print(f"tracing to neatlogs: {tracing}")
    for rnd in range(1, ROUNDS + 1):
        for name in PICK:
            ev = evals.Eval(crew, name)
            CALLS.clear()
            registry._failed_once.clear()   # TEAMLOOP_FAIL_ONCE fails once per process: make every round's save fail
            calls0, tokens0 = totals(crew.store)
            t0 = time.monotonic()
            try:
                detail, ok = await tasks[name].run(ev), True
            except AssertionError as e:
                detail, ok = str(e) or "wrong outcome", False
            except Exception as e:  # noqa: BLE001
                detail, ok = f"{type(e).__name__}: {e}", False
            if name == "live_recovery" and ok and not any(c["tool"] == "write_file" and not c["ok"] for c in CALLS):
                detail, ok = "no simulated failure happened, so recovery wasn't tested", False
            seconds = round(time.monotonic() - t0, 1)
            calls1, tokens1 = totals(crew.store)
            msgs = crew.store.messages(ev.chat_id)
            kinds = Counter(m["kind"] for m in msgs if m["sender"] != "user")
            steps = len(CALLS)
            failed = [f"{c['bot']} {c['tool']}: {c['text']}" for c in CALLS if not c["ok"]]
            row = {"round": rnd, "task": name, "ok": ok, "seconds": seconds, "model_calls": calls1 - calls0,
                   "tokens": tokens1 - tokens0, "steps": steps, "kinds": dict(kinds), "detail": detail,
                   "chat": ev.chat_id, "failures_seen": failed[:3],
                   "tool_calls": [dict(c) for c in CALLS]}
            rows.append(row)
            print(f"r{rnd} {'PASS' if ok else 'FAIL'} {name:<14} {seconds:>6}s  calls {row['model_calls']:>3}  "
                  f"tokens {row['tokens']:>6}  steps {steps:>2}  {detail[:90]}")
    trace.flush()
    out = ROOT / "evidence" / "runs" / "evals-yang.json"
    out.write_text(json.dumps({"tracing": tracing, "rows": rows}, indent=2), encoding="utf-8")
    for name in PICK:
        mine = [r for r in rows if r["task"] == name]
        okn = sum(r["ok"] for r in mine)
        avg = lambda k: round(sum(r[k] for r in mine) / len(mine), 1)  # noqa: E731
        print(f"{name:<14} {okn}/{len(mine)} passed  avg {avg('seconds')}s  {avg('model_calls')} calls  "
              f"{avg('tokens')} tokens  {avg('steps')} steps")

asyncio.run(main())
