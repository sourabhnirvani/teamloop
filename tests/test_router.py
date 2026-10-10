import pytest

from teamloop.models.router import START_RPM, AllModelsBusy, BadKey, ModelGone, RateLimited, Reply, Router, Transient

ENV = {"TEAMLOOP_CHAIN": "gemini,groq", "GEMINI_API_KEY": "g1", "GEMINI_API_KEY_2": "g2",
       "GROQ_API_KEY": "q1", "GEMINI_MODELS": "gm", "GROQ_MODELS": "qm"}


def make(behaviour, env=ENV, **kw):
    router = Router(env=env, **kw)
    router.tried = []

    async def fake_call(provider, key, model, messages, tools, max_tokens):
        router.tried.append((provider.id, key, model))
        result = behaviour(provider.id, key, model)
        if isinstance(result, BaseException):
            raise result
        return Reply(result, [], provider.id, model, 10, 5)

    router._call = fake_call
    return router


async def test_first_working_slot_answers():
    router = make(lambda p, k, m: f"{p}:{k}")
    reply = await router.chat([{"role": "user", "content": "hi"}])
    assert reply.text == "gemini:g1"


async def test_rate_limit_rests_key_and_moves_on():
    router = make(lambda p, k, m: RateLimited(retry_after=5) if k == "g1" else f"{p}:{k}")
    reply = await router.chat([])
    assert reply.text == "gemini:g2"
    st = router.state("gemini", "g1")
    assert st.rpm == START_RPM / 2 and st.rest_until > router.clock()
    assert (await router.chat([])).text == "gemini:g2"
    assert router.tried.count(("gemini", "g1", "gm")) == 1


async def test_daily_limit_rests_for_hours():
    router = make(lambda p, k, m: RateLimited(daily=True) if p == "gemini" else "groq ok")
    assert (await router.chat([])).text == "groq ok"
    assert router.state("gemini", "g1").rest_until - router.clock() > 3600


async def test_bad_key_is_never_tried_again():
    router = make(lambda p, k, m: BadKey() if k == "g1" else "ok")
    await router.chat([])
    await router.chat([])
    assert router.state("gemini", "g1").bad
    assert router.tried.count(("gemini", "g1", "gm")) == 1


async def test_gone_model_is_dropped():
    router = make(lambda p, k, m: ModelGone() if m == "gm" else "groq")
    assert (await router.chat([])).text == "groq"
    assert ("gemini", "gm") in router.dead_models
    assert all(s[2] != "gm" for s in router.slots())


async def test_everything_failing_raises_busy_with_reasons():
    router = make(lambda p, k, m: Transient("boom"))
    with pytest.raises(AllModelsBusy, match="boom"):
        await router.chat([])


async def test_no_keys_tells_person_to_add_one():
    router = make(lambda p, k, m: "x", env={"TEAMLOOP_CHAIN": "gemini"})
    with pytest.raises(AllModelsBusy, match="add a free key"):
        await router.chat([])


async def test_prefer_puts_provider_first():
    router = make(lambda p, k, m: p)
    assert (await router.chat([], prefer="groq")).text == "groq"
    assert (await router.chat([], prefer="gemini:gm")).text == "gemini"


async def test_per_minute_pace_skips_busy_key():
    router = make(lambda p, k, m: k)
    router.state("gemini", "g1").rpm = 1
    assert (await router.chat([])).text == "g1"
    assert (await router.chat([])).text == "g2"


async def test_success_streak_raises_pace():
    router = make(lambda p, k, m: k)
    for _ in range(10):
        await router.chat([])
    assert router.state("gemini", "g1").rpm == START_RPM + 2


async def test_usage_hook_records_tokens():
    seen = []
    router = make(lambda p, k, m: "ok", on_usage=lambda *a: seen.append(a))
    await router.chat([], purpose="turn:s")
    assert seen == [("gemini", "gm", 10, 5, "turn:s")]
