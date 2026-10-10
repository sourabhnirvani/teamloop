"""Things the person can say that never go to a model: pasted keys, model switching, modes, the doctor."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from teamloop import trace
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
SLEEP = re.compile(r"^\s*(?:(?:hey |ok )?(?:s|team|crew)[,:]?\s+)?(?:(?:it'?s |its )?time to sleep|go to sleep|"
                   r"sleep now|so ja(?:o)?)\s*[.!]?\s*$", re.I)
WAKE = re.compile(r"^\s*(?:(?:hey |ok )?(?:s|team|crew)[,:]?\s+)?(?:wake\s*up|wakeup|uth ja(?:o)?)\s*[.!]?\s*$", re.I)
ASLEEP_NOTE = "The crew is asleep, so nothing runs (routines wait too). Say \"S wake up\" to wake us."


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
    if P.detect_keys(text) or wallet.service_keys(text):
        sentences = wallet.add_services(text)
        if any(env == "NEATLOGS_API_KEY" for env, _, _ in wallet.service_keys(text)):
            sentences.append("Tracing is on." if trace.init() else "Tracing will start after a restart.")
        results = await wallet.add_from_text(text)
        crew.router.dead_models.clear()
        return " ".join(sentences + [r.sentence() for r in results])

    if SLEEP.match(text):
        crew.store.set_setting("asleep", True)
        return "Going to sleep: no bot will act and routines wait until you say \"S wake up\"."
    if WAKE.match(text):
        was = crew.store.get_setting("asleep", False)
        crew.store.set_setting("asleep", False)
        return "Awake and ready." if was else "Already awake."

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
        pid, _, model = target.partition(":")
        if target and not P.free_to_use(pid, model):
            return (f"{target} can cost money, so TeamLoop won't use it: everything stays free. "
                    "Pick a free one (on OpenRouter, the models ending in :free).")
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
