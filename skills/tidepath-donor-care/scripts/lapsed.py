"""Find late regular donors and failed monthly gifts in a gift CSV.

Usage: python3 lapsed.py GIFTS.csv [--today YYYY-MM-DD] [--json]
CSV columns: donor_id,name,date,amount,recurring[,status]
(recurring: monthly or empty; status: paid (default) or failed, a declined charge).
"""
import argparse
import csv
import json
import statistics
from collections import Counter, defaultdict
from datetime import date, timedelta

MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def add_month(d):
    y, m = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    for day in (d.day, 30, 29, 28):
        try:
            return date(y, m, day)
        except ValueError:
            continue


def analyse(rows, today):
    donors = defaultdict(list)
    for r in rows:
        donors[r["donor_id"]].append(r)
    out = []
    for did, rows_ in donors.items():
        rows_.sort(key=lambda g: g["date"])
        failed = [g for g in rows_ if (g.get("status") or "").strip().lower() == "failed"]
        gifts = [g for g in rows_ if g not in failed]
        if not gifts:
            continue
        dates = [date.fromisoformat(g["date"]) for g in gifts]
        amounts = [float(g["amount"]) for g in gifts]
        last = dates[-1]
        info = {
            "donor_id": did,
            "name": gifts[-1]["name"],
            "last_gift": last.isoformat(),
            "usual_amount": statistics.median(amounts),
            "usual_month": MONTHS[Counter(d.month for d in dates).most_common(1)[0][0] - 1],
        }
        if any(g.get("recurring", "").strip() == "monthly" for g in rows_):
            expected = add_month(last)
            late_by = (today - expected).days
            fail = [g for g in failed if g["date"] > gifts[-1]["date"] and g["date"] <= today.isoformat()]
            if fail:
                out.append(dict(info, status="FAILED MONTHLY", cadence="monthly", failed_on=fail[-1]["date"],
                                expected=expected.isoformat(), days_late=max(late_by, 0)))
            elif late_by > 7:
                out.append(dict(info, status="LATE MONTHLY", cadence="monthly",
                                expected=expected.isoformat(), days_late=late_by))
        elif len(dates) >= 3:
            gap = statistics.median((b - a).days for a, b in zip(dates, dates[1:]))
            expected = last + timedelta(days=gap)
            since = (today - last).days
            if since > gap * 1.25:
                out.append(dict(info, status="LATE REGULAR", cadence=f"every {gap:.0f} days",
                                expected=expected.isoformat(), days_late=(today - expected).days))
    return sorted(out, key=lambda x: (x["status"] != "FAILED MONTHLY", -x["days_late"]))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("csv")
    p.add_argument("--today", default=date.today().isoformat())
    p.add_argument("--json", action="store_true")
    a = p.parse_args()
    with open(a.csv, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    res = analyse(rows, date.fromisoformat(a.today))
    if a.json:
        print(json.dumps(res, indent=2))
        return
    if not res:
        print("No late or failed regular gifts.")
    for r in res:
        if r["status"] == "FAILED MONTHLY":
            print(f"FAILED MONTHLY: {r['name']} ({r['donor_id']}) card payment failed {r['failed_on']}, "
                  f"usual ${r['usual_amount']:.0f} monthly, last paid gift {r['last_gift']}")
            continue
        print(f"{r['status']}: {r['name']} ({r['donor_id']}) last gift {r['last_gift']}, "
              f"usual ${r['usual_amount']:.0f} {r['cadence']}, usual month {r['usual_month']}, "
              f"expected {r['expected']}, {r['days_late']} days late")


if __name__ == "__main__":
    main()
