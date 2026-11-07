"""Tidepath workshop request tracker (JSON file in the tenant workspace).

Usage: python3 pipeline.py [--db PATH] CMD ...
CMDs: add, load, missing, set, stage, slides, approve, human, list
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

FIELDS = ["date", "room", "language", "topic", "grade_age", "format", "headcount"]
STAGES = ["new", "info complete", "planning call booked", "slides drafted",
          "staff checked", "school approved", "confirmed", "delivered"]
DEFAULT_DB = os.path.join(os.environ.get("AUTOWORKER_HUB_WORKSPACE", "."), "tidepath", "workshops.json")


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load(path):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {"next_id": 1, "requests": {}}


def save(path, db):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)


def missing(req):
    return [k for k in FIELDS if not str(req["fields"].get(k, "")).strip()]


def stage_label(req):
    s = req["stage"]
    return f"{s} v{req['approved_version']}" if s == "school approved" else s


def log(req, event, by):
    req["history"].append({"at": now(), "event": event, "by": by})


def refresh(req):
    if req["stage"] == "new" and not missing(req):
        req["stage"] = "info complete"
        log(req, "stage -> info complete", "pipeline")


def new_request(db, school, contact, channel, lang, fields):
    rid = f"W{db['next_id']:03d}"
    db["next_id"] += 1
    req = {"id": rid, "school": school, "contact": contact, "channel": channel, "lang": lang,
           "fields": {k: v for k, v in fields.items() if k in FIELDS}, "stage": "new",
           "slides": [], "approved_version": None, "approved_by": None, "human": False, "history": []}
    log(req, f"created from {channel}", "pipeline")
    refresh(req)
    db["requests"][rid] = req
    return req


def get(db, rid):
    if rid not in db["requests"]:
        sys.exit(f"ERROR: unknown request {rid}")
    return db["requests"][rid]


def kv(pairs):
    out = {}
    for p in pairs or []:
        k, _, v = p.partition("=")
        if k not in FIELDS:
            sys.exit(f"ERROR: unknown field {k}; fields: {', '.join(FIELDS)}")
        out[k] = v
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--db", default=DEFAULT_DB)
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    a.add_argument("--school", required=True)
    a.add_argument("--contact", required=True)
    a.add_argument("--channel", choices=["email", "text", "phone", "web"], required=True)
    a.add_argument("--lang", choices=["en", "es", "ht"], required=True)
    a.add_argument("--set", action="append")
    sub.add_parser("load").add_argument("file")
    sub.add_parser("missing").add_argument("id")
    s = sub.add_parser("set")
    s.add_argument("id")
    s.add_argument("pairs", nargs="+")
    st = sub.add_parser("stage")
    st.add_argument("id")
    st.add_argument("stage", choices=[x for x in STAGES if x != "school approved"])
    st.add_argument("--by", required=True)
    sl = sub.add_parser("slides")
    sl.add_argument("id")
    sl.add_argument("--version", type=int, required=True)
    sl.add_argument("--file", default="")
    ap = sub.add_parser("approve")
    ap.add_argument("id")
    ap.add_argument("--version", type=int, required=True)
    ap.add_argument("--by", required=True)
    h = sub.add_parser("human")
    h.add_argument("id")
    h.add_argument("--by", required=True)
    h.add_argument("--off", action="store_true")
    sub.add_parser("list")
    args = p.parse_args()

    db = load(args.db)
    if args.cmd == "add":
        r = new_request(db, args.school, args.contact, args.channel, args.lang, kv(args.set))
        print(f"{r['id']} added, stage {r['stage']}, missing: {', '.join(missing(r)) or 'none'}")
    elif args.cmd == "load":
        with open(args.file, encoding="utf-8") as f:
            for item in json.load(f):
                r = new_request(db, item["school"], item["contact"], item["channel"], item["lang"], item["fields"])
                print(f"{r['id']} {r['school']}: stage {r['stage']}, missing: {', '.join(missing(r)) or 'none'}")
    elif args.cmd == "missing":
        print(", ".join(missing(get(db, args.id))) or "none")
    elif args.cmd == "set":
        r = get(db, args.id)
        r["fields"].update(kv(args.pairs))
        refresh(r)
        print(f"{r['id']} stage {r['stage']}, missing: {', '.join(missing(r)) or 'none'}")
    elif args.cmd == "stage":
        r = get(db, args.id)
        cur, want = STAGES.index(r["stage"]), STAGES.index(args.stage)
        if want != cur + 1:
            sys.exit(f"ERROR: {r['id']} is at '{stage_label(r)}'; next stage is '{STAGES[cur + 1] if cur + 1 < len(STAGES) else 'none'}'")
        if args.stage == "slides drafted" and not r["slides"]:
            sys.exit("ERROR: record a slide version first (slides --version N)")
        r["stage"] = args.stage
        log(r, f"stage -> {args.stage}", args.by)
        print(f"{r['id']} stage {stage_label(r)}")
    elif args.cmd == "slides":
        r = get(db, args.id)
        r["slides"].append({"version": args.version, "file": args.file, "at": now()})
        log(r, f"slides v{args.version} recorded", "pipeline")
        print(f"{r['id']} slides v{args.version} recorded")
    elif args.cmd == "approve":
        r = get(db, args.id)
        if r["stage"] != "staff checked":
            sys.exit(f"ERROR: {r['id']} must be 'staff checked' before school approval (now '{stage_label(r)}')")
        if args.version not in [s["version"] for s in r["slides"]]:
            sys.exit(f"ERROR: slides v{args.version} not recorded")
        r.update(stage="school approved", approved_version=args.version, approved_by=args.by)
        log(r, f"school approved slides v{args.version}", args.by)
        print(f"{r['id']} stage {stage_label(r)} by {args.by}")
    elif args.cmd == "human":
        r = get(db, args.id)
        r["human"] = not args.off
        log(r, "human takeover off" if args.off else "human takeover on", args.by)
        print(f"{r['id']} human takeover {'off' if args.off else 'on'}")
    elif args.cmd == "list":
        for r in db["requests"].values():
            appr = f"v{r['approved_version']} by {r['approved_by']}" if r["approved_version"] else "-"
            print(f"{r['id']} | {r['school']} | {r['lang']} | {stage_label(r)} | missing: "
                  f"{', '.join(missing(r)) or 'none'} | approved slides: {appr}{' | HUMAN' if r['human'] else ''}")
    save(args.db, db)


if __name__ == "__main__":
    main()
