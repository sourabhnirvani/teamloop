# Video voice-over, word for word (Yang records, Mon 12 Oct, from 14:30 IST)

This is for `evidence/video-script.md`: the same blocks and times, with the exact words to say. About 410 words, which is
2:50 at a calm pace. Every number comes from a file in `evidence/` (the source is in brackets; don't read those out).

## Before the first take (5 minutes)
1. `git checkout demo`, then start the desktop app (`desktop/`, `npx electron .`). The model chain is free Groq, and
   neatlogs tracing is on (the key is in `.env`).
2. Delete any earlier "Free LLM APIs for Students" report from the Desktop, and check that Routines is empty, so the run
   starts clean.
3. **Fresh chat for every take** (Team chat → new chat), so history from earlier takes can't leak in.
4. Open these tabs ahead of time, so the cut-aways are one click away:
   - the neatlogs trace of the demo run (workflow `teamloop-compare` and today's app run)
   - `evidence/runs/before-after-yang.md`, the crew vs one bot table
   - `evidence/runs/evals-local-sourabh.md`, the before/after "Not done" pair
   - a terminal showing `entire checkpoint list` and `git log -1` with an `Entire-Checkpoint:` trailer
   - `evidence/cfo/teamloop-plan.md`, the scenario table
5. Record at 1080p (OBS, or Win+Alt+R with the Xbox Game Bar). Mic test first.

---

## 0:00–0:12 · Hook (Crew Room, six bots idle)
> This is TeamLoop: a crew of AI bots that work on your laptop together, on free models, and always ask before they act
> as you.

## 0:12–1:05 · The agent, live (Team chat)
Type: *Research the top 3 free LLM APIs for students, write a short report on the Desktop, open it, and remind me about
it every Monday.*

> I'll give the crew one real job: research, write a report, open it, and remind me every Monday.
>
> S, the lead, splits it into steps and hands them out. Scout researches, and it's capped, so one search spree can't burn
> the budget. Writer saves the report.
>
> Now Desk wants to open the file. That acts as me, so it asks first. The red ring shows exactly where the mouse will
> click. I approve, and the report opens.
>
> Last, S sets a Monday 9 AM routine. Four parts, four done, each confirmed by a real tool call, on a free model.
>
> And if I touch my mouse, the crew waits. Control-Alt-Q stops everything.

[the 10:10 traced run: 4/4, 45.8 s, 18 requests, 54.8k tokens; final-pass-yang.md for the card and the routine]

## 1:05–1:45 · neatlogs (trace tab, then the before/after pair, then the table)
> Every bot turn is an agent span in neatlogs, and every tool call a tool span. Keys are stripped before anything leaves
> the laptop.
>
> The traces found our real bugs. Here a 7B local model said "saved the file". The trace shows no tool span, and there's
> no file. So now a step with no tool behind it ends with an honest "Not done". It never fakes a success.
>
> Traces also tested the design: on this goal the crew finished four out of four; one bot with every tool, zero out of
> four. For a simple two-step job one bot is cheaper, and we say so.

Optional extra line while the demo trace is on screen (if time allows):
> Even this run had two model errors inside Scout's turn; the crew retried and still finished all four parts.

[evals-local-sourabh.md; before-after-yang.md; the demo trace a3176a29… in neatlogs: 39 spans, 2 errored model calls,
4/4 done]

## 1:45–2:15 · Entire (terminal: `entire checkpoint list`, then a commit trailer)
> Two coding agents built TeamLoop as teammates, over a bridge: plans, reviews and acks. Entire recorded the work: each
> commit carries a checkpoint that links it to the agent session that wrote it. It's our audit trail of who built what,
> and why.

[checkpoints-sourabh*.md, checkpoints-jrkrishh.md; Yang's day-2 commits have no checkpoints, so show day 1 or
Sourabh's day 2]

## 2:15–2:45 · cfo.ai (the plan's scenario table)
> TeamLoop costs zero dollars per user to run: free models with your own keys, and a phone hub on your own free
> Cloudflare account. So we sell convenience: Pro at five dollars a month, and team seats.
>
> Twenty-four months of numbers gave one clear lesson. If both founders take pay from month seven, cash runs out in May
> 2027. Paid only from revenue, it never runs out and turns profitable in August 2027. What decides it is how many users
> go Pro, not model costs.

Say this line only if cfo.ai itself was used (Yang's workspace works without a card):
> We built the plan in cfo.ai from these inputs.

If cfo.ai needed a card, say this instead (honest, and it's in the submission too):
> cfo.ai's trial needed a card, so we ran the same brief through our own model; the inputs are ready for cfo.ai.

[evidence/cfo/teamloop-plan.md: base case runs out 2027-05, about $22.6k to break even in 2028-10; bootstrapped never
runs out, profitable from 2027-08]

## 2:45–3:00 · Close (the Board with the job done, then the evidence folder)
> Everything here is in the repo, with evidence: the traces, the live tests, the security review and the plan. TeamLoop,
> from team Agent S. Hashtag neatHack.

---

## If a take goes wrong
- **The demo goal stalls or S over-researches:** stop (Ctrl+Alt+Q), start a fresh chat, and take it again. It passed 3
  of the last 4 UI runs plus the traced run.
- **The approval card times out:** that's the 2-minute expiry; approve within a minute.
- **Running long:** cut "And if I touch my mouse…" and the one-bot-cheaper line first.
