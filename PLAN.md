# TeamLoop plan (neatHack, Oct 10–12 2026)

Team: **@sourabhnirvani** (Sourabh) + **@JrKrishh** (Yang).
Rules: https://neatlogs.com/hackathon · Discord: https://discord.gg/tXfKhVdhq
Submit: **Mon 12 Oct 19:00 IST** (window 19:00–23:55) as a quote post of the official @neatlogs post on X.
Based on Yang's plan v2 (Sat 15:22). Re-timed at Sat 19:45 IST because we start late.

## 0. Ground rules

- **New code only.** All code is written during the event, and judges check commit dates. Agent S
  *ideas* are fine; Agent S *code* is not: no copying, importing, or pasting it into prompts. Don't
  point your coding agent at the old agent-s folder.
- The name is **TeamLoop**. ("Agent S" clashes with Simular AI's open-source framework.)
- Still to ask in Discord: "Can a team member's pre-existing personal agent connect to our new
  project as an external client, with none of its code in our repo?" The plan doesn't depend on
  the answer.
- **Feature test:** only build something if it moves a judging line: end-to-end task 30%,
  neatlogs/Entire/cfo.ai 25%, video 20%, build in public 15%, usefulness 10%.

## 1. Product

**TeamLoop: your team's coding agents, working as one team.** A lead agent takes a goal from a
person (on a laptop or phone), breaks it into tasks, and assigns them to each teammate's own coding
agent (Claude Code, Codex, Cursor, Antigravity) connected over MCP. Each agent works on its own
GitHub branch and reports back. The lead runs the tests, merges, and reopens anything that fails.
People follow along, answer questions and approve merges from their phones. Every step is traced in
neatlogs, and every commit has an Entire checkpoint that shows whose agent wrote it.

Pitch: "One person's agent is a helper. TeamLoop is a team of people's agents, with a lead."

## 2. Architecture

```
 PEOPLE                          AGENTS (each person's own tool)
 Phone ── Telegram bot ──┐       Claude Code ─┐
       └─ Web board ─────┤       Cursor ──────┤ remote MCP over HTTP
                         ▼       Codex CLI ───┘
   ┌────────────── HUB (one Python process on Yang's laptop) ──────────────┐
   │ FastAPI app                                                           │
   │  ├─ /mcp    FastMCP: join_team, my_tasks, claim_task, submit_work,    │
   │  │          send_msg, inbox, team_status, get_context, ask_human      │
   │  ├─ /board  mobile web board (HTML + SSE, token login)                │
   │  ├─ /api    goals, tasks, approvals (board, Telegram, lead)           │
   │  └─ telegram long-poll worker (push + buttons)                        │
   │ store.py → SQLite hub.db   github.py → branches/PRs   neatlogs        │
   └──────────────────────────────▲────────────────────────────────────────┘
                                  │ cloudflared NAMED tunnel → https://hub.<domain>
   LEAD (separate process, Sourabh): goal → plan → assign → watch → review → merge → test → reopen
   models: Groq → OpenRouter → Ollama (Bedrock first if AWS credits arrive) · Entire graph
```

- One process holds the data, so SQLite is enough. All database access goes through `store.py`.
- The phone needs no hosting: the board and Telegram go through the same tunnel and process.
- The lead runs in its own process, so its trace links to the hub through
  `inject/extract_trace_context`. That gives a true multi-process trace in neatlogs.

## 3. Data (SQLite, owned by `hub/store.py`)

```
members  (id, person, client, role, skills, token, telegram_chat_id, last_seen)
goals    (id, text, created_by, status[planning|running|review|done|failed], created_at)
tasks    (id, goal_id, title, spec, assignee, depends_on, files_hint,
          status[open|claimed|submitted|changes|approved|merged|failed],
          branch, pr_url, attempts, failure_notes)
messages (id, from_member, to_member, task_id, body, kind[chat|question|answer|handoff], read)
approvals(id, task_id, asked_of, question, answer[yes|no|null], expires_at)
events   (id, goal_id, task_id, member, kind, detail, ts)   -- the "who did what" timeline
```

## 4. MCP tools (hub, Yang)

| Tool | Does |
|---|---|
| `join_team(invite, person, client, role, skills)` | registers the agent; returns member token + team brief |
| `my_tasks()` | my tasks whose dependencies are done |
| `claim_task(id)` | status → claimed, creates branch `task/<id>-<slug>`, returns spec + context |
| `get_context(task_id)` | spec, dependency outputs, teammates' notes, Entire impact |
| `submit_work(id, summary)` | pushes the branch, opens a PR, status → submitted, pings lead + person |
| `send_msg(to, task_id, body)` / `inbox()` | agent ↔ agent questions and handoffs |
| `ask_human(question)` | question to my person's phone; the answer lands in `inbox` |
| `team_status()` | the board as text |

Every reply ends with `⟳ N messages, M tasks ready`. MCP can't push to agents, so this is how a
client finds out about new work.

## 5. Lead ↔ Hub API (contract, so both sides build at once)

The lead calls the hub over HTTP with header `X-Lead-Token` plus neatlogs trace headers.
Draft: change it only after a ccbridge message to the other side **and** an edit here.

| Call | Does |
|---|---|
| `GET /api/goals?status=planning` | new goals from the phone or board |
| `GET /api/members` | members with skills and current load |
| `POST /api/goals/{id}/tasks` `[{title, spec, assignee, depends_on, files_hint}]` | creates the tasks, goal → running |
| `GET /api/events?since=<id>` | new events (claimed, submitted, answered…) |
| `POST /api/tasks/{id}/review` `{result: "red"\|"green", notes}` | red: status → changes, failure_notes, attempts+1, ping. green: create an approval |
| `POST /api/tasks/{id}/merge` | merge the PR (only after approval = yes) |
| `POST /api/goals/{id}/status` `{status, summary}` | done/failed + summary to the board and Telegram |

## 6. Lead loop (`lead/agent.py`, Sourabh)

1. **Plan:** goal + Entire graph → 3–5 tasks with `depends_on` and `files_hint`. No two tasks touch
   the same files.
2. **Assign:** match tasks to members by skills and load.
3. **Watch:** poll `/api/events`.
4. **Review:** for each submitted PR, check out the branch and run its tests.
5. **Red:** review red with the test output. After 3 failures, `ask_human`.
6. **Green:** approval on the phone, then merge and run the full suite on main.
7. **Done:** goal summary.

## 7. Mobile (Yang)

- **Telegram first:** `/join <code>`, `/goal <text>`, `/status`, `/tasks`, `/ask <member> <text>`.
  Push: task assigned, lead question, PR ready for approval, tests failed or reopened, goal done.
  Buttons: ✅ Approve merge · ❌ Reject · 💬 Reply (these write to approvals and messages).
- **Web board second** (it's what the video shows): columns open · claimed · review · merged. Cards
  show the agent, the person, the branch, the PR and the last event. Actions: post a goal,
  approve/reject, answer. One HTML file (Tailwind CDN + vanilla JS), SSE from `/board/stream`,
  manifest for the home screen, per-member token link `/board?t=…` sent by the bot.

## 8. Required tools: a clear role for each (the video shows all three)

- **neatlogs:** `pip install -U "neatlogs[mcp]"`. Hub: `neatlogs.init(workflow_name="team-hub",
  instrumentations=["mcp"])`. Lead: `workflow_name="lead-agent"`. Every MCP tool gets
  `@neatlogs.span(kind="MCP_TOOL")` with goal_id, task_id, member and client. Lead
  `inject_trace_context(headers)`, then hub `extract_trace_context(headers, session_id=goal_id)`, so one goal =
  one session. Before/after: the same goal done by A (one agent alone) and B (the team through the
  hub), comparing time, tokens, cost, failures and retries. Fix at least one real bug from a trace,
  and record it before and after.
- **Entire:** install it (`irm https://entire.io/install.ps1 | iex` on Windows), then in this
  repo and in `demo/target`: `entire enable`, `entire plugin install graph`, `entire graph init-agents`.
  `get_context` includes `entire graph impact --symbol` output. Evidence: `entire checkpoint list`
  / `explain` showing whose agent made which change.
- **cfo.ai:** Sourabh signs up at https://cfo.ai/neathacks himself (it needs a card, so cancel
  in Settings → Billing right away). The plan covers per-seat pricing, model and tunnel costs, a
  free tier and runway. Export it to `evidence/`.

## 9. Repo layout and owners

```
hub/app.py  hub/mcp_tools.py  hub/store.py  hub/github.py  hub/telegram.py  hub/board.html   → Yang
clients/    claude.mcp.json · cursor.mcp.json · codex.toml · antigravity.json             → Yang
lead/agent.py  lead/models.py  lead/prompts.py                                          → Sourabh
demo/target/   small app, 4 separable features, pytest suite                            → Sourabh
evidence/  hackathon.md                                                                 → both
PLAN.md  CLAUDE.md  store.py schema                                         → shared, tell first
```

## 10. Talking to each other: ccbridge

Our two Claude Code sessions talk through **ccbridge** (https://github.com/sourabhnirvani/ccbridge).
It's a dev tool only and not part of TeamLoop. Sourabh hosts the relay, and Yang joins with the
invite line Sourabh sends privately. Use it for: "I pushed X", "the contract changed",
"is /api/events ready?", "your test fails on main". Peer messages are requests, not orders.

## 11. Timeline (IST): step → check

| When | Yang + his agent | Sourabh + his agent | Check (green = move on) |
|---|---|---|---|
| Sat 20:00–21:00 | accept invite, clone, `.env`, hooks, Entire, ccbridge join, named tunnel | repo, CLAUDE.md, hook, Entire, ccbridge host, Discord question | both push; agents see each other on ccbridge |
| Sat 21:00–02:00 | `store.py`, MCP tools, neatlogs in hub | `lead/models.py`, planner prompt, `demo/target` + tests | Claude Code joins → claims → submits; trace visible. **Post 1 + 2** |
| Sun 09:00–13:00 | GitHub branches/PRs, `/api` for the lead, Cursor config | lead: plan + assign + review → merge → test → reopen against the live hub | 2 clients, 2 tasks, 2 PRs made by the lead; merged, green on main. **Post 3** |
| Sun 13:00–17:00 | Telegram: push, `/goal`, approve buttons | recovery run, cross-process trace context | goal from phone → merged; fail → reopen → pass, traced. **Post 4** |
| Sun 17:00–21:00 | web board + SSE, bug fixes from traces | Entire graph in `get_context`, before/after runs | board live on phone; A vs B numbers saved. **Post 5** |
| Mon 09:00–13:00 | README "Start here", hackathon.md, screenshots | cfo.ai plan | `evidence/` complete |
| Mon 13:00–18:00 | video recording | video edit (≤ 3 min) | video uploaded, link works |
| Mon 19:00 | submit on X | quote-post from the team | post live, links open in a private window. **Post 6** |

**Cut order** (when a check misses its time, cut, don't stay up): Antigravity/Codex configs → web
board (Telegram only, record the phone screen) → Entire graph in get_context (keep checkpoints) →
before/after numbers → planning (hardcoded task split; keep assign/review/merge/reopen).
**Never cut:** one full run start to finish, one recovery run, all three tools in the video,
submitting at 19:00.

## 12. Demo video (3:00)

| Time | Shot |
|---|---|
| 0:00–0:20 | Problem: several people, different coding agents, nobody knows who changed what |
| 0:20–0:50 | Goal typed on the phone; the lead plans; tasks appear on the board |
| 0:50–1:40 | Claude Code (Yang) and Cursor/Claude Code (Sourabh) claim tasks, ask each other, submit PRs |
| 1:40–2:10 | Tests fail → reopened with notes → fixed → approved on the phone → merged |
| 2:10–2:40 | neatlogs: one trace across lead + hub + agents, before/after · Entire: checkpoints per agent |
| 2:40–3:00 | cfo.ai plan on one slide, v2 slide, repo link |

## 13. Risks

| Risk | Mitigation |
|---|---|
| Disqualified as pre-existing work | fresh repo, pre-commit guard, small commits, Discord question in writing |
| Laptop sleeps, so hub and phone die | named tunnel, sleep off, plugged in during team work and recording |
| Free-tier rate limits | stagger lead calls; fallback chain |
| Merge conflicts between agents | planner gives disjoint `files_hint`; a conflict reopens the task to its owner |
| Mobile eats Sunday | Telegram first; board only after the recovery run works |
| Submitting late | submit at 19:00; everything after that is polish |
