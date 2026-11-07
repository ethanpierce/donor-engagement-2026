# S12. End-to-end verification

Status: proposed handoff, not executed. Complexity: High. Estimate: 20–40 cumulative AI hours for test fixtures, cross-module tests, fixes, and evidence.

## Outcome and scope

Prove challenge outcomes through API tests first, then visible UI workflows. A unit test, generated document, or simulated provider is not evidence of an entire implemented challenge.

Follow [the shared architecture](../architecture.md). Use the original event collection as the acceptance source. S12 tests S1–S11 and records the actual commit, fixture version, commands, outputs, screenshots, costs, and known limits.

Non-goals: production testing, real clinical notes, live donor contact, unauthorized WhatsApp access, a separate C8 feature, or claiming all external channels work from local mocks.

## Proposed verification records

| Record | Minimum fields |
|---|---|
| FixtureManifest | id, version, syntheticOnly, organizations, principals, records, expectedTotals, clock |
| TestRun | id, commit, fixtureVersion, environment, startedAt, finishedAt, status |
| CaseResult | runId, caseCode, expected, observed, status, evidenceRefs |
| EvidenceArtifact | id, runId, kind, contentHash, localPath, sensitivity |
| CoverageGap | caseCode, missingBehavior, reason, owner, nextAction |

V1. Seed fixtures deterministically through a local-only bootstrap. Reset only a disposable local database. Never point reset commands at a remote URL.

V2. Use two organizations: Tidepath for C1–C6 and Mangrove for C7. Use synthetic names, photos, addresses, messages, notes, and locations.

V3. Pin a test clock. Store timestamps in UTC. Use America/New_York for operational days and explicit funder fiscal periods.

V4. Keep fixtures out of ordinary application APIs. A test-token endpoint or fixture reset endpoint must be absent from deployed builds.

V5. Record failure honestly. “Skipped,” “blocked,” and “simulated” are not “passed.” Re-run affected cases after fixes.

## Minimal synthetic fixture

| Fixture | Contents and expected result |
|---|---|
| People | A child, guardian, mentor, and volunteer. Guardian name variants resolve to one canonical person after approval. |
| Programs | One quarter with sign-up, attendance, mentor assignment, and two unique visits of 60 and 90 minutes. One duplicate import and one pending visit do not increase approved totals. |
| Donors | Rosa Demo name variants, preserved gifts, an overdue annual gift, and a failed monthly gift with failure timestamp. |
| Workshop | One eighth-grade request, English/Spanish/Haitian Creole variants, missing room/date fields, two slide revisions, and one approved revision. |
| Counseling | Five synthetic sessions for an assigned counselor, private narrative markers, and funder field allowlists. |
| Grant | One USD grant, category budget 100,000 cents, spending 12,500 cents, July–June fiscal year, and boundary transactions. |
| Volunteers | A phone-form message, a synthetic exported chat, a photo, an urgent diaper need, and repeated source delivery. |
| Rescue | Two colonies, two photos of one cat, an injured cat, kittens, and a missed feeding. Use invented locations. |
| Access | Admin, program manager, fundraising coordinator, counselor, bookkeeper, volunteer, rescue coordinator, and limited agent tokens. |

The cross-module fixture above is separate from each module's isolated fixture. For example, S7 uses 20,000 cents spent in its own test. Do not mix their expected totals.

## Challenge acceptance matrix

| Case | API assertions | UI walk and observable outcome |
|---|---|---|
| C1-A | Import the quarter through S9. Assert one canonical record, linked enrollment/mentor/attendance, 150 approved volunteer minutes, and accurate report lineage. | Import, review duplicate, open child history, inspect missed-session task, confirm delivery receipt, generate quarter report. |
| C2-A | Before staff approval, duplicates remain separate. After approval, all gift IDs survive. Late-gift output includes last gift, usual amount and timing, plus draft note. Failed gift is detected within the agreed test threshold. | Review match reasons, approve merge, inspect complete history, open weekly late list, approve a note to the local sink. |
| C3-A | Request intake asks all missing fields together. Calendar sink has one planning event. Staff approve exact slide hash. School approval refers to that version. Reminders deliver once. | Submit externally without installing an app, answer missing questions, approve slides, use external approval link, inspect request stage and reminders. |
| C4-A | One synthetic note fills only allowlisted funder fields. Unassigned users cannot read it. Exact export manifest and all authorized accesses are recorded. | Counselor writes once, checks export preview, approves local sink delivery, and inspects access history. Private narrative marker never appears in output. |
| C5-A | Text/photo intake creates one approved visit. Duplicate delivery adds no hours. Urgent need has same-day local sink receipt. Weekly total is 150 minutes. | Submit phone form, inspect extracted fields/photo, resolve review, receive urgent task, acknowledge it, open weekly report. |
| C6-A | All draft facts cite approved sources. Missing facts remain flagged. Word limits pass. Spent=12,500 and remaining=87,500 cents. Fiscal boundary records are classified correctly. | Review the whole synthetic application, inspect citations and missing fields, approve drafts, view category balance and funder-year report. |
| C7-A | One canonical cat remains after human-approved match. Colony totals, TNR, vet needs, feeding, and same-day urgent alerts agree with source events. | Submit synthetic photo/message/location, review proposed match, confirm merge, inspect colony state and urgent queue as rescue coordinator. |
| C8-A | No implementation assertion until a real nonprofit problem, current cost, and two or three observable outcomes are selected. | Present that problem first. Test the selected bounded workflow with synthetic personal details. |

C3-A's complete channel matrix includes email, text, phone, website, existing calendars, and all three languages. A local single-channel demo can pass its bounded scenario while the full challenge remains incomplete. Explicitly list untested providers and languages.

## API-first execution recipe

These are proposed contracts, not commands that currently pass. Implement the local fixture bootstrap before running them. Follow each module's curl recipe for writes. Capture returned IDs rather than assuming production-like IDs.

```bash
API=http://localhost:3000/api/v1
curl --fail-with-body -sS "$API/orgs/tidepath-demo/foundation/session" -H "Authorization: Bearer $ADMIN_TOKEN"
curl --fail-with-body -sS "$API/orgs/tidepath-demo/intake/batches" \
  -H "Authorization: Bearer $STAFF_TOKEN" -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: s12-volunteer-intake-01' \
  --data '{"channel":"web_form","sourceId":"s12-week-01","items":[{"externalId":"s12-visit-01","occurredAt":"2026-11-02T15:00:00Z","text":"Synthetic volunteer spent 60 minutes with demo family. Needs diapers today.","synthetic":true}]}'
```

Save the intake ID as `BATCH_ID`. Preview, commit, and wait for completion.

```bash
curl --fail-with-body -sS "$API/orgs/tidepath-demo/intake/batches/$BATCH_ID/preview" -H "Authorization: Bearer $STAFF_TOKEN"
curl --fail-with-body -sS -X POST "$API/orgs/tidepath-demo/intake/batches/$BATCH_ID/commit" \
  -H "Authorization: Bearer $STAFF_TOKEN" -H 'Idempotency-Key: s12-volunteer-commit-01'
curl --fail-with-body -sS "$API/orgs/tidepath-demo/reports/snapshots" \
  -H "Authorization: Bearer $STAFF_TOKEN" -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: s12-week-report-01' \
  --data '{"kind":"volunteer_week","from":"2026-11-02T05:00:00Z","to":"2026-11-09T05:00:00Z","timeZone":"America/New_York"}'
```

Save the report ID as `REPORT_ID`. Verify it after its job completes.

```bash
curl --fail-with-body -sS "$API/orgs/tidepath-demo/reports/snapshots/$REPORT_ID" -H "Authorization: Bearer $STAFF_TOKEN"
curl -sS -o /tmp/s12-cross-org.json -w '%{http_code}\n' "$API/orgs/tidepath-demo/reports/snapshots/$REPORT_ID" -H "Authorization: Bearer $OTHER_ORG_TOKEN"
curl -sS -o /tmp/s12-anonymous.json -w '%{http_code}\n' "$API/orgs/tidepath-demo/reports/snapshots/$REPORT_ID"
```

Expect 404 for cross-organization read and 401 without a token. For the complete two-visit fixture, assert exactly 150 minutes. A report containing only the first posted visit must show 60 minutes, not the final fixture total.

## Critical regression gates

| Gate | Failure injection and required result |
|---|---|
| G1 Authorization | Cross-organization IDs, copied file URLs, search, exports, and agent tools expose no private data. Revoked access fails immediately on the next request. |
| G2 Idempotency | Repeat each import, commit, approval execution, and delivery. One business result remains. A reused key with changed body returns 409. |
| G3 Approval integrity | Edit slides, merge candidates, cat status changes, or funder exports after approval. Execution requires new approval. |
| G4 Data preservation | Merge records, correct attendance, and void transactions. Original source history remains traceable. |
| G5 Clinical boundary | Raw note marker is absent from ordinary logs, rooms, general search, model requests, and unauthorized exports. |
| G6 Deterministic totals | CSV export, API, UI, and source calculations agree for minutes, money, unique people, cats, and fiscal boundaries. |
| G7 Recovery | Stop a worker after commit. Resume without duplicate sends. Unknown provider delivery stays unknown until reconciliation. Restore synthetic backup successfully. |
| G8 Safe failures | Invalid files, ambiguous extraction, provider outage, malformed model output, and empty results show actionable errors without fabricated success. |
| G9 External intake | Schools and volunteers complete the mobile flow without BeWize installation. Scoped links cannot read internal data. |
| G10 Low-cost evidence | Record model tokens, elapsed work, provider costs, hosting assumptions, and manual steps. Do not assert affordability without measurement. |

Run G1–G10 after shared foundation, schema, identity, job, or integration changes. Also run the changed module's API tests and UI cases. Existing implemented workflows must remain green.

## UI execution and evidence

U1. Run the API fixture setup first. Use a fresh local organization state for each destructive scenario.

U2. Walk each implemented C-case using its actual role. Switch users to verify coordinator/volunteer, counselor/admin, and Tidepath/Mangrove boundaries.

U3. Test narrow mobile and desktop layouts. Check required field labels, keyboard operation, loading states, failed submissions, and recovery without lost input.

U4. Capture each approval preview, final authoritative record, report total, and delivery receipt. Mark local sinks as simulated in screenshots and the demo.

U5. Record failures, fix them, and repeat the affected case plus critical gates. Do not replace failed evidence with a claim that another account was unavailable.

## Completion and open decisions

Q1. Agree the implementation stack and exact module endpoints before execution. This handoff specifies proposed contracts only.

Q2. Select the first vertical workflow. Recommended default: C5 using S11, S1, S9, S2, S4, and S10.

Q3. Decide which real adapters are in scope. Synthetic local sinks demonstrate workflow logic, not real-world service delivery.

Done means every implemented C-case passes its API and UI checks, G1–G10 pass, and the evidence identifies the tested commit. C8 remains unestimated until selected. Unimplemented channels, modules, and production requirements remain explicit gaps, not completed work.
