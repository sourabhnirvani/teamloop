# TeamLoop: evidence index for the judges

TeamLoop is a crew of AI bots on your Windows laptop:
- **S** leads.
- **Desk** runs the computer.
- **Web** drives Chrome.
- **Scout** researches.
- **Inbox** handles mail.
- **Writer** writes.

They work in group chats on free models. Anything that acts as you waits for your approval, and every step is traced
in neatlogs.

Team **Agent S** (Sourabh + Yang/JrKrishh). The whole repo was built during the event; commit dates start
**2026-10-10 19:49 IST**.

One line per file: the claim, then where to see it. ⚠ marks items still missing at the time of writing.

## Use of neatlogs, Entire and cfo.ai (25%)
| Claim | Evidence |
|---|---|
| Every bot turn is an AGENT span and every tool call a TOOL span in neatlogs; keys are hidden before they reach neatlogs | `teamloop/trace.py`, `tests/test_trace.py` |
| A traced before/after pair on a local model: run 1 used to say "saved" with no tool behind it, and now ends "Not done: save the file"; run 2 really recovered | `evidence/runs/evals-local-sourabh.md` |
| ⚠ neatlogs trace links/screenshots for the Groq runs | Yang's machine has no neatlogs key yet; re-run `evidence/runs/before-after-yang.py` with one |
| Entire checkpoints link agent sessions to the commits they produced (both laptops) | `evidence/entire/checkpoints-sourabh.md`, `evidence/entire/checkpoints-jrkrishh.md` |
| ⚠ Entire on day 2 | Yang's day-2 work ran in the Claude desktop app, which Entire's Claude Code hook doesn't capture: no checkpoints after 11 Oct 01:51 on that laptop |
| ⚠ cfo.ai business plan (pricing, costs, revenue, runway) | Export from cfo.ai into `evidence/` (Sourabh's account) |

## The agent (30%)
| Claim | Evidence |
|---|---|
| The demo goal end to end: research, a report saved, the report opened (approval card), a Monday reminder | `evidence/runs/demo-goal-nebius.md` (69 s, 15 calls) |
| **Crew vs one bot on the demo goal: the crew finished 4/4, one bot 0/4** (it never set the reminder), at the same or fewer tokens | `evidence/runs/before-after-yang.md` |
| For a simple 2-step job one bot is cheaper (3.4x faster, 2.9x fewer tokens): written down, not hidden | `evidence/runs/before-after-yang.md` |
| **A failed action and what the agent did next:** `write_file` failed (simulated), then failed again for a real reason (a bad path), then Writer fixed the path and saved | `evidence/runs/evals-yang.md` §2 |
| Live evals on a free model: 9/9 with steps, tokens and seconds per run; 3 bugs found and fixed, recovery 36% cheaper after the fix | `evidence/runs/evals-yang.md` |
| A step with no tool behind it never reads as done (an honest "Not done: …" line) | `tests/test_honest_not_done.py`, `evidence/runs/evals-local-sourabh.md` |
| Scout's research capped per job (one turn had made 20 searches, 81% of a 135k-token job) | `evidence/runs/before-after-yang.md`, `tests/test_scout_cap.py` |
| Advanced computer use: click by name (accessibility tree, then Windows OCR), real mouse at exact pixels, checked steps. 8 live tests: Calculator, Notepad Save As, Settings, Explorer, Paint, a canvas-only page via OCR, safety, old tools under DPI | `evidence/runs/computer-use-yang.md`, `evidence/ui/cu-*.png`, design: `computer-use-design-yang.md` |
| Operator safety: the crew pauses while you use the mouse or keyboard; Ctrl+Alt+Q stops everything (live in the desktop app) | `evidence/runs/parity-yang.md` §B, `evidence/runs/operator-live-yang.out.txt`, `evidence/ui/operator-ctrl-alt-q-balloon-crop-yang.png` |
| Approval cards show a red ring where the mouse will click | `evidence/ui/cu-safety-card-ring-yang.png` |
| Key security: tool calls carrying a key are refused, programs get no keys, bots can't open the vault/.env/DB | `evidence/runs/parity-yang.md` §C, `tests/test_security.py` |
| Security review of the phone hub, pairing and approvals: 44 attempts, 7 FAIL, all fixed, re-test 0 FAIL | `evidence/runs/security-review-yang.md` |
| Local models end to end (Ollama), $0 | `evidence/runs/local-models-2026-10-11.md` |
| Fixed phone link on a free Cloudflare Worker, live | `evidence/runs/hub-live-2026-10-11.md` |
| UI audit (13 rows), all fixed and re-checked at 375/1100/1440 | `evidence/runs/ui-audit-yang.md`, `evidence/ui/audit-fix-*.png` |
| Eval results over time | `evidence/evals/*.json` |

## Building in public (15%)
| Claim | Evidence |
|---|---|
| ⚠ #neatHack posts during the event | add the post links here |
| Small commits by both people across the event, with evidence for each piece | `git log`, this folder |
| Two coding agents working as teammates over ccbridge (requests, reviews, acks) | `HANDOFF.md`, `BRIDGE.md` |

## Demo video (20%)
| Claim | Evidence |
|---|---|
| ⚠ ≤ 3 min, covering architecture, implementation, runtime, reasoning and result for each tool | draft script: `evidence/video-script.md` |
