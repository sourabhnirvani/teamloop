# TeamLoop business plan: 24 months from November 2026

Computed by `scripts/business_plan.py` from the cfo.ai brief (HANDOFF.md section 4). These are the inputs for cfo.ai: its 14-day trial needs a card, and nobody on the team will pay, so this file is the plan until the team has access.

**Real figures:** inference costs $0 per user (free models with each person's own free keys, or local Ollama/LM Studio), and the phone hub costs $0 per user (it runs on each person's own free Cloudflare account). **Everything else is an assumption**, listed below.

## Scenarios
| Scenario | Break-even (profitable from) | Cash runs out | Funding needed | Month-24 revenue | Month-24 users | Month-24 cash |
|---|---|---|---|---|---|---|
| pessimistic | not within 24 months | 2027-05 | $39,521 | $1,100/month | 2,808 free / 28 Pro / 80 seats | $-39,521 |
| base | 2028-10 | 2027-05 | $22,620 | $3,144/month | 10,961 free / 245 Pro / 160 seats | $-22,469 |
| optimistic | 2027-12 | 2027-06 | $6,886 | $10,661/month | 39,233 free / 1,556 Pro / 240 seats | $28,918 |
| base, founders paid only from revenue | 2027-08 | never | $0 | $3,144/month | 10,961 free / 245 Pro / 160 seats | $1,993 |

## What the numbers say
- **As briefed, cash runs out in 2027-05 in the base case.** Two founders' pay ($2,400/month from month 7) arrives long before revenue can carry it. The base case needs about **$22,620** of outside money to reach break-even in 2028-10.
- **Bootstrapped instead** (the founders draw pay only when the month's revenue covers it): cash never runs out, and month-24 cash is $1,993. The founders are paid from revenue as it grows.
- The levers, biggest first: how many free users go Pro (1.5% vs 5% decides everything), when the founders start drawing pay, and Team seats. Model and hosting costs barely matter: inference and the phone hub are $0 per user by design.

## Assumptions
- Prices: Free (all six bots, local); Pro $5/month (Rs 299), for phone access when away, unlimited routines and priority fixes; Team $12/seat/month from month 9.
- Costs: $50/month base hosting; $0.20 support per Pro user; 3% payment fees; marketing $100/month for months 1-6, then $400; 2 founders unpaid for 6 months, then $1,200/month each.
- Cash: $3,000 of savings, no outside funding.
- Users: 300 free users in month 1. Base: +25%/month to month 12, then +10%; 3% of new users go Pro; 4% of Pro users cancel each month; Team starts month 9 with 2 offices of 5 seats, +2 a month. Pessimistic: +15% then +6%, 1.5% go Pro, Team 1 office (+1). Optimistic: +35% then +14%, 5% go Pro, Team 3 offices (+3).

## Base scenario, month by month (USD; INR at Rs 84/$ in the CSV)
| Month | Free | Pro | Team seats | Revenue | Costs | Profit/loss | Cash |
|---|---|---|---|---|---|---|---|
| 2026-11 | 300 | 9 | 0 | $45 | $153 | $-108 | $2,892 |
| 2026-12 | 375 | 11 | 0 | $54 | $154 | $-99 | $2,792 |
| 2027-01 | 469 | 13 | 0 | $66 | $155 | $-88 | $2,704 |
| 2027-02 | 586 | 16 | 0 | $81 | $156 | $-74 | $2,630 |
| 2027-03 | 732 | 20 | 0 | $100 | $157 | $-57 | $2,573 |
| 2027-04 | 916 | 25 | 0 | $123 | $159 | $-35 | $2,538 |
| 2027-05 | 1,144 | 31 | 0 | $153 | $2,861 | $-2,708 | $-170 |
| 2027-06 | 1,431 | 38 | 0 | $190 | $2,863 | $-2,674 | $-2,844 |
| 2027-07 | 1,788 | 47 | 10 | $356 | $2,870 | $-2,514 | $-5,358 |
| 2027-08 | 2,235 | 59 | 20 | $533 | $2,878 | $-2,344 | $-7,703 |
| 2027-09 | 2,794 | 73 | 30 | $725 | $2,886 | $-2,161 | $-9,864 |
| 2027-10 | 3,492 | 91 | 40 | $936 | $2,896 | $-1,961 | $-11,824 |
| 2027-11 | 3,842 | 98 | 50 | $1,090 | $2,902 | $-1,813 | $-13,637 |
| 2027-12 | 4,226 | 106 | 60 | $1,248 | $2,909 | $-1,661 | $-15,298 |
| 2028-01 | 4,648 | 114 | 70 | $1,410 | $2,915 | $-1,505 | $-16,803 |
| 2028-02 | 5,113 | 123 | 80 | $1,577 | $2,922 | $-1,345 | $-18,148 |
| 2028-03 | 5,625 | 134 | 90 | $1,749 | $2,929 | $-1,180 | $-19,328 |
| 2028-04 | 6,187 | 145 | 100 | $1,927 | $2,937 | $-1,010 | $-20,338 |
| 2028-05 | 6,806 | 158 | 110 | $2,110 | $2,945 | $-835 | $-21,173 |
| 2028-06 | 7,486 | 172 | 120 | $2,301 | $2,953 | $-653 | $-21,826 |
| 2028-07 | 8,235 | 188 | 130 | $2,499 | $2,963 | $-464 | $-22,289 |
| 2028-08 | 9,059 | 205 | 140 | $2,705 | $2,972 | $-267 | $-22,557 |
| 2028-09 | 9,964 | 224 | 150 | $2,920 | $2,982 | $-63 | $-22,620 |
| 2028-10 | 10,961 | 245 | 160 | $3,144 | $2,993 | $151 | $-22,469 |

CSV files, one per scenario: `teamloop-plan-pessimistic.csv`, `teamloop-plan-base.csv`, `teamloop-plan-optimistic.csv`, `teamloop-plan-base-lean.csv`.
