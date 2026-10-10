import os

from fakes import call, make_crew

from teamloop.keys import vault, wallet

FAKE_GROQ = "gsk_" + "b2" * 26
FAKE_GEMINI = "AIza" + "y" * 35


def test_vault_round_trip_is_sealed(workspace):
    vault.put("GROQ_API_KEY", FAKE_GROQ)
    raw = vault.path().read_bytes()
    assert FAKE_GROQ.encode() not in raw
    assert vault.load() == {"GROQ_API_KEY": FAKE_GROQ}
    os.environ.pop("GROQ_API_KEY")
    assert vault.export_to_env() == 1 and os.environ["GROQ_API_KEY"] == FAKE_GROQ
    vault.remove("GROQ_API_KEY")
    assert vault.load() == {}


async def test_wallet_saves_dedupes_and_rejects(monkeypatch):
    for name in ("GROQ_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(name, raising=False)

    async def fake_check(provider, key):
        return provider.id == "groq"

    monkeypatch.setattr(wallet, "check", fake_check)
    added = await wallet.add_from_text(f"keys: {FAKE_GROQ} {FAKE_GEMINI}")
    assert [(a.provider, a.status) for a in added] == [("gemini", "rejected"), ("groq", "saved")]
    assert os.environ["GROQ_API_KEY"] == FAKE_GROQ
    again = await wallet.add_from_text(FAKE_GROQ)
    assert again[0].status == "duplicate"


async def test_pasted_key_never_reaches_a_model_or_the_chat_log(tmp_path, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    async def fake_check(provider, key):
        return True

    monkeypatch.setattr(wallet, "check", fake_check)
    crew = make_crew(tmp_path, [])
    await crew.post("dm-s", f"here is my key {FAKE_GROQ}")
    await crew.wait_idle("dm-s")
    msgs = crew.store.messages("dm-s")
    assert FAKE_GROQ not in msgs[0]["text"] and "[hidden key]" in msgs[0]["text"]
    assert msgs[-1]["text"] == "Saved your Groq key; it works."
    assert crew.router.calls == []


async def test_model_switching_from_chat(tmp_path):
    crew = make_crew(tmp_path, ["(model reply)"])
    await crew.post("dm-s", "use groq")
    await crew.wait_idle("dm-s")
    assert crew.store.get_setting("crew_model") == "groq"
    await crew.post("dm-s", "use gemini for desk")
    await crew.wait_idle("dm-s")
    assert crew.store.get_setting("bot_models") == {"desk": "gemini"}
    assert crew.model_for("desk") == "gemini" and crew.model_for("web") == "groq"
    await crew.post("dm-s", "switch to google chrome")
    await crew.wait_idle("dm-s")
    assert crew.router.calls, "not a model switch, so it goes to the bot"
    await crew.post("dm-s", "use auto")
    await crew.wait_idle("dm-s")
    assert crew.store.get_setting("crew_model") is None


async def test_save_tokens_mode_toggles(tmp_path):
    crew = make_crew(tmp_path, [])
    await crew.post("dm-s", "save tokens mode")
    await crew.wait_idle("dm-s")
    assert crew.saving()
    await crew.post("dm-s", "normal mode")
    await crew.wait_idle("dm-s")
    assert not crew.saving()


async def test_group_round_skips_bots_with_nothing_new(tmp_path):
    crew = make_crew(tmp_path, ["S: here's the plan.", "SKIP", "Web: I can open the sites.", "SKIP", "SKIP", "SKIP"])
    await crew.post("team", "team, any ideas for my trip?")
    await crew.wait_idle("team")
    assert [m["sender"] for m in crew.store.messages("team")] == ["user", "s", "web"]


async def test_bot_mention_in_group_hands_off_once(tmp_path):
    crew = make_crew(tmp_path, ["@Writer can you draft the note?", "Drafted it."])
    await crew.post("team", "@scout find a note idea")
    await crew.wait_idle("team")
    assert [m["sender"] for m in crew.store.messages("team")] == ["user", "scout", "writer"]


async def test_not_mine_goes_back_to_s(tmp_path):
    crew = make_crew(tmp_path, ["Not mine: Desk opens apps.", call("delegate", bot="desk", instruction="Open Calculator."),
                                "Opened Calculator.", "Desk opened Calculator."])
    await crew.post("team", "@writer open calculator")
    await crew.wait_idle("team")
    assert [m["sender"] for m in crew.store.messages("team")] == ["user", "writer", "s", "desk", "s"]


async def test_solo_mode_gives_s_the_worker_tools(tmp_path):
    crew = make_crew(tmp_path, ["done"])
    crew.store.set_setting("solo", True)
    await crew.post("dm-s", "do it alone")
    await crew.wait_idle("dm-s")
    names = {t["function"]["name"] for t in crew.router.calls[0]["tools"]}
    assert "delegate" not in names and "write_file" in names
