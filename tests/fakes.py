"""A scripted stand-in for the model router, so crew tests never call a real model."""

import asyncio
import inspect

from teamloop.crew.events import Bus
from teamloop.crew.store import Store
from teamloop.crew.team import Crew
from teamloop.models.router import Reply, ToolCall


def call(name, **args):
    return Reply("", [ToolCall(f"call-{name}", name, args)], "fake", "fake-1")


class FakeRouter:
    """Each chat() takes the next step: a str (reply), a Reply, an exception, or a (async) callable."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []
        self.dead_models = set()

    async def chat(self, messages, tools=None, prefer=None, purpose="", max_tokens=None):
        self.calls.append({"messages": [dict(m) for m in messages], "tools": tools, "purpose": purpose})
        step = self.script.pop(0) if self.script else "Done."
        if callable(step):
            step = step(messages, tools, purpose)
            if inspect.isawaitable(step):
                step = await step
        if isinstance(step, BaseException):
            raise step
        if isinstance(step, str):
            return Reply(step, [], "fake", "fake-1")
        return step


async def hang(*_):
    await asyncio.Event().wait()


def make_crew(tmp_path, script):
    from teamloop import kits

    kits.load_all()
    store = Store(tmp_path / "crew.db")
    crew = Crew(store, FakeRouter(script), Bus())
    crew.ensure_default_chats()
    return crew
