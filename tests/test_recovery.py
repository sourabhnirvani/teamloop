from fakes import call, make_crew

from teamloop import kits
from teamloop.crew import runner
from teamloop.tools import files, registry
from teamloop.tools.registry import ToolResult

kits.load_all()


async def test_a_failed_step_is_retried_until_the_file_exists(tmp_path, monkeypatch):
    monkeypatch.setenv("TEAMLOOP_FAIL_ONCE", "write_file")
    monkeypatch.setattr(registry, "_failed_once", set())
    steps = []
    crew = make_crew(tmp_path, [
        call("delegate", bot="writer", instruction="Save workspace/notes/plan.md with the text: ship it"),
        call("write_file", path="workspace/notes/plan.md", content="ship it"),
        call("write_file", path="workspace/notes/plan.md", content="ship it"),
        "Saved workspace/notes/plan.md (the first try timed out, the second worked).",
        "Done: Writer saved plan.md after one retry.",
    ])
    with crew.bus.subscribe() as queue:
        await crew.post("dm-s", "save my plan")
        await crew.wait_idle("dm-s")
        while not queue.empty():
            e = queue.get_nowait()
            if e["type"] == "step" and e.get("status") in ("done", "fail"):
                steps.append((e["tool"], e["status"]))
    assert files.resolve("workspace/notes/plan.md").read_text(encoding="utf-8") == "ship it"
    assert ("write_file", "fail") in steps and steps.index(("write_file", "fail")) < steps.index(("write_file", "done"))
    failed = [m["content"] for c in crew.router.calls for m in c["messages"] if m["role"] == "tool"]
    assert any("simulated glitch" in t for t in failed)
    assert crew.store.messages("dm-s")[-1]["text"].startswith("Done:")


async def test_a_third_identical_call_is_skipped(tmp_path, monkeypatch):
    ran = []

    async def status(args, ctx):
        ran.append(args)
        return ToolResult(True, "Right now: volume 50%.")

    monkeypatch.setattr(registry.REGISTRY["system_status"], "handler", status)
    crew = make_crew(tmp_path, [call("system_status"), call("system_status"), call("system_status"), "Volume is 50%."])
    await crew.post("dm-desk", "how loud is it")
    await crew.wait_idle("dm-desk")
    assert len(ran) == 2
    last_tool = [m for m in crew.router.calls[-1]["messages"] if m["role"] == "tool"][-1]
    assert last_tool["content"] == runner.REPEATED


async def test_a_temporary_failure_tells_the_bot_to_retry(tmp_path, monkeypatch):
    monkeypatch.setenv("TEAMLOOP_FAIL_ONCE", "write_file")
    monkeypatch.setattr(registry, "_failed_once", set())
    crew = make_crew(tmp_path, [call("write_file", path="workspace/notes/x.md", content="hi"),
                                call("write_file", path="workspace/notes/x.md", content="hi"), "Saved x.md."])
    await crew.post("dm-writer", "save x.md with hi")
    await crew.wait_idle("dm-writer")
    tool_texts = [m["content"] for c in crew.router.calls for m in c["messages"] if m["role"] == "tool"]
    assert runner.RETRY_NOTE in tool_texts[0]
    assert files.resolve("workspace/notes/x.md").read_text(encoding="utf-8") == "hi"
    assert "try it once more" in crew.router.calls[0]["messages"][0]["content"]  # the bot's own rules say so too
