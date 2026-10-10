"""Model doctor: ask each provider's models a tiny question and report which ones answer."""

from __future__ import annotations

import asyncio
import time

from teamloop.models import providers as P
from teamloop.models.router import AllModelsBusy, Router


async def check_all(router: Router, per_provider: int = 2) -> list[dict]:
    async def one(provider: P.Provider, model: str) -> dict:
        started = time.monotonic()
        try:
            reply = await asyncio.wait_for(
                router.chat([{"role": "user", "content": "Reply with the word ok."}],
                            prefer=f"{provider.id}:{model}", purpose="doctor", max_tokens=5, only=True), 40)
            ok, note = True, reply.text.strip()[:20]
        except (AllModelsBusy, asyncio.TimeoutError) as e:
            ok, note = False, str(e)[:160] or "timed out"
        return {"provider": provider.id, "name": provider.name, "model": model, "ok": ok,
                "seconds": round(time.monotonic() - started, 1), "note": note}

    jobs = []
    for provider in P.chain(router._env):
        if not P.keys_for(provider, router._env):
            continue
        models = [m for m in P.models_for(provider, router._env) if (provider.id, m) not in router.dead_models]
        jobs += [one(provider, m) for m in models[:per_provider]]
    return list(await asyncio.gather(*jobs))


def summary(results: list[dict]) -> str:
    if not results:
        return "No model keys are set up yet. Paste a free Gemini, Groq or OpenRouter key here and I'll save it."
    working = [f"{r['name']} {r['model']} ({r['seconds']}s)" for r in results if r["ok"]]
    broken = [f"{r['name']} {r['model']}" for r in results if not r["ok"]]
    text = f"Working: {', '.join(working)}." if working else "No model answered."
    if broken:
        text += f" Not answering: {', '.join(broken)}."
    return text
