import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["TEAMLOOP_TRACE"] = "0"


@pytest.fixture(autouse=True)
def workspace(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    monkeypatch.setenv("TEAMLOOP_WORKSPACE", str(ws))
    monkeypatch.setenv("TEAMLOOP_DB", str(ws / "test.db"))
    return ws
