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
