"""Hide secrets by value everywhere text leaves the process: events, logs, replies, approvals."""

from __future__ import annotations

import os
import re
from typing import Any

from teamloop.models.providers import PROVIDERS

HIDDEN = "[hidden key]"
_SECRET_NAME = re.compile(r"(_API_KEY(_\d+)?|_TOKEN|_SECRET|_PASSWORD)$")
_extra: set[str] = set()
_PATTERNS = [re.compile(p.key_pattern) for p in PROVIDERS.values() if p.key_pattern]


def add_secret(value: str) -> None:
    if value and len(value) >= 12:
        _extra.add(value)


def known_secrets() -> set[str]:
    values = {v for k, v in os.environ.items() if _SECRET_NAME.search(k) and len(v or "") >= 12}
    return values | _extra


def redact(text: str) -> str:
    if not text:
        return text
    for secret in sorted(known_secrets(), key=len, reverse=True):
        text = text.replace(secret, HIDDEN)
    for pattern in _PATTERNS:
        text = pattern.sub(HIDDEN, text)
    return text


def redact_obj(value: Any) -> Any:
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, dict):
        return {k: redact_obj(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact_obj(v) for v in value]
    return value
