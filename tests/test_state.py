"""What an app needs after it (re)connects: who is working, waiting cards, last messages, missed events."""

import asyncio

from fakes import FakeRouter, call, hang, make_crew
from fastapi.testclient import TestClient

from teamloop.crew.events import Bus
from teamloop.server import phones
from teamloop.server.app import build_crew, create_app
from teamloop.tools import registry
from teamloop.tools.registry import ToolResult

TUNNEL = {"cf-connecting-ip": "203.0.113.9"}


async def test_state_lists_working_bots_and_waiting_cards(tmp_path, monkeypatch):
    async def risky(args, ctx):
        ok = await ctx.approve("Run a command", "Remove-Item test.txt")
        return ToolResult(ok, "done" if ok else "The person said no")

    monkeypatch.setitem(registry.REGISTRY, "risky", registry.Tool("risky", "", {"type": "object"}, "memory", risky))
    crew = make_crew(tmp_path, [call("risky"), "Deleted."])
    await crew.post("dm-desk", "delete test.txt")
    for _ in range(100):
        if crew.gate.pending_in("dm-desk"):
            break
        await asyncio.sleep(0.01)
    state = crew.state()
    assert state["typing"] == {"dm-desk": ["desk"]}
    [card] = state["approvals"]
    assert (card["type"], card["chat_id"], card["bot"], card["title"]) == ("approval", "dm-desk", "desk", "Run a command")
    crew.gate.answer(card["id"], True)
    await crew.wait_idle("dm-desk")
    assert crew.state()["typing"] == {} and crew.state()["approvals"] == []


async def test_a_stopped_turn_is_not_left_working(tmp_path):
    crew = make_crew(tmp_path, [hang])
    await crew.post("dm-scout", "look something up")
    for _ in range(100):
        if crew.state()["typing"]:
            break
        await asyncio.sleep(0.01)
    assert crew.state()["typing"] == {"dm-scout": ["scout"]}
    await crew.stop("dm-scout")
    assert crew.state()["typing"] == {}


def test_chats_carry_their_last_message(tmp_path):
    app = create_app(build_crew(tmp_path / "s.db", router=FakeRouter([])))
    crew = app.state.crew
    crew.store.add_message("dm-scout", "user", "hi")
    crew.store.add_message("dm-scout", "scout", "Hello! I research things.")
    with TestClient(app) as client:
        chats = {c["id"]: c for c in client.get("/api/chats").json()}
    assert chats["dm-scout"]["last"]["text"] == "Hello! I research things."
    assert chats["dm-scout"]["last"]["sender"] == "scout"
    assert chats["dm-desk"]["last"] is None


def test_settings_change_is_announced_and_state_is_served(tmp_path):
    app = create_app(build_crew(tmp_path / "s.db", router=FakeRouter([])))
    seen = []
    bus: Bus = app.state.crew.bus
    original = bus.emit

    async def spy(type, **data):
        seen.append((type, data))
        await original(type, **data)

    bus.emit = spy
    with TestClient(app) as client:
        assert client.post("/api/settings", json={"save_tokens": True}).json()["save_tokens"] is True
        assert client.get("/api/state").json() == {"typing": {}, "approvals": [], "asleep": False, "save_tokens": True}
        assert client.get("/api/approvals").json() == []
    assert ("settings", {"chat_id": None, "save_tokens": True, "crew_model": None, "bot_models": {}}) in seen


def test_console_page_stays_on_the_laptop(tmp_path):
    app = create_app(build_crew(tmp_path / "s.db", router=FakeRouter([])))
    with TestClient(app, base_url="https://x.trycloudflare.com") as client:
        assert client.get("/console", headers=TUNNEL).status_code == 404
        assert client.get("/console").status_code == 200


async def test_poll_says_which_events_it_still_holds():
    bus = Bus()
    log = phones.EventLog(bus, size=3)
    log.start()
    await asyncio.sleep(0)
    for i in range(5):
        await bus.emit("typing", chat_id="c", bot="s", on=bool(i % 2))
    await asyncio.sleep(0.01)
    assert log.seq == 5 and log.oldest() == 3  # events 1-2 fell out: a phone that last saw 1 must reload
    assert [e["on"] for e in await log.after(2, 0.01)] == [False, True, False]
