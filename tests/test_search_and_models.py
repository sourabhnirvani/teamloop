from types import SimpleNamespace

import httpx
import openai

from teamloop.models import providers as P
from teamloop.models.router import Router
from teamloop.tools import web

WIKI = {"query": {"search": [{"title": "Large language model", "snippet": "a <b>model</b>"}]}}


def mock_client(handler):
    return lambda **kw: httpx.AsyncClient(transport=httpx.MockTransport(handler), headers={"User-Agent": web.UA},
                                          follow_redirects=True)


async def test_search_falls_back_and_wikipedia_gets_an_honest_agent(monkeypatch):
    seen = {}

    def handler(request):
        if "duckduckgo" in request.url.host:
            return httpx.Response(202, text="are you a bot?")
        seen["wiki_ua"] = request.headers["user-agent"]
        return httpx.Response(200, json=WIKI)

    async def no_browser(query, n):
        seen["browser_tried"] = True
        return []

    monkeypatch.setattr(web, "_client", mock_client(handler))
    monkeypatch.setattr(web, "_browser_search", no_browser)
    out = await web.web_search({"query": "llm"}, None)
    assert out.ok and "Wikipedia" in out.text and out.data["results"][0]["title"] == "Large language model"
    assert seen == {"browser_tried": True, "wiki_ua": web.BOT_UA}


async def test_search_uses_the_crews_chrome_when_duckduckgo_blocks_scripts(monkeypatch):
    monkeypatch.setattr(web, "_client", mock_client(lambda r: httpx.Response(202)))

    async def browser(query, n):
        return [{"title": "Groq", "url": "https://groq.com", "snippet": ""}]

    monkeypatch.setattr(web, "_browser_search", browser)
    out = await web.web_search({"query": "free llm api"}, None)
    assert out.ok and "on the web" in out.text and out.data["results"][0]["url"] == "https://groq.com"


async def test_fetching_wikipedia_uses_the_honest_agent(monkeypatch):
    seen = []
    monkeypatch.setattr(web, "_client", mock_client(lambda r: seen.append(r.headers["user-agent"]) or
                                                    httpx.Response(200, text="<title>X</title><p>hi</p>",
                                                                   headers={"content-type": "text/html"})))
    await web.fetch_page({"url": "https://en.wikipedia.org/wiki/X"}, None)
    await web.fetch_page({"url": "https://example.com/"}, None)
    assert seen == [web.BOT_UA, web.UA]


def _bad_tool_call(failed: str) -> openai.BadRequestError:
    response = httpx.Response(400, request=httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions"))
    body = {"error": {"message": "Failed to parse tool call arguments as JSON", "code": "tool_use_failed",
                      "failed_generation": failed}}
    return openai.BadRequestError("tool_use_failed", response=response, body=body)


def _router_with(monkeypatch, steps):
    calls = []

    async def create(**kwargs):
        calls.append(kwargs)
        step = steps.pop(0)
        if isinstance(step, Exception):
            raise step
        message = SimpleNamespace(content=step, tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=None)

    router = Router(env={"GROQ_API_KEY": "gsk_" + "k" * 52, "TEAMLOOP_CHAIN": "groq", "GROQ_MODELS": "m"})
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(router, "_client", lambda provider, key: client)
    return router, calls


TOOLS = [{"type": "function", "function": {"name": "web_search", "parameters": {}}}]


async def test_a_broken_tool_call_is_salvaged_or_retried(monkeypatch):
    router, calls = _router_with(monkeypatch, [_bad_tool_call('{"name": "web_search", "arguments": {"query": "x"}}')])
    reply = await router.chat([{"role": "user", "content": "hi"}], tools=TOOLS)
    assert [(c.name, c.args) for c in reply.tool_calls] == [("web_search", {"query": "x"})] and len(calls) == 1

    router, calls = _router_with(monkeypatch, [_bad_tool_call('{"name": "web_search", "arguments": {"query": '),
                                               "Here you go."])
    reply = await router.chat([{"role": "user", "content": "hi"}], tools=TOOLS)
    assert reply.text == "Here you go." and len(calls) == 2  # retried once on the same model, key not benched


def test_ollama_models_come_from_what_is_installed(monkeypatch):
    P._ollama_seen.clear()
    tags = {"models": [{"name": "qwen3:4b"}, {"name": "nomic-embed-text:latest"}]}
    monkeypatch.setattr(httpx, "get", lambda url, timeout: SimpleNamespace(json=lambda: tags))
    assert P.models_for(P.PROVIDERS["ollama"], {"OLLAMA_URL": "http://local:11434/v1"}) == ["qwen3:4b"]
    P._ollama_seen.clear()

    def down(url, timeout):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(httpx, "get", down)
    assert P.models_for(P.PROVIDERS["ollama"], {"OLLAMA_URL": "http://local:11434/v1"}) == ["qwen2.5:7b"]
    P._ollama_seen.clear()
