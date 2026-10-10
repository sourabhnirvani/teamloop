"""Paste a key anywhere: find it, check it live, save it to the vault, and use it right away."""

from __future__ import annotations

import os
from dataclasses import dataclass

import httpx

from teamloop.keys import vault
from teamloop.keys.redact import add_secret
from teamloop.models import providers as P


@dataclass
class Added:
    provider: str
    name: str        # provider display name
    status: str      # "saved", "duplicate", "rejected", "unchecked"

    def sentence(self) -> str:
        return {
            "saved": f"Saved your {self.name} key; it works.",
            "duplicate": f"That {self.name} key was already saved.",
            "rejected": f"{self.name} rejected that key, so I didn't save it.",
            "unchecked": f"Saved your {self.name} key, but I couldn't reach {self.name} to test it yet.",
        }[self.status]


async def check(provider: P.Provider, key: str) -> bool | None:
    """True = works, False = rejected, None = couldn't tell (network, rate limit)."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(P.base_url_for(provider).rstrip("/") + "/models",
                                    headers={"Authorization": f"Bearer {key}"})
    except httpx.HTTPError:
        return None
    if resp.status_code in (401, 403):
        return False
    return True if resp.status_code < 400 else None


def _free_name(provider: P.Provider) -> str:
    for name in [provider.env] + [f"{provider.env}_{i}" for i in range(2, 10)]:
        if not os.environ.get(name):
            return name
    return f"{provider.env}_9"


async def add_from_text(text: str, live_check: bool = True) -> list[Added]:
    results: list[Added] = []
    for provider, key in P.detect_keys(text):
        add_secret(key)
        if key in P.keys_for(provider):
            results.append(Added(provider.id, provider.name, "duplicate"))
            continue
        works = await check(provider, key) if live_check else None
        if works is False:
            results.append(Added(provider.id, provider.name, "rejected"))
            continue
        vault.put(_free_name(provider), key)
        results.append(Added(provider.id, provider.name, "saved" if works else "unchecked"))
    return results
