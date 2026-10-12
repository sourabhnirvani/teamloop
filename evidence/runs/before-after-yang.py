"""Before/after on the multi-skill demo goal: one bot (S alone, all tools) vs the crew, N runs each, free model.

    set TEAMLOOP_CHAIN=groq
    .venv\\Scripts\\python.exe evidence\\runs\\before-after-yang.py [runs]

Uses scripts/compare.py's run_once (fresh database per run, approval cards answered yes). On top of its numbers,
every tool call is recorded and the outcome is judged from what the tools really did: a report saved with source
links, the report opened, a weekly routine set, and research done (a search or a page read). Writes
evidence/runs/before-after-yang.json. The opened report windows are closed afterwards.
"""

import asyncio
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]

import compare  # noqa: E402
from teamloop import kits, trace  # noqa: E402
from teamloop.keys import vault  # noqa: E402
from teamloop.tools import registry  # noqa: E402

GOAL = ("Research the top 3 free LLM APIs for students, write a short report on the Desktop, open it, and remind "
        "me about it every Monday.")
CALLS: list[dict] = []
TOKENS_BY: dict[str, int] = {}   # tokens per purpose ("turn:scout", "wrapup:s", ...) for the run in progress
_real_run = registry.run
_real_usage = compare.Store.add_usage


def _usage(self, provider, model, tokens_in, tokens_out, purpose=""):
    who = (purpose or "other").split(":")[-1]
    TOKENS_BY[who] = TOKENS_BY.get(who, 0) + tokens_in + tokens_out
    return _real_usage(self, provider, model, tokens_in, tokens_out, purpose)
compare.Store.add_usage = _usage


async def _recorded(name, args, ctx):
    result = await _real_run(name, args, ctx)
    CALLS.append({"bot": getattr(ctx, "bot_id", ""), "tool": name, "ok": result.ok, "text": result.text[:150],
                  "content": str(args.get("content", ""))[:4000] if name == "write_file" else ""})
    return result
registry.run = _recorded


def judge(calls: list[dict]) -> dict:
    ok = lambda tool: [c for c in calls if c["tool"] == tool and c["ok"]]  # noqa: E731
    saved = ok("write_file")
    parts = {
        "researched": bool(ok("web_search") or ok("read_page") or ok("fetch_page") or ok("open_page")),
        "saved_with_links": any("http" in c["content"] for c in saved),
        "opened": bool(ok("open_file")),
        "routine": bool(ok("schedule_routine")),
    }
    parts["success"] = all(parts.values())
    return parts


def close_reports():
    from teamloop.computer import winapi
    for w in winapi.windows():
        if w.process.lower() == "notepad.exe" and "report" in w.title.lower() or "llm" in w.title.lower():
            winapi.close(w.hwnd)


async def main(runs: int):
    kits.load_all()
    vault.export_to_env()
    trace.init("teamloop-compare")
    rows = []
    for i in range(1, runs + 1):
        for solo in MODES:
            CALLS.clear()
            TOKENS_BY.clear()
            with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
                r = await compare.run_once(GOAL, solo, Path(tmp))
            r.update(run=i, steps=len(CALLS), outcome=judge(CALLS), tokens_by_bot=dict(TOKENS_BY),
                     tools=[f"{c['bot']}:{c['tool']}{'' if c['ok'] else ' FAILED'}" for c in CALLS])
            rows.append(r)
            o = r["outcome"]
            print(f"run {i} {r['mode']:>7}: {'SUCCESS' if o['success'] else 'INCOMPLETE'} "
                  f"({', '.join(k for k, v in o.items() if k != 'success' and not v) or 'all parts done'}) "
                  f"{r['seconds']}s, {r['model_requests']} requests, {r['tokens']} tokens, {r['steps']} steps, "
                  f"{r['tool_failures']} failed, bots {','.join(r['bots_involved'])}; tokens by bot {r['tokens_by_bot']}")
            await asyncio.sleep(1)
            close_reports()
    trace.flush()
    name = "before-after-capped-yang.json" if "--crew-only" in sys.argv else "before-after-yang.json"
    (ROOT / "evidence" / "runs" / name).write_text(
        json.dumps({"goal": GOAL, "rows": rows}, indent=2, ensure_ascii=False), encoding="utf-8")

MODES = (False,) if "--crew-only" in sys.argv else (True, False)
asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 2))
