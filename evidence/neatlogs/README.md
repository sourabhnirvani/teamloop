# The demo goal, traced in neatlogs (Mon 12 Oct, 10:09 IST, from the `demo` tag, free Groq)

The trace lives in the team's private neatlogs org, so judges may not be able to open its link. Everything it shows is
also here:

- `trace-demo-goal.md`: neatlogs' own **Copy Markdown** export of the whole trace, with all 39 spans and their inputs,
  outputs, tokens and timings. Scanned for keys before committing: none (TeamLoop hides keys before export, `teamloop/trace.py`).
- `trace-1-overview.jpg`: workflow `teamloop-compare`, 45.8 s, 39 spans. The `chat message` workflow, S's agent turn,
  `delegate` to Scout, then Scout's web searches and page fetches.
- `trace-2-errors-and-retry.jpg`: **the failure and what the agent did next.** Two model calls inside Scout's turn
  failed with HTTP 400. The model had invented a tool called `web_fetch`, which doesn't exist, and Groq rejected the
  call: "attempted to call tool 'web_fetch' which was not in request.tools". Each time, the next call retried and used
  the real `fetch_page`, and the job went on.
- `trace-3-write-open-routine.jpg`: Writer's `write_file`, Desk's `open_file`, then S's `schedule_routine`. The final
  output names the saved file, says it opened, and gives the Monday 9 am routine id.

Result: all 4 parts done, confirmed by tool spans, in 45.8 s for under $0.01. neatlogs labels the trace "Execution
Failed" only because of those two rejected calls. Link (team org members):
https://app.neatlogs.com/traces/a3176a29065ba2365e5b9ddee70474d6?orgId=11a578e3-ea50-4688-964a-ae04525d0452&projectId=abf5aff5-8fb5-4109-8bc7-34677731b7cc
