"""'Always allow' on an approval card: the same action goes ahead next time, but never for sends, buys or deletes."""

import asyncio

from fakes import FakeRouter, call, make_crew
from fastapi.testclient import TestClient

from teamloop.computer import gate as gate_mod
from teamloop.server.app import build_crew, create_app
from teamloop.tools import registry
from teamloop.tools.registry import ToolResult


def install(monkeypatch, title, details, key=None):
    async def act(args, ctx):
        if not await ctx.approve(title, details, key=key):
            return ToolResult(False, "The person said no.")
        return ToolResult(True, "Done it.")

    monkeypatch.setitem(registry.REGISTRY, "act", registry.Tool("act", "", {"type": "object"}, "memory", act))


async def run_answering(crew, text, answer):
    """Post `text` in Desk's chat; answer each card with `answer` (ok, always). Returns the cards seen."""
    cards = []

    async def answer_cards():
        with crew.bus.subscribe() as queue:
            while True:
                e = await queue.get()
                if e["type"] == "approval":
                    cards.append(e)
                    crew.gate.answer(e["id"], *answer)

    task = asyncio.create_task(answer_cards())
    await asyncio.sleep(0)
    await crew.post("dm-desk", text)
    await crew.wait_idle("dm-desk")
    task.cancel()
    return cards


async def test_always_allow_skips_the_card_next_time(tmp_path, monkeypatch):
    install(monkeypatch, "Close notepad", "Close 1 window(s): notes.txt - Notepad.")
    crew = make_crew(tmp_path, [call("act"), "Closed.", call("act"), "Closed again."])
    first = await run_answering(crew, "close notepad", (True, True))
    assert len(first) == 1 and first[0]["can_always"] is True
    [rule] = crew.gate.rules()
    assert (rule["title"], rule["key"], rule["label"]) == ("Close notepad", "", "Close notepad")  # by title
    seen = []
    with crew.bus.subscribe() as queue:
        assert await run_answering(crew, "close notepad again", (False, False)) == []  # no card this time
        while not queue.empty():
            seen.append(queue.get_nowait()["type"])
    assert "allowed" in seen  # the chat says it went ahead because of the rule


async def test_commands_are_only_allowed_exactly(tmp_path, monkeypatch):
    crew = make_crew(tmp_path, [])
    rule = crew.gate.allow("Run a command", "cmd:kill:node.exe", "desk", "Stop-Process -Name node")
    assert crew.gate.rule_for("Run a command", "cmd:kill:node.exe") == rule
    assert crew.gate.rule_for("Run a command", "cmd:kill:chrome.exe") is None  # another program still asks


def test_sending_buying_deleting_and_power_are_never_always():
    for title, key in [("Type and send", "hi there"), ('Click "Send"', ""), ("Press enter", ""),
                       ("Open a checkout page", "https://shop/checkout"), ("Replace a file", "notes.txt"),
                       ("Shutdown", ""), ("Run a command", "cmd:delete:notes.txt"), ("Run a command", "cmd:power:")]:
        assert gate_mod.can_always(title, key) is False, title
    for title, key in [("Close notepad", ""), ("Open a file", "Open report.md"), ("Run a command", "cmd:kill:node.exe"),
                       ("Turn Wi-Fi off", "")]:
        assert gate_mod.can_always(title, key) is True, title


async def test_always_is_ignored_where_it_is_not_allowed(tmp_path, monkeypatch):
    install(monkeypatch, "Type and send", "Type into WhatsApp:\nhi")
    crew = make_crew(tmp_path, [call("act"), "Sent.", call("act"), "Sent again."])
    first = await run_answering(crew, "say hi", (True, True))
    assert first[0]["can_always"] is False and crew.gate.rules() == []
    assert len(await run_answering(crew, "say hi again", (True, False))) == 1  # still asks every time


def test_rules_over_http_and_removing_one_asks_again(tmp_path):
    app = create_app(build_crew(tmp_path / "a.db", router=FakeRouter([])))
    crew = app.state.crew
    rule = crew.gate.allow("Open a file", "Open report.md (in C:/Desktop) with its usual app.", "desk")
    with TestClient(app) as client:
        assert [r["id"] for r in client.get("/api/allowed").json()] == [rule["id"]]
        assert client.delete(f"/api/allowed/{rule['id']}").json() == {"ok": True}
        assert client.get("/api/allowed").json() == []
        assert client.delete(f"/api/allowed/{rule['id']}").status_code == 404
    assert crew.gate.rule_for("Open a file", "Open report.md (in C:/Desktop) with its usual app.") is None
