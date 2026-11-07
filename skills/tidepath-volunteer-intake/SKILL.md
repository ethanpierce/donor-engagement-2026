---
name: tidepath-volunteer-intake
description: Volunteer coordinator procedures for Tidepath. Use when a volunteer posts a text, photo note or exported WhatsApp line about a visit or hours, to log it with crm.py log-volunteer, confirm it, flag urgent kid needs the same day, and write the Friday hours summary.
---

# Tidepath Volunteer Intake

CRM commands run as `python3 <tidepath-crm skill dir>/scripts/crm.py <cmd>`
(see the `tidepath-crm` skill). All data is made up.

## Sources

Accept only messages a volunteer sends on purpose: a post in Volunteers, a
photo of a note, or a line from a chat export the volunteer shared. Never
automate WhatsApp scraping, log in to WhatsApp, or read chats nobody shared.

## Parse

From each message take:

| Field | Rule |
|---|---|
| volunteer | Sender, or the name at the start of an export line |
| hours | Number; "90 min" = 1.5. Missing: ask, do not guess |
| date | Message date unless the text names a day. Format `YYYY-MM-DD` |
| kid | Kid id or first name matched with `person`. Optional |
| note | Short visit summary, no family details |
| urgent | Yes when the text names a need that cannot wait a week (no food, no school supplies for tomorrow, safety worry) |

Export line example: `[11/05/26, 4:12 PM] Maria V.: 2h with Leo today, he needs a winter coat`
gives volunteer Maria V., hours 2, date 2026-11-05, kid Leo, need winter coat, urgent yes.

## Log

`log-volunteer --volunteer <id> --hours <h> --date <YYYY-MM-DD> [--kid <id>] [--note "<text>"] [--urgent]`

## Confirm

Reply to the volunteer in one line in their language:
`Logged 2h on 2026-11-05 with Leo. Coat need sent to the program team. Thank you!`

## Urgent needs

1. Log with `--urgent`.
2. Post in Programs and mentoring the same day: kid id, need, who reported it.
3. Tell the Director so it can route and @mention Alex.
4. A safety or family distress worry goes only to the Director as
   "needs counselor call". Never post the details.

## Friday hours summary (Volunteers)

Run `urgent` and sum logged hours for the week. Post: total hours, hours per
volunteer, visits, open urgent needs. Thank volunteers by first name.
