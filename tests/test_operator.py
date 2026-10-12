"""Build B, operator safety: pause while the person uses the PC, ignore our own input, stop everything."""

import asyncio

import pytest
from fakes import FakeRouter
from fastapi.testclient import TestClient

from teamloop.computer import operator, tools
from teamloop.server.app import build_crew, create_app
from teamloop.tools import registry


class FakeClock:
    """A clock that only moves when the operator sleeps; `idle_at` maps clock time to the PC's idle seconds."""

    def __init__(self, person_until: float):
        self.now = 100.0
        self.person_until = person_until   # the person types until this clock time, then stops

    def clock(self):
        return self.now

    def idle(self):
        return 0.0 if self.now < self.person_until else self.now - self.person_until

    async def sleep(self, seconds):
        self.now += seconds


async def test_waits_while_the_person_works_then_carries_on_by_itself():
    fake = FakeClock(person_until=105.0)
    op = operator.Operator(fake.idle, fake.clock, fake.sleep)
    states = []

    async def watch(seconds):
        states.append(op.state()["paused"])
        await FakeClock.sleep(fake, seconds)
    op.sleep = watch
    waited = await op.wait_until_quiet()
    # the person stops at 105; the crew needs QUIET (3 s) of nothing after that
    assert waited == pytest.approx(5.0 + operator.QUIET, abs=0.3)
    assert states and all(states) and op.state()["paused"] is False


async def test_our_own_input_does_not_count():
    fake = FakeClock(person_until=0)
    op = operator.Operator(lambda: 0.1, fake.clock, fake.sleep)   # input 0.1 s ago...
    op.mark_ours()                                                # ...which the crew just sent
    assert not op.person_active()
    assert await op.wait_until_quiet() == 0


async def test_gives_up_after_a_minute_of_the_person_working():
    fake = FakeClock(person_until=10_000)
    op = operator.Operator(fake.idle, fake.clock, fake.sleep)
    with pytest.raises(operator.UserBusy):
        await op.wait_until_quiet()
    assert op.state()["paused"] is False


async def test_stopping_mid_wait_cancels_it_and_clears_the_pause():
    op = operator.Operator(lambda: 0.0)          # the person is always busy
    task = asyncio.create_task(op.wait_until_quiet())
    await asyncio.sleep(0.3)
    assert op.state()["paused"] is True
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert op.state()["paused"] is False


async def test_the_desktop_lease_waits_for_the_person(monkeypatch):
    calls = {"n": 0}

    def idle():
        calls["n"] += 1
        return 0.0 if calls["n"] <= 2 else 10.0   # busy for two looks, then quiet
    monkeypatch.setattr(operator.OPERATOR, "idle", idle)
    monkeypatch.setattr(operator.OPERATOR, "ours_until", 0.0)
    async with tools.lease():
        assert calls["n"] == 3
    assert operator.OPERATOR.ours_until > 0     # what we sent inside the lease is marked as ours


async def test_screen_steps_are_recorded(monkeypatch):
    monkeypatch.setattr(operator, "OPERATOR", operator.Operator(lambda: 1e9))

    @registry.tool("fake_click", "test only", kit="computer")
    async def fake_click(args, ctx):
        return registry.ToolResult(True, "Clicked OK.")
    try:
        ctx = type("Ctx", (), {"bot_id": "desk", "chat_id": "c"})()
        await registry.run("fake_click", {}, ctx)
    finally:
        registry.REGISTRY.pop("fake_click", None)
    step = operator.OPERATOR.state()["recent"][0]
    assert (step["bot"], step["tool"], step["ok"], step["text"]) == ("desk", "fake_click", True, "Clicked OK.")


def test_stop_all_stops_every_chat(tmp_path):
    async def forever(messages, tools, purpose):
        await asyncio.sleep(60)
        return "late"
    crew = build_crew(tmp_path / "s.db", router=FakeRouter([forever, forever, forever]))
    with TestClient(create_app(crew)) as c:
        team = c.post("/api/chats/team/messages", json={"text": "do something long"})
        dm = c.post("/api/chats/dm-desk/messages", json={"text": "and you too"})
        assert team.status_code == dm.status_code == 202
        result = c.post("/api/stop-all").json()
        state = c.get("/api/operator").json()
    assert set(result["stopped"]) == {"team", "dm-desk"}
    assert state["paused"] is False and state["quiet_seconds"] == operator.QUIET


def test_recorded_text_hides_keys_and_never_raises(monkeypatch):
    import os
    key = "gsk_" + "fakeoperatorkeyfortests0123456789abcdEFGH"
    os.environ["GROQ_API_KEY"] = key
    op = operator.Operator(lambda: 1e9)
    op.record("desk", "type_text", True, f"Typed {key} into Notepad.")
    op.record("desk", "type_text", True, object())   # nonsense text: still no exception
    assert key not in str(op.state()) and "[hidden key]" in op.state()["recent"][1]["text"]


def test_stop_all_refuses_other_websites_but_not_the_app(tmp_path):
    crew = build_crew(tmp_path / "o.db", router=FakeRouter([]))
    with TestClient(create_app(crew)) as c:
        assert c.post("/api/stop-all", headers={"origin": "https://evil.example"}).status_code == 403
        assert c.post("/api/stop-all").status_code == 200                      # Electron: no Origin
        assert c.post("/api/stop-all", headers={"origin": "http://127.0.0.1:8790"}).status_code == 200
