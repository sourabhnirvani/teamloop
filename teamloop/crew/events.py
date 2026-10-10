"""Live events for the UI (SSE), the phone and Telegram. Everything is redacted on the way out."""

from __future__ import annotations

import asyncio
import contextlib
import time
from typing import Iterator

from teamloop.keys.redact import redact_obj


class Bus:
    def __init__(self, queue_size: int = 500):
        self._subs: set[asyncio.Queue] = set()
        self._size = queue_size

    async def emit(self, type: str, **data) -> dict:
        event = redact_obj({"type": type, "ts": time.time(), **data})
        for queue in list(self._subs):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:  # a stuck listener loses old events, never blocks the crew
                with contextlib.suppress(asyncio.QueueEmpty):
                    queue.get_nowait()
                queue.put_nowait(event)
        return event

    @contextlib.contextmanager
    def subscribe(self) -> Iterator[asyncio.Queue]:
        queue: asyncio.Queue = asyncio.Queue(self._size)
        self._subs.add(queue)
        try:
            yield queue
        finally:
            self._subs.discard(queue)
