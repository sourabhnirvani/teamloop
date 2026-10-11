"""Local models (Ollama): every installed chat model works, the whole prompt is read, and one model's trouble
doesn't bench the others."""

import json
from types import SimpleNamespace

import httpx

from teamloop.models import local
from teamloop.models import providers as P
from teamloop.models.router import Router

TOOLS = [{"type": "function", "function": {"name": "web_search", "description": "Search the web.",
                                            "parameters": {"type": "object", "properties": {"query": {"type": "string"}},
                                                           "required": ["query"]}}}]
ENV = {"TEAMLOOP_CHAIN": "ollama", "OLLAMA_URL": "http://ollama.test:11434/v1"}


def fake_ollama(monkeypatch, answer):
    """Ollama's /api/chat answered by `answer(body) -> (status, json)`; returns the bodies it got."""
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        body = json.loads(request.content)
        seen.append(body)
        status, data = answer(body)
        return httpx.Response(status, json=data)

    real = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    return seen


def installed(monkeypatch, models):
    P._ollama_seen.clear()
    P._ollama_info.clear()
    monkeypatch.setattr(httpx, "get", lambda url, timeout: SimpleNamespace(json=lambda: {"models": models}))


async def test_local_calls_read_the_whole_prompt_and_return_tool_calls(monkeypatch):
    installed(monkeypatch, [{"name": "qwen2.5:7b", "capabilities": ["completion", "tools"],
                             "details": {"context_length": 32768}}])
    seen = fake_ollama(monkeypatch, lambda body: (200, {
        "message": {"role": "assistant", "content": "",
                    "tool_calls": [{"function": {"name": "web_search", "arguments": {"query": "capital of France"}}}]},
        "prompt_eval_count": 1990, "eval_count": 12}))
    reply = await Router(env=ENV).chat([{"role": "system", "content": "You are Scout."},
                                        {"role": "user", "content": "capital of France?"}], tools=TOOLS)
    assert [(c.name, c.args) for c in reply.tool_calls] == [("web_search", {"query": "capital of France"})]
    assert (reply.model, reply.tokens_in, reply.tokens_out) == ("qwen2.5:7b", 1990, 12)
    body = seen[0]
    # Ollama's default 4096 cut a 6000-token prompt to 2050 through the OpenAI-style door; its own API takes num_ctx
    assert body["options"]["num_ctx"] == local.CTX and body["tools"] == TOOLS and body["stream"] is False


async def test_a_model_without_tool_support_gets_the_tools_in_its_prompt(monkeypatch):
    installed(monkeypatch, [{"name": "gemma3:1b", "details": {}}])  # an older Ollama: no capabilities listed

    def answer(body):
        if "tools" in body:
            return 400, {"error": "registry.ollama.ai/library/gemma3:1b does not support tools"}
        return 200, {"message": {"content": '<tool_call>{"name": "web_search", "arguments": {"query": "news"}}</tool_call>'}}

    seen = fake_ollama(monkeypatch, answer)
    router = Router(env=ENV)
    reply = await router.chat([{"role": "system", "content": "You are Scout."}, {"role": "user", "content": "news?"}],
                              tools=TOOLS)
    assert [(c.name, c.args) for c in reply.tool_calls] == [("web_search", {"query": "news"})]
    assert "tools" not in seen[1] and "<tool_call>" in seen[1]["messages"][0]["content"]  # written into the prompt
    # the next turn: earlier calls and results go back as plain text, and native tools aren't tried again
    history = [{"role": "user", "content": "news?"}, reply.message,
               {"role": "tool", "tool_call_id": reply.tool_calls[0].id, "content": "AI news: ..."}]
    seen.clear()
    await router.chat(history, tools=TOOLS)
    assert len(seen) == 1 and "tools" not in seen[0]
    sent = [(m["role"], m["content"]) for m in seen[0]["messages"][1:]]
    assert sent[1][0] == "assistant" and "<tool_call>" in sent[1][1]
    assert sent[2] == ("user", "Result of web_search: AI news: ...")


async def test_thinking_models_answer_directly_without_their_notes(monkeypatch):
    installed(monkeypatch, [{"name": "qwen3:4b", "capabilities": ["completion", "tools", "thinking"]},
                            {"name": "gpt-oss:20b", "capabilities": ["completion", "tools", "thinking"]}])
    seen = fake_ollama(monkeypatch, lambda body: (200, {"message": {"content": "<think>hmm, France...</think>\nParis."}}))
    router = Router(env=ENV)
    assert (await router.chat([{"role": "user", "content": "capital?"}], prefer="ollama:qwen3:4b")).text == "Paris."
    assert (await router.chat([{"role": "user", "content": "capital?"}], prefer="ollama:gpt-oss:20b")).text == "Paris."
    assert [b["think"] for b in seen] == [False, "low"]  # gpt-oss can't switch thinking off, only down
    assert local.strip_think("notes the template opened</think>Paris.") == "Paris."
    assert local.strip_think("<think>never finished") == ""


def test_embedding_models_are_not_offered_as_chat_models(monkeypatch):
    installed(monkeypatch, [{"name": "llama3.2:3b", "capabilities": ["completion", "tools"]},
                            {"name": "bge-m3:latest", "capabilities": ["embedding"]},
                            {"name": "nomic-embed-text:latest"},
                            {"name": "llava:7b", "capabilities": ["completion", "vision"]}])
    assert P.models_for(P.PROVIDERS["ollama"], ENV) == ["llama3.2:3b", "llava:7b"]
    assert P.ollama_model_info(ENV["OLLAMA_URL"], "llava:7b")["tools"] is False  # it gets tools in its prompt


async def test_one_local_models_trouble_does_not_bench_the_others(monkeypatch):
    installed(monkeypatch, [{"name": "broken:1b", "capabilities": ["completion", "tools"]},
                            {"name": "qwen2.5:7b", "capabilities": ["completion", "tools"]}])
    seen = fake_ollama(monkeypatch, lambda body: (500, {"error": "model runner crashed"}) if body["model"] == "broken:1b"
                       else (200, {"message": {"content": "hi"}}))
    router = Router(env=ENV)
    for _ in range(2):  # the second call still reaches the good model straight away
        assert (await router.chat([{"role": "user", "content": "hi"}])).model == "qwen2.5:7b"
    assert [b["model"] for b in seen] == ["broken:1b", "qwen2.5:7b", "broken:1b", "qwen2.5:7b"]
    assert router.state("ollama", "").rest_until == 0


def test_a_prompt_too_big_for_the_usual_context_gets_a_bigger_one_within_the_models_limit():
    small = [{"role": "user", "content": "hi"}]
    huge = [{"role": "user", "content": "word " * 30000}]
    assert local.context_for(small, None, {}) == local.CTX
    assert local.context_for(huge, None, {}) == local.BIG_CTX
    assert local.context_for(huge, None, {"ctx": 8192}) == 8192  # never more than the model takes
    assert local.context_for(small, None, {}, {"OLLAMA_NUM_CTX": "8192"}) == 8192


def test_calls_written_like_code_and_over_wrapped_arguments_are_understood():
    from teamloop.models import textcalls

    tools = TOOLS + [{"type": "function", "function": {"name": "delegate", "parameters": {
        "type": "object", "properties": {"bot": {"type": "string"}, "instruction": {"type": "string"}},
        "required": ["bot", "instruction"]}}}]
    # seen from qwen2.5:7b with the tools in its prompt
    assert textcalls.extract_python('web_search("capital of France")', tools) == ([("web_search", {"query": "capital of France"})], "")
    assert textcalls.extract_python("`delegate(bot='desk', instruction='battery')`", tools)[0] == [
        ("delegate", {"bot": "desk", "instruction": "battery"})]
    assert textcalls.extract_python("I could call open_door(1) but won't.", tools)[0] == []  # not a tool, not alone
    # seen from qwen2.5:7b natively: the whole argument list wrapped in one of its own keys
    assert textcalls.tidy([("delegate", {"bot": {"bot": "desk", "instruction": "battery"}})], tools) == [
        ("delegate", {"bot": "desk", "instruction": "battery"})]
    assert textcalls.tidy([("delegate", {"arguments": {"bot": "desk", "instruction": "x"}})], tools)[0][1] == {
        "bot": "desk", "instruction": "x"}
    assert textcalls.tidy([("web_search", {"query": "x"})], tools) == [("web_search", {"query": "x"})]  # fine as is
    # seen from qwen2.5:7b with the tools in its prompt
    assert textcalls.tidy([("web_search", {"query": {"query": "capital of France"}})], tools) == [
        ("web_search", {"query": "capital of France"})]
    obj = [{"type": "function", "function": {"name": "set", "parameters": {"type": "object", "properties": {
        "options": {"type": "object"}}}}}]
    assert textcalls.tidy([("set", {"options": {"options": 1}})], obj) == [("set", {"options": {"options": 1}})]  # real object


def test_the_app_lists_each_local_model_with_what_it_can_do_and_says_when_ollama_is_off(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from fakes import FakeRouter
    from teamloop.server.app import build_crew, create_app

    monkeypatch.setenv("TEAMLOOP_CHAIN", "ollama")
    monkeypatch.setenv("OLLAMA_URL", ENV["OLLAMA_URL"])
    installed(monkeypatch, [{"name": "qwen2.5:7b", "capabilities": ["completion", "tools"], "details": {"context_length": 32768}},
                            {"name": "gemma3:1b", "capabilities": ["completion"]},
                            {"name": "qwen3:4b", "capabilities": ["completion", "tools", "thinking"]}])
    with TestClient(create_app(build_crew(tmp_path / "m.db", router=FakeRouter([])))) as client:
        local = client.get("/api/models").json()[0]
        assert (local["provider"], local["local"], local["running"]) == ("ollama", True, True)
        got = {m["id"]: (m["tools"], m["thinking"], m["ctx"]) for m in local["models"]}
        assert got == {"qwen2.5:7b": (True, False, 32768), "gemma3:1b": (False, False, None), "qwen3:4b": (True, True, None)}

        def down(url, timeout):
            raise httpx.ConnectError("refused")

        P._ollama_seen.clear()
        monkeypatch.setattr(httpx, "get", down)
        off = client.get("/api/models").json()[0]
        assert off["running"] is False and off["models"] == []  # no made-up "qwen2.5:7b" when Ollama is off
