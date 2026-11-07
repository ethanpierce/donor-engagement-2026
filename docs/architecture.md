# Shared architecture and delivery contract

Status: proposed design. This handoff contains documents only. API routes, fixtures, tokens, and test outcomes are specifications, not existing services or passing evidence.

## Product boundary

Tidepath Family Alliance is the fictional nonprofit for C1–C6. Mangrove Mews Cat Rescue is the fictional organization for C7. Keep their data in separate organizations. C8 requires a separately chosen real nonprofit problem using synthetic personal details.

BeWize supplies a candidate operating foundation: shared rooms, managed agents, workspaces, schedules, and operational visibility. Verify actual service contracts before reuse. A product claim does not prove an integration or a permission guarantee.

This repository proposes domain modules around that foundation. It does not authorize changes in the Roomcord client, backend, deployed tenants, or shared infrastructure. Implementation location and BeWize integration boundaries require agreement before coding outside this repository.

## Ownership

| Owner | Authoritative data |
|---|---|
| S1 | People, organizations, relationships, approved identity links |
| S2 | Program enrollment, attendance, mentor matches, volunteer visits and hours |
| S3 | Gifts, donor schedules, late-gift signals |
| S4 | Tasks, approvals, workflow stages, reminders |
| S5 | Sources, approved facts, templates, immutable document versions |
| S6 | Restricted counseling notes and funder export records |
| S7 | Grants, budget categories, accounting allocations, application questions |
| S8 | Cats, colonies, feeding visits, animal status history |
| S9 | Intake batches, mappings, provider receipts, delivery attempts |
| S10 | Derived reports and audit views, without copying authority from source modules |
| S11 | Authentication, membership, authorization, jobs, storage, idempotency, audit infrastructure |
| S12 | Cross-module test fixtures, verification cases, and result evidence |

Do not create parallel person stores or competing financial totals. Module records reference their authoritative owner by ID. Chat helps staff coordinate. It is not the business record of truth.

## Shared technical contract

- D1. Use `/api/v1/orgs/:orgId/<module>` for organization-owned API routes. Organization IDs in URLs never replace server-side authorization.
- D2. Use string IDs and UTC ISO 8601 timestamps. Display operational dates in the organization's configured timezone, initially America/New_York.
- D3. Store money as integer minor units plus currency. Store duration as integer minutes. Reject implicit currency conversion.
- D4. Use half-open report intervals `[start, end)`. Preserve each funder's fiscal dates independently from the nonprofit's year.
- D5. Require an `Idempotency-Key` for business mutations. Repeating the same request returns the same result. Reusing a key with different input returns 409.
- D6. Return 401 without authentication, 403 for a known forbidden action, 404 for inaccessible cross-organization objects, and 409 for revision conflicts. Validate input before committing it. Module-specific validation codes must be documented.
- D7. Write business changes and durable outbox entries transactionally. Retries must not duplicate records, messages, or report contributions.
- D8. Bind approvals to an immutable revision or content hash. Edits require a new approval. Maintain actor, timestamp, source, and reason.
- D9. Agents propose extraction, matching, drafting, and routing. Deterministic services validate, authorize, calculate, and commit authoritative changes.
- D10. Use a separate restricted boundary for S6. General search, ordinary agents, logs, and reports must not receive counseling-note content.

## Demo defaults

Use local services, synthetic fixtures, CSV imports, and visible delivery/calendar simulators initially. Mark simulated delivery explicitly. A local sink proves workflow logic, not successful delivery to a school or funder.

Use a responsive external form for volunteers and schools. Do not require them to install BeWize. C3's full requirement covers email, text, phone, website, existing calendars, and English, Spanish, and Haitian Creole. A single-channel demo must identify the remaining channels as incomplete.

C5 and C7 may ingest synthetic WhatsApp Export chat archives. Do not scrape live WhatsApp chats. Do not use real clinical notes or real colony locations.

## Build sequence

1. Establish S11 and the synthetic fixtures and critical gates from S12.
2. Add S1 and the minimal S9 intake path.
3. Add S4 approval and task primitives with S10 audit/report contracts.
4. Complete one vertical workflow through its API and UI before extending shared modules.
5. Add S2 and S3, then S5 and S7, then S8. Build S6 within its separate restricted boundary.
6. Run the full S12 matrix after shared contract changes.

These are delivery stages, not permission to deploy. The cumulative estimate is 192–384 AI hours. Parallel work reduces elapsed time only when dependencies and review capacity permit it.

## Decisions before live use

| Code | Decision | Proposed demo default |
|---|---|---|
| Q1 | Application stack and implementation repository | Reuse verified existing services. Choose the stack before implementation. No framework is selected by this handoff. |
| Q2 | BeWize identity and organization mapping | One explicit organization mapping per demo nonprofit. Verify the authentication contract first. |
| Q3 | External providers and credentials | Local simulators, no live credentials in repository fixtures. |
| Q4 | Clinical operating requirements | Synthetic-only isolated demo. No compliance or production-readiness claim. |
| Q5 | Actual budget, retention, backup, and operational ownership | Measure usage and agree policy before a live pilot. No low-cost claim without evidence. |
| Q6 | Which challenge is the initial delivery target | C5 is the suggested first workflow. No additional C8 scope is assumed. |

## Completion evidence

Each implementation must retain API test results, UI test results, fixture version, and the commit tested. A handoff is complete when its document is present and internally checked. A system is complete only when its challenge outcomes pass verification.
