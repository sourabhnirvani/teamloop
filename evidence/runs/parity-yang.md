# Parity and build checks: jrkrishh (Yang's side)

One row per piece. PASS only when the outcome was seen.

| Date (IST) | Piece | Check | Result | Evidence |
|---|---|---|---|---|
| Sun 11 Oct 22:20 | C. Key security: tool calls carrying a key | `tests/test_security.py`: web_search with a fake key in the query is refused, logged as `{ts, bot, tool, what}` with no key text, and listed by `GET /api/security` | PASS | pytest, 258 passed / 1 skipped |
| Sun 11 Oct 22:20 | C. Programs get no keys | `$env:GROQ_API_KEY` is empty inside `terminal.run` while a harmless variable still passes | PASS | `test_programs_get_no_keys` |
| Sun 11 Oct 22:20 | C. File tools refuse secret files | `read_file` refuses `.env`, `.env.local`, `teamloop.db`, `keys.vault`; `.env.example` still reads | PASS | `test_file_tools_refuse_secret_files` |
| Sun 11 Oct 22:20 | C. `GET /api/security` live | `scripts/rehearse.py` on 8791 answered `{"locked":0,"names":[],"blocked":[]}` | PASS | curl against the rehearsal server |
| Sun 11 Oct 22:20 | C. `SecurityPage` UI | `ui/src/settings/SecurityPage.tsx` type-checks and builds; not yet wired into SettingsView (Sourabh wires it) | PENDING visual check | `npx tsc --noEmit`, `npm run build` |

Note: `tests/test_trace.py` sent a key-shaped string through `remember` and expected OK. Build C refuses that call by
design, so the assertion now expects `FAILED: Refused`; the span is still recorded and the key is still hidden.
