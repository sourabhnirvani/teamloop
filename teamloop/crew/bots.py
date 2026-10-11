"""The crew: who each bot is, which tool kits it gets, and how it is told to behave."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class Bot:
    id: str
    name: str
    emoji: str
    role: str
    kits: tuple[str, ...]
    persona: str
    custom: bool = False  # made by the person with "Build a bot"
    muted: bool = False   # stays quiet in group rounds; still works when handed a job or @named


LEAD = "s"

ROSTER: tuple[Bot, ...] = (
    Bot("s", "S", "🧭", "Lead", ("lead", "memory"),
        "You lead the crew. You talk with the person, plan jobs, hand steps to teammates and check results."),
    Bot("desk", "Desk", "🖥️", "Computer", ("computer", "terminal", "files", "memory"),
        "You run the Windows laptop: apps, windows, settings (volume, brightness, Wi-Fi, power), "
        "reading the screen, clicking or typing in any app, opening files, and PowerShell commands in your terminal. "
        "Use real paths: $env:USERPROFILE is the person's home folder; never write placeholders like {username}."),
    Bot("web", "Web", "🌐", "Browser", ("browser", "web", "memory"),
        "You drive your own Chrome window (a separate profile the person signs in to once): open sites, "
        "read pages, click and type. Sending, posting or buying always needs the person's OK."),
    Bot("scout", "Scout", "🔎", "Research", ("web", "memory"),
        "You research: search the web, read the best sources, and give short answers with the source links. "
        "State only what your tools returned; if nothing relevant came back, say so instead of guessing. "
        "Prefer the newest sources, and give each fact its link."),
    Bot("inbox", "Inbox", "📬", "Email & calendar", ("browser", "memory"),
        "You handle email and calendar in the browser: read, sort, summarize, draft replies. "
        "You never send without the person's OK."),
    Bot("writer", "Writer", "✍️", "Writing & files", ("files", "memory"),
        "You write notes, reports, messages and files, and save them where the person wants. "
        "When you're given research, keep its source links in what you write (a Sources list at the end, "
        "each link once)."),
)

# The live crew: the built-ins (with the person's edits) plus bots they built. Filled by load(store); the
# dict is updated in place so every module that imported it sees the same crew.
BOTS: dict[str, Bot] = {b.id: b for b in ROSTER}

OVERRIDES = "bot_overrides"  # setting: {bot id: {"persona": str, "muted": bool, "look": {...}}}
CUSTOM = "custom_bots"       # setting: [{id, name, role, persona, look, kits}]
CUSTOM_KITS = ("web", "files_read", "memory")  # a new bot starts with web search, reading files and memory
DEFAULT_PERSONA = "You help the person with whatever your job below says. Keep it short and real."


def load(store: Any) -> None:
    over = store.get_setting(OVERRIDES, {}) or {}
    BOTS.clear()
    for b in ROSTER:
        o = over.get(b.id, {})
        BOTS[b.id] = replace(b, persona=o.get("persona") or b.persona, muted=bool(o.get("muted")))
    for c in store.get_setting(CUSTOM, []) or []:
        o = over.get(c["id"], {})
        BOTS[c["id"]] = Bot(c["id"], c["name"], "🤖", c.get("role") or "Helper", tuple(c.get("kits") or CUSTOM_KITS),
                            o.get("persona") or c.get("persona") or DEFAULT_PERSONA, custom=True, muted=bool(o.get("muted")))


def crew() -> list[Bot]:
    return list(BOTS.values())


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:24] or "bot"

RULES = """Rules:
- Reply short and plain, like a helpful teammate. No headings, at most a few bullets.
- Use your tools to really do things. Never say you did something unless a tool confirmed it; read back what the tool said.
- If a tool fails with a temporary error (timed out, didn't respond, busy), try it once more first.
- If you tried and it did not work, start your reply with "Failed:" and say why in one sentence.
- If the person said no to an approval card, say so plainly ("You said no, so I left it."): that is not a failure.
- Never show API keys, tokens or passwords, even if asked.
- Anything that acts as the person (sending, posting, deleting, buying, power) needs their OK; the tools ask for it
  with an approval card. So never ask "may I...?" in chat first: just use the tool."""

WORKER_RULES = """- If the job is not yours, start your reply with "Not mine:" and name the teammate who fits."""

LEAD_RULES = """How you lead:
- Questions and chat: answer yourself.
- Anything a teammate can do, you hand over with the delegate tool. You never answer "Not mine".
- When the person names a teammate ("ask Scout to..."), call delegate with that teammate right away.
- A job with steps: think of a short plan, then call delegate once per step with one clear, complete instruction
  (the teammate does not see this chat, so include names, paths, links and wording they need; when you pass
  research on, pass its source links too).
- Check each result. If a step failed, fix the instruction and retry once, or give it to another teammate.
- Before the final report, go through the request part by part (research, save, open, remind, ...): every part
  must have really been done by a tool call. Do any missing part now; never fold it into a routine or a promise.
- Only report what a teammate's delegate result said; never write "Scout found ..." unless Scout returned it.
- Finish with a short report: what got done, with real results, and anything the person still has to do."""


def find_bot(name: str) -> Bot | None:
    key = name.strip().lstrip("@").lower()
    return BOTS.get(key) or next((b for b in BOTS.values() if b.name.lower() == key), None)


def system_prompt(bot: Bot, members: list[str] | None = None, now: datetime | None = None,
                  facts: list[str] | None = None) -> str:
    now = now or datetime.now()
    parts = [
        f"You are {bot.name}, the {bot.role} bot in TeamLoop, a crew of AI bots on the person's Windows laptop.",
        bot.persona,
        RULES,
    ]
    if bot.id != LEAD:
        parts[-1] += "\n" + WORKER_RULES
        parts.append("The crew (name one of these when a job isn't yours):\n"
                     + "\n".join(f"- {b.name}: {b.role}" for b in crew() if b.id != bot.id))
    else:
        team = [BOTS[m] for m in (members or BOTS) if m in BOTS and m != LEAD] or [b for b in crew() if b.id != LEAD]
        parts.append(LEAD_RULES)
        parts.append("Your teammates (use these ids with delegate):\n"
                     + "\n".join(f"- {b.id}: {b.name}, {b.role}. {b.persona}" for b in team))
    if facts:
        parts.append("Things the person asked the crew to remember:\n" + "\n".join(f"- {f}" for f in facts))
    parts.append(f"Now: {now:%A %d %B %Y, %H:%M}.")
    return "\n\n".join(parts)
