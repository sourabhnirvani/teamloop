from fakes import make_crew

from evals import run as evals
from teamloop.keys import wallet

SAFE = ["battery", "write_file", "unapproved_delete", "terminal", "secrets_hidden"]


async def test_deterministic_evals_pass(tmp_path, monkeypatch):
    async def no_network(provider, key):
        return False

    monkeypatch.setattr(wallet, "check", no_network)
    lines = []
    results = await evals.run(only=SAFE, crew=make_crew(tmp_path, []), save=False, out=lines.append)
    assert [r["task"] for r in results] == SAFE
    assert all(r["ok"] for r in results), lines


def test_live_and_desktop_tasks_are_opt_in():
    plain = [t.name for t in evals.TASKS if not t.live and not t.desktop]
    assert "notepad" not in plain and "live_writer" not in plain and "battery" in plain
