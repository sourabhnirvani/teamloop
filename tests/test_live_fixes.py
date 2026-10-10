"""Fixes for what the live test pass on a second laptop found."""

from fakes import call, make_crew

from teamloop.crew import routines
from teamloop.crew.bots import BOTS, system_prompt
from teamloop.crew.memory import recall_facts
from teamloop.crew.runner import clean_reply


async def test_remember_is_saved_without_a_model_even_in_a_busy_chat(tmp_path):
    crew = make_crew(tmp_path, [])
    await crew.post("dm-s", "remember I like short answers")
    await crew.wait_idle("dm-s")
    assert crew.store.messages("dm-s")[-1]["text"] == "Got it, the crew will remember: I like short answers"
    assert [r["fact"] for r in recall_facts(crew.store)] == ["I like short answers"]
    assert crew.router.calls == []


async def test_remember_to_is_a_reminder_not_a_memory(tmp_path):
    crew = make_crew(tmp_path, ["I'll set that up."])
    await crew.post("dm-s", "remember to call mom at 5pm")
    await crew.wait_idle("dm-s")
    assert len(crew.router.calls) == 1 and recall_facts(crew.store) == []


async def test_the_same_routine_twice_stays_one(tmp_path):
    crew = make_crew(tmp_path, [call("schedule_routine", task="check mail", schedule="every day at 9am"),
                                call("schedule_routine", task="Check mail", schedule="every day at 9am"), "Set."])
    await crew.post("dm-s", "every day at 9am check mail")
    await crew.wait_idle("dm-s")
    assert len(routines.listing(crew, "dm-s")) == 1
    tool_texts = [m["content"] for c in crew.router.calls for m in c["messages"] if m["role"] == "tool"]
    assert "already exists" in tool_texts[-1]


async def test_per_bot_model_without_a_key_says_so(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    crew = make_crew(tmp_path, [])
    await crew.post("dm-s", "use gemini for Scout")
    await crew.wait_idle("dm-s")
    assert "no Gemini key yet" in crew.store.messages("dm-s")[-1]["text"]


def test_bots_are_told_not_to_ask_in_chat_and_citations_are_cleaned():
    assert 'never ask "may I...?" in chat' in system_prompt(BOTS["desk"])
    assert clean_reply("Groq is free 【fetch_page†0】 and fast【web_search†2】.") == "Groq is free and fast."
    assert clean_reply("") == "Done."
