---
name: tidepath-donor-care
description: Import Tidepath gift CSVs (web page, tickets, auction, checks), review duplicate donors with staff before any merge, find late regular donors and failed monthly gifts with lapsed.py, and draft personal notes. Use in the Fundraising room.
---

# Tidepath Donor Care

All data is made up. `CRM` below means
`python3 <tidepath-crm skill dir>/scripts/crm.py`.

## 1. Import gift files

Gift files come from four places: the web donation page, event tickets, the
auction, and checks typed in by staff.

1. Ask staff which file and which source it is. Do not guess the source.
2. Run `CRM import --source donations <file>` once per file.
3. Report rows read, gifts added, rows skipped and why.
4. Run `CRM dupes` right after each import.

## 2. Duplicate donors

1. Show each pair from `CRM dupes` with the reasons (same email, same phone,
   similar name, same address) and the gift count of each record.
2. Ask staff which record to keep. Do nothing until a staff member answers.
3. Run `CRM merge <keep> <drop> --approved-by "<staff name>"` only with the
   name of the person who approved in an active request.
4. Run `CRM person <keep>` and check that the gift count equals the sum of
   both records. If not, stop and tell staff. Giving history is never lost.

## 3. Late and failed regular gifts

Run `python3 scripts/lapsed.py <gifts.csv> [--today YYYY-MM-DD]`.
The CSV has `donor_id,name,date,amount,recurring` (`recurring` is `monthly`
or empty). `samples/gifts.csv` is a made-up example.

- `FAILED MONTHLY`: a monthly gift missed its expected date by more than
  7 days. Likely a card problem. Draft a gentle card-update note.
- `LATE REGULAR`: a donor who gives on a steady cadence (3 or more gifts) is
  past the usual gap by more than 25 percent. Draft a check-in note.

Show the list to staff with last gift, usual amount, usual month and cadence.
Never contact a donor. Staff choose who gets a note.

## 4. Personal note template

Keep it short, warm and specific. Fill every `{}` from the CRM. If a value is
missing, write `MISSING: <field>` and ask staff.

```
Dear {first_name},

Thank you for standing with Tidepath families {since_year_phrase}.
Your gift of {usual_amount} in {usual_month} last year helped
{one_specific_program_result}.

{reason_line}

With gratitude,
{staff_name}
Tidepath Family Alliance
```

`reason_line` for a failed monthly gift: "We noticed your monthly gift did not
go through this month. If your card changed, you can update it here: {link}.
No action is needed if you chose to pause."

`reason_line` for a late regular donor: "We think of you often and wanted to
share what your support made possible this year."
