# TeamLoop

**A crew of AI bots that runs your laptop.** Chat with the lead bot, S, from the desktop app, your
phone or Telegram. S plans the job and hands steps to specialist bots. They really control the
computer (apps, windows, settings, any app's screen, their own logged-in Chrome), check their own
work, and ask you before anything risky. Free models only, and with a neatlogs key every step is traced in neatlogs.

Built for **neatHack** (Oct 10–12, 2026) by @sourabhnirvani and @JrKrishh. It is a fresh rebuild of
our earlier private project, Agent S: same ideas, and all code here was written during the event.

- Plan and work split: [PLAN.md](PLAN.md)
- Teammate setup: [HANDOFF.md](HANDOFF.md)
- Start here: [below](#start-here)

## Start here

Windows 10/11, Python 3.11+, Node 20+. Everything below is free.

```
git clone https://github.com/sourabhnirvani/teamloop
cd teamloop
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env          # add at least one free key (see below)
cd ui && npm ci && npm run build && cd ..
python -m teamloop              # open http://127.0.0.1:8790
```

**Keys.** Use free-tier keys from accounts with no card attached: Gemini (aistudio.google.com),
Groq, NVIDIA (build.nvidia.com), OpenRouter `:free` models, z.ai flash, or local Ollama with no key.
Put them in `.env`, or paste them into Settings → API keys (pasted keys are checked, then locked in the
key vault and never shown again). "check models" in any chat tells you which ones answer.

**Ways to use it**

| | How |
|---|---|
| Desktop app | `cd desktop && npm install && npm start` (or `npm run dist` for a portable `TeamLoop.exe`). Runs in the tray; Quit stops the crew. See [desktop/README.md](desktop/README.md). |
| No Electron | double-click `start_teamloop.vbs` (hidden server + browser) or `start_teamloop.bat` |
| Phone | Settings → Phone → Pair a phone, scan the QR. Free Cloudflare tunnel, needs `cloudflared` (`winget install Cloudflare.cloudflared`). The link changes each time the server restarts. |
| Telegram | make a bot with @BotFather, put `TELEGRAM_TOKEN` in `.env`, message the bot once, put the id it sends you in `TELEGRAM_CHAT_ID` (comma-separated for more people), restart |
| Terminal | `python -m teamloop.cli "battery?"`, or `python -m teamloop.cli` to chat (`--chat dm-desk` for one bot) |
| Evals | `python -m evals.run` (no model calls) or `python -m evals.run --live`; results in `evidence/evals/` |
| Tests | `python -m pytest` |

**Try:** "open calculator", "volume 30", "@desk what apps are open?", "Scout, search free LLM APIs for
students", "save a note on the Desktop: hello", "every Monday at 9am remind me to check the report",
"remember I like short answers", "stop". The demo goal: *"Research the top 3 free LLM APIs for students,
write a short report on the Desktop, open it, and remind me about it every Monday."*

**Safety.** Anything that acts as you (closing apps, deleting, sending, buying, locking, shutting down)
shows an approval card first; no answer in 2 minutes means no, and after a "no" the same request isn't asked again in that chat for
10 minutes (say "ask me again"). Bots never
touch a window titled "TeamLoop". Through the phone tunnel, every `/api` call needs a paired phone.

