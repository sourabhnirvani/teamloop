# Local models (Ollama) end to end, Sun 11 Oct 2026 ~20:50 IST

Laptop: Ollama 0.35.1, `qwen2.5:7b` (Q4_K_M, on the GPU). No cloud keys in the chain (`TEAMLOOP_CHAIN=ollama`). $0, no tokens.

## Found before the fix
| Problem | Evidence |
|---|---|
| Ollama's OpenAI-style endpoint runs at its default 4096 context and **silently cuts a long prompt from the front** | A 6000-token prompt with `SECRET=42` at the start came back as `prompt_tokens=2050`, and the model couldn't say 42. Desk's prompt alone is 1988 tokens, so any longer job lost its rules and tools. `options.num_ctx` is ignored on that endpoint. |
| A model without tool support (gemma, phi, llava, ...) gets a 400 "does not support tools" | That error rested Ollama's one shared "key" for 20 s, so **every** local model was skipped, again and again |
| Small models wrap arguments one level too deep | qwen2.5:7b: `delegate {"bot": {"bot": "desk", "instruction": "battery"}}` |
| Small models write calls like code | qwen2.5:7b with tools in the prompt: `web_search("capital of France", 1)` |
| Thinking models (qwen3, deepseek-r1, gpt-oss) | `<think>` notes in replies; a 5-token doctor check spent on notes |
| Embedding models with no "embed" in the name (bge-m3) | would have been offered as chat models |

## The fix (`teamloop/models/local.py`, router, providers, textcalls)
- Local calls use Ollama's own `/api/chat` with `num_ctx` 16384 (32768 for one oversized prompt; never above the model's
  own limit; `OLLAMA_NUM_CTX` overrides). 5-minute timeout for a first model load.
- Model capabilities from `/api/tags`: no "completion" → not offered; no "tools" → tools written into the prompt and
  read back from `<tool_call>` text; "thinking" → `think: false` (`"low"` for gpt-oss, which can't switch off).
  Older Ollama without capabilities: native tools tried once, then text mode for that model.
- One local model's error no longer benches the others.
- Code-style calls on their own line are read; over-wrapped arguments are unwrapped using the tool's own argument names
  and types (both paths, cloud too).

## Real runs on qwen2.5:7b after the fix
| Check | Result |
|---|---|
| 6000-token prompt, `SECRET=42` at the start | `prompt_tokens=5629`, answer `42`, `ollama ps` CONTEXT 16384 |
| S / Desk / Scout real prompts + tools | `delegate(bot=desk, instruction=…)` · `system_status` · `web_search(capital of France)`, 1.7–2.2 s each |
| Tools-in-prompt mode forced on the real model | `web_search {"query": "capital of France"}`, then answered "Paris" with the link from the result |
| Team: "Ask Scout to look up the capital of Japan on the web and give me the source link" | Scout: `web_search` → answer with a Wikipedia link, 7 s |
| DM Writer: save a note as tokyo-note.txt | `write_file` → file really in Documents (OneDrive\Documents), 4 s. The model wrote one line where two were asked: model quality, not a bug |
| Team: "Find the population of Tokyo on the web, then save it with the source link in a note" | S → Scout (`web_search`) → S → Writer (`write_file`) → S's report; the file holds the figure and the link; 7 model calls, 18 s |

Test files written by these runs were deleted afterwards. pytest: 253 passed, 1 skipped (new: tests/test_local_models.py).

## Not covered
- Only one model is installed here (qwen2.5:7b). Models without tool support, thinking models and older Ollama
  versions are covered by tests that fake Ollama's real error and reply shapes, not by a live run.
- LM Studio, llama.cpp server and other local servers aren't supported; only Ollama is.
- Quality depends on the model: a 7B model follows the crew's rules less tightly than the free cloud models.
