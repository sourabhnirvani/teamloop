"""Scout's research is capped per job: at most 5 web_search and 3 fetch_page across all its turns, then "answer with
what you have". Measured: one Scout turn made 20 searches and 4 page reads (81% of a 135k-token job), and with a
per-turn cap the lead simply sent Scout back three times."""

import asyncio

from fakes import FakeRouter, Reply, ToolCall

from teamloop import kits
from teamloop.crew import runner
from teamloop.crew.bots import BOTS
from teamloop.crew.context import TurnCtx
from teamloop.server.app import build_crew
from teamloop.tools import registry


async def test_scout_stops_searching_after_the_cap(tmp_path, monkeypatch):
    kits.load_all()
    ran = {"web_search": 0, "fetch_page": 0}

    def fake(name):
        async def handler(args, ctx):
            ran[name] += 1
            return registry.ToolResult(True, f"{name} result {ran[name]}")
        return handler
    monkeypatch.setattr(registry.REGISTRY["web_search"], "handler", fake("web_search"))
    monkeypatch.setattr(registry.REGISTRY["fetch_page"], "handler", fake("fetch_page"))
    searches = Reply("", [ToolCall(f"s{i}", "web_search", {"query": f"free llm api {i}"}) for i in range(7)],
                     "fake", "fake-1")
    reads = Reply("", [ToolCall(f"f{i}", "fetch_page", {"url": f"https://example.com/{i}"}) for i in range(4)],
                  "fake", "fake-1")
    router = FakeRouter([searches, reads, "Top 3: Gemini, Groq, OpenRouter (with links)."])
    crew = build_crew(tmp_path / "c.db", router=router)
    ctx = TurnCtx("dm-scout", "scout", crew, asyncio.Event())
    reply = await runner.run_bot_turn(BOTS["scout"], router, [], "find the top 3 free LLM APIs", ctx)
    assert ran == {"web_search": 5, "fetch_page": 3}
    sent_back = [m["content"] for m in router.calls[-1]["messages"] if m.get("role") == "tool"]
    assert sent_back.count(runner.ENOUGH) == 3          # the 6th and 7th search, the 4th read
    assert reply.startswith("Top 3")


async def test_other_bots_are_not_capped(tmp_path, monkeypatch):
    kits.load_all()
    ran = []

    async def handler(args, ctx):
        ran.append(args["query"])
        return registry.ToolResult(True, "ok")
    monkeypatch.setattr(registry.REGISTRY["web_search"], "handler", handler)
    searches = Reply("", [ToolCall(f"s{i}", "web_search", {"query": f"q{i}"}) for i in range(7)], "fake", "fake-1")
    router = FakeRouter([searches, "Done."])
    crew = build_crew(tmp_path / "w.db", router=router)
    ctx = TurnCtx("dm-web", "web", crew, asyncio.Event())
    await runner.run_bot_turn(BOTS["web"], router, [], "look these up", ctx)
    assert len(ran) == 7


async def test_the_cap_holds_across_scout_turns_in_one_job(tmp_path, monkeypatch):
    kits.load_all()
    ran = []

    async def handler(args, ctx):
        ran.append(args["query"])
        return registry.ToolResult(True, "ok")
    monkeypatch.setattr(registry.REGISTRY["web_search"], "handler", handler)
    four = lambda tag: Reply("", [ToolCall(f"{tag}{i}", "web_search", {"query": f"{tag}{i}"}) for i in range(4)],  # noqa: E731
                             "fake", "fake-1")
    router = FakeRouter([four("a"), "First pass.", four("b"), "Second pass."])
    crew = build_crew(tmp_path / "j.db", router=router)
    job = TurnCtx("team", "s", crew, asyncio.Event())
    await runner.run_bot_turn(BOTS["scout"], router, [], "research it", job.for_bot("scout", depth=1))
    await runner.run_bot_turn(BOTS["scout"], router, [], "research it more", job.for_bot("scout", depth=1))
    assert len(ran) == 5                                   # 4 in the first turn, only 1 more in the second
