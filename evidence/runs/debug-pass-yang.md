# Live debug pass, Yang's laptop (Sun 11 Oct 2026, 12:55–13:35 IST)

Answers HANDOFF.md section 5. Server: `python -m teamloop` from a fresh clone at `C:\Users\BCE\dev\teamloop`
(the E: drive was full). Batches 1–2 ran on 25f316d, batches 3–4 on ae51590 (Sourabh's retry fix) with
`TEAMLOOP_FAIL_ONCE=write_file`.

Model: every model call went to Groq free tier `openai/gpt-oss-120b` (105 requests, ~186k tokens; `/api/usage`).
Startup model check: `llama-3.3-70b-versatile` returns 404 (model gone), Nebius key rejected (403),
Ollama off until started for row 30. No paid model answered anything.

How it was driven: messages posted with `POST /api/chats/{id}/messages`, events read from
`/api/events/poll`, cards answered with `POST /api/approvals/{id}`. Full timelines in `debug-pass-logs/batch1-4.log`.
Test files, routines and the Notepad window the runs created were removed afterwards.

Baseline: pytest 188 passed, 1 skipped; `python -m evals.run` 7/7; `python -m evals.run --live` **10/10**
(live_writer, live_desk, live_recovery included).

## Results

| # | Feature | Result | Evidence |
|---|---|---|---|
| 1 | Fast path "battery?" | WORKS | kind=fast, 0 model calls, 3.8 s |
| 2 | Fast path "volume 30/50/44" | WORKS, flaky once | 0 model calls, 0.5 s. The first call after server start read back 44% while the real level was 30; 0 wrong readbacks in the next 13 tries |
| 3 | "brightness?" / "wifi?" | WORKS, not instant | not in fastpath.py, so S hands to Desk (4 calls, 9 s). Sourabh adding both |
| 4 | @mention in team | WORKS | "@Scout capital of Japan": only Scout answered |
| 5 | "ask Writer to …" | WORKS | S delegate → Writer write_file → S report in 1.6 s |
| 6 | Worker "Not mine" in a DM | **FAILS** | dm-scout "open notepad" → "Not mine: Operator" (no such bot). Workers get no roster in their prompt (crew/bots.py). Backend |
| 7 | Approval: approve | WORKS | open_app, close_app, Replace-a-file cards approved and acted on |
| 8 | Approval: deny | WORKS | "The person said no, so I didn't run it" |
| 9 | "Already said no" | WORKS on an identical retry, **FAILS** on a rephrase | same request again produced `-ErrorAction SilentlyContinue` instead of `-Force` and a new card. Backend |
| 10 | Reply after a deny | **FAILS** (wording) | starts "Failed: you declined…", so the UI paints it red. Backend prompt |
| 11 | Approval 2-min expiry | WORKS, then **FAILS MID-PROCESS** | expired at 121.6 s ("No one answered the approval card in time"); Desk immediately re-ran the command and raised a second card. An expiry should count like a no. Backend. (The command also held a literal `C:\Users\{username}\…` placeholder) |
| 12 | Card screenshot | WORKS | close_app card carried a screenshot; run_command / write_file cards have none (by design) |
| 13 | Terminal: cd sticks, exit codes | WORKS | second command ran in C:\Users; exit code 7 read back |
| 14 | Notepad: open, type | **FAILS MID-PROCESS**, recovered | open_app OK; type_text failed twice ("Couldn't bring to front", then `[WinError -2147221008] CoInitialize has not been called`); Desk fell back to ui_snapshot + ui_act and typed. Not reproducible outside the server. Backend (computer/tools.py: type_text runs `uia.send_text` via `asyncio.to_thread`, not the COM thread) |
| 15 | "close notepad without saving" | **FAILS** (fast path) | fast path read the app name as "notepad without saving" → "No open window matches". Model path then asked with a card and left Notepad open at its save prompt (correct). Backend |
| 16 | Web fetch_page | WORKS | example.com heading |
| 17 | Browser open / snapshot / click / read | WORKS | clicked "Learn more" → landed on iana.org "Example Domains" |
| 18 | Browser form submit asks, file input refused | NOT TESTED | |
| 19 | Scout search with links | WORKS | 2 sources with URLs |
| 20 | Writer overwrite asks | WORKS | "Replace a file" card → approved → saved |
| 21 | Forced failure recovery (`TEAMLOOP_FAIL_ONCE=write_file`) | WORKS (ae51590) | direct "save a note" to Writer: write_file failed (simulated) → retried → card → saved. Also `evals --live` live_recovery PASS |
| 22 | Demo goal in the team chat, run 1 | **FAILS MID-PROCESS** (one step dropped) | Scout (asked twice for links) → Writer saved the report → Monday routine set → final report in 44 s, 22 calls. **"open it" never happened**: no open_file, no approval card |
| 23 | Demo goal, run 2 | **FAILS MID-PROCESS** (same) | 28 s, 12 calls; again no open_file. S folded "open it" into the routine text ("the file will be opened automatically"). Backend (S plan / prompt on gpt-oss-120b). The earlier Nebius run (demo-goal-nebius.md) did open the file |
| 24 | Stop button mid-handoff | WORKS | Stop at +11.7 s while Scout fetched → "Stopped." at +12.3 s |
| 25 | Typed "stop" mid-handoff | WORKS | "stop" at +18.8 s → "Stopped." at +19.3 s |
| 26 | Memory "remember X" / recall | WORKS | 0 model calls to store; recall found it |
| 27 | Routine fires | WORKS | "in 1 minute" set 13:07:48, fired as kind=routine ~13:09:03 |
| 28 | Routine create weekly + cancel | WORKS | `DELETE /api/routines/{id}` → `[]` |
| 29 | Sleep / wake | WORKS | asleep reply blocked a question with 0 calls; "S wake up" → "Awake and ready." |
| 30 | Model doctor "check models" | WORKS | names the working and dead models (see top) |
| 31 | "use groq", per-bot "use ollama for writer" | WORKS | settings showed `bot_models: {writer: ollama}`, then back to groq |
| 32 | Small model writing tool calls as text | NOT TESTED (couldn't) | qwen3:4b on CPU timed out at ~60 s and the router fell back to Groq (which did the job). Needs a faster small model or a longer local timeout |
| 33 | Save-tokens on / off | WORKS | both replies with 0 calls; one question answered in save mode |
| 34 | Keys hidden | WORKS (offline eval) | secrets_hidden PASS; pasting in chat/Settings by hand not tried |
| 35 | CLI | WORKS | `python -m teamloop.cli "battery?"` → Desk system_status |
| 36 | Long-poll events (`/api/events/poll`) | seen once, not reproduced | during row 32 the client missed step start/done and one usage event that the server's buffer holds; a repeat of the same slow turn delivered 5/5. Yang's (phones.py); watching it |
| 37 | Inbox / email | NOT TESTED | no mail account signed in |
| 38 | Phone over the tunnel, Telegram with a real token | NOT TESTED | needs Yang with phone and bot token |
| 39 | Desktop app tray, crash restart, .vbs/.bat | NOT TESTED | needs Yang at the desktop (and would clash with the test server on 8790) |
| 40 | neatlogs trace with Yang's key | NOT TESTED | no NEATLOGS_API_KEY on this laptop yet; see Sourabh's note: the SDK needs the *Project API key* |

## Whose fix

Backend (Sourabh): 6, 9, 10, 11, 14, 15, 22/23 (most important for the video: "open it" is skipped on gpt-oss-120b), 3.
Yang's side: 36 (watch), 18, 32, 37–40 need hands on the laptop or phone.
