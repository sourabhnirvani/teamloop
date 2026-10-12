"""Pick a working model for every call.

Walks the provider chain, rotates through each provider's keys, and rests a key that hits a limit.
Per-minute limits adapt: a 429 halves that key's pace, a run of successes raises it again, so a paid
key is never held back by a guessed free-tier number.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from teamloop import trace
from teamloop.models import local
from teamloop.models import providers as P
from teamloop.models import textcalls

log = logging.getLogger(__name__)

MIN_RPM, START_RPM, MAX_RPM = 2.0, 30.0, 60.0  # our own pace per key; a real 429 halves it
PACE_WAIT_MAX = 60.0  # seconds worth waiting for a cloud key's own pace slot instead of going local
DAILY_REST = 6 * 3600


class AllModelsBusy(RuntimeError):
    """No provider in the chain could answer right now."""


class RateLimited(Exception):
    def __init__(self, retry_after: float | None = None, daily: bool = False):
        super().__init__("rate limited")
        self.retry_after, self.daily = retry_after, daily


class BadKey(Exception):
    pass


class ModelGone(Exception):
    pass


class BadToolCall(Exception):
    """The model tried to call a tool but its arguments weren't valid JSON (worth one retry)."""


class Transient(Exception):
    pass


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict


@dataclass
class Reply:
    text: str
    tool_calls: list[ToolCall]
    provider: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0

    @property
    def message(self) -> dict:
        """The assistant message to append to the conversation before tool results."""
        msg: dict[str, Any] = {"role": "assistant", "content": self.text or ""}
        if self.tool_calls:
            msg["tool_calls"] = [
                {"id": c.id, "type": "function",
                 "function": {"name": c.name, "arguments": json.dumps(c.args)}}
                for c in self.tool_calls
            ]
        return msg


@dataclass
class KeyState:
    rpm: float = START_RPM
    rest_until: float = 0.0
    bad: bool = False
    ok_streak: int = 0
    calls: deque = field(default_factory=deque)

    def ready(self, now: float) -> bool:
        while self.calls and now - self.calls[0] > 60:
            self.calls.popleft()
        return not self.bad and now >= self.rest_until and len(self.calls) < self.rpm

    def on_limit(self, now: float, retry_after: float | None, daily: bool) -> None:
        self.rpm = max(MIN_RPM, self.rpm / 2)
        self.ok_streak = 0
        self.rest_until = now + (DAILY_REST if daily else (retry_after or 30.0))

    def on_ok(self) -> None:
        self.ok_streak += 1
        if self.ok_streak % 10 == 0:
            self.rpm = min(MAX_RPM, self.rpm + 2)


UsageHook = Callable[[str, str, int, int, str], None]


class Router:
    def __init__(self, env: Mapping[str, str] | None = None, on_usage: UsageHook | None = None,
                 clock: Callable[[], float] = time.monotonic):
        self._env = env
        self.on_usage = on_usage
        self.clock = clock
        self.sleep: Callable[[float], Any] = asyncio.sleep
        self.keys: dict[tuple[str, str], KeyState] = {}
        self.dead_models: set[tuple[str, str]] = set()
        self.text_only: set[tuple[str, str]] = set()  # local models that can't take native tools
        self.last_doctor: list[dict] = []  # the latest model doctor results
        self._clients: dict[tuple[str, str], Any] = {}

    # ---- choosing -------------------------------------------------------------------------
    def state(self, provider_id: str, key: str) -> KeyState:
        return self.keys.setdefault((provider_id, key), KeyState())

    def slots(self, prefer: str | None = None) -> list[tuple[P.Provider, str, str]]:
        """Every (provider, key, model) to try, in order. `prefer` is "provider" or "provider:model"."""
        out: list[tuple[P.Provider, str, str]] = []
        for provider in P.chain(self._env):
            for model in P.models_for(provider, self._env):
                if (provider.id, model) in self.dead_models:
                    continue
                for key in P.keys_for(provider, self._env):
                    out.append((provider, key, model))
        if prefer:
            pid, _, model = prefer.partition(":")
            out.sort(key=lambda s: not (s[0].id == pid and (not model or s[2] == model)))
        return out

    def pace_wait(self, slots: list[tuple[P.Provider, str, str]], now: float) -> float | None:
        """Seconds until the soonest cloud key that is held back only by our own pace (no 429, not bad,
        not resting) gets a free slot; None when there is no such key."""
        waits = []
        for provider, key, _ in slots:
            if provider.id in P.LOCAL:
                continue
            st = self.state(provider.id, key)
            st.ready(now)  # drops calls older than a minute
            if not st.bad and now >= st.rest_until and st.calls and len(st.calls) >= st.rpm:
                waits.append(max(0.0, 60 - (now - st.calls[0])) + 0.05)
        return min(waits) if waits else None

    def available(self) -> list[str]:
        """Provider ids that have at least one key configured (Ollama counts as configured)."""
        return [p.id for p in P.chain(self._env) if P.keys_for(p, self._env)]

    # ---- calling --------------------------------------------------------------------------
    async def chat(self, messages: list[dict], tools: list[dict] | None = None, prefer: str | None = None,
                   purpose: str = "", max_tokens: int | None = None, only: bool = False, _waited: bool = False) -> Reply:
        """`only=True` tries just the preferred provider/model, with no fallback (the doctor uses it)."""
        again = dict(messages=messages, tools=tools, prefer=prefer, purpose=purpose, max_tokens=max_tokens,
                     only=only, _waited=True)
        errors: list[str] = []
        tried_any = False
        slots = self.slots(prefer)
        if only and prefer:
            pid, _, want = prefer.partition(":")
            slots = [s for s in slots if s[0].id == pid and (not want or s[2] == want)]
        for provider, key, model in slots:
            st = self.state(provider.id, key)
            now = self.clock()
            if not st.ready(now):
                continue
            if provider.id in P.LOCAL and not _waited:
                # A cloud key that is only pacing itself frees up within a minute; that beats a slow local model.
                wait = self.pace_wait(slots, now)
                if wait is not None and wait <= PACE_WAIT_MAX:
                    log.info("waiting %.0fs for a cloud model's pace slot instead of the local model", wait)
                    await self.sleep(wait)
                    return await self.chat(**again)
            tried_any = True
            st.calls.append(now)
            try:
                reply = await self._call(provider, key, model, messages, tools, max_tokens)
            except RateLimited as e:
                st.on_limit(self.clock(), e.retry_after, e.daily)
                errors.append(f"{provider.name} {model}: limit")
                continue
            except BadKey:
                st.bad = True
                errors.append(f"{provider.name}: key rejected")
                continue
            except ModelGone:
                self.dead_models.add((provider.id, model))
                errors.append(f"{provider.name} {model}: model gone")
                continue
            except BadToolCall:
                # Not the key's fault: ask the same model once more before moving on.
                try:
                    reply = await self._call(provider, key, model, messages, tools, max_tokens)
                except (BadToolCall, Transient, RateLimited, BadKey, ModelGone) as e:
                    errors.append(f"{provider.name} {model}: broken tool call ({type(e).__name__})")
                    continue
            except Transient as e:
                if provider.id not in P.LOCAL:  # every local model shares one "key": one model's trouble mustn't bench the rest
                    st.rest_until = self.clock() + 20
                errors.append(f"{provider.name} {model}: {e}")
                continue
            if errors:
                log.info("answered by %s %s after: %s", provider.name, model, "; ".join(errors))
            st.on_ok()
            if self.on_usage:
                try:
                    self.on_usage(provider.id, model, reply.tokens_in, reply.tokens_out, purpose)
                except Exception:  # usage is bookkeeping; never fail a reply over it
                    log.exception("usage hook failed")
            return reply
        if not tried_any and not _waited:  # every key is just pacing itself: wait for the first free slot
            wait = self.pace_wait(slots, self.clock())
            if wait is not None and wait <= PACE_WAIT_MAX:
                await self.sleep(wait)
                return await self.chat(**again)
        if errors:
            log.warning("no model answered: %s", "; ".join(errors))
        if not tried_any and not errors:
            raise AllModelsBusy("No model is ready: add a free key (Gemini, Groq, OpenRouter...) or start Ollama.")
        raise AllModelsBusy("No model answered: " + "; ".join(errors[-4:]))

    def _client(self, provider: P.Provider, key: str):
        cache_key = (provider.id, key)
        if cache_key not in self._clients:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(base_url=P.base_url_for(provider, self._env), api_key=key or "none",
                                 timeout=60, max_retries=0)
            self._clients[cache_key] = trace.wrap(client)
        return self._clients[cache_key]

    async def _call(self, provider: P.Provider, key: str, model: str, messages: list[dict],
                    tools: list[dict] | None, max_tokens: int | None) -> Reply:
        if provider.id == "ollama":
            return await self._call_ollama(provider, model, messages, tools, max_tokens)
        import openai

        kwargs: dict[str, Any] = {"model": model, "messages": messages}
        if tools:
            kwargs["tools"] = tools
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        try:
            resp = await self._client(provider, key).chat.completions.create(**kwargs)
        except openai.RateLimitError as e:
            raise RateLimited(_retry_after(e), _is_daily(e)) from e
        except (openai.AuthenticationError, openai.PermissionDeniedError) as e:
            raise BadKey() from e
        except openai.NotFoundError as e:
            raise ModelGone() from e
        except openai.BadRequestError as e:
            failed = _failed_tool_call(e)
            if failed is None:
                raise Transient(_short(e)) from e
            # The model meant to call a tool but wrote broken JSON (Groq: tool_use_failed). Use what can be read.
            found, text = textcalls.extract(failed, [t["function"]["name"] for t in tools or []])
            if not found:
                raise BadToolCall() from e
            return Reply(text=text, tool_calls=[ToolCall(f"salvaged_{i}", n, a) for i, (n, a) in enumerate(found)],
                         provider=provider.id, model=model)
        except (openai.APIConnectionError, openai.APITimeoutError, openai.InternalServerError) as e:
            raise Transient(_short(e)) from e
        except openai.APIStatusError as e:
            if e.status_code == 410:
                raise ModelGone() from e
            raise Transient(_short(e)) from e
        if not resp.choices:
            raise Transient("empty reply")
        msg = resp.choices[0].message
        calls = [ToolCall(c.id or f"call_{i}", c.function.name, _parse_args(c.function.arguments))
                 for i, c in enumerate(msg.tool_calls or [])]
        text = msg.content or ""
        calls, text = _settle(calls, text, tools)
        usage = resp.usage
        return Reply(text=text, tool_calls=calls, provider=provider.id, model=model,
                     tokens_in=getattr(usage, "prompt_tokens", 0) or 0,
                     tokens_out=getattr(usage, "completion_tokens", 0) or 0)


    async def _call_ollama(self, provider: P.Provider, model: str, messages: list[dict], tools: list[dict] | None,
                           max_tokens: int | None) -> Reply:
        """A local model through Ollama's own API (see models/local.py for why not the OpenAI-style one)."""
        import httpx

        base = P.base_url_for(provider, self._env)
        info = P.ollama_model_info(base, model)
        text_tools = bool(tools) and ((provider.id, model) in self.text_only or info.get("tools") is False)
        body = local.request(model, messages, tools, max_tokens, info, text_tools, self._env)
        with trace.span(f"{model} (local)", "llm", model=model) as sp:
            try:
                async with httpx.AsyncClient(timeout=local.TIMEOUT) as client:
                    res = await client.post(P.ollama_root(base) + "/api/chat", json=body)
            except httpx.HTTPError as e:
                raise Transient(f"local model didn't answer ({type(e).__name__})") from e
            if res.status_code != 200:
                detail = _ollama_error(res)
                if tools and not text_tools and local.no_tool_support(res.status_code, detail):
                    self.text_only.add((provider.id, model))  # from now on: tools written into its prompt
                    return await self._call_ollama(provider, model, messages, tools, max_tokens)
                if res.status_code == 404:
                    raise ModelGone()
                raise Transient(f"local model: {detail[:140]}")
            data = res.json()
            msg = data.get("message") or {}
            text = local.strip_think(msg.get("content") or "")
            calls = [ToolCall(f"call_{i}", c["function"]["name"], local._args(c["function"].get("arguments")))
                     for i, c in enumerate(msg.get("tool_calls") or []) if (c.get("function") or {}).get("name")]
            calls, text = _settle(calls, text, tools)
            if not text and not calls:
                raise Transient("empty reply")
            sp.set("output.value", text or json.dumps([[c.name, c.args] for c in calls]))
        return Reply(text=text, tool_calls=calls, provider=provider.id, model=model,
                     tokens_in=data.get("prompt_eval_count") or 0, tokens_out=data.get("eval_count") or 0)


def _settle(calls: list[ToolCall], text: str, tools: list[dict] | None) -> tuple[list[ToolCall], str]:
    """The tool calls a reply really makes: native ones, else ones written as text (JSON or code-style), with
    arguments a model wrapped one level too deep unwrapped."""
    if not tools:
        return calls, text
    if not calls and text:  # the model wrote its tool calls as text: run them anyway
        found, text = textcalls.extract(text, [t["function"]["name"] for t in tools])
        if not found:
            found, text = textcalls.extract_python(text, tools)
        calls = [ToolCall(f"text_call_{i}", name, args) for i, (name, args) in enumerate(found)]
    fixed = textcalls.tidy([(c.name, c.args) for c in calls], tools)
    return [ToolCall(c.id, name, args) for c, (name, args) in zip(calls, fixed)], text


def _ollama_error(res: Any) -> str:
    try:
        return str(res.json().get("error") or res.text)
    except Exception:
        return res.text or f"HTTP {res.status_code}"


def _failed_tool_call(err: Exception) -> str | None:
    """The text of a tool call the provider couldn't parse (Groq: code tool_use_failed), or None."""
    body = getattr(err, "body", None)
    detail = body.get("error", body) if isinstance(body, dict) else {}
    code = (detail.get("code") if isinstance(detail, dict) else None) or getattr(err, "code", None)
    if code != "tool_use_failed":
        return None
    failed = detail.get("failed_generation") if isinstance(detail, dict) else None
    return failed if isinstance(failed, str) else ""


def _parse_args(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _retry_after(err: Exception) -> float | None:
    headers = getattr(getattr(err, "response", None), "headers", None) or {}
    value = headers.get("retry-after") if hasattr(headers, "get") else None
    try:
        return float(value) if value else None
    except ValueError:
        return None


def _is_daily(err: Exception) -> bool:
    return bool(re.search(r"per.?day|daily|quota", str(err), re.IGNORECASE))


def _short(err: Exception) -> str:
    return str(err).splitlines()[0][:160]
