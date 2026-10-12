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

### Fair run A: Groq's real models through an override (`GROQ_MODELS=openai/gpt-oss-120b,qwen/qwen3.8-27b,openai/gpt-oss-20b`; data in `before-after-override-yang.*`)
| Run | Mode | Result | Seconds | Model requests | Tokens | Tool steps (failed) | What was missing |
|---|---|---|---|---|---|---|---|
| 1 | one bot | **INCOMPLETE** | 32.5 | 9 | 59,883 | 10 (0) | the report had **no source links**; **no routine** |
| 1 | crew | **SUCCESS** | 40.8 | 25 | 64,369 | 19 (0) | none |
| 2 | one bot | **INCOMPLETE** | 40.8 | 9 | 74,079 | 10 (1) | **never opened** the report ("I have not opened it"); **no routine** |
| 2 | crew | **SUCCESS** | 14.4 | 14 | 29,259 | 10 (0) | none |

**Straight reading (run A):** on the multi-skill goal the crew finished **2/2**, and one bot finished **0/2**.
- **Missed by one bot:** both times, the reminder; once, opening the report; once, the links.
- **Cost:** the crew was the same or cheaper in tokens (64k vs 60k, then 29k vs 74k) and in time (41 s vs 33 s, then 14 s vs 41 s).
- **Why:** S alone with every tool loses track of a 4-part request. The crew's lead hands one clear step to each
  teammate and checks every part before reporting.

Tool steps, as recorded:
- **Crew run 2:** `scout:web_search → scout:fetch_page ×2 → s:delegate → writer:write_file → s:delegate →
  desk:open_file → desk:screen_read → s:delegate → s:schedule_routine`
- **One bot run 2:** `s:web_search → s:fetch_page → s:browser_open → s:browser_read → s:web_search ×4 →
  s:write_file (FAILED) → s:write_file`, then it stopped.

Reports the runs produced: `evidence/runs/demo-reports-yang/fair-rerun/` and `.../fixed-defaults/` (moved off the Desktop).

### Fair run B: the same models as the built-in default (after a5f28f1), with tokens per bot (`before-after-yang.json`)
| Run | Mode | Result | Seconds | Requests | Tokens | Tool steps (failed) | Tokens by bot | What was missing |
|---|---|---|---|---|---|---|---|---|
| 1 | one bot | **INCOMPLETE** | 33.1 | 8 | 32,432 | 6 (1) | S 32,432 | **no research**, **no routine** |
| 1 | crew | **SUCCESS** | 81.5 | 39 | 135,254 | 32 (0) | **Scout 109,123** · S 18,702 · Desk 4,296 · Writer 3,133 | none |
| 2 | one bot | **INCOMPLETE** | 36.3 | 10 | 99,004 | 15 (7) | S 99,004 | the report had **no links**; **no routine** |
| 2 | crew | **SUCCESS** | 18.2 | 13 | 26,387 | 10 (0) | S 9,963 · Scout 7,381 · Desk 6,471 · Writer 2,572 | none |

**Across both fair runs: the crew finished 4/4, one bot 0/4.** One bot never set the Monday reminder in any of the 4 runs.

**Where the tokens go:** crew run 1's 135k tokens were **81% Scout's research**: 20 `web_search` calls and 4
`fetch_page` calls in one turn, with every result and page fed back to the model. Crew run 2 did the same job with
3 Scout calls and 7k Scout tokens. The heavy crew runs (the 209k in the stale-model attempt, 135k here) are Scout
over-searching. That's fixable with a cap on searches per turn: the repeat guard only stops *identical* calls.
For free tiers that cap is the biggest single saving.

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

## Capping Scout's research: tried, measured, half kept (Mon ~08:30 IST, crew only, 3 runs each, Groq defaults)
| Variant | Complete | Tokens per run | What happened |
|---|---|---|---|
| No cap (fair runs A and B above) | 4/4 | 64k, 29k, 135k, 26k | one run had 20 Scout searches in a single turn |
| **Per turn:** 5 `web_search` + 3 `fetch_page` per Scout turn (5d31719) | **3/3** | 151k, 61k, 60k | S sent Scout back up to 3 times, so 15 searches + 9 reads in run 1 |
| Per job: the same caps across all Scout turns (db29278) | **1/3** | 138k, 24k, 158k | blocked Scout, so S rerouted the research to **Web** (browser tools: 40k and 76k tokens), and two runs ran out of steps before the reminder and the open |

**Straight reading:**
- **Per job made things worse.** It moved the research to a more expensive bot and lowered success, so it's
  **reverted**.
- **Per turn stays.** It stops a single runaway turn and kept success at 3/3.
- **No variant clearly cut tokens.** With 3 runs each, the noise between runs (24k-158k for the same goal) is larger
  than any cap effect.
- **The real lever is upstream.** S re-delegating research it already has costs more than any one turn. A better fix
  is S checking what it has before asking again; not attempted before the freeze.

Data: `before-after-capped-per-turn-yang.*`, `before-after-capped-per-job-yang.*`; reports in
`demo-reports-yang/capped/` and `capped-per-job/`.
