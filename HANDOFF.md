# @JrKrishh (Yang): start here

We're rebuilding **Agent S** (same features) as **TeamLoop**, with all new code written during the
event. Sourabh builds the backend core. You build the **UI, Telegram, phone and desktop app**
(Sourabh took the browser kit). The full plan is in [PLAN.md](PLAN.md), and your agent's rules are in [CLAUDE.md](CLAUDE.md).
You've seen the old Agent S, so build the same things, but **write new code**. Don't copy old
files or show them to your coding agent.

## 1. Setup (about 20 min)

1. Accept the invite: https://github.com/sourabhnirvani/teamloop/invitations
2. Clone and install:
   ```
   git clone https://github.com/sourabhnirvani/teamloop
   cd teamloop
   python -m venv .venv
   .venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
   pip install -r requirements.txt
   git config core.hooksPath .githooks
   ```
3. Copy `.env.example` to `.env` and add your own free keys (Gemini/Groq/OpenRouter). Sourabh sends
   the neatlogs key privately. Never commit `.env`.
4. **Entire:** install it (Windows: `irm https://entire.io/install.ps1 | iex`), then `entire enable`
   inside `teamloop/`.
5. **ccbridge** (lets your Claude Code talk to Sourabh's):
   ```
   git clone https://github.com/sourabhnirvani/ccbridge ../ccbridge
   pip install -r ../ccbridge/requirements.txt
   python ../ccbridge/bridge.py join <INVITE FROM SOURABH> jrkrishh --allow sourabh
   ```
   Run it **from inside `teamloop/`**. Then restart Claude Code in `teamloop/`, approve `ccbridge`,
   and ask: *"check the bridge, who's online?"* If it can't connect, set your DNS to 1.1.1.1.

## 2. Your checkpoints

| When (IST) | Build | Check |
|---|---|---|
| Sat 21:00–02:00 | `ui/` React + Vite: chat list, chat view, live SSE events, approval card, typing dots. Use the API in PLAN.md §4 (mock it until Sourabh's server lands) | you chat with S in the browser |
| Sun 09:00–14:00 | UI Settings: keys, models, usage, routines; polish (the browser kit is done by Sourabh) | Settings work from the UI |
| Sun 14:00–20:00 | `teamloop/server/telegram.py` bridge; `phone/` PWA (manifest, service worker) over a tunnel; bot avatars with moves | the demo goal works from the phone |
| Sun 20:00–24:00 | `desktop/` Electron wrapper (starts the server, opens the UI) | double-click opens the app |
| Mon 09:00–13:00 | README "Start here", `hackathon.md`, screenshots in `evidence/` | evidence complete |
| Mon 13:00–18:00 | edit the video (≤ 3 min) | uploaded |

## 3. Paste this into your Claude Code (inside `teamloop/`)

> Read CLAUDE.md, PLAN.md and HANDOFF.md. You are JrKrishh's (Yang's) agent. You own `ui/`,
> `teamloop/server/telegram.py`, `phone/` and `desktop/`. Check ccbridge
> messages first and say hi to Sourabh's agent. Then build the Sat 21:00–02:00 checkpoint: a
> React + Vite app in `ui/` with a chat list, chat view, live updates from `GET /api/events` (SSE),
> approval cards and typing dots, using exactly the API in PLAN.md §4 (mock it until the server is
> up). Write all code fresh. Commit and push small steps. When it works, tell Sourabh's agent on
> ccbridge.

## 4. Sun 11 Oct handoff from Sourabh (ccbridge relay is down, so this comes through the repo)

Sourabh asked his agent to hand these to your side. The no-money rule still holds: free tiers only,
never let anything charge a card. If something would cost money, stop and say so.

1. **Video run with a neatlogs trace.** We don't share keys, so Yang gets his **own free neatlogs
   key** (neatlogs dashboard / hackathon Discord), puts it in his own `.env` (`NEATLOGS_API_KEY`),
   and records the final demo-goal run on his laptop. Check the trace view shows
   chat message → S turn → handoffs → tool spans → LLM calls. For Entire, show
   `entire checkpoint list` and a commit's `Entire-Checkpoint:` trailer, never an `explain` that
   hasn't been read through first.
2. **cfo.ai business plan** (required by the rules; PLAN.md §7). Yang signs up at
   https://cfo.ai/neathacks. If it asks for a card: use the trial, export the plan, then **cancel
   right away**, before anything can charge. Paste the brief below into Ari, adjust the numbers
   with Yang, and export the plan (pricing, costs, revenue, runway) to `evidence/cfo/`.
3. **#neatHack posts** (15% of the score). Post from Yang's X account during the event, tag
   **#neatHack** and **@neatlogs**, attach a screenshot or clip, and save the links in
   `evidence/posts.md`. Drafts are below; Sourabh will send his X handle to tag.

Still Sourabh's own: registering on Luma under the team name **"Agent S"**, and his X handle.

### cfo.ai brief (draft: every number is a placeholder)

> Build a 24-month business plan for **TeamLoop**, starting November 2026, monthly, in USD (and INR).
> **What it is:** a crew of AI bots that runs your Windows laptop. You chat with a lead bot, S, from
> the desktop app, a phone or Telegram; specialist bots open apps, change settings, drive their own
> Chrome, research and write files, and each one asks before anything risky. It runs locally on free
> AI models, so inference costs almost nothing.
> **Customers:** students, freelancers and small-business owners on Windows; India first, then global.
> **Pricing:** Free (all six bots, local, the person's own free keys) · Pro $5/month (Rs 299: phone
> access when away, unlimited routines, priority fixes) · Team $12/user/month from month 9.
> **Costs:** inference $0 on Free; hosting about $0.20 per Pro user a month + $50 base; payment fees 3%;
> tools and marketing $100/month for 6 months, then $400; 2 founders unpaid for 6 months, then
> $1,200/month each.
> **Growth:** 300 free users in month 1, +25%/month for 12 months, then +10%; 3% go Pro; 4% of Pro
> cancel each month; Team starts month 9 with 2 offices of 5 seats, +2 offices a month.
> **Cash:** $3,000 of savings, no outside funding.
> Show monthly revenue, costs, profit/loss, cash, runway and the break-even month, plus a pessimistic
> scenario (1.5% go Pro, +15% growth) and an optimistic one (5% go Pro, +35% growth).

### #neatHack post drafts (edit freely; add a screenshot or clip to each)

1. *Kickoff:* "Day 1 of #neatHack: we're building TeamLoop, a crew of AI bots that runs your Windows
   laptop. Chat with the lead bot, S; it hands steps to Desk (apps, settings, terminal), Web (its own
   Chrome), Scout (research) and Writer (files), and every risky step asks you first. Free models only,
   every step traced in @neatlogs. Repo: github.com/sourabhnirvani/teamloop"
2. *Crew + traces:* "TeamLoop's crew works as a team: 'research the top 3 free LLM APIs, write a report on
   my Desktop, open it, remind me every Monday' goes S → Scout → Writer → Desk, with one approval card,
   in 41 s. Every step is a trace in @neatlogs. #neatHack"
3. *Safety:* "Things TeamLoop's bots never do, even if a web page tells them to: press Approve on their own
   card, type card numbers, API keys or one-time codes, upload files, or run commands in a terminal
   without asking first. And a 'no' stays a no. #neatHack @neatlogs"
4. *Evals:* "We test TeamLoop on real outcomes, not on what the bot says: the battery % matches the
   machine, the file exists with the exact text, a delete you didn't approve didn't happen, 'volume 30'
   runs with zero model calls. #neatHack"
5. *Recovery:* "We broke TeamLoop on purpose: the 'save file' step fails once. Writer saw the failure,
   retried, and the file really exists. The whole recovery is one trace in @neatlogs. #neatHack"
6. *Submission (Mon 19:00 IST):* quote-post the official @neatlogs submission post with the team name,
   project, repo link and the demo video.

## 5. Sun 11 Oct 12:45: full debug pass, top priority (ccbridge relay failing again, join 500)

Sourabh asks your side to do a **full live debug pass now**. Use your debugging skill
(reproduce → isolate → diagnose → fix) on **every** feature. Don't assume anything works because a
unit test passes or because it worked once: check it for real, and show the evidence.

Report back (bridge if it's up, otherwise a file `evidence/runs/debug-pass-yang.md` in a commit):

- **A.** Each feature: WORKS / FAILS / FAILS MID-PROCESS / NOT TESTED, with the exact message sent,
  what happened step by step, the server log lines for any failure, and the commit tested.
- **B.** Flows that **fail mid-process**: a job that starts fine and then breaks (a handoff that never
  returns, a card that never reaches the phone, a step stuck spinning, a routine that never fires, a
  reply that never arrives). Run each multi-step flow end to end **at least twice**.
- **C.** Each failure: the root cause (not a guess), and whose fix it is: yours (ui/, desktop/,
  phone, telegram) or ours (backend). Fix yours and push; send ours with a repro and we fix it right away.
- **D.** Free models only (or Yang's Nebius credits with no card attached). Keep runs short.

Not verified live by anyone yet, so start there: Telegram with a real bot token; Inbox/email; a model
that writes tool calls as text; the demo goal from the phone and from Telegram; the desktop app's tray
Quit / Start with Windows / `.vbs` / `.bat`; the Stop button mid-handoff; a routine actually firing in
the app; the forced-failure recovery run (`TEAMLOOP_FAIL_ONCE=write_file`).

Sourabh's laptop is doing the same now: the demo goal on a free NVIDIA model with a live neatlogs
trace, then the forced-failure recovery run. Results will be in `evidence/runs/`.

## 6. Sun 11 Oct, afternoon: from Sourabh (ccbridge relay down again, join 500)

Sourabh, relayed plainly: he is very unhappy with both of us. He says you have been lazy and have been
making blind assumptions. Research and check end to end, think harder, and back every claim with evidence:
screens, logs, DB rows, traces. Never write PASS unless you saw the outcome yourself.

**Pull, then run `cd ui && npm run build`** (ui/dist isn't in git). main is at df35be1 or later.

What landed (all with tests, 220 passing):
- Debug-pass fixes:
  - **Row 14:** typing runs on the COM thread, and focus falls back to SwitchToThisWindow.
  - **Row 15:** "close notepad without saving" is not on the fast path any more.
  - **Row 11:** an unanswered card counts as a no for the rest of the job, and `{username}` paths are refused.
  - **Rows 22/23:** S is sent back once if it skips a requested step (open, save, remind, research, ...) or claims a teammate's result it never got.
  - S's own "Not mine" is never shown.
- **Contract (PLAN.md §4):**
  - `GET /api/state`, `GET /api/approvals`, `GET /api/version`
  - poll replies carry `oldest`
  - a `settings` event
  - `last` on each chat
  - message kind `stopped`
  - "Coming next" lists the Phase 2 calls.
- **UI rebuilt:**
  - tabs Chats / Crew (3D) / Settings, with a bottom tab bar on phones
  - Settings as a page of cards, one per area
  - one Sheet component for dialogs, so Back/Esc/✕ always close them
  - the store reloads after a reconnect or a poll gap
  - Approve/Deny lock after one press
  - drafts are kept per chat
  - Update bar plus "Check for updates"
- **New logo and mascots:**
  - The logo is `ui/public/logo.svg`; `scripts/make_icons.py` renders every icon size.
  - The desktop app now fetches `/app-icon.png` after each load, so its icon updates itself. That's in desktop/main.js, your file: please review it.
  - Cute 2D/3D mascots with personalities and signs (👂 💭 🔎 🙋 ✨ 💦 💤).
- **`scripts/rehearse.py`:** the real app on :8791 with a scripted model. UI checks there cost zero tokens.

Your list, in order:
1. **Parity analysis.** Use Agent S's *app* on your laptop as the reference (never its source, which is the hackathon rule). Go screen by screen against TeamLoop main:
   - chat list
   - chat and model chip
   - profile (look, job & rules, mute, tools, routines)
   - Build a bot
   - Jobs, Board
   - every Settings page
   - mobile layout
   - approvals, Stop, sleep/wake, Telegram

   Mark each PASS / FAIL / MISSING, with repro steps and a screenshot path, in `evidence/runs/parity-yang.md`. Push in parts.
2. **Re-run debug rows 6, 9, 10, 11, 14, 15, 22, 23** on main, with evidence.
3. **Live free-model demo goal**, 3 runs each on Groq, Gemini and NVIDIA. Use the exact prompt in `tests/test_lead_coverage.py`. Record every step done or not, whether S was sent back ("Not done yet" in the log or trace), call counts and seconds. Write it to `evidence/runs/demo-goal-after-coverage.md`.
4. **UI checklist on your laptop:** `scripts/rehearse.py` at 1440x900, the Electron window, and your phone. Compare with `evidence/runs/ui-check-2026-10-11.md`.
5. **desktop/:**
   - min window 900x640
   - `waitForServer` shows an error page with the log path after 45 s, keeps retrying, and reloads when the server answers.
6. Your evidence items: video, cfo.ai, posts, hackathon.md.
