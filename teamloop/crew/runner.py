"""One bot turn: the model thinks, calls tools, sees their read-backs, and finally replies."""

from __future__ import annotations

import json
import logging
from typing import Any

from teamloop import trace
from teamloop.crew.bots import Bot, system_prompt
from teamloop.crew.context import TurnCtx
from teamloop.tools import registry

log = logging.getLogger(__name__)

MAX_STEPS = 8
WRAP_UP = "Stop using tools now. Reply to the person: what you did and the real result."


async def run_bot_turn(bot: Bot, router: Any, history: list[dict], user_text: str, ctx: TurnCtx,
                       prefer: str | None = None, members: list[str] | None = None,
                       max_steps: int = MAX_STEPS) -> str:
    tools = registry.tools_for_kits(list(bot.kits))
    tool_schemas = registry.schemas(tools) or None
    messages: list[dict] = [{"role": "system", "content": system_prompt(bot, members)}, *history,
                            {"role": "user", "content": user_text}]
    with trace.span(f"{bot.name} turn", "agent", bot=bot.id, chat=ctx.chat_id, depth=ctx.depth):
        for _ in range(max_steps):
            ctx.check_stop()
            reply = await router.chat(messages, tools=tool_schemas, prefer=prefer, purpose=f"turn:{bot.id}")
            if not reply.tool_calls:
                return reply.text.strip() or "Done."
            messages.append(reply.message)
            for call in reply.tool_calls:
                ctx.check_stop()
                await ctx.emit("step", bot=bot.id, tool=call.name, args=call.args, status="start")
                result = await registry.run(call.name, call.args, ctx.for_bot(bot.id))
                await ctx.emit("step", bot=bot.id, tool=call.name, status="done" if result.ok else "fail",
                               text=result.text)
                messages.append({"role": "tool", "tool_call_id": call.id, "content": _tool_content(result)})
        ctx.check_stop()
        final = await router.chat(messages + [{"role": "user", "content": WRAP_UP}], prefer=prefer,
                                  purpose=f"wrapup:{bot.id}")
        return final.text.strip() or "Done."


def _tool_content(result: registry.ToolResult) -> str:
    head = ("OK: " if result.ok else "FAILED: ") + result.text
    if not result.data:
        return head
    data = json.dumps(result.data, ensure_ascii=False, default=str)
    return f"{head}\n{data[:6000]}"
