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
