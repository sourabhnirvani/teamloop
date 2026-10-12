"""Two small-model failures from Sourabh's traced local run: a prefixed text call that never ran, and the request
itself stored as a "fact" (a later turn then offered to redo the old task)."""

from types import SimpleNamespace

from fakes import make_crew

from teamloop import kits
from teamloop.crew import bots, memory
from teamloop.models import textcalls
from teamloop.tools import registry


def _tools():
    kits.load_all()
    return registry.schemas([registry.REGISTRY["delegate"], registry.REGISTRY["web_search"]])


def test_prefixed_python_style_calls_are_read():
    for line in ('.delegate("desk", "Create the file workspace/evals/x.txt")',
                 'functions.delegate("desk", "Create the file workspace/evals/x.txt")',
                 'tools.delegate(bot="desk", instruction="Create the file workspace/evals/x.txt")'):
        calls, rest = textcalls.extract_python(f"I'll hand it over.\n{line}\n", _tools())
        assert calls == [("delegate", {"bot": "desk", "instruction": "Create the file workspace/evals/x.txt"})], line
        assert "delegate(" not in rest


def test_a_call_inside_a_sentence_is_still_not_a_call():
    calls, _ = textcalls.extract_python('You could try delegate("desk", "x") later.', _tools())
    assert calls == []


async def test_remember_refuses_the_request_itself(tmp_path):
    crew = make_crew(tmp_path, [])
    request = "Save a file at workspace/evals/recover-1791771666.txt with the text: recovered"
    crew.store.add_message("dm-s", "user", request)
    ctx = SimpleNamespace(crew=crew, chat_id="dm-s", bot_id="s")
    for fact in (request, "Save a file at workspace/evals/recover-1791771666.txt", "open the report on Monday"):
        result = await memory.remember({"fact": fact}, ctx)
        assert not result.ok and "task, not a fact" in result.text, fact
    assert memory.recall_facts(crew.store) == []
    # a real fact still goes in
    assert (await memory.remember({"fact": "The person's name is Yang"}, ctx)).ok


async def test_remember_keeps_it_when_the_person_asked_to(tmp_path):
    crew = make_crew(tmp_path, [])
    crew.store.add_message("dm-s", "user", "Remember: send the invoice to Priya every Friday")
    ctx = SimpleNamespace(crew=crew, chat_id="dm-s", bot_id="s")
    assert (await memory.remember({"fact": "send the invoice to Priya every Friday"}, ctx)).ok


def test_the_prompt_says_facts_are_not_tasks():
    prompt = bots.system_prompt(bots.BOTS["s"], facts=["The person's name is Yang"])
    assert "Facts about the person (not tasks; never redo something listed here)" in prompt
