"""Final-pass run 4: Desk's open card went unanswered and S then skipped the Monday reminder too. The lead is told to
finish the parts that don't depend on a blocked step."""

from fakes import call, make_crew

from teamloop import kits
from teamloop.crew import bots, routines
from teamloop.tools import registry


def test_the_lead_is_told_to_keep_going_past_a_blocked_step():
    line = "If one step is blocked, declined or unanswered, still do the other parts that don't depend on it"
    assert line in bots.LEAD_RULES and line in bots.system_prompt(bots.BOTS["s"])


async def test_a_declined_open_still_gets_the_reminder_set(tmp_path, monkeypatch):
    kits.load_all()

    async def declined_open(args, ctx):
        return registry.ToolResult(False, "The person said no, so the file wasn't opened.")
    monkeypatch.setattr(registry.REGISTRY["open_file"], "handler", declined_open)
    crew = make_crew(tmp_path, [
        call("delegate", bot="writer", instruction="Save Desktop/r.md with: report"),
        call("write_file", path="Desktop/r.md", content="report"), "Saved Desktop/r.md.",
        call("delegate", bot="desk", instruction="Open Desktop/r.md"),
        call("open_file", path="Desktop/r.md"), "You said no, so I left it.",
        call("schedule_routine", task="Review Desktop/r.md", schedule="every monday at 9am"),
        "Saved the report; you said no to opening it; the Monday reminder is set.",
    ])
    await crew.post("team", "write a short report on the Desktop, open it, and remind me about it every Monday")
    await crew.wait_idle("team")
    final = crew.store.messages("team")[-1]["text"]
    assert [r["text"] for r in routines.listing(crew)] == ["Review Desktop/r.md"]
    assert "Not done" not in final            # the declined open was attempted; the reminder really ran
