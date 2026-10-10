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


def test_free_only_by_default():
    assert "nebius" not in [p.id for p in P.chain({})]
    assert "nebius" in [p.id for p in P.chain({"TEAMLOOP_ALLOW_PAID": "1"})]
    env = {"OPENROUTER_MODELS": "openai/gpt-4o, meta-llama/llama-3.3-70b-instruct:free"}
    assert P.models_for(P.PROVIDERS["openrouter"], env) == ["meta-llama/llama-3.3-70b-instruct:free"]
    assert all(m.endswith(":free") for m in P.models_for(P.PROVIDERS["openrouter"], {}))
    assert P.free_to_use("groq", "llama-3.3-70b-versatile") and not P.free_to_use("openrouter", "openai/gpt-4o")


async def test_switching_to_a_paid_model_is_refused(tmp_path):
    from fakes import make_crew

    crew = make_crew(tmp_path, [])
    for text in ("use nebius", "use openrouter:openai/gpt-4o"):
        await crew.post("dm-s", text)
        await crew.wait_idle("dm-s")
        assert "can cost money" in crew.store.messages("dm-s")[-1]["text"]
    assert crew.store.get_setting("crew_model") is None
    await crew.post("dm-s", "use openrouter:meta-llama/llama-3.3-70b-instruct:free")
    await crew.wait_idle("dm-s")
    assert crew.store.get_setting("crew_model") == "openrouter:meta-llama/llama-3.3-70b-instruct:free"
