"""Build E, the API keys page backend: one row per key, test all, remove, clean up. Fake keys only."""

import os

import pytest
from fakes import FakeRouter
from fastapi.testclient import TestClient

from teamloop.keys import vault, wallet
from teamloop.keys.redact import _SECRET_NAME
from teamloop.server.app import build_crew, create_app

GOOD = "gsk_" + "fakegoodkeyfortestsonly0123456789abcdWXYZ"
BAD = "gsk_" + "fakebadkeyfortestsonly01234567890abcdQRST"
ENV_BAD = "AIza" + "fakeenvkeyfortestsonly0123456789abLMNO"


@pytest.fixture(autouse=True)
def no_real_keys():
    """This machine's own keys (.env) must not show up in these rows; conftest restores them afterwards."""
    for name in [n for n in os.environ if _SECRET_NAME.search(n.upper())]:
        del os.environ[name]


def client(tmp_path):
    return TestClient(create_app(build_crew(tmp_path / "keys.db", router=FakeRouter([]))))


async def fake_check(provider, key):
    return {GOOD: True, BAD: False}.get(key)


def test_no_clear_answer_after_a_test_is_said_plainly(tmp_path, monkeypatch):
    monkeypatch.setattr(wallet, "check", fake_check)
    os.environ["GEMINI_API_KEY"] = ENV_BAD          # fake_check answers None for it
    with client(tmp_path) as c:
        before = c.get("/api/keys/entries").json()[0]
        after = c.post("/api/keys/test").json()[0]
    assert before["status"] == after["status"] == "unchecked"
    assert before["reason"] == "not tested yet" and "no clear yes or no" in after["reason"]


def test_rows_are_masked_and_unchecked_until_tested(tmp_path):
    vault.put("GROQ_API_KEY", GOOD)
    with client(tmp_path) as c:
        rows = c.get("/api/keys/entries").json()
    assert rows == [{"env": "GROQ_API_KEY", "provider": "groq", "provider_name": rows[0]["provider_name"],
                     "masked": "…WXYZ", "status": "unchecked", "reason": rows[0]["reason"], "source": "vault"}]
    assert GOOD not in str(rows)


def test_test_all_marks_works_and_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(wallet, "check", fake_check)
    vault.put("GROQ_API_KEY", GOOD)
    vault.put("GROQ_API_KEY_2", BAD)
    with client(tmp_path) as c:
        rows = {r["env"]: r for r in c.post("/api/keys/test").json()}
        assert rows["GROQ_API_KEY"]["status"] == "works"
        assert rows["GROQ_API_KEY_2"]["status"] == "rejected" and "401" in rows["GROQ_API_KEY_2"]["reason"]
        # statuses persist without testing again
        again = {r["env"]: r["status"] for r in c.get("/api/keys/entries").json()}
    assert again == {"GROQ_API_KEY": "works", "GROQ_API_KEY_2": "rejected"}


def test_remove_vault_key_and_refuse_env_key(tmp_path):
    vault.put("GROQ_API_KEY", GOOD)
    os.environ["GEMINI_API_KEY"] = ENV_BAD   # as if from .env
    with client(tmp_path) as c:
        assert c.delete("/api/keys/GROQ_API_KEY").status_code == 200
        assert "GROQ_API_KEY" not in vault.load() and not os.environ.get("GROQ_API_KEY")
        blocked = c.delete("/api/keys/GEMINI_API_KEY")
        assert blocked.status_code == 409 and ".env" in blocked.json()["detail"]
        assert c.delete("/api/keys/NOPE_API_KEY").status_code == 404
    assert os.environ["GEMINI_API_KEY"] == ENV_BAD


def test_cleanup_removes_rejected_vault_keys_only(tmp_path, monkeypatch):
    monkeypatch.setattr(wallet, "check", fake_check)
    vault.put("GROQ_API_KEY", GOOD)
    vault.put("GROQ_API_KEY_2", BAD)
    os.environ["GEMINI_API_KEY"] = ENV_BAD
    monkeypatch.setattr(wallet, "check", lambda p, k: fake_check(p, k) if k != ENV_BAD else _false())
    with client(tmp_path) as c:
        c.post("/api/keys/test")
        result = c.post("/api/keys/cleanup").json()
        left = [r["env"] for r in c.get("/api/keys/entries").json()]
    assert result == {"removed": ["GROQ_API_KEY_2"], "kept_env": ["GEMINI_API_KEY"]}
    assert set(left) == {"GROQ_API_KEY", "GEMINI_API_KEY"} and "GROQ_API_KEY_2" not in vault.load()


async def _false():
    return False
