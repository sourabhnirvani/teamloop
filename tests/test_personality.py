"""Each bot talks in its own manner; bots people build get a personality they pick, and it can be changed."""

from fakes import FakeRouter
from fastapi.testclient import TestClient

from teamloop.crew import bots as crew_bots
from teamloop.crew.bots import BOTS, PERSONALITIES, ROSTER, system_prompt
from teamloop.server.app import build_crew, create_app


def manner_line(bot_id: str) -> str:
    return next(line for line in system_prompt(BOTS[bot_id]).splitlines() if line.startswith("Your manner"))


def client_for(tmp_path):
    return TestClient(create_app(build_crew(tmp_path / "p.db", router=FakeRouter([]))))


def test_each_bot_has_its_own_manner():
    lines = {b.id: manner_line(b.id) for b in ROSTER}
    assert len(set(lines.values())) == len(ROSTER)  # six bots, six different manners
    assert "captain" in lines["s"] and "tinkerer" in lines["desk"] and "explorer" in lines["scout"]
    for b in ROSTER:  # the manner is tone only: the real rules still follow it
        prompt = system_prompt(b)
        assert prompt.index("Your manner") < prompt.index("Never say you did something unless a tool confirmed it")


def test_a_built_bot_talks_in_the_personality_you_picked(tmp_path):
    with client_for(tmp_path) as client:
        kinds = client.get("/api/personalities").json()
        assert {k["id"] for k in kinds} == set(PERSONALITIES) and all(k["label"] and k["blurb"] for k in kinds)
        made = client.post("/api/bots", json={"name": "Pip", "role": "Helper", "personality": "shy"}).json()
        assert made["personality"] == "shy" and made["default_personality"] is None
        assert PERSONALITIES["shy"].manner in manner_line("pip")
        assert client.post("/api/bots", json={"name": "Nope", "personality": "evil"}).status_code == 400
        assert "nope" not in BOTS  # a refused bot isn't half made
        plain = client.post("/api/bots", json={"name": "Plain"}).json()
        assert plain["personality"] == "cheerful"  # no pick: a friendly default


def test_personality_can_be_changed_and_put_back(tmp_path):
    with client_for(tmp_path) as client:
        bot = client.patch("/api/bots/scout", json={"personality": "sleepy"}).json()
        assert bot["personality"] == "sleepy" and bot["default_personality"] == "explorer"
        assert PERSONALITIES["sleepy"].manner in manner_line("scout")
        assert client.patch("/api/bots/scout", json={"personality": "grumpy"}).status_code == 400
        back = client.patch("/api/bots/scout", json={"personality": ""}).json()
        assert back["personality"] == "explorer" and "explorer" in manner_line("scout")


def test_a_saved_personality_survives_a_restart(tmp_path):
    with client_for(tmp_path) as client:
        client.post("/api/bots", json={"name": "Pip", "personality": "bossy"})
        client.patch("/api/bots/writer", json={"personality": "calm"})
    crew_bots.BOTS.clear()
    crew_bots.BOTS.update({b.id: b for b in ROSTER})
    with client_for(tmp_path) as client:  # same database, fresh start
        got = {b["id"]: b["personality"] for b in client.get("/api/bots").json()}
    assert got["pip"] == "bossy" and got["writer"] == "calm" and got["s"] == "captain"
