---
name: tidepath-counseling-notes
description: Turn one made-up Tidepath counseling session note into a funder report that contains only that funder's required fields, with a "will be sent / stays inside" preview and an access and send log. Use only in the Counseling (restricted) room. Not a HIPAA-approved system.
---

# Tidepath Counseling Notes

This is a demo with made-up notes. It is NOT a HIPAA-approved system. Say this
before every preview. Never paste note content into another room, a board
card, or shared memory.

## 1. Note format

One note is one JSON object. `samples/note-001.json` is a made-up example.
Common keys: `client_id`, `client_name`, `date`, `counselor`, `service_type`,
`minutes`, `zip`, `age_band`, `language`, `presenting_issue`, `narrative`,
`risk_flags`, `referrals`, `household_size`, `income_band`.

If a note has a real-looking name, phone or address and staff did not mark it
as made up, stop and ask staff to remove it.

## 2. Funder field maps

Each `funders/<funder>.json` lists ONLY the fields that funder requires:

```json
{"funder": "...", "fields": {"<report name>": "<note key>"}}
```

Never add a field that the funder did not require. Staff change these files.

## 3. Preview, then export

1. `python3 scripts/funder_export.py preview <note.json> --funder funders/<f>.json --by Alex`
2. Post the preview in this room only. It shows `WILL BE SENT` and
   `STAYS INSIDE` lists. The values of stay-inside fields are never shown.
3. Wait for staff approval in an active request.
4. `python3 scripts/funder_export.py export <note.json> --funder funders/<f>.json --by Alex --out <file>`
   writes the funder file with allowed fields only.
5. A person sends the file through the funder's own channel. You never send it.

Every preview and export appends one line to the access and send log at
`$AUTOWORKER_HUB_WORKSPACE/tidepath/counseling-access.log` (override with
`--log`). The log holds note id, funder, action, person and field names,
never field values.
