"""One worker thread for all COM work (audio, UI Automation), so COM objects stay in their apartment."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, TypeVar

T = TypeVar("T")


def _init() -> None:
    import comtypes

    comtypes.CoInitialize()


_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="teamloop-com", initializer=_init)


async def run(fn: Callable[..., T], *args) -> T:
    return await asyncio.get_running_loop().run_in_executor(_pool, fn, *args)
