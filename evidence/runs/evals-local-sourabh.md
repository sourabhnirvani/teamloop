# Evals on the local model with neatlogs tracing (Sourabh's laptop, Mon 12 Oct 2026, 07:51 IST)

Model: qwen2.5:7b through Ollama (local, no cloud keys, $0). Tracing: neatlogs on (Sourabh's own project key from
the vault; the SDK started and shut down cleanly). Each eval task is its own neatlogs session, named after its chat:
`eval-live_writer-1791771661` and `eval-live_recovery-1791771666`.

Command: `TEAMLOOP_CHAIN=ollama python -m evals.run --only live_writer live_recovery` (the Notepad one was skipped,
since it opens windows on the person's screen).

| Task | Result | What happened |
|---|---|---|
| live_writer | PASS, 5.4 s | S handed the job to Writer, and the file really exists with the right text |
| live_recovery (write_file fails once on purpose) | **FAIL**, 4.3 s | S replied "Got it, saved the file workspace/evals/recover-1791771666.txt", but it **never delegated or called a tool**, and no file exists |

## The failed action, and what we do about it
- The coverage check did fire: "save … file" in the request with no `write_file` used, so S was sent back once.
- The 7B model ignored that one nudge and claimed the save again, and the fabricated reply reached the person.
- On Groq's free model the same eval passes 3/3 (`evidence/runs/evals-yang.md`), so this is a small-model failure. The
  crew still has to stay honest with any model.
- Fix, assigned to jrkrishh: after the single nudge, if a requested step still has no tool behind it, the runner
  itself adds "Not done: save the file (no tool ran for it)". The same traced eval is re-run here afterwards: that's
  the "after" half of a neatlogs before/after pair.

## After the fix (24ad856), same eval, same model, tracing on (08:11 IST)
neatlogs sessions `eval-live_recovery-1791772849` and `eval-live_recovery-1791772873`.

| Run | Result | What happened |
|---|---|---|
| 1 | FAIL, honestly | S wrote its hand-off as text (`.delegate("desk", ...)`), so nothing ran. The reply now ends with the runner's line **"Not done: save the file (no tool ran for it). Say "try again" and I'll do it."** Before the fix it said "saved". |
| 2 | **PASS** | S handed it to Desk; write_file failed (simulated); Desk said "Failed: ... didn't respond in time"; S retried; the file exists with the right text |

**Before → after: a fabricated "saved" became an honest "Not done".** That's the neatlogs before/after pair: session
`eval-live_recovery-1791771666` (before) against `eval-live_recovery-1791772849` (after).

## Two more small-model problems this run showed (both assigned to jrkrishh)
1. **The call wasn't read:** `.delegate("desk", ...)` with a leading dot. Code-style calls are read only when they start
   with the tool name, so this one, or a `functions.delegate(...)` prefix, was missed.
2. **The request was stored as a memory:** in the "before" run S called `remember` with the request itself ("Save a file
   at …recover-1791771666.txt …"). Every later prompt carried it as something "the person asked the crew to remember",
   so run 2's S offered to save that old file again. Memory must hold facts the person asked to keep, not to-dos.

## After 77de6fc (dotted calls read; requests not stored as memories), 08:28 IST
The eval database still held 3 "memories" the 7B model had stored from requests before the fix; they were removed first.

| Run | Result | What happened |
|---|---|---|
| 1 | FAIL, honest | "Failed: No model answered: Local (Ollama) qwen2.5:7b: empty reply". The local model returned an empty message, and with one local model installed there was nothing to fall back to. Assigned: retry an empty local reply once before giving up |
| 2 | **PASS** | write_file failed (simulated), the crew retried, and the file exists |

## After 71cba18 (an empty local reply gets one more try), 3 rounds, 08:45 IST
| Task | Result |
|---|---|
| live_writer | **3/3 PASS** |
| live_recovery | **1/3 PASS**; the 2 failures were honest: "Failed: The write_file attempt timed out. Let's try again." and "Failed: The file path is outside the allowed locations…" |

**No fabricated success in any of the 6 runs** (before the fixes: "saved the file" with no file). The 7B model sometimes
gives up after the simulated failure instead of retrying. That's a capability limit of a small local model (Groq's free
model passes it 3/3), and it now reports the failure truthfully.
