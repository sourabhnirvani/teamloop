"""Build a bot, edit a bot's job & rules, mute it, remove it; add a routine from the app."""

from fakes import FakeRouter, call
from fastapi.testclient import TestClient

from teamloop.crew import bots as crew_bots
from teamloop.crew.bots import system_prompt
from teamloop.server.app import build_crew, create_app


def client_for(tmp_path, script=()):
    app = create_app(build_crew(tmp_path / "c.db", router=FakeRouter(list(script))))
    return app, TestClient(app)


def test_custom_bot_gets_a_chat_joins_the_team_and_reads_but_cannot_write(tmp_path):
    app, client = client_for(tmp_path)
    with client:
        made = client.post("/api/bots", json={"name": "Blog Pulse", "role": "Content", "persona": "Drafts posts, never posts.",
                                              "look": {"body": "bean", "accessory": "bow", "eyes": "sparkle", "colour": "#ff8a3d", "x": "no"}}).json()
        assert (made["id"], made["name"], made["role"], made["custom"]) == ("blog-pulse", "Blog Pulse", "Content", True)
        assert made["look"] == {"body": "bean", "accessory": "bow", "eyes": "sparkle", "colour": "#ff8a3d"}
        assert {"web_search", "read_file", "list_files", "remember"} <= set(made["tools"])
        assert "write_file" not in made["tools"] and "run_command" not in made["tools"]
        chats = {c["id"]: c for c in client.get("/api/chats").json()}
        assert chats["dm-blog-pulse"]["members"] == ["blog-pulse"] and "blog-pulse" in chats["team"]["members"]
        assert client.post("/api/bots", json={"name": "blog pulse"}).status_code == 409  # names stay unique
        assert client.post("/api/bots", json={"name": "  "}).status_code == 400


async def test_s_can_delegate_to_a_bot_you_built(tmp_path):
    app = create_app(build_crew(tmp_path / "d.db", router=FakeRouter([
        call("delegate", bot="blog-pulse", instruction="Draft a tweet about TeamLoop."), "Draft: TeamLoop is a crew…", "Done."])))
    with TestClient(app) as client:
        client.post("/api/bots", json={"name": "Blog Pulse", "role": "Content"})
    crew = app.state.crew
    await crew.post("team", "draft a tweet about teamloop")
    await crew.wait_idle("team")
    said = [(m["sender"], m["kind"]) for m in crew.store.messages("team")]
    assert ("s", "handoff") in said and ("blog-pulse", "chat") in said
    assert "Blog Pulse: Content" in system_prompt(crew_bots.BOTS["desk"])  # workers know the whole crew


def test_job_and_rules_edit_reaches_the_prompt_and_resets(tmp_path):
    app, client = client_for(tmp_path)
    with client:
        edited = client.patch("/api/bots/scout", json={"persona": "Only use .gov and .edu sources."}).json()
        assert edited["persona"] == "Only use .gov and .edu sources." and edited["default_persona"].startswith("You research")
        assert "Only use .gov and .edu sources." in system_prompt(crew_bots.BOTS["scout"])
        reset = client.patch("/api/bots/scout", json={"persona": ""}).json()
        assert reset["persona"] == reset["default_persona"]
        assert client.patch("/api/bots/nope", json={"muted": True}).status_code == 404


async def test_muted_bot_skips_group_rounds_but_answers_when_named(tmp_path):
    app = create_app(build_crew(tmp_path / "m.db", router=FakeRouter(["S here.", "SKIP", "SKIP", "SKIP", "SKIP", "Writer here."])))
    with TestClient(app) as client:
        client.patch("/api/bots/inbox", json={"muted": True})
    crew = app.state.crew
    await crew.post("team", "team, say hi everyone")
    await crew.wait_idle("team")
    asked = [c["purpose"] for c in crew.router.calls]
    assert "turn:inbox" not in asked and "turn:desk" in asked  # a round skips the muted bot
    await crew.post("team", "@inbox are you there?")
    await crew.wait_idle("team")
    assert crew.router.calls[-1]["purpose"] == "turn:inbox"  # @naming it still works


def test_only_bots_you_built_can_be_removed(tmp_path):
    app, client = client_for(tmp_path)
    with client:
        client.post("/api/bots", json={"name": "Temp"})
        client.post("/api/chats", json={"title": "Pair", "members": ["s", "temp"]})
        assert client.delete("/api/bots/desk").status_code == 400
        assert client.delete("/api/bots/temp").json() == {"ok": True}
        chats = {c["id"]: c for c in client.get("/api/chats").json()}
        assert "dm-temp" not in chats and "temp" not in chats["team"]["members"]
        assert all("temp" not in c["members"] for c in chats.values())
        assert "temp" not in {b["id"] for b in client.get("/api/bots").json()}


def test_add_routine_over_http_and_a_bad_schedule_says_why(tmp_path):
    app, client = client_for(tmp_path)
    with client:
        row = client.post("/api/routines", json={"chat_id": "dm-scout", "text": "Check AI news", "schedule": "every day at 9am"}).json()
        assert row["chat_id"] == "dm-scout" and row["schedule"] == "every day at 9am"
        bad = client.post("/api/routines", json={"chat_id": "dm-scout", "text": "x", "schedule": "whenever"})
        assert bad.status_code == 400 and "every monday at 9am" in bad.json()["detail"]
        assert client.post("/api/routines", json={"chat_id": "nope", "text": "x", "schedule": "in 5 minutes"}).status_code == 404
