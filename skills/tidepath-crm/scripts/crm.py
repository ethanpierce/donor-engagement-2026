#!/usr/bin/env python3
"""Tidepath Family Alliance CRM. Python 3 stdlib only.

Usage: python3 crm.py [--db PATH] <command> [args]
DB default: $AUTOWORKER_WORKSPACE/tidepath/crm.db (tenant workspace, persists).
"""
import argparse
import csv
import datetime as dt
import difflib
import json
import os
import re
import sqlite3
import sys
import unicodedata

SCHEMA = """
CREATE TABLE IF NOT EXISTS people(id INTEGER PRIMARY KEY, name TEXT, phone TEXT, email TEXT,
  address TEXT, merged_into INTEGER);
CREATE TABLE IF NOT EXISTS contacts(person_id INTEGER, kind TEXT, value TEXT, UNIQUE(person_id, kind, value));
CREATE TABLE IF NOT EXISTS roles(person_id INTEGER, role TEXT, UNIQUE(person_id, role));
CREATE TABLE IF NOT EXISTS signups(id INTEGER PRIMARY KEY, kid_id INTEGER, parent_id INTEGER, grade TEXT,
  school TEXT, programs TEXT, signup_date TEXT);
CREATE TABLE IF NOT EXISTS counseling_notes(kid_id INTEGER, note TEXT);
CREATE TABLE IF NOT EXISTS attendance(id INTEGER PRIMARY KEY, kid_id INTEGER, date TEXT, session TEXT,
  status TEXT, UNIQUE(kid_id, date, session));
CREATE TABLE IF NOT EXISTS matches(id INTEGER PRIMARY KEY, mentor_id INTEGER, kid_id INTEGER, match_date TEXT,
  status TEXT);
CREATE TABLE IF NOT EXISTS visits(id INTEGER PRIMARY KEY, volunteer_id INTEGER, kid_id INTEGER, date TEXT,
  hours REAL, activity TEXT, note TEXT);
CREATE TABLE IF NOT EXISTS urgent(id INTEGER PRIMARY KEY, person_id INTEGER, need TEXT, reported_by INTEGER,
  date TEXT, status TEXT, resolved_date TEXT);
CREATE TABLE IF NOT EXISTS donations(id INTEGER PRIMARY KEY, donor_id INTEGER, date TEXT, amount REAL,
  frequency TEXT, campaign TEXT);
CREATE TABLE IF NOT EXISTS source_rows(id INTEGER PRIMARY KEY, source TEXT, row TEXT, outcome TEXT);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, at TEXT, action TEXT, detail TEXT, approved_by TEXT);
"""

SOURCES = {"signup": "signups.csv", "attendance": "attendance.csv", "mentors": "mentor_matches.csv",
           "volunteer_hours": "volunteer_hours.csv", "donations": "donations.csv"}


def default_db():
    ws = os.environ.get("AUTOWORKER_WORKSPACE") or os.environ.get("AUTOWORKER_HUB_WORKSPACE")
    if not ws:
        ws = os.path.join(os.path.expanduser("~"), "workspace")
    return os.path.join(ws, "tidepath", "crm.db")


def connect(path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    return db


# ---------- helpers ----------

def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", s.lower())).strip()


def norm_phone(p):
    d = re.sub(r"\D", "", p or "")
    return d[-10:] if len(d) >= 10 else ""


def norm_addr(a):
    a = norm(a)
    for k, v in (("street", "st"), ("avenue", "ave"), ("court", "ct"), ("northwest", "nw")):
        a = re.sub(r"\b%s\b" % k, v, a)
    return a.split(" miami")[0]


def table(headers, rows):
    if not rows:
        return "_No rows._"
    esc = lambda v: ("" if v is None else str(v)).replace("|", "/").replace("\n", " ")
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join(esc(v) for v in r) + " |" for r in rows]
    return "\n".join(out)


def live(db, pid):
    while True:
        r = db.execute("SELECT merged_into FROM people WHERE id=?", (pid,)).fetchone()
        if not r or not r["merged_into"]:
            return pid
        pid = r["merged_into"]


def add_contact(db, pid, kind, value):
    if value:
        db.execute("INSERT OR IGNORE INTO contacts VALUES(?,?,?)", (pid, kind, value.strip()))


def upsert_person(db, name, role, phone="", email="", address=""):
    """Exact normalized-name match reuses a record. Anything fuzzier goes to `dupes`."""
    name = name.strip()
    pid = None
    for r in db.execute("SELECT id, name FROM people WHERE merged_into IS NULL"):
        if norm(r["name"]) == norm(name):
            pid = r["id"]
            break
    if pid is None:
        pid = db.execute("INSERT INTO people(name, phone, email, address) VALUES(?,?,?,?)",
                         (name, phone or None, email or None, address or None)).lastrowid
    else:
        db.execute("UPDATE people SET phone=COALESCE(phone,?), email=COALESCE(email,?), address=COALESCE(address,?)"
                   " WHERE id=?", (phone or None, email or None, address or None, pid))
    add_contact(db, pid, "phone", phone)
    add_contact(db, pid, "email", email)
    add_contact(db, pid, "address", address)
    db.execute("INSERT OR IGNORE INTO roles VALUES(?,?)", (pid, role))
    return pid


def find_person(db, q):
    if str(q).isdigit():
        r = db.execute("SELECT * FROM people WHERE id=?", (live(db, int(q)),)).fetchone()
        return [r] if r else []
    rows = db.execute("SELECT * FROM people WHERE merged_into IS NULL").fetchall()
    nq = norm(q)
    exact = [r for r in rows if norm(r["name"]) == nq]
    if exact:
        return exact
    sub = [r for r in rows if nq in norm(r["name"])]
    if sub:
        return sub
    names = {norm(r["name"]): r for r in rows}
    return [names[n] for n in difflib.get_close_matches(nq, list(names), n=3, cutoff=0.6)]


def one_person(db, q, role=None):
    hits = find_person(db, q)
    if len(hits) != 1:
        if role and not hits:
            return upsert_person(db, q, role)
        raise SystemExit("ERROR: %s match(es) for %r: %s" % (len(hits), q, ", ".join(
            "%s (#%s)" % (h["name"], h["id"]) for h in hits) or "none"))
    if role:
        db.execute("INSERT OR IGNORE INTO roles VALUES(?,?)", (hits[0]["id"], role))
    return hits[0]["id"]


def record_source(db, source, row, outcome):
    db.execute("INSERT INTO source_rows(source, row, outcome) VALUES(?,?,?)", (source, json.dumps(row), outcome))


def add_visit(db, vol_id, kid_id, date, hours, activity, note, source):
    """Same volunteer + kid + date is one visit. Without a kid, same volunteer + date + note."""
    if kid_id:
        dup = db.execute("SELECT id FROM visits WHERE volunteer_id=? AND kid_id=? AND date=?",
                         (vol_id, kid_id, date)).fetchone()
    else:
        dup = db.execute("SELECT id FROM visits WHERE volunteer_id=? AND kid_id IS NULL AND date=? AND note=?",
                         (vol_id, date, note or "")).fetchone()
    if dup:
        return None
    return db.execute("INSERT INTO visits(volunteer_id, kid_id, date, hours, activity, note) VALUES(?,?,?,?,?,?)",
                      (vol_id, kid_id, date, hours, activity, note or "")).lastrowid


# ---------- import ----------

def import_csv(db, path, source):
    n = {"imported": 0, "duplicate": 0}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            outcome = "imported"
            if source == "signup":
                parent = upsert_person(db, row["parent_name"], "parent", row["parent_phone"], row["parent_email"],
                                       row["address"])
                kid = upsert_person(db, row["kid_name"], "kid", address=row["address"])
                if db.execute("SELECT 1 FROM signups WHERE kid_id=?", (kid,)).fetchone():
                    outcome = "duplicate"
                else:
                    db.execute("INSERT INTO signups(kid_id, parent_id, grade, school, programs, signup_date)"
                               " VALUES(?,?,?,?,?,?)", (kid, parent, row["grade"], row["school"], row["programs"],
                                                        row["signup_date"]))
                    if row.get("counseling_note"):
                        db.execute("INSERT INTO counseling_notes VALUES(?,?)", (kid, row["counseling_note"]))
            elif source == "attendance":
                kid = upsert_person(db, row["kid_name"], "kid")
                cur = db.execute("INSERT OR IGNORE INTO attendance(kid_id, date, session, status) VALUES(?,?,?,?)",
                                 (kid, row["date"], row["session"], row["status"].lower()))
                outcome = "imported" if cur.rowcount else "duplicate"
            elif source == "mentors":
                m = upsert_person(db, row["mentor_name"], "mentor", row["mentor_phone"], row["mentor_email"])
                db.execute("INSERT OR IGNORE INTO roles VALUES(?,?)", (m, "volunteer"))
                kid = upsert_person(db, row["kid_name"], "kid")
                if db.execute("SELECT 1 FROM matches WHERE mentor_id=? AND kid_id=?", (m, kid)).fetchone():
                    outcome = "duplicate"
                else:
                    db.execute("INSERT INTO matches(mentor_id, kid_id, match_date, status) VALUES(?,?,?,?)",
                               (m, kid, row["match_date"], row.get("status") or "active"))
            elif source == "volunteer_hours":
                v = upsert_person(db, row["volunteer_name"], "volunteer", row.get("volunteer_phone", ""))
                kid = upsert_person(db, row["kid_name"], "kid") if row.get("kid_name") else None
                vid = add_visit(db, v, kid, row["date"], float(row["hours"]), row.get("activity", ""),
                                row.get("note", ""), source)
                outcome = "imported" if vid else "duplicate"
                if vid and row.get("urgent_need"):
                    res = row.get("urgent_resolved_date") or None
                    db.execute("INSERT INTO urgent(person_id, need, reported_by, date, status, resolved_date)"
                               " VALUES(?,?,?,?,?,?)", (kid, row["urgent_need"], v, row["date"],
                                                        "resolved" if res else "open", res))
            elif source == "donations":
                d = upsert_person(db, row["donor_name"], "donor", row.get("donor_phone", ""), row.get("donor_email", ""))
                db.execute("INSERT INTO donations(donor_id, date, amount, frequency, campaign) VALUES(?,?,?,?,?)",
                           (d, row["date"], float(row["amount"]), row.get("frequency", ""), row.get("campaign", "")))
            else:
                raise SystemExit("ERROR: unknown source %r" % source)
            record_source(db, source, row, outcome)
            n[outcome] += 1
    db.commit()
    return n


def cmd_seed(db, a):
    rows = []
    for source, fname in SOURCES.items():
        p = os.path.join(a.dir, fname)
        if os.path.exists(p):
            n = import_csv(db, p, source)
            rows.append((fname, source, n["imported"], n["duplicate"]))
    print("**Seeded from %s**\n" % a.dir)
    print(table(["file", "source", "imported", "duplicates skipped"], rows))


def cmd_import(db, a):
    n = import_csv(db, a.csv, a.source)
    print(table(["file", "source", "imported", "duplicates skipped"],
                [(os.path.basename(a.csv), a.source, n["imported"], n["duplicate"])]))


# ---------- dupes / merge ----------

def name_match(a, b):
    """Return (score 0..1, reasons) for two person names."""
    ta, tb = norm(a).split(), norm(b).split()
    if not ta or not tb:
        return 0.0, []
    reasons = []
    if ta[-1] != tb[-1]:
        r = difflib.SequenceMatcher(None, ta[-1], tb[-1]).ratio()
        if r < 0.85:
            return 0.0, []
        reasons.append("last names similar (%s / %s)" % (ta[-1], tb[-1]))
        score = 0.6
    else:
        reasons.append("same last name '%s'" % ta[-1].title())
        score = 0.5
    fa, fb = ta[0], tb[0]
    if fa == fb:
        reasons.append("same first name '%s'" % fa.title())
        score += 0.4
    elif (len(fa) == 1 and fb.startswith(fa)) or (len(fb) == 1 and fa.startswith(fb)):
        reasons.append("first initial '%s.' fits '%s'" % (min(fa, fb, key=len).upper(), max(fa, fb, key=len).title()))
        score += 0.25
    elif difflib.SequenceMatcher(None, fa, fb).ratio() >= 0.8:
        reasons.append("first names similar (%s / %s)" % (fa, fb))
        score += 0.2
    else:
        return 0.0, []
    mid = set(ta[1:-1]) ^ set(tb[1:-1])
    if mid:
        reasons.append("middle name/initial differs only (%s)" % " ".join(sorted(mid)).upper())
    if a.strip() != b.strip() and norm(a) == norm(b):
        reasons.append("same name apart from accents/punctuation")
    return min(score, 1.0), reasons


def contacts_of(db, pid):
    c = {"phone": set(), "email": set(), "address": set()}
    for r in db.execute("SELECT kind, value FROM contacts WHERE person_id=?", (pid,)):
        v = {"phone": norm_phone, "email": lambda x: x.strip().lower(), "address": norm_addr}[r["kind"]](r["value"])
        if v:
            c[r["kind"]].add(v)
    return c


def find_dupes(db):
    people = db.execute("SELECT id, name FROM people WHERE merged_into IS NULL ORDER BY id").fetchall()
    cons = {p["id"]: contacts_of(db, p["id"]) for p in people}
    roles = {p["id"]: role_list(db, p["id"]) for p in people}
    out = []
    for i, p in enumerate(people):
        for q in people[i + 1:]:
            ns, reasons = name_match(p["name"], q["name"])
            cp, cq = cons[p["id"]], cons[q["id"]]
            extra = 0.0
            if cp["phone"] & cq["phone"]:
                reasons.append("same phone"); extra += 0.3
            if cp["email"] & cq["email"]:
                reasons.append("same email"); extra += 0.3
            if cp["address"] & cq["address"]:
                reasons.append("same address"); extra += 0.2
            if ns == 0.0:
                continue  # different names; shared household contact is not a duplicate person
            if "kid" in roles[p["id"]] and "kid" in roles[q["id"]] and ns < 0.9:
                continue  # siblings share last name and address
            score = round(min(1.0, ns * 0.6 + extra), 2)
            if score >= 0.5:
                out.append((score, p, q, reasons))
    out.sort(key=lambda x: -x[0])
    return out


def cmd_dupes(db, a):
    d = find_dupes(db)
    print("**Candidate duplicates** (review only; nothing merged)\n")
    print(table(["score", "keep?", "drop?", "roles", "reasons"],
                [(s, "%s (#%s)" % (p["name"], p["id"]), "%s (#%s)" % (q["name"], q["id"]),
                  "/".join(role_list(db, p["id"])) + " + " + "/".join(role_list(db, q["id"])), "; ".join(r))
                 for s, p, q, r in d]))
    if d:
        print("\nMerge needs staff approval: `merge <keep_id> <drop_id> --approved-by <staff name>`")


def cmd_merge(db, a):
    if not (a.approved_by or "").strip():
        raise SystemExit("ERROR: merge needs --approved-by <staff name>")
    keep, drop = live(db, a.keep_id), live(db, a.drop_id)
    if keep == drop:
        raise SystemExit("ERROR: same person")
    k = db.execute("SELECT * FROM people WHERE id=?", (keep,)).fetchone()
    d = db.execute("SELECT * FROM people WHERE id=?", (drop,)).fetchone()
    if not k or not d:
        raise SystemExit("ERROR: unknown id")
    moved = {}
    for tbl, cols in (("signups", ["kid_id", "parent_id"]), ("attendance", ["kid_id"]),
                      ("matches", ["mentor_id", "kid_id"]), ("visits", ["volunteer_id", "kid_id"]),
                      ("urgent", ["person_id", "reported_by"]), ("donations", ["donor_id"]),
                      ("counseling_notes", ["kid_id"])):
        for c in cols:
            n = db.execute("UPDATE OR IGNORE %s SET %s=? WHERE %s=?" % (tbl, c, c), (keep, drop)).rowcount
            if n:
                moved["%s.%s" % (tbl, c)] = n
    db.execute("INSERT OR IGNORE INTO roles SELECT ?, role FROM roles WHERE person_id=?", (keep, drop))
    db.execute("INSERT OR IGNORE INTO contacts SELECT ?, kind, value FROM contacts WHERE person_id=?", (keep, drop))
    db.execute("UPDATE people SET phone=COALESCE(phone,?), email=COALESCE(email,?), address=COALESCE(address,?)"
               " WHERE id=?", (d["phone"], d["email"], d["address"], keep))
    db.execute("UPDATE people SET merged_into=? WHERE id=?", (keep, drop))
    detail = {"keep": [keep, k["name"]], "drop": [drop, d["name"]], "moved": moved}
    db.execute("INSERT INTO audit(at, action, detail, approved_by) VALUES(?,?,?,?)",
               (dt.datetime.now().isoformat(timespec="seconds"), "merge", json.dumps(detail), a.approved_by.strip()))
    db.commit()
    print("**Merged** %s (#%s) into %s (#%s), approved by %s\n" % (d["name"], drop, k["name"], keep, a.approved_by))
    print(table(["history moved", "rows"], sorted(moved.items())))


# ---------- person ----------

def role_list(db, pid):
    order = ["kid", "parent", "mentor", "volunteer", "donor"]
    rs = [r["role"] for r in db.execute("SELECT role FROM roles WHERE person_id=?", (pid,))]
    return sorted(rs, key=lambda r: order.index(r) if r in order else 99)


def pname(db, pid):
    if not pid:
        return ""
    r = db.execute("SELECT name FROM people WHERE id=?", (pid,)).fetchone()
    return r["name"] if r else ""


def cmd_person(db, a):
    hits = find_person(db, a.query)
    if not hits:
        raise SystemExit("ERROR: no person matches %r" % a.query)
    if len(hits) > 1:
        print("**%d matches**, pick an id:\n" % len(hits))
        print(table(["id", "name", "roles"], [(h["id"], h["name"], "/".join(role_list(db, h["id"]))) for h in hits]))
        return
    p = hits[0]
    pid = p["id"]
    print("**%s** (#%s) roles: %s" % (p["name"], pid, ", ".join(role_list(db, pid))))
    c = db.execute("SELECT kind, value FROM contacts WHERE person_id=? ORDER BY kind", (pid,)).fetchall()
    if c:
        print("Contact: " + "; ".join("%s %s" % (r["kind"], r["value"]) for r in c))
    s = db.execute("SELECT * FROM signups WHERE kid_id=?", (pid,)).fetchone()
    if s:
        note = db.execute("SELECT 1 FROM counseling_notes WHERE kid_id=?", (pid,)).fetchone()
        print("\nSign-up %s: grade %s, %s, programs %s, parent %s%s" % (
            s["signup_date"], s["grade"], s["school"], s["programs"].replace(";", ", "), pname(db, s["parent_id"]),
            " (counseling notes on file, withheld)" if note else ""))
        att = db.execute("SELECT status, COUNT(*) n FROM attendance WHERE kid_id=? GROUP BY status", (pid,)).fetchall()
        miss = db.execute("SELECT date FROM attendance WHERE kid_id=? AND status='absent' ORDER BY date DESC LIMIT 5",
                          (pid,)).fetchall()
        print("Attendance: " + ", ".join("%s %s" % (r["n"], r["status"]) for r in att) +
              ("; recent misses " + ", ".join(r["date"] for r in miss) if miss else ""))
        m = db.execute("SELECT mentor_id, match_date FROM matches WHERE kid_id=? AND status='active'", (pid,)).fetchall()
        print("Mentor: " + (", ".join("%s since %s" % (pname(db, r["mentor_id"]), r["match_date"]) for r in m) or "none"))
    kids = db.execute("SELECT kid_id FROM signups WHERE parent_id=?", (pid,)).fetchall()
    if kids:
        print("Parent of: " + ", ".join(pname(db, r["kid_id"]) for r in kids))
    mentees = db.execute("SELECT kid_id FROM matches WHERE mentor_id=? AND status='active'", (pid,)).fetchall()
    if mentees:
        print("Mentors: " + ", ".join(pname(db, r["kid_id"]) for r in mentees))
    v = db.execute("SELECT date, volunteer_id, kid_id, hours, activity, note FROM visits WHERE volunteer_id=? OR kid_id=?"
                   " ORDER BY date DESC LIMIT 8", (pid, pid)).fetchall()
    if v:
        print("\nVisits / hours (latest 8):\n")
        print(table(["date", "volunteer", "kid", "hours", "activity", "note"],
                    [(r["date"], pname(db, r["volunteer_id"]), pname(db, r["kid_id"]), r["hours"], r["activity"],
                      r["note"]) for r in v]))
    g = db.execute("SELECT date, amount, frequency, campaign FROM donations WHERE donor_id=? ORDER BY date DESC",
                   (pid,)).fetchall()
    if g:
        print("\nGifts:\n")
        print(table(["date", "amount", "frequency", "campaign"], [tuple(r) for r in g]))
    u = db.execute("SELECT date, need, status FROM urgent WHERE person_id=? ORDER BY date DESC", (pid,)).fetchall()
    if u:
        print("\nUrgent needs:\n")
        print(table(["date", "need", "status"], [tuple(r) for r in u]))


# ---------- at-risk ----------

def at_risk(db, week):
    w = dt.date.fromisoformat(week)
    a_from, m_from = (w - dt.timedelta(days=21)).isoformat(), (w - dt.timedelta(days=14)).isoformat()
    end = (w + dt.timedelta(days=7)).isoformat()
    out = []
    for s in db.execute("SELECT kid_id, parent_id, programs FROM signups WHERE signup_date < ?", (end,)).fetchall():
        if "mentoring" not in s["programs"]:
            continue
        kid = s["kid_id"]
        missed = db.execute("SELECT COUNT(*) FROM attendance WHERE kid_id=? AND status='absent' AND date>=? AND date<?",
                            (kid, a_from, end)).fetchone()[0]
        mentors = [r["mentor_id"] for r in db.execute(
            "SELECT mentor_id FROM matches WHERE kid_id=? AND status='active' AND match_date < ?", (kid, end))]
        last = db.execute("SELECT MAX(date) FROM visits WHERE kid_id=? AND date<?", (kid, end)).fetchone()[0]
        reasons = []
        if missed >= 2:
            reasons.append("missed %d sessions in last 3 weeks" % missed)
        if mentors and (not last or last < m_from):
            reasons.append("no mentor meeting since %s" % (last or "match"))
        if not mentors:
            reasons.append("no mentor matched")
        if reasons:
            p = db.execute("SELECT name, phone, email FROM people WHERE id=?", (s["parent_id"],)).fetchone()
            owner = (pname(db, mentors[0]) + " (mentor)") if mentors else "Program coordinator"
            if missed >= 2 and "counseling" in s["programs"]:
                owner += " + family counselor"
            out.append((pname(db, kid), "; ".join(reasons), last or "", p["name"], p["phone"] or p["email"] or "",
                        owner))
    return out


def cmd_at_risk(db, a):
    rows = at_risk(db, a.week)
    print("**At-risk kids, week of %s**\n" % a.week)
    print(table(["kid", "why", "last mentor meeting", "parent", "parent contact", "suggested follow-up owner"], rows))


# ---------- volunteer log / urgent ----------

def cmd_log_volunteer(db, a):
    vol = one_person(db, a.volunteer, role="volunteer")
    kid = one_person(db, a.kid) if a.kid else None
    row = {"volunteer": a.volunteer, "kid": a.kid or "", "date": a.date, "hours": a.hours, "note": a.note or "",
           "urgent": a.urgent or ""}
    vid = add_visit(db, vol, kid, a.date, a.hours, "mentor visit" if kid else "volunteer", a.note, "chat")
    record_source(db, "volunteer_log", row, "imported" if vid else "duplicate")
    if a.urgent:
        if not db.execute("SELECT 1 FROM urgent WHERE need=? AND status='open'", (a.urgent,)).fetchone():
            db.execute("INSERT INTO urgent(person_id, need, reported_by, date, status) VALUES(?,?,?,?, 'open')",
                       (kid, a.urgent, vol, a.date))
    db.commit()
    if vid:
        print("Logged: %s, %sh on %s%s%s" % (pname(db, vol), a.hours, a.date, " with " + pname(db, kid) if kid else "",
                                              "; urgent need opened: " + a.urgent if a.urgent else ""))
    else:
        print("Already logged: %s with %s on %s. Counted once, not added again." % (
            pname(db, vol), pname(db, kid) or "no kid", a.date))


def cmd_urgent(db, a):
    rows = db.execute("SELECT id, date, person_id, need, reported_by FROM urgent WHERE status='open' ORDER BY date").fetchall()
    print("**Open urgent needs**\n")
    print(table(["id", "date", "for", "need", "reported by"],
                [(r["id"], r["date"], pname(db, r["person_id"]) or "(family, see need)", r["need"],
                  pname(db, r["reported_by"])) for r in rows]))


def cmd_resolve(db, a):
    n = db.execute("UPDATE urgent SET status='resolved', resolved_date=? WHERE id=? AND status='open'",
                   (a.date, a.id)).rowcount
    db.commit()
    print("Resolved urgent need #%s on %s" % (a.id, a.date) if n else "ERROR: no open urgent need #%s" % a.id)


# ---------- report ----------

def quarter_bounds(q):
    m = re.fullmatch(r"(\d{4})Q([1-4])", q)
    if not m:
        raise SystemExit("ERROR: quarter must look like 2026Q3")
    y, n = int(m.group(1)), int(m.group(2))
    start = dt.date(y, 3 * n - 2, 1)
    end = dt.date(y + (n == 4), 1 if n == 4 else 3 * n + 1, 1)
    return start.isoformat(), end.isoformat()


def report(db, q):
    s, e = quarter_bounds(q)
    one = lambda sql, *p: db.execute(sql, p).fetchone()[0] or 0
    att = one("SELECT COUNT(*) FROM attendance WHERE date>=? AND date<?", s, e)
    present = one("SELECT COUNT(*) FROM attendance WHERE date>=? AND date<? AND status='present'", s, e)
    m = {
        "kids enrolled": one("SELECT COUNT(DISTINCT kid_id) FROM signups WHERE signup_date<?", e),
        "sessions held": one("SELECT COUNT(DISTINCT date || session) FROM attendance WHERE date>=? AND date<?", s, e),
        "attendance records": att,
        "attendance rate": "%.1f%%" % (100.0 * present / att) if att else "n/a",
        "mentor matches (active)": one("SELECT COUNT(*) FROM matches WHERE status='active' AND match_date<?", e),
        "mentor meetings": one("SELECT COUNT(*) FROM visits WHERE kid_id IS NOT NULL AND date>=? AND date<?", s, e),
        "volunteer hours": round(one("SELECT SUM(hours) FROM visits WHERE date>=? AND date<?", s, e), 1),
        "urgent needs resolved": one("SELECT COUNT(*) FROM urgent WHERE resolved_date>=? AND resolved_date<?", s, e),
        "urgent needs still open": one("SELECT COUNT(*) FROM urgent WHERE status='open' AND date<?", e),
    }
    # Reconcile against the raw source rows, independent of the normalized tables.
    src = {}
    for r in db.execute("SELECT source, row, outcome FROM source_rows"):
        src.setdefault(r["source"], []).append((json.loads(r["row"]), r["outcome"]))
    inq = lambda d: s <= d < e
    checks = []
    a_rows = [x for x, _ in src.get("attendance", []) if inq(x["date"])]
    a_pairs = {(norm(x["kid_name"]), x["date"], x["session"]) for x in a_rows}
    checks.append(("attendance records = unique source rows", att, len(a_pairs)))
    checks.append(("present = source rows marked present", present,
                   len({(norm(x["kid_name"]), x["date"], x["session"]) for x in a_rows if x["status"] == "present"})))
    hrs, dup_hrs, dups = 0.0, 0.0, 0
    for name in ("volunteer_hours", "volunteer_log"):
        for x, o in src.get(name, []):
            if inq(x["date"]):
                h = float(x["hours"])
                hrs += h
                if o == "duplicate":
                    dup_hrs += h; dups += 1
    checks.append(("volunteer hours = source hours - %d duplicate reports (%.1fh)" % (dups, dup_hrs),
                   m["volunteer hours"], round(hrs - dup_hrs, 1)))
    kids_src = {norm(x["kid_name"]) for x, _ in src.get("signup", []) if x["signup_date"] < e}
    checks.append(("kids enrolled = unique kids in sign-up rows", m["kids enrolled"], len(kids_src)))
    checks.append(("mentor matches = unique source match rows", m["mentor matches (active)"],
                   len({(norm(x["mentor_name"]), norm(x["kid_name"])) for x, _ in src.get("mentors", [])
                        if x["match_date"] < e})))
    return m, checks, (s, e)


def cmd_report(db, a):
    m, checks, (s, e) = report(db, a.quarter)
    print("**Tidepath Family Alliance, outcome report %s** (%s to %s, end exclusive)\n" % (a.quarter, s, e))
    print(table(["measure", "value"], list(m.items())))
    print("\n**Reconciliation with source rows**\n")
    print(table(["check", "report", "source", "ok"], [(c, r, sv, "yes" if r == sv else "NO") for c, r, sv in checks]))
    ok = all(r == sv for _, r, sv in checks)
    print("\n" + ("All totals reconcile." if ok else "ERROR: totals do not reconcile."))
    if not ok:
        sys.exit(1)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="crm.py", description="Tidepath Family Alliance CRM")
    ap.add_argument("--db", default=None, help="SQLite path (default $AUTOWORKER_WORKSPACE/tidepath/crm.db)")
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("seed"); p.add_argument("dir"); p.set_defaults(f=cmd_seed)
    p = sp.add_parser("import"); p.add_argument("csv"); p.add_argument("--source", required=True, choices=list(SOURCES))
    p.set_defaults(f=cmd_import)
    sp.add_parser("dupes").set_defaults(f=cmd_dupes)
    p = sp.add_parser("merge"); p.add_argument("keep_id", type=int); p.add_argument("drop_id", type=int)
    p.add_argument("--approved-by", required=True); p.set_defaults(f=cmd_merge)
    p = sp.add_parser("person"); p.add_argument("query"); p.set_defaults(f=cmd_person)
    p = sp.add_parser("at-risk"); p.add_argument("--week", required=True); p.set_defaults(f=cmd_at_risk)
    p = sp.add_parser("log-volunteer"); p.add_argument("--volunteer", required=True)
    p.add_argument("--hours", type=float, required=True); p.add_argument("--date", required=True)
    p.add_argument("--kid"); p.add_argument("--note"); p.add_argument("--urgent"); p.set_defaults(f=cmd_log_volunteer)
    sp.add_parser("urgent").set_defaults(f=cmd_urgent)
    p = sp.add_parser("resolve"); p.add_argument("id", type=int); p.add_argument("--date", required=True)
    p.set_defaults(f=cmd_resolve)
    p = sp.add_parser("report"); p.add_argument("--quarter", required=True); p.set_defaults(f=cmd_report)
    a = ap.parse_args(argv)
    db = connect(a.db or default_db())
    a.f(db, a)


if __name__ == "__main__":
    main()
