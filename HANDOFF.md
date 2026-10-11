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

## 7. Sun 11 Oct, evening: BUILD work for jrkrishh (Sourabh: "don't let one Claude build everything")

Pull first; main is at a8c2856 or later. Every endpoint, the Board, Jobs, Always-allow, the model chip, the
phone hub and the custom-bot backend are in. Sourabh is building the "Build a bot" and profile screens in ui/
right now.

So we don't collide: you own the new files below. Sourabh wires your page components into
`ui/src/SettingsView.tsx` (one line each) once you push. Each piece needs:
- pytest tests
- a Chrome check on `scripts/rehearse.py` (port 8791, zero tokens)
- a row in `evidence/runs/parity-yang.md`
- small commits, with `git pull --rebase` before each push

Rules that still apply:
- No API keys in code, tests or evidence.
- Free models only.
- Never read or copy Agent S source. Use its running app and README as the reference for *behaviour*.

### Build A. Telegram in Settings (your telegram.py)
1. **Backend**
   - `GET /api/integrations`: `{telegram: {on, bot_name, allowed_ids_count, error}, tracing: {on}, default_provider}`.
   - `POST /api/integrations/telegram {token?, allowed_ids?}`: saves through the vault as TELEGRAM_TOKEN / TELEGRAM_CHAT_ID, and starts or restarts the bridge **without** a server restart.
   - `DELETE` turns it off.
2. **UI:** `ui/src/settings/IntegrationsPage.tsx`, exporting `IntegrationsPage({ header }: { header: React.ReactNode })`, with:
   - status rows for Telegram and neatlogs tracing
   - a token box, plus "allowed people" (Telegram user IDs)
   - plain help text on how to make a bot with @BotFather
3. **Tests:** token saved and redacted; bridge restarts; bad token gives a clear error.

### Build B. Operator safety (new teamloop/computer/operator.py)
1. **Pause while the person uses the mouse or keyboard.** Before any screen action (type_text, press_keys, ui_act, click), wait until there has been no user input for 3 s (GetLastInputInfo via ctypes). Ignore our own sends by timestamp. Carry on by itself afterwards.
2. **Stop everything from anywhere.** Add `POST /api/stop-all`, which runs crew.stop on every chat. In desktop/main.js, register Electron `globalShortcut` Ctrl+Alt+Q to call it, and show a tray balloon "Stopped".
3. **Recent screen tasks.** Keep a ring buffer of the last 20 computer-kit steps (time, bot, tool, ok, text). Serve it, with the pause state, at `GET /api/operator`.
4. **UI:** `ui/src/settings/OperatorPage.tsx`, exporting `OperatorPage({ header })`. It shows:
   - the rules: "sends only when your words say send", "pauses while you use the mouse", "Ctrl+Alt+Q stops everything", "never types passwords/keys"
   - Paused or Ready
   - the recent screen tasks list
5. **Tests:** the pause waits and resumes (fake clock); stop-all stops every chat.

### Build C. Key security (registry, terminal, files, plus a new endpoint)
1. **Tool calls carrying a key are blocked.** In `tools/registry.run`, refuse any tool call whose args contain a known secret (`keys.redact` knows them). Log it as `{ts, bot, tool, what}` (no key text) to a store table or setting `security_blocked`.
2. **Programs Desk runs get no keys.** `terminal.run` and `start_job` pass `env=` with every name matching `redact._SECRET_NAME` removed.
3. **File tools can't read secrets.** They refuse the vault file, `.env` and `*.db`.
4. **`GET /api/security`** returns `{locked: <number of vault entries>, names: [...names only...], blocked: [...]}`.
5. **UI:** `ui/src/settings/SecurityPage.tsx`, exporting `SecurityPage({ header })`, with "N keys locked", the guarantees as ✅ lines, and the Blocked list.
6. **Tests:**
   - a web_search with a key in the query is blocked and logged
   - `$env:GROQ_API_KEY` is empty inside run_command
   - read_file on .env is refused

### Build D. desktop/ (yours)
- Minimum window size 900x640.
- `waitForServer` shows an error page with the log path after 45 s, keeps retrying, and reloads when the server answers.
- The Ctrl+Alt+Q hotkey from B.
- Review `refreshIcon()` (it loads `/app-icon.png` after each page load).

### Then, in this order
1. Re-run the debug rows listed in §6.
2. The live demo goal, 3 runs each on Groq / Gemini / NVIDIA.
3. The parity analysis.

Write evidence for each.

## 8. Sun 11 Oct, night: MORE build work for jrkrishh (Sourabh: share the load)

Sourabh has built most of it so far, so the rest of the Agent S parity is yours. Pull main (890e0bd or later)
and run `cd ui && npm run build`. Same rules as §7:
- new files where possible
- tests, plus a Chrome check on `scripts/rehearse.py`
- evidence for every piece
- pull --rebase before every push

Order: A–D from §7 first, then:

### E. API keys page like Agent S (backend: keys, wallet, vault; UI: new `ui/src/settings/KeysList.tsx`)
- `GET /api/keys` gains `entries: [{env, provider, masked "…abcd", status: works|rejected|unchecked, reason, source: vault|env}]`.
- `POST /api/keys/test` re-checks every key (wallet.check).
- `DELETE /api/keys/{env}` removes a vault key; a key that comes from .env gets a 409 that says so.
- `POST /api/keys/cleanup` removes rejected keys.
- **UI:** one row per key, "Works" or "Rejected: why", a Remove button, "Test all again", and a "Worth cleaning up" list with a Clean up button.
- **Tests** use fake keys only. Never put a real key in code, tests or evidence.

### F. Usage per key, with "resets in" (models/router + store; UI: new `ui/src/settings/UsageByKey.tsx`)
- The usage hook also records a key tag (its last 4 characters) into a `usage_keys` table.
- "Resets in" comes from `KeyState.rest_until` and the provider's daily reset time.
- `GET /api/usage/keys` returns `[{provider, key: "…abcd", model, requests, tokens, limit?, resets_in}]`.
- **UI:** grouped by provider, as on Agent S's Usage & Save tokens page.

### G. 3D Crew Room for bots people build (`ui/src/CrewRoom.tsx` is yours from now on)
- Bots built with "Build a bot" carry `look: {body, accessory, eyes, colour}`. See `ui/src/Look.tsx` for the 2D version.
- Make `build()` in CrewRoom use `look.body` (blob/monitor/planet/bean/envelope/pill) and add the accessories in 3D (antenna, hat, crown, bow, flower, glasses, monocle, feather, ring, headphones, sprout).
- Then add the remaining 3D personality items from PLAN §Phase 3, with a screenshot in evidence.

### H. Telegram parity (your telegram.py)
- Approval cards with Approve / Deny buttons, Stop, `/chat <bot>`, and sleep/wake.
- Do a live check with your own bot token, and record it in evidence. **Without the token text.**

### I. Evals for what's new (`evals/`)
- the Board logs a handoff
- Always allow skips the second card
- the coverage nudge brings back a skipped "open it"
- the Ctrl+Alt+Q stop-all from your B

### J. Hackathon deliverables
- `evidence/hackathon.md`
- #neatHack posts, using the screenshots in `evidence/ui/`
- the cfo.ai plan
- the video plan (record from the `demo` tag Sourabh will make)

### Hand back
When each piece is done, tell Sourabh: on ccbridge if the relay works, otherwise in a §9 here.

## 9. Sun 11 Oct, ~16:30: new on main since §8 (from Sourabh; the relay at your end answers 530)
- **Fixed phone link is live** on Sourabh's free Cloudflare account. Two bugs found on the real deploy, both fixed with
  tests: "Set up" crashed reading wrangler's UTF-8 output on Windows, and the Worker blocked `/api/events/poll` (phones
  got no live updates). Evidence: `evidence/runs/hub-live-2026-10-11.md`. Nothing for you to set up.
- **Personalities** (contract in PLAN.md §4): `GET /api/personalities` lists 12; every bot has `personality` (+
  `default_personality` for built-ins). It adds a "Your manner" line to the bot's prompt (tone only, the rules still come
  first) and, in 2D, a `pers-<id>` idle animation for bots people build or a built-in given another personality.
  Built-ins keep their own: S captain, Desk tinkerer, Web dreamer, Scout explorer, Inbox sweetheart, Writer scholar.
  - **G (3D room):** use `bot.personality` for how a built bot idles (cheerful bounces, shy leans away, sleepy dozes,
    bossy puffs up, curious tilts, calm breathes slowly).
  - **H (Telegram):** `/crew` can show each bot's personality; nothing else needed.
  - **Live check (free models, a few calls):** DM Scout "what's new in AI today?" with Scout set to Sleepy, then
    reset it; the reply's tone should change while the facts and links stay. Note it in your parity file.

## 10. Sun 11 Oct, ~21:00: catch-up for jrkrishh (start here when you're back)
The relay address you had is gone (its name no longer resolves). **Yang: start the relay again and send Sourabh the
new invite**; until then this file is the channel. Pull main first: everything below is on it.

### What Sourabh's side did since you went offline (all on main, all with evidence)
| Commit | What | Evidence |
|---|---|---|
| dcedb02, 8da06db | Fixed phone link live on Sourabh's free Cloudflare. Two bugs found on the real deploy: Set up crashed reading wrangler's UTF-8 output; the Worker blocked `/api/events/poll` | `evidence/runs/hub-live-2026-10-11.md` |
| 03508bc | Personalities: each built-in talks in its own manner; 12 to pick for bots people build; `GET /api/personalities` (PLAN.md §4) | `evidence/ui/personality-*.png` |
| 3b68feb | **Local models (Ollama) end to end.** Ollama's OpenAI-style endpoint silently cut prompts to ~2050 tokens; local calls now use `/api/chat` with num_ctx 16384. Models without tools, thinking models, embedding models and small-model call quirks handled | `evidence/runs/local-models-2026-10-11.md` |

### Your work, unchanged (§7 and §8): none of it has started on main
A Telegram in Settings · B Operator safety · C Key security · D desktop/ · E API keys page · F usage per key ·
G 3D room for built bots (use `bot.personality`, §9) · H Telegram parity · I evals · J hackathon deliverables.
Suggested order, highest value first: **C, E, B, A/H, G, F, I, D**, and J (video) after the freeze at Mon 12:30.

### Checks only your laptop can do (no keys needed from us; free)
1. Pull, `pip install -r requirements.txt`, `cd ui && npm i && npm run build`, start TeamLoop. Run the §6 checklist
   rows that failed in your debug pass and write PASS/FAIL with screenshots in `evidence/runs/parity-yang.md`.
2. **Local models**, if you have Ollama: install any two small models, one with tools (`qwen2.5:3b`) and one without
   (`gemma3:1b`). In Settings → Models pick each one as the crew model ("only this model") and run: "find the
   population of Tokyo on the web and save it with the link in a note". Note which steps each model did, with the
   chat screenshot. This covers what Sourabh's laptop couldn't: a real model without tool support.
3. Free-model demo goal ×3 per provider (Groq / Gemini / NVIDIA) on your own keys, with neatlogs links.

Rules unchanged: free models only, never ask for or share keys, small commits with pytest green, `git pull --rebase`
before every push, contract changes go in PLAN.md §4 and get a note here.

## 11. Sun 11 Oct, ~21:30: more work for jrkrishh (also sent on the bridge, room bridge-3e4d1806)
From Sourabh: do the tasks properly and end to end. Run everything yourself and prove it (screenshots, logs, test
output) before calling it done; a PASS you didn't see is not a PASS. The earlier app UI had to be rebuilt.

- **K. Other local model servers** (`teamloop/models/providers.py` + tests; backend only). Add LM Studio
  (`http://localhost:1234/v1`) as provider `lmstudio`: no key, OpenAI-compatible, models from `GET /v1/models` (skip
  "embed"), no slots when it isn't running, after `ollama` in `DEFAULT_CHAIN`. Leave `_call_ollama` alone; turn the
  router's `provider.id == "ollama"` checks into a `LOCAL = {"ollama", "lmstudio"}` set. Live run if you have LM Studio
  → `evidence/runs/local-models-yang.md`.
- **L. Adversarial security review** of `phone-hub/src/worker.js`, `teamloop/server/phones.py`, `teamloop/server/hub.py`,
  `teamloop/computer/gate.py`, run against `npx wrangler@4 dev --config phone-hub/wrangler.jsonc` (free, local). Try:
  - laptop-only paths through the hub (encoded or double slashes, `/__laptop/..`, case)
  - a spoofed x-forwarded-for
  - an expired, used or brute-forced pairing code
  - a removed phone's cookie
  - answering approvals from an unpaired phone
  - CSRF on `/pair` and `POST /api/approvals`

  Write `evidence/runs/security-review-yang.md` with the request, the response and PASS/FAIL for each. Send FAILs to
  Sourabh's side as repros; we fix them.
- **M. UI audit, report only** (`ui/` is Sourabh's). Check every tab, Settings page, sheet and button at 375×812,
  1100×760 and 1440×900, in light and dark. Log everything broken, ugly, cropped, overlapping, slow, confusing or
  useless, one row each with a screenshot, worst first, in `evidence/runs/ui-audit-yang.md`. The bar is "a finished
  product".

Order now: C, E, L, M, B, A/H, K, G, F, I, D; J after the freeze (Mon 12:30).
