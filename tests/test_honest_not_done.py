"""A step with no tool behind it never reads as done: the lead is nudged once, and if it still says "saved" the
runner adds its own honest "Not done: ..." line (seen live: qwen2.5:7b said "saved the file" with no tool call)."""

from fakes import FakeRouter, call

from teamloop.crew import coverage
from teamloop.server.app import build_crew


async def test_lead_that_says_saved_twice_without_a_tool_gets_an_honest_line(tmp_path):
    router = FakeRouter(["Got it, saved the file workspace/evals/x.txt.", "Saved it, all done."])
    crew = build_crew(tmp_path / "h.db", router=router)
    await crew.post("dm-s", "Save a file at workspace/evals/x.txt with the text: recovered")
    await crew.wait_idle("dm-s")
    final = crew.store.messages("dm-s")[-1]["text"]
    assert final.startswith("Saved it, all done.")
    assert "Not done: save the file (no tool ran for it)" in final and 'Say "try again"' in final
    assert len(router.calls) == 2                              # one nudge, then the honest line: no loop
    assert "Not done yet: save the file" in router.calls[1]["messages"][-1]["content"]


async def test_a_lead_that_really_saves_gets_no_extra_line(tmp_path):
    router = FakeRouter([call("delegate", bot="writer", instruction="Save workspace/evals/y.txt with: ok"),
                         call("write_file", path="workspace/evals/y.txt", content="ok"), "Saved.",
                         "Writer saved workspace/evals/y.txt."])
    crew = build_crew(tmp_path / "g.db", router=router)
    await crew.post("dm-s", "Save a file at workspace/evals/y.txt with the text: ok")
    await crew.wait_idle("dm-s")
    final = crew.store.messages("dm-s")[-1]["text"]
    assert "Not done" not in final


def test_questions_and_research_are_not_held_to_a_tool():
    assert coverage.missing_actions("can you save files?", set()) == []
    assert coverage.missing_actions("research the top 3 free LLM APIs", set()) == []
    assert coverage.missing_actions("save a note and remind me every Monday", {"write_file"}) == ["set the reminder"]
