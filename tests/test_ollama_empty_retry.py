"""A local model that answers with nothing once gets one more try on the same model (seen live: qwen2.5:7b,
"No model answered: ... empty reply"); a second empty answer is still a failure, not a loop."""

import httpx
import pytest

from teamloop.models import providers as P
from teamloop.models.router import Router, Transient


class FakeOllama:
    """Stands in for httpx.AsyncClient: each POST /api/chat takes the next canned answer."""
    answers: list = []
    bodies: list = []

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, json=None):
        FakeOllama.bodies.append(json)
        content = FakeOllama.answers.pop(0)
        return httpx.Response(200, json={"message": {"content": content}, "prompt_eval_count": 10, "eval_count": 3})


@pytest.fixture
def ollama(monkeypatch):
    FakeOllama.bodies = []
    monkeypatch.setattr(httpx, "AsyncClient", FakeOllama)
    return FakeOllama


async def test_an_empty_reply_is_retried_once_on_the_same_model(ollama):
    ollama.answers = ["", "Paris."]
    reply = await Router(env={})._call_ollama(P.PROVIDERS["ollama"], "qwen2.5:7b",
                                              [{"role": "user", "content": "capital of France?"}], None, None)
    assert reply.text == "Paris." and reply.model == "qwen2.5:7b"
    assert len(ollama.bodies) == 2 and ollama.bodies[0] == ollama.bodies[1]   # the same request, sent again


async def test_two_empty_replies_still_fail(ollama):
    ollama.answers = ["", ""]
    with pytest.raises(Transient, match="empty reply"):
        await Router(env={})._call_ollama(P.PROVIDERS["ollama"], "qwen2.5:7b",
                                          [{"role": "user", "content": "hi"}], None, None)
    assert len(ollama.bodies) == 2
