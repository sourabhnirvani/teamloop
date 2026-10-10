from fakes import call, make_crew

from teamloop import cli
from teamloop.tools import registry
from teamloop.tools.registry import ToolResult


async def test_one_task_prints_steps_and_the_reply(tmp_path):
    crew = make_crew(tmp_path, [call("remember", fact="likes tea"), "Noted: you like tea."])
    lines = []
    assert await cli.run("note that I like tea", "dm-s", crew=crew, out=lines.append) == 0
    assert any("remember" in ln and "→" in ln for ln in lines)
    assert lines[-1].endswith("S: Noted: you like tea.")


async def test_approvals_are_asked_in_the_terminal(tmp_path, monkeypatch):
    asked = []

    async def risky(args, ctx):
        ok = await ctx.approve("Do the risky thing", "It can't be undone.")
        return ToolResult(ok, "Did it." if ok else "The person said no, so I didn't do it.")

    monkeypatch.setitem(registry.REGISTRY, "risky", registry.Tool("risky", "", {"type": "object"}, "memory", risky))
    crew = make_crew(tmp_path, [call("risky"), "Okay, I left it."])
    lines = []
    await cli.run("do it", "dm-s", crew=crew, out=lines.append, ask=lambda prompt: asked.append(prompt) or "n")
    assert "Do the risky thing" in asked[0]
    tool_msg = next(m for m in crew.router.calls[1]["messages"] if m["role"] == "tool")
    assert "said no" in tool_msg["content"]


async def test_chat_mode_until_exit(tmp_path):
    crew = make_crew(tmp_path, ["Hi!"])
    typed = iter(["hello", "exit"])
    lines = []
    await cli.run(None, "dm-s", crew=crew, out=lines.append, ask=lambda prompt: next(typed))
    assert "S: Hi!" in lines[-1] and len(crew.router.calls) == 1


async def test_unknown_chat(tmp_path):
    lines = []
    assert await cli.run("hi", "nope", crew=make_crew(tmp_path, []), out=lines.append) == 2
