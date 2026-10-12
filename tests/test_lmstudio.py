"""K: LM Studio as a local provider: no key, models from its /v1/models (embeddings skipped), nothing when it isn't
running, after Ollama in the chain, and treated as local by the router (no pace waits, no shared-key benching)."""

import httpx
import pytest

from teamloop.models import providers as P
from teamloop.models.router import Router


class _Res:
    def __init__(self, body):
        self.body = body

    def json(self):
        return self.body


@pytest.fixture(autouse=True)
def fresh_cache():
    P._lmstudio_seen.clear()
    yield
    P._lmstudio_seen.clear()


def test_models_come_from_lm_studio_without_embeddings(monkeypatch):
    seen = []

    def fake_get(url, timeout):
        seen.append(url)
        return _Res({"data": [{"id": "qwen2.5-7b-instruct"}, {"id": "text-embedding-nomic-embed-text-v1.5"},
                              {"id": "llama-3.2-3b-instruct"}]})
    monkeypatch.setattr(httpx, "get", fake_get)
    lm = P.PROVIDERS["lmstudio"]
    assert P.models_for(lm, {}) == ["qwen2.5-7b-instruct", "llama-3.2-3b-instruct"]
    assert seen == ["http://localhost:1234/v1/models"]
    assert P.keys_for(lm, {}) == [""]                       # no key needed


def test_not_running_means_no_models(monkeypatch):
    def refused(url, timeout):
        raise httpx.ConnectError("connection refused")
    monkeypatch.setattr(httpx, "get", refused)
    assert P.models_for(P.PROVIDERS["lmstudio"], {}) == []


def test_lm_studio_url_can_be_moved(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda url, timeout: _Res({"data": [{"id": url}]}))
    assert P.models_for(P.PROVIDERS["lmstudio"], {"LMSTUDIO_URL": "http://192.168.1.5:1234/v1"}) == \
        ["http://192.168.1.5:1234/v1/models"]


def test_it_comes_right_after_ollama_and_counts_as_local():
    order = list(P.DEFAULT_CHAIN)
    assert order.index("lmstudio") == order.index("ollama") + 1
    assert P.LOCAL == {"ollama", "lmstudio"}
    assert P.PROVIDERS["lmstudio"].base_url == "http://localhost:1234/v1"


def test_the_router_never_pace_waits_for_a_local_model():
    router = Router(env={})
    slots = [(P.PROVIDERS["lmstudio"], "", "qwen2.5-7b-instruct"), (P.PROVIDERS["ollama"], "", "qwen2.5:7b")]
    assert router.pace_wait(slots, now=1000.0) is None



def test_the_app_lists_lm_studio_models_when_it_runs_and_says_so_when_it_doesnt(tmp_path, monkeypatch):
    # (Sourabh's side) the model picker and Settings > AI models
    from fakes import FakeRouter
    from fastapi.testclient import TestClient

    from teamloop.models import providers as P
    from teamloop.server.app import build_crew, create_app

    monkeypatch.setenv("TEAMLOOP_CHAIN", "lmstudio")
    monkeypatch.setattr(P, "lmstudio_models", lambda base_url, ttl=60.0: ["qwen2.5-7b-instruct"])
    with TestClient(create_app(build_crew(tmp_path / "l.db", router=FakeRouter([])))) as client:
        [row] = client.get("/api/models").json()
        assert (row["provider"], row["local"], row["running"]) == ("lmstudio", True, True)
        assert [m["id"] for m in row["models"]] == ["qwen2.5-7b-instruct"]
        monkeypatch.setattr(P, "lmstudio_models", lambda base_url, ttl=60.0: [])
        [off] = client.get("/api/models").json()
        assert off["running"] is False and off["models"] == []
