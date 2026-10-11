"""One registry for every tool a bot can call.

A tool is `async def handler(args: dict, ctx) -> ToolResult`. `text` is one plain sentence that reads
back what really happened ("Opened Calculator; its window is in front."), which is what the model sees.
Tools are grouped in kits ("computer", "browser", "web", "files", "lead") and each bot gets kits.
"""

from __future__ import annotations

import logging
import os
import time
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


READ_ONLY_FILES = ("read_file", "list_files")


def tools_for_kits(kits: list[str]) -> list[Tool]:
    """A kit's tools; "files_read" is the files kit without writing (what a new bot starts with)."""
    return [t for t in REGISTRY.values()
            if t.kit in kits or ("files_read" in kits and t.kit == "files" and t.name in READ_ONLY_FILES)]


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


SAID_NO = "The person said no"


def _say_how_the_card_ended(result: ToolResult, answer: str) -> ToolResult:
    """Tools say "The person said no..."; tell the model what really happened with the card."""
    if result.ok or not result.text.startswith(SAID_NO):
        return result
    if answer == "expired":
        result.text = ("No one answered the approval card in time" + result.text[len(SAID_NO):]
                       + " The person didn't say no: tell them nobody answered the card, so you left it, and they can"
                         " ask again. Don't try it again yourself.")
    elif answer == "expired_before":
        result.text = ("No one answered the card for this a moment ago, so it wasn't asked again"
                       + result.text[len(SAID_NO):] + " Tell the person nobody answered the card; they can ask again.")
    elif answer == "denied_before":
        result.text = ("The person already said no to this a few minutes ago (not asked again)"
                       + result.text[len(SAID_NO):] + " Don't try it again unless they ask for it.")
    return result


BLOCKED = "security_blocked"   # store setting: the last calls refused for carrying a key (no key text)
KEEP_BLOCKED = 50


def _block_key_leak(name: str, args: dict, ctx: Any) -> ToolResult | None:
    """A tool call whose input holds a known key never runs; it is logged without the key."""
    from teamloop.keys.redact import redact_obj

    if redact_obj(args) == args:
        return None
    store = getattr(getattr(ctx, "crew", None), "store", None)
    if store is not None:
        entry = {"ts": time.time(), "bot": getattr(ctx, "bot_id", ""), "tool": name,
                 "what": "an API key or token in its input"}
        store.set_setting(BLOCKED, [*(store.get_setting(BLOCKED, []) or []), entry][-KEEP_BLOCKED:])
    log.warning("blocked %s: its input carried a key", name)
    return ToolResult(False, f"Refused: the {name} call carried an API key, and keys never leave TeamLoop. "
                             "Do it without the key.")


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
            result = _block_key_leak(name, args or {}, ctx) or await found.handler(args or {}, ctx)
        except Exception as e:  # a broken tool must not kill the bot's turn
            if type(e).__name__ == "Stopped":
                raise
            log.exception("tool %s failed", name)
            result = ToolResult(False, f"{name} failed: {e}")
        if not isinstance(result, ToolResult):
            result = ToolResult(False, f"{name} returned nothing usable.")
        result = _say_how_the_card_ended(result, getattr(ctx, "last_answer", ""))
        sp.set("output.value", ("OK: " if result.ok else "FAILED: ") + result.text)
        sp.set("tool.ok", result.ok)
    return result
