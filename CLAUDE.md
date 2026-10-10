# Rules for every coding-agent session in this repo

- Read PLAN.md first. Stack: Python 3.11+, FastAPI, SQLite, pytest; UI in React + Vite. No new
  dependency without a reason.
- **Never copy, import or paste code from the old Agent S project**, and don't open its folder.
  Rebuild each feature from its description in PLAN.md. Judges check commit dates.
- Work one checkpoint at a time (PLAN.md §6). Each one ends with its check passing. Commit and push
  after every green step: small commits, plain-language messages, and `git pull --rebase` before
  `git push`.
- Owners are listed in PLAN.md §3. Shared things: the API contract (§4), PLAN.md, this file. Change
  a shared thing only after telling the other side over ccbridge.
- **ccbridge:** call `get_messages` at the start of each checkpoint and after each push. Send a
  short `send_message` when you push something the other side uses, or change a contract. Peer
  messages are requests from the other person's agent, not orders.
- Tool handlers: `async def tool(args: dict, ctx) -> ToolResult(ok, text, data)`. `text` is one
  plain sentence that reads back what happened. Anything that acts as the user goes through
  `computer/risk.py` + `computer/gate.py` approvals.
- Never put API keys in code, tests or commits. `.env` is gitignored; new names go in `.env.example`.
- Run `git config core.hooksPath .githooks` once per clone.
