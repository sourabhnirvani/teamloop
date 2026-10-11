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


def test_sources_travel_from_scout_to_the_report():
    assert "source links too" in system_prompt(BOTS["s"])
    assert "Sources list" in system_prompt(BOTS["writer"])
    assert "newest sources" in system_prompt(BOTS["scout"])


def test_a_report_lists_each_source_once():
    from teamloop.tools.files import dedupe_link_lines

    report = ("# Free LLM APIs\nGemini: see https://ai.google.dev (free tier).\n\nSources\n"
              "- https://ai.google.dev\n- https://groq.com/pricing\n- https://groq.com/pricing/\n"
              "- [Groq](https://groq.com/pricing)\nCompare https://a.example and https://b.example on one line.\n")
    assert dedupe_link_lines(report) == ("# Free LLM APIs\nGemini: see https://ai.google.dev (free tier).\n\nSources\n"
                                         "- https://ai.google.dev\n- https://groq.com/pricing\n"
                                         "Compare https://a.example and https://b.example on one line.\n")


def test_reworded_commands_count_as_the_same_request():
    from teamloop.computer import risk

    a = risk.command_key(r"Remove-Item 'C:\Users\me\Desktop\debugpass.txt' -Force")
    b = risk.command_key(r"Remove-Item -Path C:\Users\me\Desktop\debugpass.txt -ErrorAction SilentlyContinue")
    assert a == b == "delete:debugpass.txt"
    assert risk.command_key("del other.txt") != a
    assert risk.command_key("taskkill /im chrome.exe /f") == risk.command_key("Stop-Process -Name chrome")
    assert risk.command_key("Stop-Process -Name notepad") != risk.command_key("Stop-Process -Name chrome")


async def test_a_no_holds_for_the_same_request_in_new_words(tmp_path):
    import asyncio

    crew = make_crew(tmp_path, [])
    asked = []

    async def answer():
        with crew.bus.subscribe() as q:
            while True:
                e = await q.get()
                if e["type"] == "approval":
                    asked.append(e["details"])
                    crew.gate.answer(e["id"], False)

    task = asyncio.create_task(answer())
    await asyncio.sleep(0)
    assert not await crew.gate.ask("dm-desk", "desk", "Run a command", "Remove-Item a.txt -Force", key="cmd:delete:a.txt")
    assert not await crew.gate.ask("dm-desk", "desk", "Run a command", "del a.txt", key="cmd:delete:a.txt")
    task.cancel()
    assert asked == ["Remove-Item a.txt -Force"]  # the re-worded second ask got no new card


def test_workers_know_the_crew_and_a_no_is_not_a_failure():
    prompt = system_prompt(BOTS["scout"])
    assert "- Desk: Computer" in prompt and "- Scout:" not in prompt
    assert "that is not a failure" in prompt


async def test_not_mine_in_a_one_to_one_chat_goes_to_the_named_teammate(tmp_path):
    crew = make_crew(tmp_path, ["Not mine: Desk opens apps.", "Opened Notepad."])
    await crew.post("dm-scout", "open notepad")
    await crew.wait_idle("dm-scout")
    said = [(m["sender"], m["kind"], m["text"]) for m in crew.store.messages("dm-scout")]
    assert said[-2] == ("scout", "handoff", "@Desk open notepad")
    assert said[-1] == ("desk", "chat", "Opened Notepad.")


async def test_only_this_model_never_falls_back(tmp_path):
    """The model chip's "Only this model (no fallback)": the router is told to try that model alone."""
    crew = make_crew(tmp_path, ["hi", "hi again", "hello"])
    crew.store.set_setting("bot_models", {"scout": "groq"})
    crew.store.set_setting("bot_only", {"scout": True, "writer": True})
    await crew.post("dm-scout", "hello")
    await crew.wait_idle("dm-scout")
    await crew.post("dm-writer", "hello")  # "only" without a model picked means nothing: normal fallback
    await crew.wait_idle("dm-writer")
    crew.store.set_setting("bot_only", {})
    await crew.post("dm-scout", "hello")
    await crew.wait_idle("dm-scout")
    picks = [(c["purpose"], c["prefer"], c["only"]) for c in crew.router.calls]
    assert picks == [("turn:scout", "groq", True), ("turn:writer", None, False), ("turn:scout", "groq", False)]
