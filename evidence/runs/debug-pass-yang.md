# Live debug pass, Yang's laptop (Sun 11 Oct 2026)

Answers HANDOFF.md section 5. Server: `python -m teamloop` from a fresh clone at `C:\Users\BCE\dev\teamloop`
(E: drive was full). Model: Groq free tier (`llama-3.3-70b-versatile`), no paid model used.
Each run was driven over the HTTP API (`POST /api/chats/{id}/messages`, events read from `/api/events/poll`),
with approval cards answered through `POST /api/approvals/{id}`; full timelines are in `debug-pass-logs/`.

Baseline at 25f316d: pytest 188 passed, 1 skipped; `python -m evals.run` 7/7 (`evidence/evals/`).

## Results

| # | Feature | Result | Evidence (timeline in the log) |
|---|---|---|---|
| 1 | Fast path "battery?" | WORKS | kind=fast, 0 model calls, 3.8 s (system_status) |
| 2 | Fast path "volume 30/50/44" | WORKS, flaky once | 0 model calls, 0.5 s. First call after server start read back 44% while the real level was 30; 0 wrong readbacks in the 13 tries after |
| 3 | "brightness?" / "wifi?" | WORKS, not instant | not in fastpath.py, so S hands to Desk (4 model calls, 9 s). Sourabh adding both to the fast path |
| 4 | @mention in team ("@Scout capital of Japan") | WORKS | only Scout answered, web_search, 2 calls |
| 5 | "ask Writer to save a note" | WORKS | S delegate → Writer write_file → S report, 1.6 s |
| 6 | Worker "Not mine" in a DM | FAILS | dm-scout "open notepad" → "Not mine: Operator" (no such bot). Root cause: workers get no roster in their prompt (crew/bots.py). Backend, sent to Sourabh |
| 7 | Approval deny | WORKS | card → deny → "The person said no, so I didn't run it" |
| 8 | "Already said no" | WORKS on an identical retry, FAILS on a rephrase | same command text is blocked; the same request again made a slightly different command and asked again. Backend, sent |
| 9 | Reply after a deny | FAILS (wording) | starts with "Failed:" so the UI paints it red. Backend prompt, sent |
| 10 | Terminal: cd sticks, exit code | WORKS | second command ran in C:\Users; exit code 7 read back |
| 11 | Web fetch_page | WORKS | example.com heading read |
| 12 | Scout search with links | WORKS | 2 sources with URLs |
| 13 | Memory "remember X" / recall | WORKS | 0 model calls to store; recall tool found it |
| 14 | Routine "in 1 minute" | WORKS | set 13:07:48, fired as kind=routine at ~13:09:03 |
| 15 | Stop button mid-handoff | WORKS | demo goal, Stop at +11.7 s while Scout was fetching → "Stopped." at +12.3 s |
| 16 | Typed "stop" mid-handoff | WORKS | "stop" at +18.8 s → "Stopped." at +19.3 s |

(More rows follow as each batch finishes.)
