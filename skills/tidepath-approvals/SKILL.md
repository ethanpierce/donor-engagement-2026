---
name: tidepath-approvals
description: Run the Tidepath Director's approval queue, route urgent needs to the right room, steward People CRM merges, and write the weekly digest. Use when a specialist asks for approval, reports an urgent need, Alex says approve or reject, or the weekly digest is due.
---

# Tidepath Approvals

CRM commands run as `python3 <tidepath-crm skill dir>/scripts/crm.py <cmd>`
(see the `tidepath-crm` skill). All data is made up.

## What needs approval

Nothing in this list happens before Alex writes "approve" for that exact item:

- CRM merges (`merge <keep> <drop> --approved-by Alex`).
- Any outbound message to a parent, mentor, volunteer, donor, school or funder.
- Funder or grant submissions and quarterly reports sent outside Tidepath.

## Queue procedure

1. Give each new item a short id: `A-<yyyymmdd>-<n>`.
2. Post it in Director desk in this shape:
   `A-20261109-1 | merge | keep P-014, drop P-022 | from People CRM | reason: same phone and name`
3. Wait. Do not act on silence, a thumbs-up from an agent, or "looks fine".
4. On "approve A-...": do the action, then reply with the result in one line.
   For a merge run `merge <keep> <drop> --approved-by Alex` and post the result
   in People CRM.
5. On "reject A-..." or a change request: mark it closed or revised, and tell
   the requesting specialist in its room.
6. Keep open items in memory. List open items at the top of every digest.

## People CRM stewardship

- Run `dupes` when asked or during the weekly digest.
- Post each duplicate pair as one queue item. Never merge without approval.
- Use `person <id>` to answer lookups. Share only fields the asker needs.

## Routing table

When a specialist reports an urgent need, post it to the target room and
@mention Alex. One post per need.

| Need | Target room | What to post |
|---|---|---|
| Kid need (supplies, tutoring, mentor gap) | Programs and mentoring | Kid id, need, source, due date |
| Family distress | Counseling (restricted) | Only "Family <id> needs a counselor call." No details, no quotes, no names. |
| Donor question or gift | Fundraising | Donor id, ask, deadline |
| School or workshop request | Workshop requests | School, request, date |
| Grant or finance item | Grants and finance | Funder, item, deadline |

The Director never reads or posts in Counseling (restricted) beyond that one
line. If the type is unclear, ask Alex in Director desk.

## Weekly digest (Director desk)

```
Tidepath weekly digest, week of <date>
Open approvals: <n>  (list ids, one line each)
Urgent needs this week: <n> (run `urgent`) , routed to: <rooms>
At-risk kids: <n> (from `at-risk --week <yyyy-Www>`)
Volunteer hours: <total> by <n> volunteers
CRM duplicates waiting: <n>
Decisions needed from Alex: <bullets>
```

Keep it under 15 lines. Numbers come from `crm.py`, never from memory.
