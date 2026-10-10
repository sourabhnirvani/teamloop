"""Import every tool module so its tools register. Kits that aren't built yet are skipped."""

from __future__ import annotations

import importlib
import logging

log = logging.getLogger(__name__)

MODULES = (
    "teamloop.crew.team",       # delegate
    "teamloop.crew.routines",   # schedule_routine, list_routines, cancel_routine
    "teamloop.tools.web",
    "teamloop.tools.files",
    "teamloop.computer.tools",  # Desk (Windows)
    "teamloop.browser.kit",     # Web (Chrome)
)


def load_all() -> list[str]:
    loaded = []
    for name in MODULES:
        try:
            importlib.import_module(name)
        except ModuleNotFoundError as e:
            if e.name and name.startswith(e.name):
                log.info("kit %s not built yet", name)
            else:
                log.warning("kit %s skipped: missing %s", name, e.name)
            continue
        loaded.append(name)
    return loaded
