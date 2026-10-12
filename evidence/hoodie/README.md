# Hoodie redesign: checks for the merge (Mon 12 Oct)

Branch `hoodie`, from main 30db22a. UI only (`ui/src`, `ui/public`): no API, contract or backend changes.

| Check | Result |
|---|---|
| `pytest` | 371 passed, 1 skipped |
| `npm run build` (`tsc -b && vite build`) | clean; the bundle drops three.js (327 KB JS) |
| Screens, light (1440×900) | `1-chat` `2-crew-room` `3-board` `4-settings` `5-settings-phone` `6-profile-scout` `7-jobs` |
| Phone (390×844) | `8-phone-chat-390` `9-phone-crew-390` |
| Dark | `10-dark-chat` `11-dark-crew-room` `12-dark-settings` |
| Console errors | 0 on every screen (`console-errors.json`, `proofs.json`) |
| Approvals | a waiting card renders (`proof-approval-card-light/dark`); Approve sends `POST /api/approvals/<id> {"ok":true,"always":false}` (`proof-approval-approved`) |
| Stop | the header's Stop sends `POST /api/chats/<id>/stop` |
| Phone pairing | "Pair a phone" sends `POST /api/phones/pair` and the panel shows the QR, the code and the link (`proof-phone-pairing-panel`) |
| Ctrl+Alt+Q | the hotkey lives in the backend (unchanged); `tests/test_operator.py` passes, and the Operator page still explains it (`proof-operator-ctrl-alt-q`) |

How the shots were taken: `python -m teamloop` from this worktree on port 8795, with a copy of the workspace and no keys.
In the proofs, `/api/state` was patched to hold one waiting approval and a busy chat, and the three POSTs were
intercepted and recorded, so no real click, tunnel or model call happened.

What changed:
- Hoodie tokens: light is the default, with dark as well. There are no gradients, glass or glows.
- Fonts are system stacks (Bricolage Grotesque, Figtree and JetBrains Mono when installed). There's no CDN, so the app
  works offline.
- `Icon.tsx` replaces every emoji and stock glyph.
- Every crew bot is the mascot: S uses its real frames (`ui/public/mascot/*.webp`). Desk, Web, Scout, Inbox and Writer use the same frames with only the hoodie recoloured (`ui/public/mascot/<bot>/`, 9 moods each). Bots people build keep the hood drawing.
- Second pass: every screen is rebuilt to the approved mockup (https://claude.ai/artifact/JUs1XHLmxnKgTrBWSD6uuF), with real data only. Where the app has no data for something the mockup shows (tool counts, step durations), it is left out rather than invented.
- The Crew Room is 2D; three.js is no longer imported.
- Sourabh's `logo.svg`, `app-icon.png` and `icons/` are untouched.
