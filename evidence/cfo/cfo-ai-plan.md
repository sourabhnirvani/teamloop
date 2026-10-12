# The business plan inside cfo.ai (Mon 12 Oct, ~14:10–14:25 IST)

**Where it lives:** Yang's cfo.ai workspace, the one Sourabh was invited to. It needed **no card**: there was no paywall
and no trial prompt. These pages hold the model:
- **Model:** Main Scenario (the base case), plus 3 more scenarios: TeamLoop — Pessimistic, TeamLoop — Optimistic and
  TeamLoop — Bootstrapped base.
- **Pages:**
  - **TeamLoop — Business plan:** scenario results, costs, cash, and a runway simulator.
    https://app.cfo.ai/boopathi-cd140dfe/pages/f438d787-9996-4deb-bc1b-1505e6eccd2c (opens for workspace members)
  - **TeamLoop — Inputs:** editable pricing and assumptions.
  - **TeamLoop — Users and revenue:** acquisition, churn, offices, seats and paid revenue.

**How it was built:** we gave cfo.ai's AI CFO, Ari, the exact inputs of `teamloop-plan.md` (the HANDOFF section 4 brief,
with the real $0-per-user inference and phone-hub costs) in one message. Ari:
1. saved the inputs and pricing;
2. built linked user, revenue, cost and cash schedules for Nov 2026 – Oct 2028;
3. created the 3 extra scenarios;
4. reconciled revenue, founder pay, cash flow and cash across all 24 months in all 4 cases;
5. added a walkthrough.

Screenshots: `cfo-ai-plan-overview.jpg`, `cfo-ai-plan-scenarios.jpg`, `cfo-ai-plan-cash-bridge.jpg`.

## cfo.ai's results (USD; funding is extra to the $3,000 savings)
| Case | Sustained break-even | Cash runs out | Extra funding needed | Oct 2028 revenue | Oct 2028 cash | First profitable month | Full founder pay affordable |
|---|---|---|---|---|---|---|---|
| Base (Main Scenario) | Oct 2028 | May 2027 | $22,620 | $3,144 | −$22,469 | Oct 2028 | Oct 2028 |
| Pessimistic | not by Oct 2028 | May 2027 | $39,521 | $1,100 | −$39,521 | not by Oct 2028 | not by Oct 2028 |
| Optimistic | Dec 2027 | Jun 2027 | $6,887 | $10,661 | $28,918 | Feb 2027 | Dec 2027 |
| Bootstrapped base | Aug 2027 | never (through Oct 2028) | $0 | $3,144 | $18,331 | Aug 2027 | Oct 2028 |

## Cross-check against our own script (`scripts/business_plan.py`, `teamloop-plan.md`)
| Case | Script | cfo.ai | Match |
|---|---|---|---|
| Base | Oct 2028 · May 2027 · $22,620 · $3,144 · −$22,469 | the same | ✅ identical |
| Pessimistic | not within 24 months · May 2027 · $39,521 · $1,100 · −$39,521 | the same | ✅ identical |
| Optimistic | Dec 2027 · Jun 2027 · $6,886 · $10,661 · $28,918 | $6,887 funding | ✅ cfo.ai rounds funding up |
| Bootstrapped | Aug 2027 · never · $0 · $3,144 · month-24 cash $1,993 | month-24 cash $18,331 | ⚠ a policy difference, below |

The bootstrapped difference is a different founder-pay rule, not an error:
- **cfo.ai** pays the founders' full $2,400 only in months where revenue covers all other costs *and* the full draw;
  otherwise it pays nothing that month. Under that rule the founders are paid once, in Oct 2028, so cash builds up to
  $18,331.
- **The script** pays whatever revenue allows each month, which leaves $1,993.
- Both say the same thing: **bootstrapped, the company never runs out of cash**. How much the founders take home is the
  real trade-off.

## What cfo.ai pointed out (the reasoning beat for the video)
- **The decision that matters is founder pay, not inference cost.** In the base case, starting the $2,400/month draw
  in May 2027 exhausts cash that same month.
- **The optimistic case has a trap.** It turns profitable in Feb 2027 while the founders are unpaid, then goes back into
  losses once pay starts. Strong cash at the end doesn't remove the earlier funding gap.
- **Bootstrapped survives without funding, but the founders aren't paid.** "Company survival is not the same as funding
  your personal living costs."
- **Ari's recommendation:** use the bootstrapped base case as the operating guardrail unless the cash bridge (about
  $22.6k) is secured.
