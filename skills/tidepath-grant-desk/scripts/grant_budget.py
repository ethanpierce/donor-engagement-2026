"""Spent and left per grant budget category in the funder fiscal year.

Usage: python3 grant_budget.py QUICKBOOKS.csv BUDGET.json [--as-of YYYY-MM-DD] [--json]
"""
import argparse
import csv
import json
import sys
from datetime import date, timedelta

WARN_AT = 0.90


def fiscal_year(as_of, start_month):
    year = as_of.year if as_of.month >= start_month else as_of.year - 1
    start = date(year, start_month, 1)
    end = date(year + 1, start_month, 1) - timedelta(days=1)
    return start, end


def amount(text):
    t = text.replace(",", "").replace("$", "").strip()
    if t.startswith("(") and t.endswith(")"):
        t = "-" + t[1:-1]
    return float(t or 0)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("csv")
    p.add_argument("budget")
    p.add_argument("--as-of", default=date.today().isoformat())
    p.add_argument("--json", action="store_true")
    a = p.parse_args()
    as_of = date.fromisoformat(a.as_of)
    with open(a.budget, encoding="utf-8") as f:
        budget = json.load(f)
    if budget["fiscal_year_start_month"] not in range(1, 13):
        sys.exit("ERROR: fiscal_year_start_month must be 1..12")
    start, end = fiscal_year(as_of, budget["fiscal_year_start_month"])
    spend_by = date.fromisoformat(budget["spend_by"]) if budget.get("spend_by") else end

    spent = {c: 0.0 for c in budget["categories"]}
    unbudgeted = {}
    with open(a.csv, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row.get("Class", "").strip() != budget["class"]:
                continue
            d = date.fromisoformat(row["Date"].strip())
            if not (start <= d <= min(end, as_of)):
                continue
            cat = row["Account"].strip()
            target = spent if cat in spent else unbudgeted
            target[cat] = target.get(cat, 0.0) + amount(row["Amount"])

    rows = []
    for cat, b in budget["categories"].items():
        s = spent[cat]
        rows.append({"category": cat, "budget": b, "spent": s, "left": b - s,
                     "used_pct": round(100 * s / b, 1) if b else 0.0, "warning": b > 0 and s / b > WARN_AT})
    result = {"grant": budget["grant"], "fiscal_year": [start.isoformat(), end.isoformat()],
              "as_of": as_of.isoformat(), "spend_by": spend_by.isoformat(),
              "days_left": (spend_by - as_of).days, "categories": rows, "unbudgeted": unbudgeted}
    if a.json:
        print(json.dumps(result, indent=2))
        return
    print(f"{budget['grant']}: fiscal year {start} to {end}, as of {as_of}")
    print(f"Spend by {spend_by} ({result['days_left']} days left)")
    print(f"{'Category':<22}{'Budget':>10}{'Spent':>10}{'Left':>10}{'Used':>8}")
    for r in rows:
        flag = "  WARNING: over 90% used" if r["warning"] else ""
        print(f"{r['category']:<22}{r['budget']:>10,.0f}{r['spent']:>10,.0f}{r['left']:>10,.0f}{r['used_pct']:>7.1f}%{flag}")
    tb = sum(r["budget"] for r in rows)
    ts = sum(r["spent"] for r in rows)
    print(f"{'Total':<22}{tb:>10,.0f}{ts:>10,.0f}{tb - ts:>10,.0f}{100 * ts / tb if tb else 0:>7.1f}%")
    for cat, s in unbudgeted.items():
        print(f"NOTE: {s:,.0f} charged to '{cat}', which is not in the grant budget. Ask staff.")


if __name__ == "__main__":
    main()
