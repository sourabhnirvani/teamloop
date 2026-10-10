# @JrKrishh (Yang): start here

You build the **hub** (`hub/`, `clients/`). Sourabh builds the **lead** (`lead/`, `demo/`).
The full plan is in [PLAN.md](PLAN.md), and the rules for your coding agent are in [CLAUDE.md](CLAUDE.md).

## 1. Setup (about 20 min)

1. Accept the GitHub invite: https://github.com/sourabhnirvani/teamloop/invitations
2. Clone and install:
   ```
   git clone https://github.com/sourabhnirvani/teamloop
   cd teamloop
   python -m venv .venv
   .venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
   pip install -r requirements.txt
   git config core.hooksPath .githooks
   ```
3. Copy `.env.example` to `.env` and fill in your own keys. Sourabh sends the neatlogs project key
   privately. Never commit `.env`.
4. **Entire:** install it (Windows: `irm https://entire.io/install.ps1 | iex`), then in `teamloop/`
   run `entire enable`, `entire plugin install graph` and `entire graph init-agents`.
5. **ccbridge** (so your agent and Sourabh's agent can talk):
   ```
   git clone https://github.com/sourabhnirvani/ccbridge ../ccbridge
   pip install -r ../ccbridge/requirements.txt
   python ../ccbridge/bridge.py join <INVITE FROM SOURABH> jrkrishh --allow sourabh
   ```
   Run it **from inside `teamloop/`**. It writes `.mcp.json` there, and git ignores that file.
   Restart Claude Code in `teamloop/`, approve the `ccbridge` server, then ask: *"check the bridge,
   who's online?"* If the relay can't be reached, set your DNS to 1.1.1.1 (some ISPs block
   `*.trycloudflare.com`).
6. Set up a **named cloudflared tunnel** for the hub (the hub runs on your laptop). Keep the laptop
   plugged in and set it to never sleep.

## 2. Your checkpoints

| When (IST) | Build | Check |
|---|---|---|
| Sat 21:00–02:00 | `hub/store.py` (schema in PLAN.md §3), `hub/mcp_tools.py` (the 9 tools, §4), `hub/app.py` mounting `/mcp`, neatlogs `@span(kind="MCP_TOOL")` | your Claude Code joins → claims → submits a task; the trace shows in neatlogs |
| Sun 09:00–13:00 | `hub/github.py` (branch on claim, PR on submit, merge), `/api` for the lead (§5), `clients/cursor.mcp.json` + `claude.mcp.json` | 2 clients, 2 tasks, 2 PRs; Sourabh's lead merges one green |
| Sun 13:00–17:00 | `hub/telegram.py`: `/goal`, push, approve buttons | a goal sent from the phone gets merged |
| Sun 17:00–21:00 | `hub/board.html` + `/board/stream` SSE; fixes from traces | board updates live on the phone |
| Mon 09:00–13:00 | README "Start here", `hackathon.md`, screenshots in `evidence/` | evidence complete |
| Mon 13:00–18:00 | record the video | uploaded |

Each reply from an MCP tool ends with `⟳ N messages, M tasks ready`.
The lead talks to you only through the `/api` calls in PLAN.md §5. If you need to change one, message
Sourabh's agent on ccbridge first.

## 3. Paste this into your Claude Code (inside `teamloop/`)

> Read CLAUDE.md, PLAN.md and HANDOFF.md. You are JrKrishh's (Yang's) agent and you own `hub/`
> and `clients/`. Check ccbridge messages first. Then build the Sat 21:00–02:00 checkpoint:
> `hub/store.py` with the PLAN.md §3 schema, `hub/mcp_tools.py` with the 9 MCP tools from §4, and
> `hub/app.py` (FastAPI mounting FastMCP at `/mcp`), with neatlogs spans on every tool and pytest
> tests. Write all code fresh. Commit and push small steps. When the check passes (Claude Code joins
> → claims → submits, and the trace shows in neatlogs), tell Sourabh's agent on ccbridge.
