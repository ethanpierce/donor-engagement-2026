---
name: tidepath-workshop-pipeline
description: Intake and stage tracking for Tidepath school workshop requests from email, text, phone notes or the web form, in English, Spanish or Haitian Creole. Asks all missing fields in one reply and records slide versions and approvers with pipeline.py. Use in the Workshop requests room.
---

# Tidepath Workshop Pipeline

`PIPE` below means `python3 scripts/pipeline.py`. The tracker is a JSON file
at `$AUTOWORKER_HUB_WORKSPACE/tidepath/workshops.json` (override with
`--db`). All requests in this build are made up.

## 1. Intake

Requests arrive by email, text, phone notes typed by staff, or the web form.
Note the channel and the language (`en`, `es`, `ht`).

Required fields: `date`, `room`, `language`, `topic`, `grade_age`,
`format` (`in-person` or `online`), `headcount`.

1. Read the request. Fill only the fields that it states. Never guess.
2. `PIPE add --school "<school>" --contact "<name>" --channel email --lang es --set topic="..."`
3. `PIPE missing <id>` lists what is still empty.
4. Draft ONE reply that asks for all missing fields at once, in the request
   language. Staff approve the reply before it goes out.
5. When all fields are set, the tracker moves the request to `info complete`.

Reply templates (list only the missing items):

- en: "Thank you for your request. To plan the workshop, please tell us: {items}."
- es: "Gracias por su solicitud. Para planear el taller, por favor indíquenos: {items}."
- ht: "Mèsi pou demann ou. Pou nou ka prepare atelye a, tanpri di nou: {items}."

Field words: date / fecha / dat; room / salón / sal; language / idioma / lang;
topic / tema / sijè; grade or age / grado o edad / klas oswa laj;
in person or online / presencial o en línea / an pèsòn oswa sou entènèt;
number of people / número de personas / konbyen moun.

## 2. Stages

`new -> info complete -> planning call booked -> slides drafted ->
staff checked -> school approved vX -> confirmed -> delivered`

- `PIPE stage <id> "planning call booked" --by Alex` only after staff say the
  call is in their calendar. There is no calendar integration today. Staff
  use their existing calendar.
- `PIPE slides <id> --version 2 --file deck-v2.pdf` records a slide version.
- `PIPE stage <id> "staff checked" --by Alex` after staff review.
- `PIPE approve <id> --version 2 --by "<school contact>"` records which
  version the school approved and who approved it. The stage becomes
  `school approved v2`.
- `PIPE stage <id> confirmed --by Alex`, then `delivered`.

Stages move forward one step at a time. The script refuses jumps.

## 3. Human takeover

Alex can take over any request. Run `PIPE human <id> --by Alex`. After that,
do not draft replies for it until staff run `PIPE human <id> --off --by Alex`.

## 4. Status

`PIPE list` shows every request with stage, missing fields and the last
approved slide version. Post it when staff ask for the pipeline.

`samples/requests.json` holds two made-up requests for a demo:
`PIPE --db demo-workshops.json load samples/requests.json`.
