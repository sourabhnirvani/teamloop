"""neatlogs tracing.

A WORKFLOW span per chat message (session = the chat), an AGENT span per bot turn, a TOOL span per
tool call, and LLM spans from the wrapped model clients. Without NEATLOGS_API_KEY everything here is a
no-op, so tests and offline runs work the same.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
from typing import Any, Iterator

log = logging.getLogger(__name__)

_neat: Any = None
MAX_ATTR = 8000  # characters kept per input/output value
KINDS = {"workflow": "WORKFLOW", "agent": "AGENT", "tool": "TOOL", "chain": "CHAIN"}


def init(workflow: str = "teamloop") -> bool:
    global _neat
    if _neat is not None:
        return True
    key = os.getenv("NEATLOGS_API_KEY")
    if not key or os.getenv("TEAMLOOP_TRACE") == "0":
        return False
    try:
        import neatlogs

        neatlogs.init(api_key=key, workflow_name=workflow, endpoint=os.getenv("NEATLOGS_ENDPOINT") or None)
    except Exception as e:
        log.warning("neatlogs is off: %s", e)
        return False
    _neat = neatlogs
    log.info("neatlogs tracing on (workflow %s)", workflow)
    return True


def enabled() -> bool:
    return _neat is not None


def wrap(client: Any) -> Any:
    if _neat is None:
        return client
    try:
        return _neat.wrap(client)
    except Exception as e:
        log.debug("neatlogs could not wrap %s: %s", type(client).__name__, e)
        return client


class Span:
    """What a `with span(...) as s:` block gets: s.set("output.value", text). A no-op when tracing is off.
    Text is redacted on the way out, so keys never reach neatlogs."""

    def __init__(self, raw: Any = None):
        self.raw = raw

    def set(self, key: str, value: Any) -> None:
        if self.raw is None:
            return
        from teamloop.keys.redact import redact

        if not isinstance(value, (str, int, float, bool)):
            value = json.dumps(value, ensure_ascii=False, default=str)
        if isinstance(value, str):
            value = redact(value)[:MAX_ATTR]
        try:
            self.raw.set_attribute(key, value)
        except Exception as e:
            log.debug("neatlogs attribute %s skipped: %s", key, e)


@contextlib.contextmanager
def span(name: str, kind: str = "chain", session_id: str | None = None, **attrs: Any) -> Iterator[Span]:
    if _neat is None:
        yield Span()
        return
    try:
        cm = _neat.trace(name, kind=KINDS.get(kind, kind.upper()), session_id=session_id,
                         **{k: str(v) for k, v in attrs.items()})
        handle = Span(cm.__enter__())
        # trace() marks hand-made spans internal (hidden in the trace view); ours are the story, so show them.
        handle.set("neatlogs.internal", False)
    except Exception as e:
        log.debug("neatlogs span %s skipped: %s", name, e)
        yield Span()
        return
    exc: tuple = (None, None, None)
    try:
        yield handle
    except BaseException as e:
        exc = (type(e), e, e.__traceback__)
        raise
    finally:
        try:
            cm.__exit__(*exc)
        except Exception as e:
            log.debug("neatlogs span %s close failed: %s", name, e)


def flush() -> None:
    if _neat is not None:
        with contextlib.suppress(Exception):
            _neat.flush(5000)
