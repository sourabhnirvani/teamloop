"""Free model providers. They all speak the OpenAI chat API, so one client type covers them.

Keys come from the environment: GEMINI_API_KEY, GEMINI_API_KEY_2, ... form one pool.
Model lists can be overridden per provider, e.g. GROQ_MODELS="openai/gpt-oss-120b,...".
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class Provider:
    id: str
    name: str
    base_url: str
    env: str                      # key variable; NAME, NAME_2 ... NAME_9 form a pool
    models: tuple[str, ...]
    key_pattern: str | None = None  # spots a pasted key of this provider
    needs_key: bool = True
    aliases: tuple[str, ...] = ()   # other variable names people already use for this key

    @property
    def prefix(self) -> str:
        return self.env.removesuffix("_API_KEY")


PROVIDERS: dict[str, Provider] = {p.id: p for p in [
    Provider("gemini", "Gemini", "https://generativelanguage.googleapis.com/v1beta/openai/",
             "GEMINI_API_KEY", ("gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash"),
             r"AIza[0-9A-Za-z_\-]{35}", aliases=("GOOGLE_API_KEY",)),
    Provider("groq", "Groq", "https://api.groq.com/openai/v1",
             "GROQ_API_KEY", ("openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"),  # Oct 2026 list
             r"gsk_[0-9A-Za-z]{52}"),
    Provider("openrouter", "OpenRouter", "https://openrouter.ai/api/v1",
             "OPENROUTER_API_KEY", ("openai/gpt-oss-20b:free", "meta-llama/llama-3.3-70b-instruct:free",
                                    "deepseek/deepseek-chat-v3.1:free"),
             r"sk-or-v1-[0-9a-f]{64}"),
    Provider("nvidia", "NVIDIA", "https://integrate.api.nvidia.com/v1",
             "NVIDIA_API_KEY", ("nvidia/nemotron-3-super-120b-a12b", "nvidia/nemotron-3.5-lightning-30b-a3b",
                               "z-ai/glm-5.3-flash"),
             r"nvapi-[0-9A-Za-z_\-]{64}", aliases=("NVIDIA_NIM_API_KEY",)),
    Provider("zai", "GLM (z.ai)", "https://api.z.ai/api/paas/v4",
             "ZAI_API_KEY", ("glm-5.3-flash", "glm-4.5-flash"),
             r"[0-9a-f]{32}\.[0-9A-Za-z]{16}"),
    Provider("nebius", "Nebius", "https://api.studio.nebius.com/v1/",
             "NEBIUS_API_KEY", ("meta-llama/Llama-3.3-70B-Instruct",)),
    Provider("ollama", "Local (Ollama)", "http://localhost:11434/v1",
             "OLLAMA_API_KEY", ("qwen2.5:7b",), needs_key=False),
]}

DEFAULT_CHAIN: tuple[str, ...] = ("gemini", "groq", "openrouter", "nvidia", "zai", "nebius", "ollama")


# Free only, always, unless TEAMLOOP_ALLOW_PAID=1: Nebius bills per token once its trial credit runs out,
# and on OpenRouter only the ":free" models cost nothing. (Gemini and Groq keys are free unless billing is
# switched on for that account; use keys from accounts without billing.)
PAID_PROVIDERS = {"nebius"}


def paid_allowed(env: Mapping[str, str] | None = None) -> bool:
    env = os.environ if env is None else env
    return (env.get("TEAMLOOP_ALLOW_PAID") or "").strip() == "1"


def free_to_use(provider_id: str, model: str = "", env: Mapping[str, str] | None = None) -> bool:
    if paid_allowed(env):
        return True
    if provider_id in PAID_PROVIDERS:
        return False
    if provider_id == "openrouter" and model:
        return model.endswith(":free")
    return True


def chain(env: Mapping[str, str] | None = None) -> list[Provider]:
    env = os.environ if env is None else env
    order = [p.strip() for p in env.get("TEAMLOOP_CHAIN", "").split(",") if p.strip()] or DEFAULT_CHAIN
    return [PROVIDERS[p] for p in order if p in PROVIDERS and free_to_use(p, env=env)]


def keys_for(provider: Provider, env: Mapping[str, str] | None = None) -> list[str]:
    env = os.environ if env is None else env
    if not provider.needs_key:
        return [""]
    names = [provider.env] + [f"{provider.env}_{i}" for i in range(2, 10)] + list(provider.aliases)
    keys: list[str] = []
    for name in names:
        value = (env.get(name) or "").strip()
        if value and value not in keys:
            keys.append(value)
    return keys


def models_for(provider: Provider, env: Mapping[str, str] | None = None) -> list[str]:
    env = os.environ if env is None else env
    override = env.get(f"{provider.prefix}_MODELS", "")
    models = [m.strip() for m in override.split(",") if m.strip()]
    if not models and provider.id == "ollama":
        models = installed_ollama_models(base_url_for(provider, env))
    models = models or list(provider.models)
    return [m for m in models if free_to_use(provider.id, m, env)]


_ollama_seen: dict[str, tuple[float, list[str]]] = {}
# what Ollama says about each installed model: {"tools": bool | None, "ctx": int | None} (None: it didn't say)
_ollama_info: dict[str, dict[str, dict]] = {}
_ollama_up: dict[str, bool] = {}  # did Ollama answer at the last look


def ollama_root(base_url: str) -> str:
    return base_url.rstrip("/").removesuffix("/v1")


def installed_ollama_models(base_url: str, ttl: float = 60.0) -> list[str]:
    """The chat models this Ollama really has (GET /api/tags), checked at most once a minute."""
    now = time.monotonic()
    cached = _ollama_seen.get(base_url)
    if cached and now - cached[0] < ttl:
        return cached[1]
    models: list[str] = []
    info: dict[str, dict] = {}
    up = False
    try:
        import httpx

        tags = httpx.get(ollama_root(base_url) + "/api/tags", timeout=0.5).json()
        up = True
        for m in tags.get("models", []):
            name, caps = m.get("name", ""), m.get("capabilities")
            if "embed" in name or (isinstance(caps, list) and caps and "completion" not in caps):
                continue  # an embedding model can't chat
            models.append(name)
            info[name] = {"tools": ("tools" in caps) if isinstance(caps, list) and caps else None,
                          "thinking": isinstance(caps, list) and "thinking" in caps,
                          "ctx": (m.get("details") or {}).get("context_length")}
    except Exception:
        pass  # not running: the default model name stays, and a call fails fast
    _ollama_seen[base_url] = (now, models)
    _ollama_info[ollama_root(base_url)] = info
    _ollama_up[ollama_root(base_url)] = up
    return models


def ollama_running(base_url: str) -> bool:
    installed_ollama_models(base_url)  # refreshed at most once a minute
    return _ollama_up.get(ollama_root(base_url), False)


def ollama_model_info(base_url: str, model: str) -> dict:
    return _ollama_info.get(ollama_root(base_url), {}).get(model, {})


def base_url_for(provider: Provider, env: Mapping[str, str] | None = None) -> str:
    env = os.environ if env is None else env
    if provider.id == "ollama":
        return env.get("OLLAMA_URL") or provider.base_url
    return provider.base_url


def detect_keys(text: str) -> list[tuple[Provider, str]]:
    """Find provider keys inside free text (a pasted key, a chat message, a .env dump)."""
    found: list[tuple[Provider, str]] = []
    for provider in PROVIDERS.values():
        if not provider.key_pattern:
            continue
        for match in re.finditer(rf"(?<![0-9A-Za-z_\-]){provider.key_pattern}(?![0-9A-Za-z_\-])", text):
            if all(match.group(0) != key for _, key in found):
                found.append((provider, match.group(0)))
    return found
