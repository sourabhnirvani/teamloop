"""TeamLoop's 24-month business plan from the cfo.ai brief (HANDOFF.md section 4), for three scenarios.

    python scripts/business_plan.py        writes evidence/cfo/teamloop-plan.md and teamloop-plan-<scenario>.csv

The same inputs go into cfo.ai when the team has access. cfo.ai's trial needs a card and nobody on the team will pay,
so this script computes the plan meanwhile. Every input is listed at the top; change one and re-run.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "evidence" / "cfo"
MONTHS = 24
START = (2026, 11)  # November 2026
INR = 84.0          # rupees per dollar, for the INR column

# ---- prices ------------------------------------------------------------------------------------------------------
PRO_PRICE = 5.0       # $ per month (Rs 299 in India), for phone access when away, unlimited routines and priority fixes
TEAM_PRICE = 12.0     # $ per seat per month, from month 9

# ---- costs (real where we know them, conservative where we don't) ----------------------------------------------------
INFERENCE_PER_USER = 0.0   # REAL: TeamLoop runs on free models with each person's own free keys, or locally (Ollama)
HUB_PER_USER = 0.0         # REAL: the phone hub runs on each person's own free Cloudflare account, not ours
SUPPORT_PER_PRO = 0.20     # assumption: email, backups and support tooling per Pro user per month
BASE_HOSTING = 50.0        # assumption: website, update channel and domain, per month
PAYMENT_FEES = 0.03        # assumption: 3% card or UPI fees on revenue
MARKETING = (100.0, 400.0)  # assumption: per month for months 1-6, then after
FOUNDER_PAY = 1200.0       # assumption: per founder per month from month 7 (unpaid for the first 6)
FOUNDERS = 2
START_CASH = 3000.0        # assumption: founders' savings, no outside funding


@dataclass(frozen=True)
class Scenario:
    name: str
    first_users: int
    growth_first_year: float   # monthly growth in free users, months 2-12
    growth_after: float        # monthly growth from month 13
    to_pro: float              # share of NEW free users who go Pro
    pro_churn: float           # share of Pro users who cancel each month
    team_offices_start: int    # offices on Team in month 9 (5 seats each)
    team_offices_added: int    # new offices each month after that
    lean: bool = False         # founders draw pay only in months the revenue covers it (bootstrapped)


SCENARIOS = [
    Scenario("pessimistic", 300, 0.15, 0.06, 0.015, 0.04, 1, 1),
    Scenario("base", 300, 0.25, 0.10, 0.03, 0.04, 2, 2),
    Scenario("optimistic", 300, 0.35, 0.14, 0.05, 0.04, 3, 3),
    Scenario("base, founders paid only from revenue", 300, 0.25, 0.10, 0.03, 0.04, 2, 2, lean=True),
]


def month_label(i: int) -> str:
    y, m = START
    m += i
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1
    return f"{y}-{m:02d}"


def run(s: Scenario) -> list[dict]:
    rows, free, pro, cash = [], 0.0, 0.0, START_CASH
    for i in range(MONTHS):
        month = i + 1
        new_free = s.first_users if month == 1 else free * (s.growth_first_year if month <= 12 else s.growth_after)
        free += new_free
        pro = pro * (1 - s.pro_churn) + new_free * s.to_pro
        seats = 0 if month < 9 else 5 * (s.team_offices_start + s.team_offices_added * (month - 9))
        revenue = PRO_PRICE * pro + TEAM_PRICE * seats
        running = (BASE_HOSTING + SUPPORT_PER_PRO * pro + (INFERENCE_PER_USER + HUB_PER_USER) * free
                   + PAYMENT_FEES * revenue + (MARKETING[0] if month <= 6 else MARKETING[1]))
        pay = 0.0 if month <= 6 else FOUNDER_PAY * FOUNDERS
        if s.lean:  # bootstrapped: the founders take what the month's profit allows, up to their full pay
            pay = max(0.0, min(pay, revenue - running))
        costs = running + pay
        profit = revenue - costs
        cash += profit
        rows.append({"month": month_label(i), "free_users": round(free), "pro_users": round(pro), "team_seats": seats,
                     "revenue_usd": round(revenue, 2), "costs_usd": round(costs, 2), "profit_usd": round(profit, 2),
                     "cash_usd": round(cash, 2), "cash_inr": round(cash * INR)})
    return rows


def summary(s: Scenario, rows: list[dict]) -> dict:
    # break-even: the first month from month 7 (when the founders start being paid) with a profit, staying profitable
    be = next((r["month"] for k, r in enumerate(rows) if k >= 6 and all(x["profit_usd"] >= 0 for x in rows[k:])), None)
    broke = next((r["month"] for r in rows if r["cash_usd"] < 0), None)
    low = min(rows, key=lambda r: r["cash_usd"])
    return {"scenario": s.name, "break_even": be or "not within 24 months", "cash_runs_out": broke or "never",
            "lowest_cash": f"${low['cash_usd']:,.0f} ({low['month']})", "m24_revenue": rows[-1]["revenue_usd"],
            "m24_users": f"{rows[-1]['free_users']:,} free / {rows[-1]['pro_users']:,} Pro / {rows[-1]['team_seats']} seats",
            "m24_cash": rows[-1]["cash_usd"], "funding_needed": max(0.0, -low["cash_usd"])}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    sums, base_rows = [], []
    for s in SCENARIOS:
        rows = run(s)
        with open(OUT / f"teamloop-plan-{s.name.split(',')[0]}{'-lean' if s.lean else ''}.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        sums.append(summary(s, rows))
        if s.name == "base":
            base_rows = rows
    lines = ["# TeamLoop business plan: 24 months from November 2026",
             "",
             "Computed by `scripts/business_plan.py` from the cfo.ai brief (HANDOFF.md section 4). These are the inputs "
             "for cfo.ai: its 14-day trial needs a card, and nobody on the team will pay, so this file is the plan "
             "until the team has access.",
             "",
             "**Real figures:** inference costs $0 per user (free models with each person's own free keys, or local "
             "Ollama/LM Studio), and the phone hub costs $0 per user (it runs on each person's own free Cloudflare "
             "account). **Everything else is an assumption**, listed below.",
             "",
             "## Scenarios",
             "| Scenario | Break-even (profitable from) | Cash runs out | Funding needed | Month-24 revenue | Month-24 users | Month-24 cash |",
             "|---|---|---|---|---|---|---|"]
    for x in sums:
        lines.append(f"| {x['scenario']} | {x['break_even']} | {x['cash_runs_out']} | ${x['funding_needed']:,.0f} | "
                     f"${x['m24_revenue']:,.0f}/month | {x['m24_users']} | ${x['m24_cash']:,.0f} |")
    base_sum = next(x for x in sums if x["scenario"] == "base")
    lean_sum = next(x for x in sums if "only from revenue" in x["scenario"])
    lines += ["",
              "## What the numbers say",
              f"- **As briefed, cash runs out in {base_sum['cash_runs_out']} in the base case.** Two founders' pay "
              f"(${FOUNDER_PAY * FOUNDERS:,.0f}/month from month 7) arrives long before revenue can carry it. The base "
              f"case needs about **${base_sum['funding_needed']:,.0f}** of outside money to reach break-even in "
              f"{base_sum['break_even']}.",
              f"- **Bootstrapped instead** (the founders draw pay only when the month's revenue covers it): cash "
              f"{'never runs out' if lean_sum['cash_runs_out'] == 'never' else 'runs out in ' + lean_sum['cash_runs_out']}, "
              f"and month-24 cash is ${lean_sum['m24_cash']:,.0f}. The founders are paid from revenue as it grows.",
              "- The levers, biggest first: how many free users go Pro (1.5% vs 5% decides everything), when the "
              "founders start drawing pay, and Team seats. Model and hosting costs barely matter: inference and the "
              "phone hub are $0 per user by design.",
              "",
              "## Assumptions",
              f"- Prices: Free (all six bots, local); Pro ${PRO_PRICE:.0f}/month (Rs 299), for phone access when away, "
              f"unlimited routines and priority fixes; Team ${TEAM_PRICE:.0f}/seat/month from month 9.",
              f"- Costs: ${BASE_HOSTING:.0f}/month base hosting; ${SUPPORT_PER_PRO:.2f} support per Pro user; "
              f"{PAYMENT_FEES:.0%} payment fees; marketing ${MARKETING[0]:.0f}/month for months 1-6, then "
              f"${MARKETING[1]:.0f}; {FOUNDERS} founders unpaid for 6 months, then ${FOUNDER_PAY:,.0f}/month each.",
              f"- Cash: ${START_CASH:,.0f} of savings, no outside funding.",
              "- Users: 300 free users in month 1. Base: +25%/month to month 12, then +10%; 3% of new users go Pro; "
              "4% of Pro users cancel each month; Team starts month 9 with 2 offices of 5 seats, +2 a month. "
              "Pessimistic: +15% then +6%, 1.5% go Pro, Team 1 office (+1). Optimistic: +35% then +14%, 5% go Pro, "
              "Team 3 offices (+3).",
              "",
              "## Base scenario, month by month (USD; INR at Rs 84/$ in the CSV)",
              "| Month | Free | Pro | Team seats | Revenue | Costs | Profit/loss | Cash |",
              "|---|---|---|---|---|---|---|---|"]
    for r in base_rows:
        lines.append(f"| {r['month']} | {r['free_users']:,} | {r['pro_users']:,} | {r['team_seats']} | "
                     f"${r['revenue_usd']:,.0f} | ${r['costs_usd']:,.0f} | ${r['profit_usd']:,.0f} | ${r['cash_usd']:,.0f} |")
    lines += ["", "CSV files, one per scenario: `teamloop-plan-pessimistic.csv`, `teamloop-plan-base.csv`, "
                  "`teamloop-plan-optimistic.csv`, `teamloop-plan-base-lean.csv`."]
    (OUT / "teamloop-plan.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for x in sums:
        print(x)


if __name__ == "__main__":
    main()
