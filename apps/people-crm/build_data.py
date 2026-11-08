"""Build the People CRM room app data from the Tidepath made-up demo data.

Usage: python3 build_data.py [--db /tmp/app.db]
Seeds the db with crm.py, reads it, and writes the JSON into index.html
between the DATA markers. crm.py is imported read-only for its dupe,
at-risk and report logic.
"""
import argparse, json, os, re, sqlite3, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
MARKET = os.path.normpath(os.path.join(HERE, "..", ".."))  # repo root: skills/ and demo-data/
SCRIPTS = os.path.join(MARKET, "skills/tidepath-crm/scripts")
WEEK, QUARTER = "2026-09-28", "2026Q3"

ap = argparse.ArgumentParser()
ap.add_argument("--db", default="/tmp/app.db")
a = ap.parse_args()
if os.path.exists(a.db):
    os.remove(a.db)
subprocess.run([sys.executable, os.path.join(SCRIPTS, "crm.py"), "--db", a.db, "seed",
                os.path.join(MARKET, "demo-data")], check=True, stdout=subprocess.DEVNULL)
sys.path.insert(0, SCRIPTS)
import crm  # noqa: E402

db = sqlite3.connect(a.db)
db.row_factory = sqlite3.Row
rows = lambda sql, *p: [dict(r) for r in db.execute(sql, p)]

people = rows("SELECT id, name, phone, email, address FROM people WHERE merged_into IS NULL ORDER BY name")
roles = {}
for r in rows("SELECT person_id, role FROM roles ORDER BY role"):
    roles.setdefault(r["person_id"], []).append(r["role"])
dupes = []
for score, p, q, reasons in crm.find_dupes(db):
    dupes.append({"key": "%d-%d" % (p["id"], q["id"]), "score": score, "reasons": reasons,
                  "a": p["id"], "b": q["id"]})
dupe_ids = {d["a"] for d in dupes} | {d["b"] for d in dupes}
for p in people:
    p["roles"] = roles.get(p["id"], [])
    p["possibleDuplicate"] = p["id"] in dupe_ids

name = {p["id"]: p["name"] for p in rows("SELECT id, name FROM people")}
kids = []
for s in rows("SELECT * FROM signups ORDER BY kid_id"):
    k = s["kid_id"]
    kids.append({
        "id": k, "name": name.get(k), "parent": name.get(s["parent_id"]),
        "signup": {"date": s["signup_date"], "grade": s["grade"], "school": s["school"], "programs": s["programs"]},
        "attendance": rows("SELECT date, session, status FROM attendance WHERE kid_id=? ORDER BY date, session", k),
        "mentors": [dict(m, mentor=name.get(m["mentor_id"])) for m in
                    rows("SELECT mentor_id, match_date, status FROM matches WHERE kid_id=? ORDER BY match_date", k)],
        "visits": [dict(v, volunteer=name.get(v["volunteer_id"])) for v in
                   rows("SELECT volunteer_id, date, hours, activity, note FROM visits WHERE kid_id=? ORDER BY date", k)],
        "urgent": [dict(u, reportedBy=name.get(u["reported_by"])) for u in
                   rows("SELECT date, need, status, reported_by FROM urgent WHERE person_id=? ORDER BY date", k)],
    })
risk = [dict(zip(["kid", "reason", "lastMeeting", "parent", "contact", "owner"], r)) for r in crm.at_risk(db, WEEK)]
m, checks, (s, e) = crm.report(db, QUARTER)
hours = rows("SELECT p.name, ROUND(SUM(v.hours),1) AS hours, COUNT(*) AS visits FROM visits v "
             "JOIN people p ON p.id=v.volunteer_id WHERE v.date>=? AND v.date<? GROUP BY v.volunteer_id "
             "ORDER BY hours DESC, p.name", s, e)
assert round(sum(h["hours"] for h in hours), 1) == m["volunteer hours"], "volunteer hours do not match the report"
risk_by_kid = {r["kid"]: r["reason"] for r in risk}
for k in kids:
    k["atRisk"] = risk_by_kid.get(k["name"])
# Relations shown under each name on the People tab.
rel = {}
add = lambda pid, text: rel.setdefault(pid, []).append(text)
for k in kids:
    add(k["id"], "child of " + (k["parent"] or "?"))
    p = [x for x in rows("SELECT parent_id FROM signups WHERE kid_id=?", k["id"])][0]["parent_id"]
    add(p, "parent of " + k["name"])
for r in rows("SELECT mentor_id, kid_id FROM matches WHERE status='active'"):
    add(r["mentor_id"], "mentor to " + name.get(r["kid_id"], "?"))
for r in rows("SELECT donor_id, ROUND(SUM(amount)) AS total, COUNT(*) AS n FROM donations GROUP BY donor_id"):
    add(r["donor_id"], "$%s given in %d gift%s" % (format(int(r["total"]), ","), r["n"], "" if r["n"] == 1 else "s"))
for p in people:
    p["relations"] = rel.get(p["id"], [])
data = {
    "week": WEEK, "people": people, "dupes": dupes, "kids": kids, "volunteerHours": hours, "atRisk": risk,
    "report": {"quarter": QUARTER, "start": s, "end": e, "measures": [[k, v] for k, v in m.items()],
               "checks": [{"check": c, "report": r, "source": sv, "ok": r == sv} for c, r, sv in checks]},
}
path = os.path.join(HERE, "index.html")
html = open(path).read()
blob = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
html = re.sub(r"(/\*DATA\*/).*?(/\*END\*/)", lambda mt: mt.group(1) + blob + mt.group(2), html, flags=re.S)
open(path, "w").write(html)
print("people=%d dupes=%d kids=%d atRisk=%d bytes=%d" % (len(people), len(dupes), len(kids), len(risk), len(html)))
