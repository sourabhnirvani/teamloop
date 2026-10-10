"""Things the person can say that never go to a model: pasted keys, model switching, modes, the doctor."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from teamloop.crew.bots import find_bot
from teamloop.keys import wallet
from teamloop.models import doctor
from teamloop.models import providers as P

if TYPE_CHECKING:
    from teamloop.crew.team import Crew

PROVIDER_WORDS = {
    "gemini": "gemini", "groq": "groq", "openrouter": "openrouter", "nvidia": "nvidia", "nemotron": "nvidia",
    "glm": "zai", "z.ai": "zai", "zai": "zai", "nebius": "nebius", "local": "ollama", "local model": "ollama",
    "ollama": "ollama", "qwen": "ollama",
}
SWITCH = re.compile(r"^\s*(?:please\s+)?(?:use|switch to|change to)\s+(?P<target>[\w.:/\- ]+?)"
                    r"(?:\s+(?:model\s+)?(?:for|on)\s+@?(?P<bot>\w+))?(?:\s+model)?\s*[.!]?\s*$", re.IGNORECASE)
SAVE_ON = re.compile(r"^\s*(?:turn on |switch to |use )?(?:save|saving) tokens?(?: mode)?(?: on)?\s*[.!]?\s*$", re.I)
SAVE_OFF = re.compile(r"^\s*(?:turn off save tokens?(?: mode)?|(?:switch to |use )?normal mode|save tokens?(?: mode)? off)\s*[.!]?\s*$", re.I)
DOCTOR = re.compile(r"^\s*(?:check (?:the )?models|which models (?:work|are working)|model doctor)\s*[.?!]?\s*$", re.I)


def _target(word: str) -> str | None:
    word = word.strip().lower()
    if word in ("auto", "default", "automatic", "any"):
        return ""
    if word in PROVIDER_WORDS:
        return PROVIDER_WORDS[word]
    pid, sep, model = word.partition(":")
    if sep and pid in P.PROVIDERS and model:
        return f"{pid}:{model}"
    return None


async def handle(crew: "Crew", chat: dict, text: str) -> str | None:
    if P.detect_keys(text):
        results = await wallet.add_from_text(text)
        crew.router.dead_models.clear()
        return " ".join(r.sentence() for r in results)

    if SAVE_ON.match(text):
        crew.store.set_setting("save_tokens", True)
        return "Save tokens mode is on: shorter history, fewer steps, and only S answers in groups. Say \"normal mode\" to go back."
    if SAVE_OFF.match(text):
        crew.store.set_setting("save_tokens", False)
        return "Normal mode is on."

    if DOCTOR.match(text):
        return doctor.summary(await doctor.check_all(crew.router))

    match = SWITCH.match(text)
    if match:
        target = _target(match.group("target"))
        if target is None:
            return None  # "switch to google chrome" is not about models
        bot = find_bot(match.group("bot")) if match.group("bot") else None
        if match.group("bot") and bot is None:
            return None
        if bot:
            models = dict(crew.store.get_setting("bot_models", {}) or {})
            if target:
                models[bot.id] = target
            else:
                models.pop(bot.id, None)
            crew.store.set_setting("bot_models", models)
            return f"{bot.name} now uses {target or 'the automatic choice'}."
        crew.store.set_setting("crew_model", target or None)
        if target and not P.keys_for(P.PROVIDERS[target.partition(':')[0]]):
            return f"Switched the crew to {target}, but there's no key for it yet; paste one here and I'll save it."
        return f"The crew now uses {target or 'the automatic choice (best free model that answers)'}."
    return None
