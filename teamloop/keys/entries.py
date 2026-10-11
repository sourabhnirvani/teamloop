"""Every saved model key, one row each: which provider, masked, does it work, where it comes from.

Statuses come from the last "test all" (`test_all`) and live in the store setting STATUS, keyed by env name,
so the page shows them without calling every provider on each load. Key text never leaves this module unmasked.
"""

from __future__ import annotations

import asyncio
import os
import time

from teamloop.keys import vault, wallet
from teamloop.models import providers as P

STATUS = "key_status"   # store setting: {env name: {status, reason, ts}}

REASONS = {
    "works": "",
    "rejected": "the provider said this key isn't valid (401/403)",
    "unchecked": "not tested yet",
}
NO_CLEAR_ANSWER = "tested, but the provider gave no clear yes or no (network, rate limit or another error)"


def mask(key: str) -> str:
    return "…" + key[-4:] if len(key) > 8 else "…"


def _names(provider: P.Provider) -> list[str]:
    return [provider.env] + [f"{provider.env}_{i}" for i in range(2, 10)] + list(provider.aliases)


def _saved() -> list[tuple[str, P.Provider, str]]:
    """(env name, provider, key) for every key-needing provider's keys in the environment, first name wins."""
    out, seen = [], set()
    for provider in P.PROVIDERS.values():
        if not provider.needs_key:
            continue
        for name in _names(provider):
            value = (os.environ.get(name) or "").strip()
            if value and value not in seen:
                seen.add(value)
                out.append((name, provider, value))
    return out


def _vault() -> dict[str, str]:
    try:
        return vault.load()
    except (OSError, ValueError):
        return {}


def source(name: str, value: str, in_vault: dict[str, str]) -> str:
    """"vault" when the vault holds this exact key, else "env" (.env or the system wins over the vault)."""
    return "vault" if in_vault.get(name, "").strip() == value else "env"


def entries(store) -> list[dict]:
    statuses = store.get_setting(STATUS, {}) or {}
    in_vault = _vault()
    rows = []
    for name, provider, value in _saved():
        known = statuses.get(name) or {}
        status = known.get("status", "unchecked")
        reason = NO_CLEAR_ANSWER if status == "unchecked" and known else REASONS[status]
        rows.append({"env": name, "provider": provider.id, "provider_name": provider.name, "masked": mask(value),
                     "status": status, "reason": reason, "source": source(name, value, in_vault)})
    return rows


async def test_all(store) -> list[dict]:
    """Check every saved key live and remember each answer."""
    saved = _saved()
    answers = await asyncio.gather(*(wallet.check(provider, value) for _, provider, value in saved))
    now = time.time()
    statuses = {name: {"status": {True: "works", False: "rejected"}.get(ok, "unchecked"), "ts": now}
                for (name, _, _), ok in zip(saved, answers)}
    store.set_setting(STATUS, statuses)
    return entries(store)


class FromEnv(Exception):
    """The key is set in .env or the system, so TeamLoop can't remove it."""


def remove(store, name: str) -> bool:
    """Remove a vault key. False if no saved key has that name; FromEnv if it comes from .env."""
    row = next((r for r in entries(store) if r["env"] == name), None)
    if row is None:
        return False
    if row["source"] != "vault":
        raise FromEnv(f"{name} comes from .env or the system, not the vault. Remove it there and restart TeamLoop.")
    vault.remove(name)
    statuses = store.get_setting(STATUS, {}) or {}
    statuses.pop(name, None)
    store.set_setting(STATUS, statuses)
    return True


def cleanup(store) -> dict:
    """Remove every vault key the last test rejected; rejected .env keys are listed, not touched."""
    removed, kept = [], []
    for row in entries(store):
        if row["status"] != "rejected":
            continue
        if row["source"] == "vault":
            remove(store, row["env"])
            removed.append(row["env"])
        else:
            kept.append(row["env"])
    return {"removed": removed, "kept_env": kept}
