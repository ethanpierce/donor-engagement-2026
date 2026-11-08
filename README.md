# Tidepath Family Alliance agents

Website: https://tidepathfamily.org

DevDay Exchange Community Hackathon 2026, Miami. Tidepath Family Alliance is a
fictional Miami-Dade nonprofit. All data in this repository is made up.

Tidepath runs as a private server on Roomcord. Each staff process has its own
room. Each room has a specialist agent on an Autoworker Hub with the Codex
runtime. One operator (Alex) plays every staff role and approves every merge,
outbound message and funder submission.

## Agents (flavors)

| Flavor | Problem | Room | Job |
|---|---|---|---|
| `tidepath_director` | all | Director desk + all rooms except Counseling | Approval queue, weekly digest, cross-room routing of urgent needs, People CRM steward |
| `tidepath_programs` | P1 | Programs and mentoring | Weekly at-risk kids, follow-up drafts (EN/ES/HT), quarterly outcome report |
| `tidepath_volunteers` | P5 | Volunteers | Volunteer texts and forms become logged hours and visits, counted once. Urgent needs reach staff the same day |
| `tidepath_fundraising` | P2 | Fundraising | Duplicate donors with match reasons, late regular gifts, failed monthly gifts |
| `tidepath_workshops` | P3 | Workshop requests | Request to confirmed workshop, one reply for all missing details, approved slide version tracked |
| `tidepath_counseling` | P4 | Counseling (restricted) | Note written once, funder gets only its required fields, send and access log |
| `tidepath_grants` | P6 | Grants and finance | Drafts from approved, sourced facts within word limits, grant spend by category in the funder's year |

## Layout

```
flavors/     flavor sources (agent_specialization.md, flavor.yaml, cron/)
skills/      skill packages; scripts are Python 3 stdlib
  tidepath-crm/   shared CRM: dedupe with reasons, approved merge, at-risk list,
                  volunteer log, reconciled quarterly report (+ tests)
build/       flattened flavors, base included, ready to install on a Hub
demo-data/   one made-up quarter (Q3 2026): sign-ups, attendance, mentors,
             volunteer hours and messages, donations
```

`flavors/*/composition.yaml` names the `roomcord_base` base from the Autoworker
flavor market. `build/` holds the same flavors with that base already applied.

## Try the CRM

```bash
python3 skills/tidepath-crm/scripts/crm.py --db /tmp/tidepath.db seed demo-data
python3 skills/tidepath-crm/scripts/crm.py --db /tmp/tidepath.db dupes
python3 skills/tidepath-crm/scripts/crm.py --db /tmp/tidepath.db at-risk --week 2026-09-28
python3 skills/tidepath-crm/scripts/crm.py --db /tmp/tidepath.db report --quarter 2026Q3
python3 -m pytest skills/tidepath-crm/tests
```

## System map

[docs/system-map.html](docs/system-map.html) shows how the portal, rooms, agents
and data connect, and the path of each problem.

## Planning documents

The system handoffs, the architecture contract and the original event
document are in [docs/README.md](docs/README.md).

## Limits

- Made-up data only. The counseling flow is not a HIPAA-approved system.
- No WhatsApp scraping. Agents read only messages that volunteers send on
  purpose, or chats exported with WhatsApp's Export chat option.
- Agents draft. A person approves every merge, message and submission.
