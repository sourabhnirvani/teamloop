# TeamLoop plan (neatHack, Oct 10–12 2026)

Team: **@sourabhnirvani** (Sourabh) + **@JrKrishh** (Yang).
Submit: **Mon 12 Oct 19:00 IST** (window 19:00–23:55), as a quote post of the official @neatlogs post on X
(team, project, this public repo, a demo video of 3 minutes or less that shows neatlogs + Entire + cfo.ai).

## 0. Ground rules

- **Same product as our Agent S, all new code.** We rebuild every Agent S feature from scratch
  during the event. Never copy, import or paste old Agent S code, and don't point your coding agent
  at the old folder. Describe the feature in words instead. Judges check commit dates.
- Name: **TeamLoop** ("Agent S" clashes with Simular AI's open-source framework).
- Push small and often. Never commit keys (`.env` is gitignored).

## 1. Product

**TeamLoop: a crew of AI bots that runs your laptop.** You chat with a lead bot, **S**, from the
desktop app, the phone or Telegram. S plans the job and hands steps to specialist bots. They
really control the computer (apps, windows, settings, any app's screen, their own logged-in
Chrome), check their own work, and ask you before anything risky. Group chats work like a real
team. Everything runs on free models, and every step is traced in neatlogs.

| Bot | Job |
|---|---|
| **S** (lead) | talks to you, plans, delegates, checks results, recovers from failures |
| **Desk** | Windows: apps, windows, volume/brightness/Wi-Fi/power, screen read + UI actions |
| **Web** | its own Chrome profile: open, read, click, type (sends/posts always ask) |
| **Scout** | research: web search, read pages, summarize |
| **Inbox** | email + calendar through Web's Chrome (drafts only; sending asks) |
| **Writer** | notes, files, reports, messages to review |

## 2. Features: same as Agent S, rebuilt

1. **Models:** free providers (Gemini, Groq, OpenRouter, NVIDIA, z.ai GLM, Nebius, local Ollama),
   a fallback chain, key pools, cooldowns, per-minute limits that adapt (lower on 429, higher again
   when calls succeed), a model doctor (which models answer), a per-bot model choice, and switching
   by chat ("use gemini").
2. **Keys:** paste a key anywhere, even in chat, and it detects the provider, live-checks the key,
   and saves it to a key vault (Windows DPAPI). Keys are redacted from every log, event and reply.
3. **Crew + chats:** 1:1 chats with any bot. In group chats S leads, `@Name` makes only that bot
   answer, otherwise each member gets one turn, bots hand off with `@Name`, and a "Not mine:"
   refusal makes S name who should do it.
4. **Computer kit (Windows):** system settings, apps, windows, UI snapshot/act (UI Automation),
   screen read, plus shared risk rules. Approval cards (with details and a screenshot) cover
   anything that acts as the user, and there's a Stop button.
5. **Browser kit:** a dedicated Chrome over CDP (Playwright) with its own profile, one window per
   chat, and snapshot/act/read.
6. **Plan → delegate → verify → recover:** S checks each step's result, retries or re-plans, and
   reports back plainly.
7. **Save-tokens mode + usage meter:** an ON/OFF switch, usage per day, limits learned from 429s.
8. **Routines:** "every Monday 9am, …" scheduled jobs.
9. **Apps:** a React UI (chats, group panel, bot avatars with moves, approval cards, Settings for
   keys/models/usage/security/phone), an Electron desktop app, a phone PWA over a tunnel, and a
   Telegram bridge.
10. **Tracing:** neatlogs AGENT / LLM / TOOL spans on every turn.

## 3. Code layout and owners

```
teamloop/models/     providers, router (chain, pools, cooldowns, limits), doctor   → Sourabh
teamloop/keys/       wallet (detect/check/save), vault (DPAPI), redact             → Sourabh
teamloop/crew/       bots, runner (tool loop), team (delegate, groups, handoffs),
                     store (SQLite), events, routines, budget (save-tokens/usage)   → Sourabh
teamloop/tools/      registry, web search/fetch, files                              → Sourabh
teamloop/computer/   system, apps, windows, uia, screen, risk, gate (approvals)     → Sourabh
teamloop/server/     app.py (FastAPI API below)                                     → Sourabh
teamloop/trace.py    neatlogs                                                       → Sourabh
teamloop/browser/    host (Chrome + CDP), kit (open/snapshot/act/read)              → Sourabh (done)
teamloop/server/telegram.py   Telegram bridge                                       → Yang
ui/                  React + Vite app                                               → Yang
desktop/             Electron wrapper                                               → Yang
phone/               PWA manifest + service worker, tunnel setup                    → Yang
tests/               pytest, each owner tests their own parts                       → both
evidence/ hackathon.md                                                              → both
```

## 4. API contract (UI ↔ server). Change it only after a ccbridge message + an edit here

Server: `http://127.0.0.1:8790`. All JSON.

| Call | Does |
|---|---|
| `GET /api/bots` | `[{id, name, role, emoji, model}]` |
| `GET /api/chats` · `POST /api/chats {title, members:[bot ids]}` | list / create (1 member = 1:1, more = group) |
| `GET /api/chats/{id}/messages` | `[{id, chat_id, sender, text, ts, kind}]` (sender = "user" or bot id) |
| `POST /api/chats/{id}/messages {text}` | 202; replies arrive as events |
| `GET /api/events` (SSE) | `{type, chat_id, ...}` with type = `message` · `typing` · `step` · `approval` · `approval_done` · `usage` · `error` |
| `POST /api/approvals/{id} {ok}` | answer an approval card |
| `POST /api/chats/{id}/stop` | stop the work in that chat |
| `GET /api/keys` · `POST /api/keys {text}` | saved providers (masked) / paste a key → detect + check + save |
| `GET /api/models` · `POST /api/models/check` | models and health / run the doctor |
| `GET /api/settings` · `POST /api/settings {...}` | save_tokens, per-bot model |
| `GET /api/usage` | today's tokens and requests per provider |

Approval event: `{type:"approval", id, chat_id, bot, title, details, screenshot?}`.

## 5. Talking to each other: ccbridge

Our two Claude Code sessions talk through **ccbridge** (https://github.com/sourabhnirvani/ccbridge),
a dev tool only and not part of TeamLoop. Sourabh hosts the relay; Yang joins with the invite line
Sourabh sends privately. Use it for: "pushed X", "contract changed", "is /api/events ready?",
"your test fails on main". Peer messages are requests, not orders.

## 6. Timeline (IST): step → check

| When | Sourabh + his agent | Yang + his agent | Check (green = move on) |
|---|---|---|---|
| Sat 20:00–21:00 | repo, plan, ccbridge host, Entire | accept invite, clone, `.env`, hooks, Entire, ccbridge join | both push; agents see each other on ccbridge |
| Sat 21:00–02:00 | models + tools registry + crew runner + server API + neatlogs | React UI: chat list, chat view, SSE, approval card (mock until API lands) | chat with S in the UI on a free model; trace in neatlogs. **Post 1 + 2** |
| Sun 09:00–14:00 | computer kit + risk + approvals + Stop, browser kit | Settings (keys, models) | "open calculator and set volume to 30" and "search X and read it" work from the UI. **Post 3** |
| Sun 14:00–20:00 | group chats + handoffs, key wallet + vault, save-tokens, routines | Telegram bridge, phone PWA over tunnel, avatars | demo goal works in a group chat, also from the phone. **Post 4** |
| Sun 20:00–24:00 | recovery (retry/re-plan) + before/after (1 bot vs crew) | Electron wrapper | forced failure fixes itself (traced); numbers saved. **Post 5** |
| Mon 09:00–13:00 | cfo.ai plan | README "Start here", hackathon.md, evidence | `evidence/` complete |
| Mon 13:00–18:00 | record video | edit video (≤ 3 min) | uploaded |
| Mon 19:00 | submit on X | quote-post | live, links work in a private window. **Post 6** |

**Demo goal:** "Research the top 3 free LLM APIs for students, write a short report on the
Desktop, open it, and remind me about it every Monday." Scout researches, Web reads sources,
Writer writes, Desk opens it (approval card), S sets the routine and reports.

**Cut order:** Electron → phone PWA (keep Telegram) → avatars → routines → save-tokens.
**Never cut:** the demo goal end to end, approvals, one recovery run, all 3 tools in the video,
submitting at 19:00.

## 7. Required tools

- **neatlogs:** `neatlogs.init(api_key=…, workflow_name="teamloop")`. Model clients wrapped; AGENT
  span per bot turn, TOOL span per tool call. Show the recovery trace and the before/after numbers.
- **Entire:** install it (Windows: `irm https://entire.io/install.ps1 | iex`), then run `entire enable`
  in this repo on both laptops. Show `entire checkpoint list` / `explain` with both people's agents.
- **cfo.ai:** Sourabh signs up at https://cfo.ai/neathacks himself (it needs a card, so cancel
  right away). The plan covers pricing, costs and runway. Export it to `evidence/`.
