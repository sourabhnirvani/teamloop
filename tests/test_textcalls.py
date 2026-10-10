from types import SimpleNamespace

import pytest

from teamloop.models import providers as P
from teamloop.models.router import Router
from teamloop.models.textcalls import extract

NAMES = ["open_app", "set_volume", "web_search"]


@pytest.mark.parametrize("text, calls, left", [
    ('<tool_call>{"name": "open_app", "arguments": {"name": "Calculator"}}</tool_call>',
     [("open_app", {"name": "Calculator"})], ""),
    ('Sure.\n```json\n{"name": "set_volume", "parameters": {"level": 30}}\n```',
     [("set_volume", {"level": 30})], "Sure."),
    ('<function=web_search>{"query": "free llm apis"}</function>',
     [("web_search", {"query": "free llm apis"})], ""),
    ('[TOOL_CALLS] [{"name": "open_app", "arguments": {"name": "Notepad"}}, '
     '{"name": "set_volume", "arguments": "{\\"mute\\": true}"}]',
     [("open_app", {"name": "Notepad"}), ("set_volume", {"mute": True})], ""),
    ('<|python_tag|>{"type": "function", "function": {"name": "open_app", "arguments": {"name": "Paint"}}}',
     [("open_app", {"name": "Paint"})], ""),
])
def test_text_tool_calls_are_found(text, calls, left):
    assert extract(text, NAMES) == (calls, left)


@pytest.mark.parametrize("text", [
    "Volume is now 30%.",
    'Here is the JSON you asked for: {"name": "Alice", "arguments": {"age": 3}}',
    '{"name": "delete_everything", "arguments": {}}',  # not a tool this bot has
    '{"name": "open_app", "arguments": "not json"}',
])
def test_plain_text_and_unknown_tools_stay_text(text):
    assert extract(text, NAMES) == ([], text)


async def test_router_runs_text_tool_calls(monkeypatch):
    message = SimpleNamespace(content='<tool_call>{"name": "open_app", "arguments": {"name": "Calculator"}}</tool_call>',
                              tool_calls=None)

    async def create(**kwargs):
        return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=None)

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    router = Router(env={})
    monkeypatch.setattr(router, "_client", lambda provider, key: client)
    tools = [{"type": "function", "function": {"name": n, "parameters": {}}} for n in NAMES]
    reply = await router._call(P.PROVIDERS["groq"], "k", "m", [{"role": "user", "content": "hi"}], tools, None)
    assert [(c.name, c.args) for c in reply.tool_calls] == [("open_app", {"name": "Calculator"})]
    assert reply.text == "" and reply.message["tool_calls"][0]["function"]["name"] == "open_app"

    no_tools = await router._call(P.PROVIDERS["groq"], "k", "m", [], None, None)
    assert no_tools.tool_calls == [] and no_tools.text == message.content


async def test_doctor_runs_at_startup_and_again_later(monkeypatch):
    import asyncio

    from teamloop.models import doctor

    runs = []

    async def fake_check(router):
        runs.append(set(router.dead_models))
        router.dead_models.add(("groq", "old-model"))
        return [{"provider": "groq", "name": "Groq", "model": "m", "ok": True, "seconds": 0.1, "note": "ok"}]

    monkeypatch.setattr(doctor, "check_all", fake_check)
    router = Router(env={})
    task = asyncio.create_task(doctor.keep_checking(router, hours=0.05 / 3600, first_delay=0))
    for _ in range(100):
        if len(runs) >= 2:
            break
        await asyncio.sleep(0.02)
    task.cancel()
    assert len(runs) >= 2 and runs[1] == set()  # each run gives dead models another chance
    assert router.last_doctor[0]["ok"] is True
    assert await doctor.keep_checking(router, hours=0) is None  # 0 = off
