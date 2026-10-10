"""Tool calls a model wrote as text instead of emitting them.

Free models often answer with `<tool_call>{"name": ..., "arguments": {...}}</tool_call>`, a ```json block,
`<function=open_app>{...}</function>`, `[TOOL_CALLS] [...]` or Llama's `<|python_tag|>{...}`. Only names
of tools the bot was actually given are accepted, so a JSON example in a normal answer stays text.
"""

from __future__ import annotations

import json
import re
from typing import Iterable

_DECODER = json.JSONDecoder()
_FUNCTION_TAG = re.compile(r"<function=([\w.\-]+)>\s*", re.I)
_WRAPPERS = re.compile(r"</?tool_call>|</function>|\[TOOL_CALLS\]|<\|python_tag\|>|<\|eom_id\|>|<\|eot_id\|>|"
                       r"```(?:json|tool_call|python)?", re.I)
ARG_KEYS = ("arguments", "parameters", "args", "input")


def _args(value: object) -> dict | None:
    if isinstance(value, str):
        try:
            value = json.loads(value) if value.strip() else {}
        except json.JSONDecodeError:
            return None
    return value if isinstance(value, dict) else None


def _as_call(obj: object, names: set[str], name: str | None = None) -> tuple[str, dict] | None:
    if not isinstance(obj, dict):
        return None
    if name:  # <function=name>{...args...}
        return (name, obj) if name in names else None
    if isinstance(obj.get("function"), dict):  # {"type": "function", "function": {...}}
        obj = obj["function"]
    called = obj.get("name") or obj.get("tool") or obj.get("tool_name")
    if not isinstance(called, str) or called not in names:
        return None
    raw = next((obj[k] for k in ARG_KEYS if k in obj), {})
    args = _args(raw)
    return (called, args) if args is not None else None


def extract(text: str, tool_names: Iterable[str]) -> tuple[list[tuple[str, dict]], str]:
    """(calls found, the text left over once they and their wrappers are removed)."""
    names = set(tool_names)
    if not text or not names:
        return [], text
    calls: list[tuple[str, dict]] = []
    spans: list[tuple[int, int]] = []
    tagged = {m.end(): (m.start(), m.group(1)) for m in _FUNCTION_TAG.finditer(text)}
    i = 0
    while i < len(text):
        if text[i] not in "{[":
            i += 1
            continue
        try:
            obj, end = _DECODER.raw_decode(text, i)
        except json.JSONDecodeError:
            i += 1
            continue
        start, tag_name = tagged.get(i, (i, None))
        found = [_as_call(o, names, tag_name) for o in (obj if isinstance(obj, list) else [obj])]
        if found and all(found):
            calls.extend(found)  # type: ignore[arg-type]
            spans.append((start, end))
            i = end
        else:
            i += 1
    if not calls:
        return [], text
    left, last = [], 0
    for start, end in spans:
        left.append(text[last:start])
        last = end
    left.append(text[last:])
    rest = _WRAPPERS.sub("", "".join(left))
    return calls, re.sub(r"\n{3,}", "\n\n", rest).strip()
