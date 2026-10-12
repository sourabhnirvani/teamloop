"""Did the lead do every step the person asked for, and only report what really happened?

A plain checklist from the request's verbs ("research …, save it as a report, open it, remind me every
Monday") against the tools the crew really used in this job. Free models like to fold a step into the
report ("the file will be opened automatically") or say "Scout found …" without asking Scout; the runner
sends the lead back once with what is missing.
"""

from __future__ import annotations

import re

# (what the person asked for, how they say it, tools that do it)
ASKS: list[tuple[str, re.Pattern, frozenset[str]]] = [
    # "open" as a verb: not "what apps are open", "open-source", "open windows"
    ("open it", re.compile(r"(?<!are )(?<!is )(?<!still )(?<!already )\b(?:open|launch)\b"
                           r"(?![\s-]+(?:source|ai|weights?|ended|minded|apps|windows|programs|right now)\b)(?!\s*\?)",
                           re.I),
     frozenset({"open_file", "open_app", "browser_open"})),
    ("save the file", re.compile(r"\b(?:save|write|create|draft)\b[^.?!]{0,60}\b(?:file|report|note|notes|doc|document|"
                                 r"summary|list|txt|md)\b", re.I),
     frozenset({"write_file"})),
    ("set the reminder", re.compile(r"\bremind\b|\bschedule\b|\bevery\s+(?:day|morning|evening|night|week|weekday|month|"
                                    r"hour|\d+|monday|tuesday|wednesday|thursday|friday|saturday|sunday)", re.I),
     frozenset({"schedule_routine"})),
    ("do the research", re.compile(r"\b(?:research|look up|find out|search(?:\s+the\s+web)?\s+for|top\s+\d+)\b", re.I),
     frozenset({"web_search", "fetch_page", "browser_read", "browser_open"})),
    ("close it", re.compile(r"\bclose\b", re.I), frozenset({"close_app", "press_keys", "ui_act"})),
    ("set the volume", re.compile(r"\bvolume\b|\bmute\b", re.I), frozenset({"set_volume"})),
    ("set the brightness", re.compile(r"\bbrightness\b", re.I), frozenset({"set_brightness"})),
]

# "Scout found …", "Writer saved …", "Scout: …" — a teammate's result in the lead's own words
_CLAIM = r"\b{name}\b(?:'s)?\s*(?::|says?\b|said\b|found\b|reports?\b|saved\b|wrote\b|opened\b|searched\b|set\b|did\b|" \
         r"looked\b|checked\b|confirmed\b)"


def missing(goal: str, used: set[str]) -> list[str]:
    """The asks in `goal` that no tool used in this job covers (an attempt counts, even a denied one)."""
    return [label for label, said, tools in ASKS if said.search(goal or "") and not (tools & used)]


def missing_actions(goal: str, used: set[str]) -> list[str]:
    """Like missing(), for things done to the laptop only (save, open, remind, close, volume, brightness), and
    never for a question ("can you save files?"): those must have a tool behind them even when the lead
    handed nothing out. Research is left out: the lead may answer a question from what it knows."""
    if (goal or "").rstrip().endswith("?"):
        return []
    return [label for label in missing(goal, used) if label != "do the research"]


def not_done(todo: list[str]) -> str:
    """The runner's own honest line when the lead still says a step is done that no tool did."""
    return f'Not done: {", ".join(todo)} (no tool ran for it). Say "try again" and I\'ll do it.'


def false_claims(text: str, names: dict[str, str], spoke: set[str]) -> list[str]:
    """Teammate names the reply quotes as having done something, though they never ran in this job.
    `names` maps bot id -> display name (the lead excluded)."""
    out = []
    for bot_id, name in names.items():
        if bot_id not in spoke and re.search(_CLAIM.format(name=re.escape(name)), text or "", re.I):
            out.append(name)
    return out


def nudge(todo: list[str], claimed: list[str]) -> str:
    parts = []
    if todo:
        parts.append(f"Not done yet: {', '.join(todo)}. The person asked for it, so do it now with delegate "
                     "(Desk opens files and apps, Writer saves files, Scout researches; set reminders with "
                     "schedule_routine), then give the final report.")
    if claimed:
        who = " and ".join(claimed)
        parts.append(f"You wrote what {who} did, but {who} didn't work on this job. Use delegate to have them "
                     "do it, or report only what really happened.")
    return " ".join(parts) + " Never say a teammate did something unless delegate returned it."
