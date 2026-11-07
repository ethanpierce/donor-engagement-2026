---
name: tidepath-programs-ops
description: Program manager procedures for Tidepath Programs and mentoring. Use for the weekly at-risk check, drafting follow-ups to parents or mentors in English, Spanish or Haitian Creole, the quarterly program report, and reconciling program numbers.
---

# Tidepath Programs Ops

CRM commands run as `python3 <tidepath-crm skill dir>/scripts/crm.py <cmd>`
(see the `tidepath-crm` skill). All data is made up.

## Weekly at-risk check

1. Run `at-risk --week <yyyy-Www>` for the current ISO week.
2. For each kid, state one reason in one line (missed sessions, no mentor
   visit, open urgent need).
3. Draft a follow-up for each kid (see below).
4. Post the list and drafts in Programs and mentoring.
5. Send each draft to the Director's queue as an outbound message for approval.

## Follow-up drafts

- Recipient: the parent or the mentor on the kid record (`person <id>`).
- Language: the record's preferred language: `en`, `es` or `ht`. Default `en`.
- At most 4 sentences. Warm, specific, one clear ask, one contact time.
- No diagnosis, no family details, no other kids' names.
- Label each draft `DRAFT, not sent` with the recipient id and language.
- Never send. Only the Director sends after Alex approves.

Example (es): "Hola, somos Tidepath. Notamos que Sofi no pudo venir a dos
sesiones de tutoría. ¿Le queda bien una llamada corta el jueves a las 5 pm?
Estamos para ayudar."

## Quarterly report

1. Run `report --quarter <yyyyQn>` (for example `2026Q3`).
2. Reconcile before posting (next section).
3. Post the summary in Programs and mentoring. Kids served, sessions,
   mentor visits, volunteer hours, outcomes, open risks.
4. A copy for funders goes to the Director's queue for approval.

## Reconcile numbers

- Volunteer hours in the report equal the sum of logged hours for the quarter.
- Kids served is no larger than active kid records.
- If a number does not match, show both values and the command that produced
  them. Do not round, guess or fix data by hand. Ask Alex.
