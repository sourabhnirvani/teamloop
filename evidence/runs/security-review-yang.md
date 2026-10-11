# Security review L: phone hub, pairing, approvals (jrkrishh, Sun 11 Oct ~22:30 IST)

Scope: `phone-hub/src/worker.js`, `teamloop/server/phones.py`, `teamloop/server/hub.py`, `teamloop/computer/gate.py`,
plus the laptop API they protect (`teamloop/server/app.py`). Everything was run on this machine against the real app
code. No real keys were used and nothing left the machine.

How to re-run:
- `.venv\Scripts\python.exe evidence\runs\security-probe-yang.py`: 44 attempts against the real app, in-process. Output is in
  `security-probe-yang.out.txt`.
- `node evidence/runs/worker-probe-yang.mjs`: the Worker's own path filter, with the Durable Object stubbed. Output is in
  `worker-probe-yang.out.txt`.

I did not run `wrangler dev`. The Worker's filter is pure JavaScript and was exercised directly. The hop from the Worker
to the laptop was exercised through `hub.answer()`, the same function the live websocket calls.

**Result: 44 attempts, 7 FAIL.** The phone side holds: pairing, cookies, removed phones, unpaired approvals, and path
tricks against the guard all PASS. The FAILs are against **the laptop itself**: a web page the person opens on the laptop
can drive TeamLoop.

## FAILs, worst first (Sourabh's files: repro plus a suggested fix for each)

### 1. HIGH: DNS rebinding gives any website full control of the laptop's TeamLoop
- **Repro:**
  - `GET /api/keys` with `Host: evil.example` answers **200**.
  - `POST /api/chats/dm-s/messages` with JSON `{"text": ...}`, `Host: evil.example:8790` and
    `Origin: http://evil.example:8790` answers **202**. The message is posted and the crew acts on it.
- **Why:** the server answers any `Host`. A page on a rebinding domain (TTL 0, re-resolved to 127.0.0.1) is then
  same-origin with `http://evil.example:8790`. CORS doesn't apply, so it can read every answer and send JSON.
- **What that means:**
  - The page can read chats and settings.
  - It can tell S to do things.
  - It can answer approval cards: it lists them with `GET /api/approvals`, then sends `POST /api/approvals/{id}` with
    `{"ok": true, "always": true}`.
- **Fix:** add a Host allowlist before everything else (Starlette `TrustedHostMiddleware` or a few lines in `guard`):
  - `localhost`, `127.0.0.1` and `[::1]`, on any port
  - `testclient`, for tests
  - `hub`, the base URL `hub.answer` uses
  - `*.trycloudflare.com`
  - the hub's own `*.workers.dev` host
  
  Anything else gets a 400.

### 2. MEDIUM: CSRF on POST endpoints that take no body (a plain cross-site form post runs them)
FastAPI already rejects a `text/plain` body for JSON models, so approving cards and sending messages by CSRF fail
(**PASS, 422**). Endpoints with **no body** run from any website, though (all answered 200 with `Origin: https://evil.example`):

| Endpoint | Effect when another site posts it |
|---|---|
| `POST /api/phones/pair` | **starts a cloudflared quick tunnel**, so the laptop is reachable from the internet, and mints a pairing code (the site can't read it) |
| `POST /api/hub/setup` | starts the Cloudflare sign-in and deploy flow |
| `POST /api/chats/{id}/stop`, `POST /api/jobs/{id}/stop` | stops the crew or a job |
| `POST /api/keys/test`, `POST /api/keys/cleanup` (mine, Build E) | re-tests keys, removes rejected vault keys |
| `POST /api/models/check` | spends free-tier calls |

**Fix:** in `guard`, refuse any non-GET/HEAD request whose `Origin` is present and whose host isn't the request's
`Host` (or localhost). Also refuse `Sec-Fetch-Site: cross-site` when it's sent. Phones (same origin as the hub or tunnel)
and the Electron app aren't affected.

### 3. LOW-MEDIUM: the SSE stream can be pulled through the hub and hangs the laptop side forever
- **Repro:**
  - The Worker blocks `/api/events` but passes `/api/%65vents`, `//x/api/events` and `/api/events/` to the laptop
    (`worker-probe-yang.out.txt`).
  - Starlette decodes `/api/%65vents` back to `/api/events`.
  - With a paired cookie, `hub.answer()` on `/api/events` never returns (I gave it 10 s): `ASGITransport` waits for a body
    that never ends.
- **Why it matters:** each such request leaves a task and an open stream on the laptop. One paired phone, or a stolen
  cookie, can pile them up.
- **Fix:** in `guard`, answer `404` to `/api/events` when `is_remote(request)`. Phones use `/api/events/poll`, so the
  stream has no remote use. Optionally, the Worker could compare on `decodeURIComponent(pathname)` with duplicate
  slashes collapsed.

### Notes (not FAIL)
- **Worker filter only:** the Worker's laptop-only filter also lets `/c%6Fnsole` and `//x/console` through. **The laptop
  stops them:** `/c%6Fnsole` gets 404, and `//x/console` comes out of `hub.answer` as `/console`, which also gets 404.
  Defence in depth works; the Worker list alone is not a boundary.
- **Pairing fail counter:** it is global and never resets after a success, so anyone who can reach `/pair` can wipe a
  code the person is about to type, by sending 10 wrong codes. That's an annoyance, not a bypass: there are 24^8
  possible codes and every one dies after 10 misses.

## PASSes (what held)
| Attempt | Result |
|---|---|
| Pair with a fresh code | 303. The cookie is `HttpOnly; Secure; SameSite=strict`, 1 year |
| Reuse a used code / use an expired code | 400 / 400 |
| Brute-force codes | every open code is wiped after 10 wrong tries |
| API without a cookie, from the tunnel or hub | 401 |
| Spoof `x-forwarded-for: 127.0.0.1` | 401: any proxy header counts as remote, whatever its value |
| `//api/chats`, `/API/chats`, `/api/../api/chats`, `/%61pi/chats`, `/api%2Fchats`, `/api/chats/` | 404 or 401, never data |
| `/docs`, `/DOCS`, `/docs/`, `/redoc`, `/openapi.json`, `/console`, `/c%6Fnsole` from remote | 404 |
| `//console` from remote | 200, but it is the app's own index page (byte-identical to `/`), not the console |
| Paired phone manages phones / opens `/docs`, `/console`, `/openapi.json` | 403 / 404 |
| Answer a card from an unpaired phone / with a removed phone's cookie | 401 / 401 |
| CSRF: approve a card or post a message with a `text/plain` JSON body | 422, rejected |
| CSRF on `/pair` | needs a live code from this laptop; the cookie's SameSite=Strict blocks riding a pairing |
| Hub hop with no proxy headers / `//host/...` path / phone's own `X-Forwarded-For` | 401 / 401 / 401: `hub.answer` always marks it remote |
| `/__laptop` without the secret | 404 at the Worker |

## Re-test after Sourabh's fixes (d096d93), Sun 11 Oct ~22:55 IST
I re-ran the same probe against main: **44 attempts, 0 FAIL** (`security-probe-yang.retest.out.txt`).
- DNS rebinding: a foreign `Host` now gets **400** "This address isn't TeamLoop's.", both for reading and for driving the crew.
- CSRF: every cross-site POST, with or without a body, now gets **403** "Only TeamLoop's own pages can do that.". No tunnel
  and no hub setup starts.
- SSE through the hub hop: `hub.answer` on `/api/events` now returns (no hang).
- Pairing, paired-phone access, removed cookies and the guard's path tricks still behave as before (all PASS).
