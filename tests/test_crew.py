import asyncio

from fakes import call, hang, make_crew

from teamloop.computer.gate import Gate
from teamloop.crew.events import Bus
from teamloop.crew.store import Store
from teamloop.models.router import AllModelsBusy


def senders(crew, chat_id):
    return [m["sender"] for m in crew.store.messages(chat_id)]


async def test_one_to_one_chat_gets_a_reply(tmp_path):
    crew = make_crew(tmp_path, ["Hi, I'm S."])
    await crew.post("dm-s", "hello")
    await crew.wait_idle("dm-s")
    assert senders(crew, "dm-s") == ["user", "s"]
    assert crew.store.messages("dm-s")[-1]["text"] == "Hi, I'm S."


async def test_lead_delegates_checks_and_reports(tmp_path):
    crew = make_crew(tmp_path, [
        call("delegate", bot="scout", instruction="Find the capital of France."),
        "Paris is the capital of France.",
        "Scout checked it: Paris.",
    ])
    await crew.post("team", "what's the capital of France?")
    await crew.wait_idle("team")
    msgs = crew.store.messages("team")
    assert senders(crew, "team") == ["user", "s", "scout", "s"]
    assert msgs[1]["kind"] == "handoff" and msgs[1]["text"].startswith("@Scout")
    third_call = crew.router.calls[2]["messages"]
    assert any(m["role"] == "tool" and "Paris" in m["content"] for m in third_call)


async def test_mentions_pick_who_answers(tmp_path):
    crew = make_crew(tmp_path, [])
    team = crew.store.get_chat("team")
    assert [b.id for b in crew.responders(team, "@Writer draft it, @desk open it")] == ["writer", "desk"]
    assert [b.id for b in crew.responders(team, "plan my day")] == ["s"]
    assert [b.id for b in crew.responders(crew.store.get_chat("dm-web"), "@scout hi")] == ["web"]


async def test_delegate_to_unknown_bot_explains(tmp_path):
    crew = make_crew(tmp_path, [call("delegate", bot="pilot", instruction="x"), "Sorry, no such teammate."])
    await crew.post("dm-s", "do it")
    await crew.wait_idle("dm-s")
    tool_msg = next(m for m in crew.router.calls[1]["messages"] if m["role"] == "tool")
    assert "no teammate called" in tool_msg["content"]


async def test_stop_cancels_running_work(tmp_path):
    crew = make_crew(tmp_path, [hang])
    await crew.post("dm-desk", "tidy up everything")
    await asyncio.sleep(0.05)
    assert await crew.stop("dm-desk")
    assert crew.store.messages("dm-desk")[-1]["text"] == "Stopped."


async def test_typed_stop_word_stops(tmp_path):
    crew = make_crew(tmp_path, [hang])
    await crew.post("dm-desk", "tidy up everything")
    await asyncio.sleep(0.05)
    await crew.post("dm-desk", "stop")
    assert crew.store.messages("dm-desk")[-1]["text"] == "Stopped."


async def test_busy_models_become_a_plain_failure(tmp_path):
    crew = make_crew(tmp_path, [AllModelsBusy("No model answered: Gemini gm: limit")])
    await crew.post("dm-s", "hi")
    await crew.wait_idle("dm-s")
    assert crew.store.messages("dm-s")[-1]["text"].startswith("Failed: No model answered")


async def test_history_marks_who_said_what(tmp_path):
    crew = make_crew(tmp_path, [])
    crew.store.add_message("team", "user", "hi all")
    crew.store.add_message("team", "scout", "found it")
    crew.store.add_message("team", "s", "great")
    crew.store.add_message("team", "user", "next")
    assert crew.history("team", "s") == [
        {"role": "user", "content": "hi all"},
        {"role": "user", "content": "[Scout] found it"},
        {"role": "assistant", "content": "great"},
    ]


async def test_gate_approve_deny_and_timeout(tmp_path):
    store, bus = Store(tmp_path / "g.db"), Bus()
    gate = Gate(store, bus, timeout=1)
    with bus.subscribe() as queue:
        task = asyncio.create_task(gate.ask("c1", "desk", "Close Word", "Unsaved changes may be lost."))
        event = await queue.get()
        assert event["type"] == "approval" and event["title"] == "Close Word"
        assert gate.answer(event["id"], True)
        assert await task is True
    assert gate.answer(event["id"], True) is False

    task = asyncio.create_task(gate.ask("c1", "desk", "Shut down", "Turns the laptop off."))
    await asyncio.sleep(0.01)
    assert gate.deny_all("c1") == 1
    assert await task is False

    gate.timeout = 0.05
    assert await gate.ask("c1", "desk", "Sleep", "x") is False
    assert store.pending_approvals() == []
