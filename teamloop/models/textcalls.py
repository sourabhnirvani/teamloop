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


_PY_CALL = re.compile(r"(?m)^[ \t`]*([A-Za-z_]\w*)\((.*)\)[ \t`;]*$")


def _params(tools: Iterable[dict]) -> dict[str, dict]:
    return {t["function"]["name"]: t["function"].get("parameters") or {} for t in tools}


def extract_python(text: str, tools: list[dict]) -> tuple[list[tuple[str, dict]], str]:
    """Calls a small model wrote like code, on a line of their own: web_search("capital of France", 1)."""
    import ast

    known = _params(tools)
    calls: list[tuple[str, dict]] = []
    rest = text or ""
    for m in _PY_CALL.finditer(text or ""):
        name = m.group(1)
        if name not in known:
            continue
        try:
            node = ast.parse(f"f({m.group(2)})", mode="eval").body
            pos = [ast.literal_eval(a) for a in node.args]  # type: ignore[attr-defined]
            kw = {k.arg: ast.literal_eval(k.value) for k in node.keywords if k.arg}  # type: ignore[attr-defined]
        except (SyntaxError, ValueError, AttributeError):
            continue
        order = list((known[name].get("properties") or {}).keys())
        if len(pos) > len(order):
            continue
        calls.append((name, {**dict(zip(order, pos)), **kw}))
        rest = rest.replace(m.group(0), "", 1)
    return calls, rest.strip() if calls else text


def fit_args(args: dict, parameters: dict | None) -> dict:
    """Arguments a model wrapped one level too deep, e.g. {"bot": {"bot": "desk", "instruction": "..."}},
    {"query": {"query": "..."}} or {"arguments": {...}}: unwrapped when the inner dict is made only of this tool's
    argument names and the outer key isn't an argument that really takes an object."""
    props = (parameters or {}).get("properties") or {}
    if len(args) != 1 or not props:
        return args
    (key, inner), = args.items()
    if not (isinstance(inner, dict) and inner and set(inner) <= set(props)):
        return args
    if key in props and (props[key] or {}).get("type") == "object":
        return args  # a real object argument
    return inner


def tidy(calls: list[tuple[str, dict]], tools: list[dict] | None) -> list[tuple[str, dict]]:
    known = _params(tools or [])
    return [(name, fit_args(args, known.get(name))) for name, args in calls]
