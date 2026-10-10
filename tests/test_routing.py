from fakes import make_crew


async def test_addressing_a_bot_by_name_routes_to_it(tmp_path):
    crew = make_crew(tmp_path, [])
    team = crew.store.get_chat("team")
    assert [b.id for b in crew.responders(team, "Scout, search free LLM APIs")] == ["scout"]
    assert [b.id for b in crew.responders(team, "Desk: open Paint")] == ["desk"]
    assert [b.id for b in crew.responders(team, "Yes, do it")] == ["s"]
    assert [b.id for b in crew.responders(team, "ok, thanks")] == ["s"]


async def test_lead_saying_not_mine_hands_the_job_over(tmp_path):
    crew = make_crew(tmp_path, ["Not mine: Scout", "neatlogs traces AI agents (https://neatlogs.com)."])
    await crew.post("dm-s", "what is neatlogs? look it up")
    await crew.wait_idle("dm-s")
    said = [(m["sender"], m["kind"], m["text"]) for m in crew.store.messages("dm-s")]
    assert said[-2] == ("s", "handoff", "@Scout what is neatlogs? look it up")
    assert said[-1][0] == "scout" and "neatlogs.com" in said[-1][2]
    assert crew.router.calls[1]["purpose"] == "turn:scout"


async def test_a_bot_quoting_another_does_not_trigger_a_handoff(tmp_path):
    crew = make_crew(tmp_path, ["Scout: it traces agents."])
    await crew.post("team", "what did scout find")
    await crew.wait_idle("team")
    assert len(crew.router.calls) == 1  # S's reply starting "Scout:" didn't start a Scout turn
