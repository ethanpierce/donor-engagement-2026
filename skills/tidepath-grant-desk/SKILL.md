---
name: tidepath-grant-desk
description: Tidepath grant drafting from approved facts only (facts.json with fact, source, approved_by, date), within word limits, with [source] tags and MISSING flags; and grant_budget.py for spent and left per budget category in the funder fiscal year from a QuickBooks CSV export. Use in the Grants and finance room.
---

# Tidepath Grant Desk

Staff approve every fact, every draft and every budget number. A person
submits the application on the funder website. You never submit.

## 1. Approved-fact library

The library is `$AUTOWORKER_HUB_WORKSPACE/tidepath/facts.json`.
`samples/facts.json` is a made-up example. Schema, one object per fact:

```json
{"id": "F01", "fact": "...", "source": "2025 annual report p.4",
 "approved_by": "Alex", "date": "2026-09-12"}
```

- A fact without `source`, `approved_by` and `date` is not approved. Do not use it.
- To add a fact, show it to staff with its source. Add it only after staff
  approve, with their name in `approved_by` and today's date.
- Facts older than 18 months: use them, but tell staff the date.

## 2. Drafting an answer

1. Read the question, the word limit and the funder's scoring notes.
2. List the facts the answer needs. Find each in the library.
3. Write the answer with only those facts. Put `[source]` right after each
   claim, using the fact `source` value.
4. For each needed fact that is not in the library, write
   `MISSING: <what is needed>` in the text. Never fill the gap.
5. Count the words without the `[source]` tags. Stay at or under the limit.
   Print the count at the end: `Words: 142 / 150`.
6. Post the draft for staff review. Staff approve or edit it.

Template:

```
<answer text with [source] tags and MISSING: flags>

Words: <n> / <limit>
Facts used: F01, F04
MISSING: <list, or none>
```

## 3. Grant budget report

`python3 scripts/grant_budget.py <quickbooks.csv> <budget.json> [--as-of YYYY-MM-DD]`

- The QuickBooks CSV export needs `Date`, `Class`, `Account`, `Amount`
  columns (Transaction Detail by Account, exported as CSV). `Class` is the
  grant. `Account` is the budget category.
- The budget JSON has `grant`, `class`, `funder`, `fiscal_year_start_month`
  (7 = July, 10 = October, 1 = January), optional `spend_by`, and
  `categories` with the budget per category.
- The report covers the funder fiscal year that holds `--as-of`. It shows
  budget, spent, left and percent used per category, the spend-by date and
  the days left. `WARNING` marks a category over 90 percent used.
- `samples/qb-export.csv`, `samples/budget-childfund.json` (July start) and
  `samples/budget-county.json` (October start) are made up.

Post the report for staff. Never move money between categories. Tell staff
to ask the funder about any category over budget.
