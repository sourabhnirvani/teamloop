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
    assert not any(t.lower().startswith("not mine") for who, _, t in said if who == "s")  # S's line isn't shown


async def test_follow_up_not_mine_from_s_is_routed_too(tmp_path):
    # Writer says Not mine in the group, S is asked to re-route and itself answers "Not mine: Scout"
    crew = make_crew(tmp_path, ["Not mine: Scout researches.", "Not mine: Scout",
                                "neatlogs traces AI agents (https://neatlogs.com)."])
    await crew.post("team", "@writer what is neatlogs? look it up")
    await crew.wait_idle("team")
    said = [(m["sender"], m["kind"]) for m in crew.store.messages("team")]
    assert said == [("user", "chat"), ("writer", "chat"), ("s", "handoff"), ("scout", "chat")]


async def test_lead_not_mine_naming_nobody_plans_it_itself(tmp_path):
    crew = make_crew(tmp_path, ["Not mine: Operator", "I'll take it: the Calculator app is open."])
    await crew.post("dm-s", "open calculator for me then tell me")
    await crew.wait_idle("dm-s")
    said = [(m["sender"], m["text"]) for m in crew.store.messages("dm-s")]
    assert said[-1] == ("s", "I'll take it: the Calculator app is open.")
    assert "Don't reply \"Not mine\"" in crew.router.calls[1]["messages"][-1]["content"]
    assert not any(t.startswith("Not mine") for _, t in said)


async def test_a_bot_quoting_another_does_not_trigger_a_handoff(tmp_path):
    crew = make_crew(tmp_path, ["Scout: it traces agents."])
    crew.store.add_message("team", "scout", "neatlogs traces AI agents (https://neatlogs.com).")  # Scout really said it
    await crew.post("team", "what did scout find")
    await crew.wait_idle("team")
    assert len(crew.router.calls) == 1  # S's reply starting "Scout:" didn't start a Scout turn
