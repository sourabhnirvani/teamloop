"""One bot turn: the model thinks, calls tools, sees their read-backs, and finally replies."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from teamloop import trace
from teamloop.crew import coverage
from teamloop.crew.bots import BOTS, LEAD, Bot, system_prompt
from teamloop.crew.context import TurnCtx
from teamloop.tools import registry

log = logging.getLogger(__name__)

MAX_STEPS = 8
MAX_SAME_CALL = 2  # one retry of the exact same call is fine (a glitch may pass); a third is a loop
WRAP_UP = "Stop using tools now. Reply to the person: what you did and the real result."
# A failure that looks temporary gets one retry before the bot reports it (the forced-failure demo, a slow app).
TEMPORARY = re.compile(r"didn't respond in time|timed out|time ?out|temporar|try again|busy|connection (reset|refused)", re.I)
RETRY_NOTE = "This looks temporary: try the same call once more before you report a failure."
RETRY_NUDGE = "\n(" + RETRY_NOTE + ")"
REPEATED = ("SKIPPED: you already made this exact call twice and the result won't change. Use what you have, "
            "try something different, or reply to the person.")
# Research caps per turn (measured: one Scout turn ran 20 web_search + 4 fetch_page, 81% of a 135k-token job;
# the same job done well took 3 calls). Different queries each time, so the repeat guard alone never stopped it.
CAPS = {"scout": {"web_search": 5, "fetch_page": 3}}
ENOUGH = "SKIPPED: You've searched enough: answer with the sources you have."


async def run_bot_turn(bot: Bot, router: Any, history: list[dict], user_text: str, ctx: TurnCtx,
                       prefer: str | None = None, members: list[str] | None = None,
                       max_steps: int = MAX_STEPS, only: bool = False) -> str:
    pick = {"prefer": prefer, "only": True} if only and prefer else {"prefer": prefer}  # only: no fallback
    tools = registry.tools_for_kits(list(bot.kits))
    tool_schemas = registry.schemas(tools) or None
    messages: list[dict] = [{"role": "system", "content": system_prompt(bot, members, facts=_facts(ctx))}, *history,
                            {"role": "user", "content": user_text}]
    seen: dict[tuple[str, str], int] = {}
    counted: dict[str, int] = {}  # research calls this turn, for CAPS
    ctx.spoke.add(bot.id)
    checked = False  # the lead is sent back at most once per job for a skipped step or an invented result
    with trace.span(f"{bot.name} turn", "agent", bot=bot.id, chat=ctx.chat_id, depth=ctx.depth) as sp:
        sp.set("input.value", user_text)
        steps = max_steps
        while steps > 0:
            steps -= 1
            ctx.check_stop()
            reply = await router.chat(messages, tools=tool_schemas, purpose=f"turn:{bot.id}", **pick)
            if not reply.tool_calls:
                text = clean_reply(reply.text)
                back = None if checked else _check_lead(bot, ctx, user_text, text, history)
                if back:
                    checked = True
                    sp.set("coverage.nudge", back)
                    messages += [{"role": "assistant", "content": text}, {"role": "user", "content": back}]
                    steps = max(steps, 4)  # room to do the missing step and report
                    continue
                text = _honest(bot, ctx, user_text, text)
                sp.set("output.value", text)
                return text
            messages.append(reply.message)
            for call in reply.tool_calls:
                ctx.check_stop()
                ctx.used.add(call.name)
                key = (call.name, json.dumps(call.args, sort_keys=True, default=str))
                seen[key] = seen.get(key, 0) + 1
                if seen[key] > MAX_SAME_CALL:  # free models loop; a third identical call won't change anything
                    messages.append({"role": "tool", "tool_call_id": call.id, "content": REPEATED})
                    continue
                cap = CAPS.get(bot.id, {}).get(call.name)
                if cap is not None:
                    counted[call.name] = counted.get(call.name, 0) + 1
                    if counted[call.name] > cap:
                        messages.append({"role": "tool", "tool_call_id": call.id, "content": ENOUGH})
                        continue
                await ctx.emit("step", bot=bot.id, tool=call.name, args=call.args, status="start")
                result = await registry.run(call.name, call.args, ctx.for_bot(bot.id))
                await ctx.emit("step", bot=bot.id, tool=call.name, status="done" if result.ok else "fail",
                               text=result.text)
                content = _tool_content(result)
                if not result.ok and TEMPORARY.search(result.text):
                    content += RETRY_NUDGE
                messages.append({"role": "tool", "tool_call_id": call.id, "content": content})
        ctx.check_stop()
        final = await router.chat(messages + [{"role": "user", "content": WRAP_UP}], purpose=f"wrapup:{bot.id}", **pick)
        text = _honest(bot, ctx, user_text, clean_reply(final.text))
        sp.set("output.value", text)
        return text


_CITATION = re.compile(r"\s?【[^】\n]{0,80}】")  # gpt-oss leaves "【fetch_page†0】" markers in its text


def _check_lead(bot: Bot, ctx: TurnCtx, goal: str, text: str, history: list[dict]) -> str | None:
    """For the lead's own reply to the person: a nudge when a requested step was skipped (only in a job it
    handed out) or when it reports a teammate's result that teammate never produced (in this job or the chat)."""
    if bot.id != LEAD or ctx.depth != 0 or text.startswith("Not mine"):  # "Not mine" is routing, handled by the crew
        return None
    todo = coverage.missing(goal, ctx.used) if "delegate" in ctx.used else coverage.missing_actions(goal, ctx.used)
    names = {b.id: b.name for b in BOTS.values() if b.id != LEAD}
    heard = {i for i, n in names.items() if any(str(m.get("content", "")).startswith(f"[{n}]") for m in history)}
    claimed = coverage.false_claims(text, names, ctx.spoke | heard)
    return coverage.nudge(todo, claimed) if (todo or claimed) else None


def _honest(bot: Bot, ctx: TurnCtx, goal: str, text: str) -> str:
    """The lead's final reply, plus the runner's own "Not done: ..." line for any asked-for action that still has no
    tool behind it (a small model may ignore the nudge and say "saved" anyway). Never reads a skipped step as done."""
    if bot.id != LEAD or ctx.depth != 0 or text.startswith("Not mine"):
        return text
    todo = coverage.missing(goal, ctx.used) if "delegate" in ctx.used else coverage.missing_actions(goal, ctx.used)
    return f"{text}\n\n{coverage.not_done(todo)}" if todo else text


def clean_reply(text: str) -> str:
    return _CITATION.sub("", text or "").strip() or "Done."


def _facts(ctx: TurnCtx) -> list[str]:
    try:
        from teamloop.crew.memory import recall_facts

        return [r["fact"] for r in recall_facts(ctx.crew.store, limit=10)]
    except Exception:  # memory is a nice-to-have; a turn never fails over it
        return []


def _tool_content(result: registry.ToolResult) -> str:
    head = ("OK: " if result.ok else "FAILED: ") + result.text
    if not result.data:
        return head
    data = json.dumps(result.data, ensure_ascii=False, default=str)
    return f"{head}\n{data[:6000]}"
