# Nonprofit systems handoff

Planning documents for the DevDay Exchange Community Hackathon, November 7–8, 2026.

These documents propose a synthetic-data demo built on BeWize. No system is implemented or tested by this handoff. The repository's existing license is unchanged.

## Start here

1. Read [the original challenges and event document](source/original-challenges-and-event.md).
2. Read [the shared architecture and delivery contract](architecture.md).
3. Select the challenge and read its system handoffs below.
4. Implement the API and run its curl cases before testing the UI.
5. Use S12 to verify the complete workflow.

The original document is the collected event snapshot from November 7. It includes the full eight problem statements, constraints, judging criteria, submission requirements, and community snapshot. It is preserved without changes. Organizer requirements take precedence over proposed implementation choices.

## Systems and estimates

Estimates are cumulative AI implementation hours, including tests and fixes, with developer review. They are rough planning ranges, not delivery commitments. They assume synthetic demo data and reuse of verified BeWize capabilities. They exclude production readiness, live provider onboarding, and clinical compliance work.

| Code | System handoff | Challenges | Complexity | AI hours |
|---|---|---|---|---:|
| S1 | [Nonprofit CRM](handoffs/s01-crm.md) | C1, C2, C3, C5 | Medium | 12–24 |
| S2 | [Program management](handoffs/s02-program-management.md) | C1, C5 | Medium | 10–20 |
| S3 | [Fundraising management](handoffs/s03-fundraising.md) | C2 | Medium | 10–20 |
| S4 | [Workflow management](handoffs/s04-workflow-management.md) | C1–C7 | High | 20–40 |
| S5 | [Documents and knowledge](handoffs/s05-documents-knowledge.md) | C3, C4, C6 | Medium | 12–24 |
| S6 | [Restricted case management](handoffs/s06-case-management.md) | C4 | High | 20–40 |
| S7 | [Grants and budgets](handoffs/s07-grants-budgets.md) | C6 | High | 20–40 |
| S8 | [Animal and colony registry](handoffs/s08-animal-colony-registry.md) | C7 | Medium | 12–24 |
| S9 | [Integrations and intake](handoffs/s09-integrations-intake.md) | C1–C7 | High | 24–48 |
| S10 | [Reporting and audit](handoffs/s10-reporting-audit.md) | C1–C7 | Medium | 12–24 |
| S11 | [Shared foundation](handoffs/s11-foundation.md) | All selected workflows | High | 20–40 |
| S12 | [End-to-end verification](handoffs/s12-verification.md) | All selected workflows | High | 20–40 |
| | Total | C1–C7 | High | 192–384 |

C8 is the open track. Shared systems can support it, but no additional open-track problem is selected or estimated.

## Challenge routes

| Code | Original challenge | Systems needed |
|---|---|---|
| C1 | From sign-up to quarterly report | S1, S2, S4, S9, S10, S11, S12 |
| C2 | Duplicate donor records, and donors who quietly stop giving | S1, S3, S4, S9, S10, S11, S12 |
| C3 | From request to approved workshop | S1, S4, S5, S9, S10, S11, S12 |
| C4 | Private counseling notes typed twice | S4, S5 templates only, S6, S9 restricted adapter, S10 restricted audit, S11, S12 |
| C5 | Volunteer updates lost in group chats | S1, S2, S4, S9, S10, S11, S12 |
| C6 | Grant applications and reports, each with its own rules | S4, S5, S7, S9, S10, S11, S12 |
| C7 | Bonus challenge: Cat colony updates scattered across chats and photos | S4, S8, S9, S10, S11, S12 |
| C8 | Open track: your own nonprofit problem | Define the problem first, then select systems |
