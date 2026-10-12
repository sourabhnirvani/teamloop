# I: Evals for the judges (jrkrishh, Mon 12 Oct ~08:05 IST)

**Free model only:** `TEAMLOOP_CHAIN=groq`, Groq's free tier, on this laptop. Nebius is skipped as paid.

**Tracing is OFF:** `trace.init()` returned False because there is **no `NEATLOGS_API_KEY` on this machine**. So there
are **no neatlogs links yet**. To compensate, every tool call (neatlogs' TOOL spans) was recorded locally around
`registry.run`, in `evals-yang.json`. Once Yang adds a neatlogs key, re-running the same script gives the trace links.

## 1. Live crew tasks, 3 rounds (`evals-yang.py`, `evals-yang.out.txt`, `evals-yang.json`)
These are evals/run.py's own live tasks. Each outcome is checked **on the machine**: the file exists with the right
content, the Notepad window really opened.

| Task | Passed | Avg seconds | Avg model calls | Avg tokens | Avg tool steps |
|---|---|---|---|---|---|
| `live_writer`: "Ask Writer to save a file…" | **3/3** | 1.2 | 2.0 | 1,670 | 1.0 (`write_file`) |
| `live_desk`: "Ask Desk to open Notepad" | **3/3** | 4.1 | 2.0 | 4,031 | 2.0 (`open_app`, `close_app`) |
| `live_recovery`: a save that **fails on purpose** (`TEAMLOOP_FAIL_ONCE=write_file`) | **3/3** | 3.4 | 6.3 | 8,338 | 4.0 |

Per run:

| Round | writer s / calls / tokens | desk s / calls / tokens | recovery s / calls / tokens / steps |
|---|---|---|---|
| 1 | 2.0 / 2 / 1,677 | 4.6 / 2 / 4,027 | 3.7 / 6 / 6,869 / 4 |
| 2 | 0.7 / 2 / 1,691 | 3.7 / 2 / 4,015 | 2.1 / 5 / 5,626 / 3 |
| 3 | 1.0 / 2 / 1,643 | 3.9 / 2 / 4,050 | 4.3 / 8 / 12,518 / 5 |

## 2. A failed action, and what the crew did next (round 1 of `live_recovery`, tool calls in order)
1. `writer write_file` → **FAILED**: "the app didn't respond in time" (the simulated glitch).
2. `writer write_file` → **FAILED** again, for a real reason: S's instruction gave Writer the path
   `$env:USERPROFILE\workspace\evals\…`, and the file tool doesn't expand PowerShell variables (WinError 123).
3. `writer write_file` → OK: Writer fixed the path and saved `workspace\files\evals\recover-….txt`.
4. `s delegate` → "Writer replied: Saved the file…". The outcome check found the file with "recovered" in it.

In rounds 2 and 3 the simulated failure came first, Writer retried once and saved. In round 3, S also had Desk read the
file back to verify it (`desk read_file` → "File exists. Its content is: recovered").

## 3. Before/after: one bot vs the crew (`scripts/compare.py`, Groq; copy in `before-after-yang.json`, Wi-Fi name hidden)
The goal was "Check my battery and Wi-Fi, then save a one-line status to workspace/status.txt".

| Mode | Seconds | Model requests | Tokens | Tool calls (failed) | Bots |
|---|---|---|---|---|---|
| One bot (S alone, all tools) | 4.1 | 3 | 8,401 | 2 (0) | s |
| Crew | 14.0 | 14 | 24,560 | 10 (1) | s, desk, writer |

**Honest reading:** for a simple 2-step job, the crew took **3.4x the time and 2.9x the tokens** of one bot, and both
finished. The crew's value is in jobs that need different skills and approvals. This goal doesn't show it, and the
write-up shouldn't claim it does.

## Bugs these runs found (for Sourabh)
1. **The recovery eval passes without a failure.**
   - **What happens:** `TEAMLOOP_FAIL_ONCE` fails a tool once per *process* (`registry._failed_once`). A second
     `live_recovery` in the same process never fails, yet `evals/run.py` still reports "write_file failed once
     (simulated) and the crew retried".
   - **Seen:** my first two runs showed this in rounds 2 and 3.
   - **My script's fix:** it clears `_failed_once` before each run and marks a run FAIL if no failure happened.
   - **Suggested fix for `evals/run.py`:** do the same.
2. **The crew reports wrong file locations.**
   - Writer told the person the file was at `C:\Users\BCE\workspace\evals\…`, and the crew said
     `…\teamloop\workspace\status.txt`. Both times the real file is under `…\teamloop\workspace\files\…`.
   - The model guesses the full path from "workspace/…".
   - **Suggested fix:** have the write_file/read_file result say the real full path, and have S's and Writer's replies
     quote the tool's path, not a guess.
3. **PowerShell variables in file paths.**
   - S hands Writer `$env:USERPROFILE\…`, because Desk's "use real paths" hint leaks into S's instructions. The file
     tool takes it literally and fails.
   - **Suggested fix:** `files.resolve` expands `$env:NAME` / `%NAME%`, or S's persona says file paths start with
     Desktop/Documents/Downloads/workspace.

## Still needed from Yang
- **A neatlogs key, for trace links:** add `NEATLOGS_API_KEY` in Settings > API keys, or in `.env`. Then run
  `set TEAMLOOP_CHAIN=groq && .venv\Scripts\python.exe evidence\runs\evals-yang.py` once.
- **Keys for the other providers:** Gemini and NVIDIA free keys, if the "×3 per provider" table is wanted. Only Groq
  has a key here.

## After fixing those 3 bugs (same script, same free model, ~08:15 IST)
Sourabh OK'd edits to his files. The fixes:
- `evals/run.py`'s recovery task really fails first, and asserts that it did.
- `files.resolve` expands `$env:X` and `%X%`, then runs the same folder checks.
- RULES says "tell the person the exact path the tool returned".
- The lead sees only each teammate's first persona sentence, so Desk's `$env:USERPROFILE` note no longer reaches S.

Tests: `tests/test_eval_and_path_fixes.py` (4).

| Task | Passed | Avg seconds | Avg calls | Avg tokens | Avg steps |
|---|---|---|---|---|---|
| live_writer | 3/3 | 1.1 | 2.0 | 1,712 | 1.0 |
| live_desk | 3/3 | 4.7 | 2.0 | 4,132 | 2.0 |
| live_recovery | 3/3 | 2.3 | 5.0 | **5,310** (was 8,338) | 3.0 (was 4.0) |

- **Paths:** every Writer and S reply now quotes the real path (`…\teamloop\workspace\files\evals\…`).
- **No `$env:`:** none of the 9 runs' messages contain `$env:`.
- **Cheaper recovery:** it costs 36% fewer tokens, because no turn is spent on a bad path.

Raw data: `evals-yang-before-fixes.json`, `evals-yang-after-fixes.json`.
