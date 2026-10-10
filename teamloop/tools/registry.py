"""One registry for every tool a bot can call.

A tool is `async def handler(args: dict, ctx) -> ToolResult`. `text` is one plain sentence that reads
back what really happened ("Opened Calculator; its window is in front."), which is what the model sees.
Tools are grouped in kits ("computer", "browser", "web", "files", "lead") and each bot gets kits.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from teamloop import trace

log = logging.getLogger(__name__)


@dataclass
class ToolResult:
    ok: bool
    text: str
    data: dict = field(default_factory=dict)


Handler = Callable[[dict, Any], Awaitable[ToolResult]]


@dataclass
class Tool:
    name: str
    description: str
    params: dict
    kit: str
    handler: Handler

    def schema(self) -> dict:
        return {"type": "function",
                "function": {"name": self.name, "description": self.description, "parameters": self.params}}


REGISTRY: dict[str, Tool] = {}


def tool(name: str, description: str, params: dict | None = None, kit: str = "core"):
    """Register a tool. `params` is a JSON schema `properties` dict plus optional "required" list."""
    spec = dict(params or {})
    required = spec.pop("required", [])
    schema = {"type": "object", "properties": spec, "required": required}

    def register(handler: Handler) -> Handler:
        REGISTRY[name] = Tool(name, description, schema, kit, handler)
        return handler

    return register


def tools_for_kits(kits: list[str]) -> list[Tool]:
    return [t for t in REGISTRY.values() if t.kit in kits]


def schemas(tools: list[Tool]) -> list[dict]:
    return [t.schema() for t in tools]


_failed_once: set[str] = set()


def _demo_glitch(name: str) -> ToolResult | None:
    """TEAMLOOP_FAIL_ONCE=open_app,write_file makes each listed tool fail once, to record a recovery run."""
    wanted = {n.strip() for n in os.getenv("TEAMLOOP_FAIL_ONCE", "").split(",") if n.strip()}
    if name in wanted and name not in _failed_once:
        _failed_once.add(name)
        return ToolResult(False, f"{name} failed: the app didn't respond in time (simulated glitch for the recovery demo).")
    return None


async def run(name: str, args: dict, ctx: Any) -> ToolResult:
    found = REGISTRY.get(name)
    if found is None:
        return ToolResult(False, f"There is no tool called {name}.")
    glitch = _demo_glitch(name)
    if glitch is not None:
        return glitch
    with trace.span(name, "tool", tool=name, bot=getattr(ctx, "bot_id", ""), chat=getattr(ctx, "chat_id", "")) as sp:
        sp.set("input.value", args or {})
        try:
            result = await found.handler(args or {}, ctx)
        except Exception as e:  # a broken tool must not kill the bot's turn
            if type(e).__name__ == "Stopped":
                raise
            log.exception("tool %s failed", name)
            result = ToolResult(False, f"{name} failed: {e}")
        if not isinstance(result, ToolResult):
            result = ToolResult(False, f"{name} returned nothing usable.")
        sp.set("output.value", ("OK: " if result.ok else "FAILED: ") + result.text)
        sp.set("tool.ok", result.ok)
    return result
