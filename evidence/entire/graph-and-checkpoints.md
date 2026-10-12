# Entire bonus: entire-graph on TeamLoop, and checkpoints as our decision log (Mon 12 Oct, ~21:00 IST)

Two of the three Entire bonus items:
- **entire-graph:** finding code and assessing risky changes.
- **Checkpoints:** showing progress and key decisions.

Every command below runs on a clone of this repo. The raw outputs are in `evidence/entire/graph/`.

## entire-graph

`entire plugin install graph` installed **entire-graph v0.4.0**, Entire's official plugin, from
https://github.com/entireio/entire-graph. `entire graph doctor` reports `no_egress=true`: the graph is built and queried
entirely on the laptop.

`entire graph index` built the graph in 12 s:
- 241 files, **2,919 symbols** and **9,824 relations**: CALLS, IMPORTS, HANDLES_ROUTE, HANDLES_TOOL, DATA_FLOWS,
  FILE_CHANGES_WITH and more.
- Languages: Python 122 files, TypeScript 29, plus CSS, JSON and Markdown.
- 3 TSX files parsed with warnings, which the plugin marks as "degraded" completeness.

### 1. Assessing a risky change before submitting: was the redesign really "UI only"?

The Hoodie redesign was merged from Yang's branch two hours before the deadline. The demo video was recorded from tag
`video`. We claimed the redesign changed no backend code, and the graph checks that claim at the level of functions,
not lines:

    entire graph diff --base demo --head video -- teamloop/
    -> "No semantic entity changes detected."              (graph/diff-backend.txt)

    entire graph diff --base demo --head video -- ui/src
    -> 308 entity changes, ranked by dependents             (graph/diff-ui.txt)

The UI changes with the most dependents are:
- the removed 3D-room fields (`Rig.id`, 325 dependents)
- the reworked `status` function (116)
- the approval card's selectors (81)

So our own rehearsal check re-ran the approval card, Stop and the phone layout before the merge:
`evidence/hoodie/`, commit messages b5256c7 and 5356513.

**Decision:** merge, because the backend is untouched. Record the recorded build as tag `video`.

### 2. Reviewing a checkpoint: the phone fix after the video

    entire graph checkpoint 01M4R2Z68JJPDE0FTMD5F3B6XZ    (graph/checkpoint-phonefix.txt)

This checkpoint is commit f61f473, made after the video, which fixed the phone's stale logo and status bar. Three
entities changed:
- `ui/public/sw.js` (0 dependents)
- `ui/index.html` (0 dependents)
- the `App` body (2 dependents)

That's a small blast radius, so it was safe to keep after the video was cut.

### 3. Blast radius of the safety-critical code, and where the graph needs help

TeamLoop's promise is "it asks before acting as you". So we asked the graph what breaks if the approval path changes:

    entire graph impact --symbol teamloop/computer/gate.py:55   (Gate.ask)    graph/impact-gate-ask.txt
    entire graph impact --symbol click_risk                     (risk check)  graph/impact-click_risk.txt
    entire graph impact --symbol teamloop/crew/context.py:36    (TurnCtx.approve) graph/impact-approve.txt

**What the graph got right:** co-change coupling. `gate.py` historically changes together with:
- `risk.py`, `context.py` and `team.py`
- `bots.py` and `app.py`
- `tests/test_computer.py`

So any change to approvals has to re-run the risk tests too. We did:
- `tests/test_computer.py`, `test_discard_clicks.py` and `test_always_allow.py`: **40 passed, 1 skipped**
- `test_gate_approve_deny_and_timeout`: passed

**What it missed, which we checked by hand:** callers reached through a module or a duck-typed parameter.

| Symbol | Graph's callers | Real call sites (grep) |
|---|---|---|
| `click_risk` | 0 | 4 production sites (`risk.click_risk(...)` in pointer.py ×3, tools.py, browser/kit.py) + tests |
| `TurnCtx.approve` | 0 | 16 sites in 5 files (`ctx.approve(...)` from every risky tool) |
| `Gate.ask` | tests only | 1 production site (`self.crew.gate.ask(...)` in context.py) |

**Rule we took from this:** on safety paths, treat the graph's caller list as a lower bound and confirm with a text
search. The co-change list is the part to trust.

### 4. Finding code from a plain-language question

    entire graph search --query "approval gate: wait for the user's OK, time out as not done, always-allow rules"
    -> 1. teamloop/computer/gate.py Gate.rule_for   2. Gate.allow   ...
       VERIFY: python -m pytest tests/test_always_allow.py -k test_commands_are_only_allowed_exactly  (we ran it: passed)

A vaguer phrasing ("where the crew asks the user for approval...") ranked `Crew.post` first and the UI's `Approval`
card fifth (`graph/search-approval.txt`). The precise query found the gate and its covering test at once.

## Checkpoints: progress and key decisions

88 commits carry an `Entire-Checkpoint:` trailer (`checkpoint-trailers.md`). These are the decisions that shaped TeamLoop,
each traceable to the agent session that made it. Run `git log --format='%h %(trailers:key=Entire-Checkpoint,valueonly)'`
to map any of them.

| When | Commit | Checkpoint | Decision |
|---|---|---|---|
| Sat 10 Oct 23:45 | cb6051a | 01M4KGD401QZ3XHY2WDJFCJCEV | A "no" stays a no: a denied step is never retried behind the user's back |
| Sun 11 Oct 14:05 | f0a9b01 | 01M4N1NA68MZKNRY2N77VSCCEH | An unanswered approval card counts as a no for the rest of the job |
| Sun 11 Oct 15:05 | 4168a03 | 01M4N52P6P23YDXFF5JSDKN94M | "Always allow" exists, but only for exact actions, and Settings can undo it |
| Sun 11 Oct 15:16 | 0249685 | 01M4N5PBGFSJS23YD8YESDK6WH | The phone link is our own free Cloudflare hub that the laptop dials out to, with no open ports |
| Sun 11 Oct 20:54 | 3b68feb | 01M4NS1KYYMMVG4HN35984RHAV | Local models via Ollama's native API with a 16k context, so free and offline really works |
| Mon 12 Oct 08:12 | a003e15 | 01M4PZVKDHWBTSWVJYGBZ5TQ64 | A traced fabricated "saved" became an honest "Not done" (found with neatlogs) |
| Mon 12 Oct 08:37 | c6a53c7 | 01M4Q18SAADSWG0P14PPNS3ANV | Small local models: accept honest failures, zero fabrications |
| Mon 12 Oct 18:26 | f61f473 | 01M4R2Z68JJPDE0FTMD5F3B6XZ | After the video: fix the phone's stale logo cache, kept because the graph showed a small blast radius |

Not captured: Yang's day-2 sessions ran in the Claude desktop app, which Entire's Claude Code hook doesn't record. His
commits are in `git log`, but have no trailer.

Entire's `entire recap` needs a signed-in Entire account to show team activity, and ours isn't signed in. So the local
trailers above are the record.
