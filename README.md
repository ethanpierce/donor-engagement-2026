# Tidepath: one person, seven nonprofit jobs, a team of AI agents

**Tidepath Family Alliance** mentors kids and supports their families in Miami.
It has seven staff jobs. In this project, one person, Alex, does all of them,
with an AI agent for each job working beside Alex in Roomcord.

Built in 48 hours at the DevDay Exchange Community Hackathon 2026, Miami.
Tidepath is a made-up nonprofit and all data here is fictional. The six problems
are real, from a survey of 14 South Florida nonprofits.

## Watch the demo

[![Tidepath main demo](https://img.youtube.com/vi/gnyIQc3T68o/maxresdefault.jpg)](https://youtu.be/gnyIQc3T68o)

| Video | What you see |
|---|---|
| [**Main demo** (5:30)](https://youtu.be/gnyIQc3T68o) | All six hackathon problems solved inside Roomcord, from a volunteer's phone check-in to grant spending |
| [**A calendar app, built by asking** (0:48)](https://youtu.be/484fODyxdsc) | Alex asks the workshop agent in chat for a calendar. The agent builds a room app, Alex approves it, and the planning calls appear on their days |
| [**OpenAI Dots + Roomcord API** (1:39)](https://youtu.be/prb46nfY95E) | OpenAI Dots reads Tidepath's rooms through the Roomcord API, reports on the week and posts a reply after Alex approves |

## Try it live

- **Public website:** https://tidepathfamily.org. The made-up nonprofit's own
  site for families, volunteers, schools and donors. It exists only for this
  hackathon. Every page says so, and all data is made up.
- **How we operate:** https://tidepathfamily.org/how-we-operate/. How Tidepath
  runs on Roomcord rooms with specialist agents, with the full demo and one
  video per problem.
- **Portal for parents, volunteers and schools:** https://app.tidepathfamily.org.
  Volunteers check in, families ask for help and schools request workshops,
  in English, Spanish and Haitian Creole. Nobody installs an app or makes an
  account. The portal runs as a Cloudflare Worker.

## Why it works

- **People and agents in one place.** Every job has its own Roomcord room and
  its own agent. Staff talk to agents the way they talk to a colleague.
- **Configured by talking.** The agents run on a Codex engine. To change what an
  agent does, you tell it. To get a new tool, you ask. The workshop agent built
  the calendar app from one chat request.
- **One shared record.** Every check-in, sign-up and gift goes into one CRM that
  all agents read. The record grows every week, and the agents get more useful
  with it.
- **A person approves everything.** Agents draft. Alex approves every merge,
  every message to a family and every funder submission.
- **Open to other tools.** Rooms, messages and agent replies are available
  through the Roomcord API, so tools like OpenAI Dots can use them as a data
  source.

## Six problems, six rooms

| Problem | Room | What changes |
|---|---|---|
| **P1** From sign-up to quarterly report | Programs and mentoring | Each kid has one record. The agent flags kids who need a call this week and drafts the follow-up. The quarterly report is ready in seconds and matches every list |
| **P2** Duplicate donors and donors who stop giving | Fundraising + People CRM | Duplicates are merged only after Alex sees why they match. Late regular gifts show each week, and a failed card charge is flagged the next morning |
| **P3** From request to approved workshop | Workshop requests | A request gets a same-day reply that asks for all missing details. The room tracks which slide version the school approved, and planning calls sit on the room's calendar |
| **P4** Private counseling notes typed twice | Counseling (restricted) | The counselor writes a note once. The screen shows exactly which fields go to the funder. Names, the family's story and risk flags stay inside |
| **P5** Volunteer updates lost in group chats | Volunteers | A one-minute phone check-in becomes a logged hour, counted once. An urgent need reaches the right person the same day |
| **P6** Grants, each with its own rules | Grants and finance | Drafts use only approved, sourced facts within the word limit. Spending is tracked by category in the funder's own year |

## Under the hood

```
Parents, volunteers, schools ──> portal (app.tidepathfamily.org) ──┐
                                                                    v
Alex ─────────────────────────> Roomcord: one room per job, one agent per room
                                    │             │
                                    v             v
                     People CRM room app    shared CRM (one record per person)
                                                  ^
OpenAI Dots ──> Roomcord API ─────────────────────┘ (reads rooms and messages)
```

| Agent (flavor) | Room | Job |
|---|---|---|
| `tidepath_director` | Director desk + all rooms except Counseling | Approval queue, weekly digest, routing urgent needs between rooms, People CRM steward |
| `tidepath_programs` | Programs and mentoring | At-risk kids each week, follow-up drafts (EN/ES/HT), quarterly outcome report |
| `tidepath_volunteers` | Volunteers | Volunteer texts and forms become logged hours and visits, counted once. Urgent needs flagged the same day |
| `tidepath_fundraising` | Fundraising | Duplicate donors with match reasons, late regular gifts, failed monthly charges |
| `tidepath_workshops` | Workshop requests | Request to confirmed workshop, one reply for all missing details, approved slide version, room calendar |
| `tidepath_counseling` | Counseling (restricted) | Note written once, funder gets only its required fields, send and access log |
| `tidepath_grants` | Grants and finance | Drafts from approved, sourced facts within word limits, grant spend by category in the funder's year |
| `tidepath_web` | Website | Updates announcements on tidepathfamily.org and redeploys the site |

```
flavors/     agent roles: instructions, rules, skills, schedules
skills/      agent skills, Python 3 stdlib scripts with tests
build/       flattened flavors, ready to install on an Autoworker Hub
apps/        People CRM room app
portal/      public portal for parents, volunteers and schools
website/     tidepathfamily.org (Hugo, Cloudflare Pages)
demo-data/   one made-up quarter (Q3 2026)
docs/        system map, architecture and planning documents
tools/demo-video/   the kit that made the demo videos
```

Try the shared CRM locally:

```bash
python3 skills/tidepath-crm/scripts/crm.py --db /tmp/tidepath.db seed demo-data
python3 skills/tidepath-crm/scripts/crm.py --db /tmp/tidepath.db dupes
python3 skills/tidepath-crm/scripts/crm.py --db /tmp/tidepath.db at-risk --week 2026-09-28
python3 skills/tidepath-crm/scripts/crm.py --db /tmp/tidepath.db report --quarter 2026Q3
python3 -m pytest skills
```

More: the [system map](docs/system-map.html) shows how the portal, rooms, agents
and data connect. The planning documents are in [docs/README.md](docs/README.md).

## Limits

- Made-up data only. The counseling flow is not a HIPAA-approved system.
- No WhatsApp scraping. Agents read only messages that volunteers send on
  purpose, or chats exported with WhatsApp's Export chat option.
- Agents draft. A person approves every merge, message and submission.
