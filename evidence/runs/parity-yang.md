# Parity and build checks: jrkrishh (Yang's side)

One row per piece. PASS only when the outcome was seen.

| Date (IST) | Piece | Check | Result | Evidence |
|---|---|---|---|---|
| Sun 11 Oct 21:55 | C. Key security: tool calls carrying a key | `tests/test_security.py`: web_search with a fake key in the query is refused, logged as `{ts, bot, tool, what}` with no key text, and listed by `GET /api/security` | PASS | pytest, 258 passed / 1 skipped |
| Sun 11 Oct 21:55 | C. Programs get no keys | `$env:GROQ_API_KEY` is empty inside `terminal.run` while a harmless variable still passes | PASS | `test_programs_get_no_keys` |
| Sun 11 Oct 21:55 | C. File tools refuse secret files | `read_file` refuses `.env`, `.env.local`, `teamloop.db`, `keys.vault`; `.env.example` still reads | PASS | `test_file_tools_refuse_secret_files` |
| Sun 11 Oct 21:55 | C. `GET /api/security` live | `scripts/rehearse.py` on 8791 answered `{"locked":0,"names":[],"blocked":[]}` | PASS | curl against the rehearsal server |
| Sun 11 Oct 21:55 | C. `SecurityPage` UI | `ui/src/settings/SecurityPage.tsx` type-checks and builds; not yet wired into SettingsView (Sourabh wires it) | PASS (mounted in a local, uncommitted build; real wiring is Sourabh's) | `evidence/ui/keys-cleanup-and-security-yang.jpg`, `evidence/ui/keys-and-security-375-yang.jpg` |
| Sun 11 Oct 22:05 | E. Key rows | `GET /api/keys/entries`: one row per key, masked `…abcd`, `unchecked` until tested, source vault/env; no key text in the response | PASS | `tests/test_key_entries.py` (5 tests) |
| Sun 11 Oct 22:05 | E. Test all, live | Rehearsal server with fake keys only: 2 fake Groq keys in the vault and 1 fake Gemini key in env. "Test all again" called the real providers: Groq answered 401, so both rows show "Rejected: … (401/403)"; Gemini gave no 401/403, so its row says "No clear answer" | PASS | `evidence/ui/keys-list-tested-yang.jpg` |
| Sun 11 Oct 22:05 | E. Clean up, live | "Clean up" removed both rejected vault keys ("Removed 2 rejected keys."); the env key stayed and its Remove is disabled ("from .env"); `DELETE` on it is a 409 in tests | PASS | `evidence/ui/keys-cleanup-and-security-yang.jpg` |
| Sun 11 Oct 22:05 | E. Phone width | KeysList and SecurityPage at 375x812: no sideways scroll, rows wrap | PASS | `evidence/ui/keys-and-security-375-yang.jpg` |

Notes:
- `tests/test_trace.py` sent a key-shaped string through `remember` and expected OK. Build C refuses that call by design,
  so the assertion now expects `FAILED: Refused`; the span is still recorded and the key is still hidden.
- **UI bug found on the way (Sourabh's index.css):** `.page` is a fixed-height flex column with `overflow:auto`, and
  `.list` has `overflow:hidden` with the default `flex-shrink:1`. As soon as a Settings page is taller than the window,
  every list collapses to a sliver instead of the page scrolling (API keys page with several keys, any long page on a
  phone). Repro: open Settings → API keys with enough content to overflow, then measure `ul.list` heights (32/21/14 px
  against scrollHeight 292/188/125). Fix that worked in the browser: `.page > * { flex-shrink: 0 }`. The screenshots
  above were taken with that one rule injected in the browser only, not committed.

