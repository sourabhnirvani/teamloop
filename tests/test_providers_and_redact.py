from teamloop.keys.redact import HIDDEN, redact, redact_obj
from teamloop.models import providers as P

FAKE_GEMINI = "AIza" + "x" * 35
FAKE_GROQ = "gsk_" + "a1" * 26


def test_detects_pasted_keys_in_free_text():
    found = P.detect_keys(f"here: {FAKE_GEMINI} and also {FAKE_GROQ}, thanks")
    assert [(p.id, k) for p, k in found] == [("gemini", FAKE_GEMINI), ("groq", FAKE_GROQ)]


def test_key_pool_reads_numbered_names_and_dedupes():
    env = {"GEMINI_API_KEY": "a", "GEMINI_API_KEY_2": "b", "GEMINI_API_KEY_3": "a"}
    assert P.keys_for(P.PROVIDERS["gemini"], env) == ["a", "b"]
    assert P.keys_for(P.PROVIDERS["ollama"], env) == [""]


def test_chain_and_models_can_be_overridden():
    env = {"TEAMLOOP_CHAIN": "groq, ollama, nope", "GROQ_MODELS": "m1,m2"}
    assert [p.id for p in P.chain(env)] == ["groq", "ollama"]
    assert P.models_for(P.PROVIDERS["groq"], env) == ["m1", "m2"]


def test_redact_hides_known_and_pattern_keys(monkeypatch):
    monkeypatch.setenv("MY_SERVICE_TOKEN", "super-secret-token-123")
    text = redact(f"token super-secret-token-123 and key {FAKE_GEMINI}")
    assert "super-secret" not in text and FAKE_GEMINI not in text
    assert text.count(HIDDEN) == 2
    assert redact_obj({"a": [FAKE_GROQ], "n": 3}) == {"a": [HIDDEN], "n": 3}
