# TeamLoop: 3-minute demo video, draft script (jrkrishh, Mon 12 Oct)

The rules ask, for **each** tool (neatlogs, Entire, cfo.ai): architecture, implementation, runtime, reasoning, result.
Times are targets. Each block lists the screen, then the voice-over.
- **Record from:** the `demo` tag.
- **Model:** Groq's free tier.
- **Tracing:** neatlogs on.

## 0:00-0:12 Hook
- **Screen:** the Crew Room, six bots idling.
- **Voice:** "This is TeamLoop: a crew of AI bots that work on your laptop together, on free models, and ask before
  they act as you."

## 0:12-1:05 The agent: the demo goal, live
- **Screen:** the Team chat. Type: *"Research the top 3 free LLM APIs for students, write a short report on the
  Desktop, open it, and remind me about it every Monday."*
- **Show, in this order:**
  1. S's plan and the hand-offs (S → Scout → Writer → Desk).
  2. The approval card with the **red ring** on the spot Desk will click; press Approve.
  3. The report opens.
  4. The routine is set.
- **Voice:**
  - "S splits the job. Scout researches, capped so it can't burn tokens."
  - "Writer saves, and Desk opens the file, but only after I approve; the ring shows exactly where it will click."
  - "If I move my mouse, the crew waits; Ctrl+Alt+Q stops everything."

## 1:05-1:45 neatlogs
- **Screen:** the neatlogs trace of that run: workflow, then one AGENT span per bot turn, then TOOL spans.
- **Architecture:** each bot turn is an AGENT span and each tool call a TOOL span. Keys are hidden before anything
  leaves the laptop (`teamloop/trace.py`).
- **Runtime:** open the recovery trace: `write_file` failed, then retried, then saved.
- **Reasoning:** "The trace is how we found real bugs." Examples:
  - a 7B model said "saved" with no tool call, and now gets an honest "Not done" line
  - Scout once made 20 searches in one job
- **Result:** the before/after table, crew **4/4** vs one bot **0/4** on this goal, with steps, tokens and seconds.
  Be honest about the simple-goal case too: one bot is cheaper there.

## 1:45-2:15 Entire
- **Screen:** `entire checkpoint list` on both laptops, and one commit's `Entire-Checkpoint:` trailer.
- **Architecture / implementation:** both coding agents (Sourabh's and Yang's Claude Code) ran with Entire enabled.
  Every commit links back to the agent session that wrote it.
- **Runtime / reasoning:** two agents built this as teammates over a bridge: plans, reviews and acks. Entire is the
  audit trail of who built what and why.
- **Result:** checkpoints on both laptops, plus commit dates inside the event window.
- ⚠ **Gap:** Yang's day-2 commits came from the desktop app and have no checkpoints. Show day 1, or record day-2
  work from the CLI.

## 2:15-2:45 cfo.ai
- **Screen:** the cfo.ai plan: pricing, costs, revenue, runway.
- **Architecture / reasoning:** TeamLoop costs **$0 to run** (free tiers plus local models), so the business is in
  paid convenience: a hosted phone hub, more parallel bots, team plans.
- **Result:** the runway number from the plan. ⚠ The plan export still has to land in `evidence/`.

## 2:45-3:00 Close
- **Screen:** the Board with the job done; the evidence folder.
- **Voice:** "Everything here is in the repo with evidence: the traces, the live tests and the security review.
  TeamLoop, team Agent S, #neatHack."

## Shots to grab before recording (all exist except the ⚠ ones)
- The red-ring card: `evidence/ui/cu-safety-card-ring-yang.png`, or live.
- The before/after table: `evidence/runs/before-after-yang.md`.
- Ctrl+Alt+Q balloon: `evidence/ui/operator-ctrl-alt-q-balloon-crop-yang.png`.
- ⚠ The neatlogs trace of the demo run.
- ⚠ The cfo.ai plan.
- ⚠ The #neatHack posts.
