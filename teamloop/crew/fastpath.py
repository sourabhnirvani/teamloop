"""The direct fast path: plain one-step commands run one tool straight away, with no model call.

"open calculator", "volume 30", "brightness up", "battery?", "wifi off", "lock the laptop",
"search free llm apis". Anything longer, joined with "and"/"then", or aimed at a named bot goes to the
bots as usual. Tools still ask for approval and still show up as steps and TOOL spans.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

from teamloop.crew.context import TurnCtx
from teamloop.tools import registry

if TYPE_CHECKING:
    import asyncio

    from teamloop.crew.team import Crew

MAX_WORDS = 8
MAX_SEARCH_WORDS = 12
_JOINERS = re.compile(r"\b(and|then|after|before|if|but|also|aur|phir|fir)\b|[,;]", re.I)
_POLITE = re.compile(r"^(?:(?:hey|hi|ok|okay)\s+)?(?:s\b[,:]?\s*)?(?:please\s+|pls\s+|can you\s+|could you\s+)?|"
                     r"\s+(?:please|pls|for me|now)$", re.I)
_URL = re.compile(r"^(?:https?://\S+|(?:www\.)?[\w-]+(?:\.[\w-]+)*\.(?:com|org|net|io|ai|dev|in|co|edu|gov|app|me|so)"
                  r"(?:/\S*)?)$", re.I)
_LEVEL = r"(?:to\s+)?(\d{1,3})\s*(?:%|percent)?"
_UP_DOWN = {"up": 10, "down": -10, "higher": 10, "lower": -10, "badhao": 10, "kam karo": -10}

Match = tuple[str, dict]  # (tool name, args)


def _app_or_site(target: str) -> Match:
    target = target.strip().strip("\"'")
    if _URL.match(target):
        return "browser_open", {"url": target}
    return "open_app", {"name": re.sub(r"\s+(?:app|application)$", "", target, flags=re.I)}


RULES: list[tuple[re.Pattern, Callable[[re.Match], Match | None]]] = [
    (re.compile(r"^(?:open|launch)\s+(?:the\s+)?(.+)$", re.I), lambda m: _app_or_site(m.group(1))),
    (re.compile(r"^(.+?)\s+(?:kholo|khol do|chalu karo)$", re.I), lambda m: _app_or_site(m.group(1))),
    (re.compile(r"^(?:close|quit)\s+(?:the\s+)?(.+?)(?:\s+app)?$", re.I),
     lambda m: ("close_app", {"name": m.group(1)})),
    (re.compile(r"^(.+?)\s+band karo$", re.I), lambda m: ("close_app", {"name": m.group(1)})),

    (re.compile(rf"^(?:set\s+|turn\s+)?(?:the\s+)?(?:volume|sound)\s+{_LEVEL}$", re.I),
     lambda m: ("set_volume", {"level": int(m.group(1))})),
    (re.compile(r"^(?:turn\s+)?(?:the\s+)?(?:volume|sound)\s+(up|down|higher|lower|badhao|kam karo)$", re.I),
     lambda m: ("set_volume", {"change": _UP_DOWN[m.group(1).lower()]})),
    (re.compile(r"^(mute|unmute)(?:\s+(?:the\s+)?(?:sound|volume|audio|laptop))?$", re.I),
     lambda m: ("set_volume", {"mute": m.group(1).lower() == "mute"})),

    (re.compile(rf"^(?:set\s+|turn\s+)?(?:the\s+)?(?:screen\s+)?brightness\s+{_LEVEL}$", re.I),
     lambda m: ("set_brightness", {"level": int(m.group(1))})),
    (re.compile(r"^(?:turn\s+)?(?:the\s+)?(?:screen\s+)?brightness\s+(up|down|higher|lower|badhao|kam karo)$", re.I),
     lambda m: ("set_brightness", {"change": _UP_DOWN[m.group(1).lower()]})),

    (re.compile(r"^(?:turn\s+)?wi-?fi\s+(on|off)$|^turn\s+(on|off)\s+(?:the\s+)?wi-?fi$", re.I),
     lambda m: ("set_wifi", {"on": (m.group(1) or m.group(2)).lower() == "on"})),

    (re.compile(r"^(?:what(?:'s| is)\s+(?:my\s+|the\s+)?|how much\s+|check\s+(?:the\s+)?)?"
                r"(?:battery(?:\s+(?:level|left|status))?|system status|laptop status)\??$", re.I),
     lambda m: ("system_status", {})),
    (re.compile(r"^(?:what|which)\s+(?:apps|windows|programs)\s+(?:are\s+)?(?:open|running)\??$|"
                r"^(?:list|show)\s+(?:the\s+|my\s+)?(?:open\s+)?windows$", re.I),
     lambda m: ("list_windows", {})),
    (re.compile(r"^(?:take\s+a\s+)?screenshot$|^screenshot\s+(?:the\s+)?screen$", re.I),
     lambda m: ("screenshot", {})),
    (re.compile(r"^lock\s+(?:the\s+|my\s+)?(?:laptop|pc|computer|screen)$", re.I),
     lambda m: ("power", {"action": "lock"})),

    (re.compile(r"^(?:search|google)\s+(?:for\s+|the web for\s+)?(.+)$", re.I),
     lambda m: ("web_search", {"query": m.group(1)})),
]

_FINAL = ("refused", "the person said no")  # failures the fast path answers itself; others go to the bots

# The bot whose kit has the tool answers; S answers when that bot isn't in the chat.
OWNER = {"browser_open": "web", "web_search": "scout"}


def clean(text: str) -> str:
    text = text.strip().rstrip(".!?").strip()
    for _ in range(2):
        text = _POLITE.sub("", text).strip()
    return text


def match(text: str) -> Match | None:
    text = clean(text)
    words = len(text.split())
    if not text or words > MAX_SEARCH_WORDS or "@" in text or _JOINERS.search(text):
        return None
    for pattern, build in RULES:
        found = pattern.match(text)
        if found:
            hit = build(found)
            if hit and (hit[0] == "web_search" or words <= MAX_WORDS):
                return hit
            return None
    return None


def _reply(result: registry.ToolResult) -> str:
    text = result.text
    if result.ok and result.data.get("windows"):
        titles = [w.get("title") or w.get("app") for w in result.data["windows"] if isinstance(w, dict)]
        text += " " + "; ".join(t for t in titles[:12] if t) + "."
    if result.ok and result.data.get("results"):
        top = [r for r in result.data["results"][:3] if isinstance(r, dict)]
        text += "\n" + "\n".join(f"- {r.get('title', '')}: {r.get('url', '')}" for r in top)
    if not result.ok and not text.lower().startswith(("failed",) + _FINAL):
        text = "Failed: " + text
    return text


async def handle(crew: "Crew", chat: dict, text: str, stop: "asyncio.Event") -> bool:
    """Run the command if it is a plain one-step one. True when it was handled here."""
    if not crew.store.get_setting("fast_path", True):
        return False
    hit = match(text)
    if hit is None:
        return False
    name, args = hit
    if name not in registry.REGISTRY:
        return False
    owner = OWNER.get(name, "desk")
    sender = owner if owner in chat["members"] else "s" if "s" in chat["members"] else None
    if sender is None:
        return False
    ctx = TurnCtx(chat["id"], sender, crew, stop)
    await ctx.emit("step", bot=sender, tool=name, args=args, status="start")
    result = await registry.run(name, args, ctx)
    await ctx.emit("step", bot=sender, tool=name, status="done" if result.ok else "fail", text=result.text)
    if not result.ok and not result.text.lower().startswith(_FINAL):
        return False  # "open everything" isn't an app: let the bots work out what was meant
    await crew.say(chat["id"], sender, _reply(result))
    return True
