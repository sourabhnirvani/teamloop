# Before/after: one bot vs the crew (jrkrishh, Mon 12 Oct ~08:00 IST)

- **Free model only:** Groq's free tier (`TEAMLOOP_CHAIN=groq`).
- **No neatlogs links yet:** there's no neatlogs key on this machine.
- **Script:** `evidence/runs/before-after-yang.py`. It wraps `scripts/compare.py`'s `run_once`: a fresh database per
  run, approval cards answered yes, plus every tool call recorded.
- **How success is judged:** from what the tools did, not from the bot's reply. All four parts must have happened:
  research ran, a report was saved **with source links**, the report was opened, and a weekly routine was set.

## The demo goal (multi-skill)
"Research the top 3 free LLM APIs for students, write a short report on the Desktop, open it, and remind me about it
every Monday."

### Fair run: Groq's models as Groq serves them today (`GROQ_MODELS=openai/gpt-oss-120b,qwen/qwen3.8-27b,openai/gpt-oss-20b`)
| Run | Mode | Result | Seconds | Model requests | Tokens | Tool steps (failed) | What was missing |
|---|---|---|---|---|---|---|---|
| 1 | one bot | **INCOMPLETE** | 32.5 | 9 | 59,883 | 10 (0) | the report had **no source links**; **no routine** |
| 1 | crew | **SUCCESS** | 40.8 | 25 | 64,369 | 19 (0) | none |
| 2 | one bot | **INCOMPLETE** | 40.8 | 9 | 74,079 | 10 (1) | **never opened** the report ("I have not opened it"); **no routine** |
| 2 | crew | **SUCCESS** | 14.4 | 14 | 29,259 | 10 (0) | none |

**Straight reading:** on the multi-skill goal the crew finished **2/2**, and one bot finished **0/2**.
- **Missed by one bot:** both times, the reminder; once, opening the report; once, the links.
- **Cost:** the crew was the same or cheaper in tokens (64k vs 60k, then 29k vs 74k) and in time (41 s vs 33 s, then 14 s vs 41 s).
- **Why:** S alone with every tool loses track of a 4-part request. The crew's lead hands one clear step to each
  teammate and checks every part before reporting.

Tool steps, as recorded:
- **Crew run 2:** `scout:web_search → scout:fetch_page ×2 → s:delegate → writer:write_file → s:delegate →
  desk:open_file → desk:screen_read → s:delegate → s:schedule_routine`
- **One bot run 2:** `s:web_search → s:fetch_page → s:browser_open → s:browser_read → s:web_search ×4 →
  s:write_file (FAILED) → s:write_file`, then it stopped.

Reports the runs produced: `evidence/runs/demo-reports-yang/fair-rerun/` (moved off the Desktop).

### First attempt, with the stale Groq model list (kept for honesty: `before-after-stale-groq-models-yang.*`)
Our config lists `llama-3.3-70b-versatile` and `llama-3.1-8b-instant`. **Groq has retired both** (404; its
`/models` list no longer has them), so Groq had only `gpt-oss-120b` left. With every tool in one prompt it returned a
broken tool call, 4 times out of 4. One bot: **0/4** ("No model answered"); the crew: **2/2** (108 s / 209k tokens,
32 s / 63k tokens). That comparison is confounded by the dead models, so the fair run above is the one to quote.

## A simple 2-step goal, for contrast (`before-after-simple-goal-yang.json`)
"Check my battery and Wi-Fi, then save a one-line status to workspace/status.txt"

| Mode | Seconds | Requests | Tokens | Tool calls (failed) |
|---|---|---|---|---|
| one bot | 4.1 | 3 | 8,401 | 2 (0) |
| crew | 14.0 | 14 | 24,560 | 10 (1) |

Here one bot is the better choice: 3.4x faster and 2.9x cheaper, and both finished. **The crew pays off when a job has
several parts that need different skills, and costs extra when it doesn't.**

## Bugs found on the way (sent to Sourabh)
- **Stale Groq models:** `providers.py` lists the retired Llamas. Suggested list:
  `openai/gpt-oss-120b, qwen/qwen3.8-27b, openai/gpt-oss-20b`.
- **press_keys "page down" crash:** `uia.keys_to_sendkeys` produced `{PAGE}` / `{PGDOWN}`, which pywinauto rejects.
