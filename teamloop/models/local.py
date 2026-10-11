"""Local models through Ollama's own API.

Ollama's OpenAI-style endpoint runs every model with Ollama's default context (4096 tokens here) and silently
cuts longer prompts from the front: a crew prompt plus a page of search results lost its rules and tools. Its
own /api/chat takes `num_ctx`, so the whole prompt is read. This module also makes every kind of installed model
usable: models without tool support get the tools in the prompt and answer with <tool_call> text (read by
textcalls), and "thinking" models have their <think> notes taken out of the reply.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Mapping

CTX = 16384        # enough for a bot's prompt, its tools and a few results; OLLAMA_NUM_CTX changes it
BIG_CTX = 32768    # used for one call when a prompt wouldn't fit, if the model takes that much
TIMEOUT = 300.0    # a first call loads the model into memory, which takes a while on a slow disk

_THINK = re.compile(r"<think>.*?</think>", re.S | re.I)
_NO_TOOLS = re.compile(r"does not support tools", re.I)


class NoToolSupport(Exception):
    """This model can't take native tools: ask it again with the tools written into the prompt."""


def strip_think(text: str) -> str:
    """A thinking model's reply without its <think> notes (some templates open the tag in the prompt)."""
    text = _THINK.sub("", text or "")
    if "</think>" in text.lower():
        text = re.split(r"</think>", text, flags=re.I)[-1]
    if text.lstrip().lower().startswith("<think>"):  # it never closed: all notes, no answer
        return ""
    return text.strip()


def context_for(messages: list[dict], tools: list[dict] | None, info: Mapping[str, Any],
                env: Mapping[str, str] | None = None) -> int:
    env = os.environ if env is None else env
    try:
        ctx = int(env.get("OLLAMA_NUM_CTX") or CTX)
    except ValueError:
        ctx = CTX
    need = (len(json.dumps(messages, ensure_ascii=False)) + len(json.dumps(tools or []))) // 3 + 1024  # ~3 chars/token
    if need > ctx:
        ctx = max(ctx, BIG_CTX)
    most = info.get("ctx")
    return min(ctx, most) if isinstance(most, int) and most > 0 else ctx


def _tool_names(messages: list[dict]) -> dict[str, str]:
    return {c.get("id", ""): c["function"]["name"] for m in messages for c in m.get("tool_calls") or []}


def _args(raw: Any) -> dict:
    if isinstance(raw, dict):
        return raw
    try:
        value = json.loads(raw or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def to_ollama(messages: list[dict], text_tools: bool = False) -> list[dict]:
    """OpenAI-style chat messages in Ollama's shape. With `text_tools`, earlier tool calls and their results
    become plain text, for a model whose template has no tool roles."""
    names = _tool_names(messages)
    out: list[dict] = []
    for m in messages:
        role, content = m.get("role", "user"), m.get("content") or ""
        if not isinstance(content, str):  # a list of parts: keep the text
            content = "\n".join(p.get("text", "") for p in content if isinstance(p, dict))
        calls = m.get("tool_calls") or []
        if role == "tool":
            name = names.get(m.get("tool_call_id", ""), "")
            out.append({"role": "user", "content": f"Result of {name or 'the tool'}: {content}"} if text_tools
                       else {"role": "tool", "content": content, "tool_name": name})
        elif calls and text_tools:
            written = "".join("<tool_call>" + json.dumps({"name": c["function"]["name"],
                                                          "arguments": _args(c["function"].get("arguments"))})
                              + "</tool_call>" for c in calls)
            out.append({"role": "assistant", "content": (content + "\n" + written).strip()})
        elif calls:
            out.append({"role": "assistant", "content": content,
                        "tool_calls": [{"function": {"name": c["function"]["name"],
                                                     "arguments": _args(c["function"].get("arguments"))}}
                                       for c in calls]})
        else:
            out.append({"role": role, "content": content})
    return out


def tool_prompt(tools: list[dict]) -> str:
    """The tools, written out for a model that can't take them natively."""
    lines = []
    for t in tools:
        f = t["function"]
        props = (f.get("parameters") or {}).get("properties") or {}
        need = set((f.get("parameters") or {}).get("required") or [])
        # the same JSON shape the call takes (a code-like signature made small models answer in code)
        args = ", ".join(f'"{k}": {v.get("type", "any")}{"" if k in need else " (optional)"}' for k, v in props.items())
        lines.append(f"- {f['name']}: {f.get('description', '').strip()} Arguments: {{{args}}}")
    first = tools[0]["function"]
    param = next(iter(((first.get("parameters") or {}).get("properties") or {"value": {}}).keys()))
    example = json.dumps({"name": first["name"], "arguments": {param: "..."}})
    return ("You can use these tools. To use one, reply with only this, and nothing after it:\n"
            f"<tool_call>{example}</tool_call>\n"
            "The result comes back in the next message. When you have what you need, answer normally.\n"
            "Tools:\n" + "\n".join(lines))


def with_tool_prompt(messages: list[dict], tools: list[dict]) -> list[dict]:
    note = tool_prompt(tools)
    if messages and messages[0]["role"] == "system":
        return [{**messages[0], "content": messages[0]["content"] + "\n\n" + note}, *messages[1:]]
    return [{"role": "system", "content": note}, *messages]


def request(model: str, messages: list[dict], tools: list[dict] | None, max_tokens: int | None, info: Mapping[str, Any],
            text_tools: bool, env: Mapping[str, str] | None = None) -> dict:
    """The /api/chat body for one call."""
    body_messages = to_ollama(messages, text_tools)
    if tools and text_tools:
        body_messages = with_tool_prompt(body_messages, tools)
    options: dict[str, Any] = {"num_ctx": context_for(body_messages, None if text_tools else tools, info, env)}
    if max_tokens:
        options["num_predict"] = max_tokens
    body: dict[str, Any] = {"model": model, "messages": body_messages, "stream": False, "options": options}
    if info.get("thinking"):  # answer directly: the crew's prompts don't need long hidden notes, and they're slow
        body["think"] = "low" if model.startswith("gpt-oss") else False  # gpt-oss can't switch thinking off
    if tools and not text_tools:
        body["tools"] = tools
    return body


def no_tool_support(status: int, detail: str) -> bool:
    return status == 400 and bool(_NO_TOOLS.search(detail))
