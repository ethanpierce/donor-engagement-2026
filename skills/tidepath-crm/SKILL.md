---
name: tidepath-crm
description: Tidepath Family Alliance CRM (kids, parents, mentors, volunteers, donors). Use to import sign-up, attendance, mentor, volunteer-hour and donation CSVs, look up a person, find duplicate records, merge with staff approval, list at-risk kids, log volunteer visits from chat, track urgent needs, and build the quarterly outcome report.
---

# Tidepath CRM

One SQLite database per tenant at `$AUTOWORKER_WORKSPACE/tidepath/crm.db`.
The workspace persists. Pass `--db PATH` only for tests or demos.

Run every command as:

```sh
python3 <this skill dir>/scripts/crm.py [--db PATH] <command> ...
```

Output is compact Markdown, ready to post in the room.

## Commands

| Command | Use it to |
|---|---|
| `seed <demo-data-dir>` | Import every known CSV in a folder (first setup or demo). |
| `import <csv> --source signup\|attendance\|mentors\|volunteer_hours\|donations` | Import one new export. Repeated rows are skipped and counted. |
| `dupes` | List candidate duplicate people with a score and reasons. Never merges. |
| `merge <keep_id> <drop_id> --approved-by "<staff name>"` | Merge two records after staff approval. History moves to the kept record and an audit row is written. |
| `person "<name or id>"` | One record: roles, sign-up, attendance, mentor, visits, gifts, urgent needs. |
| `at-risk --week YYYY-MM-DD` | Kids with 2+ missed sessions in the last 3 weeks or no mentor meeting in 14 days, with parent contact and follow-up owner. |
| `log-volunteer --volunteer "<name>" --hours N --date YYYY-MM-DD [--kid "<name>"] [--note "..."] [--urgent "..."]` | Log one volunteer report from chat. The same volunteer, kid and date is counted once. |
| `urgent` | Open urgent needs. |
| `resolve <id> --date YYYY-MM-DD` | Close an urgent need. |
| `report --quarter 2026Q3` | Quarterly outcomes plus a check that totals reconcile with the source rows. Exit 1 if they do not. |

## Volunteer texts

Read each text, then call `log-volunteer` once per visit. Use the visit date,
not the send time. Put a concrete need (laptop, diapers, food, rent) in
`--urgent`. A resent message is safe: the tool reports "Already logged".

## Privacy

- Share only what the room needs for the task. A volunteer gets the kid's
  first name, the meeting plan and the need, not the family's address,
  phone or other kids.
- Never quote, summarize or hint at counseling notes. The tool withholds them.
  Say "counseling notes on file" only to counseling staff.
- Parent contact details go only to the staff member who owns the follow-up.
- Do not post donor amounts outside fundraising or leadership rooms.

## Approval

- Never run `merge` without a named staff member's explicit approval of that
  exact pair in the current conversation. Put that name in `--approved-by`.
- `dupes` output is a proposal. Show it and ask. A shared phone or address
  alone can be a household, not one person.
- Imports and `log-volunteer` add records only. They never delete.
