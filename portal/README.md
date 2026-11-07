# Tidepath portal

A small public website for people who are not in the Roomcord app: volunteers,
school staff and parents. Each form posts one structured message into the
right room of the Tidepath Family Alliance Roomcord server and mentions the
specialist agent of that room. The agent then acts on it (logs hours, opens a
workshop request, adds a family to the CRM, records a slide approval).

Made-up demo. Tidepath is a fictional nonprofit.

## Run

Node 20 or newer. No npm install: the server uses only `node:http` and `fetch`.

```bash
cp .env.example .env     # then fill in the values
node server.js           # http://localhost:8080
npm test                 # unit tests for validation and message format
```

Docker:

```bash
docker build -t tidepath-portal .
docker run -p 8080:8080 --env-file .env tidepath-portal
```

Any host that runs Node 20 or a container works (a VM, Cloud Run, Fly.io,
Render). Put it behind HTTPS. Behind a reverse proxy, set `TRUST_PROXY=1` so the
rate limit uses the client IP from `X-Forwarded-For`. `GET /healthz` reports
which forms are configured.

## Configuration

Environment variables only. `server.js` also reads a local `.env` file if one
exists. Variables that are already set win.

| Variable | Meaning |
|---|---|
| `ROOMCORD_API_URL` | Roomcord API base, including `/api/v1` |
| `ROOMCORD_BOT_TOKEN` | Bearer token of the "Tidepath portal" bot user |
| `ROOM_VOLUNTEERS_ID`, `ROOM_WORKSHOPS_ID`, `ROOM_PROGRAMS_ID` | Target room ids |
| `AGENT_VOLUNTEERS_ID`, `AGENT_WORKSHOPS_ID`, `AGENT_PROGRAMS_ID` | Agent to mention in each room: the `agentId` that the room member list shows (the room binding id) |
| `AGENT_*_NAME` | Fallback display name if the member lookup fails |
| `PORT` | Listen port, default 8080 |
| `RATE_LIMIT_MAX`, `RATE_LIMIT_WINDOW_SEC` | Posts per IP per window, default 10 per 600 s |
| `TRUST_PROXY` | `1` to use `X-Forwarded-For` for the client IP |
| `PORTAL_DRY_RUN` | `1` to validate and log messages without posting |

The bot user must be a member of the three rooms. Give it no other rooms.

## Forms and rooms

| Page | Room | Mention | Message starts with |
|---|---|---|---|
| `/volunteer` Volunteer check-in | Volunteers | Tidepath Volunteers | `Portal · Volunteer check-in · Maria Alvarez · 2026-11-07 · 1h · met Kevin · urgent: needs a laptop for school` |
| `/workshop` Workshop request | Workshop requests | Tidepath Workshops | `Portal · Workshop request · <school> · grade 7 · 60 students · safety · in person · <language>` |
| `/family` Family sign-up | Programs and mentoring | Tidepath Programs | `Portal · Family sign-up · <parent> · child <name> (<age>) · <school> · <program> · language <lang>` |
| `/approve?request=W001&version=v2` Slide approval | Workshop requests | Tidepath Workshops | `School approved W001 v2` or `School requested changes to W001 v2` + the comment |

The first line is the compact summary. The next lines hold the details (what
happened, contact, notes). The message body is `@<agent display name> <text>`,
the same format as `workcord messages send-text --mention-agent`. The server
reads the display name from the room member list, so Roomcord resolves the
mention to the agent and the agent receives the message.

A volunteer photo is resized in the browser (max 1600 px, JPEG), uploaded with
`POST /rooms/:id/images` and attached to the message. If the upload fails, the
message is still sent and says so.

All pages work in English, Spanish and Haitian Creole. The language comes from
`?lang=en|es|ht`, then the last choice on the device, then the browser language.

## Validation and errors

- The server checks every field again (required fields, date, hours 0.25 to 24,
  email, phone, headcount, age 3 to 21, consent, `W001`/`v2` format).
  Invalid fields come back as `400 {fields: {name: code}}`, and the page shows
  the message in the visitor's language next to the field.
- Text is cleaned before posting: one line per field, length limits, no control
  characters, no markup, and no `@` mentions, so a visitor cannot ping other
  agents or people.
- `429` after too many posts from one IP (in-memory, resets on restart).
  `502` when Roomcord does not accept the message. `503` when the form is not
  configured. The page keeps the answers so the visitor can try again.
- A hidden honeypot field drops simple bots.

## Privacy

- No login, no cookies, no analytics. The language choice is kept in the
  browser's local storage only.
- The server does not store submissions. It forwards each one to one room and
  keeps nothing. Logs hold the form name, a reference code and the message id,
  never the content (except in `PORTAL_DRY_RUN` mode).
- Only the room members (Tidepath staff and the room's agents) see a message.
- The volunteer form asks for the kid's first name only and no faces in photos.
- The family form needs explicit consent before it sends.
- Strict security headers: CSP with `'self'` only, no framing, no referrer.

## Next

- Outbound replies: send the agent's answer back to the person by SMS or email
  (for example the workshop coordinator's questions to the school contact).
- Signed approval links, so only the school that got the email can approve.
- A shared rate-limit store when the portal runs on more than one instance.
