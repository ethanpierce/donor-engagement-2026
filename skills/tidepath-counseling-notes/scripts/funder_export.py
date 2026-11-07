"""Export only funder-required fields from one counseling note. NOT HIPAA-approved.

Usage:
  python3 funder_export.py preview NOTE.json --funder FUNDER.json --by NAME [--log PATH]
  python3 funder_export.py export  NOTE.json --funder FUNDER.json --by NAME --out FILE [--log PATH]
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

DEFAULT_LOG = os.path.join(os.environ.get("AUTOWORKER_HUB_WORKSPACE", "."), "tidepath", "counseling-access.log")
INTERNAL = {"note_id", "made_up"}


def append_log(path, entry):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=["preview", "export"])
    p.add_argument("note")
    p.add_argument("--funder", required=True)
    p.add_argument("--by", required=True)
    p.add_argument("--out")
    p.add_argument("--log", default=DEFAULT_LOG)
    a = p.parse_args()
    with open(a.note, encoding="utf-8") as f:
        note = json.load(f)
    with open(a.funder, encoding="utf-8") as f:
        funder = json.load(f)
    if note.get("made_up") is not True:
        sys.exit("ERROR: note is not marked made_up=true; this demo accepts made-up notes only")

    mapping = funder["fields"]
    sent = {}
    missing = []
    for report_name, key in mapping.items():
        if key in note and str(note[key]).strip():
            sent[report_name] = note[key]
        else:
            missing.append(report_name)
    used = set(mapping.values())
    inside = sorted(k for k in note if k not in used and k not in INTERNAL)

    if a.action == "export":
        if missing:
            sys.exit(f"ERROR: required fields missing: {', '.join(missing)}")
        if not a.out:
            sys.exit("ERROR: --out is required for export")
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump({"funder": funder["funder"], "record": sent}, f, indent=2, ensure_ascii=False)

    append_log(a.log, {
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "action": a.action, "by": a.by, "note_id": note.get("note_id"),
        "funder": funder["funder"], "fields_sent": list(sent), "out": a.out,
    })

    print("NOTICE: demo only. This is NOT a HIPAA-approved system.")
    print(f"Funder: {funder['funder']}  Note: {note.get('note_id')}")
    print("WILL BE SENT:")
    for k, v in sent.items():
        print(f"  + {k}: {v}")
    for k in missing:
        print(f"  ! MISSING required field: {k}")
    print("STAYS INSIDE (values not shown):")
    for k in inside:
        print(f"  - {k}")
    if a.action == "export":
        print(f"Wrote {a.out} with {len(sent)} fields. A person sends it; nothing was sent.")
    print(f"Logged to {a.log}")


if __name__ == "__main__":
    main()
