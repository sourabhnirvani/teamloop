import asyncio

from fakes import call, make_crew


async def test_remembered_facts_reach_every_bot(tmp_path):
    crew = make_crew(tmp_path, [call("remember", fact="My sister is called Riya."), "Got it.", "Hi!"])
    await crew.post("dm-s", "keep in mind that my sister is called Riya")
    await crew.wait_idle("dm-s")
    await crew.post("dm-writer", "hello")
    await crew.wait_idle("dm-writer")
    writer_prompt = crew.router.calls[-1]["messages"][0]["content"]
    assert "My sister is called Riya." in writer_prompt


async def test_typed_yes_answers_the_waiting_card(tmp_path):
    crew = make_crew(tmp_path, [])
    result = {}

    async def ask():
        result["ok"] = await crew.gate.ask("dm-desk", "desk", "Close Word", "Unsaved work may be lost.")

    task = asyncio.create_task(ask())
    await asyncio.sleep(0.01)
    await crew.post("dm-desk", "yes")
    await task
    assert result["ok"] is True
    assert crew.router.calls == []  # "yes" went to the card, not to a model


async def test_typed_no_denies(tmp_path):
    crew = make_crew(tmp_path, [])
    task = asyncio.create_task(crew.gate.ask("dm-desk", "desk", "Shut down", "x"))
    await asyncio.sleep(0.01)
    await crew.post("dm-desk", "no")
    assert await task is False
