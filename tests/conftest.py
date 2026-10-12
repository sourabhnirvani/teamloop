import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["TEAMLOOP_TRACE"] = "0"
os.environ["TEAMLOOP_DOCTOR_HOURS"] = "0"  # no background model checks in tests
os.environ["OLLAMA_URL"] = "http://127.0.0.1:9/v1"  # never ask a real local Ollama which models it has


@pytest.fixture(autouse=True)
def workspace(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    monkeypatch.setenv("TEAMLOOP_WORKSPACE", str(ws))
    monkeypatch.setenv("TEAMLOOP_DB", str(ws / "test.db"))
    monkeypatch.setenv("TEAMLOOP_VAULT", str(ws / "keys.vault"))
    return ws


@pytest.fixture(autouse=True)
def person_away(monkeypatch):
    """Tests never wait for whoever is typing on this PC (operator safety reads the real idle time)."""
    from teamloop.computer import operator
    monkeypatch.setattr(operator.OPERATOR, "idle", lambda: 1e9)


@pytest.fixture(autouse=True)
def restore_environ():
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
