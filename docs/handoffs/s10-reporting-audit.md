# S10. Reporting and audit

Status: proposed handoff, not implemented or tested. Complexity: Medium. Estimate: 12–24 cumulative AI hours for the demo.

## Outcome and challenge mapping

Produce reproducible reports from approved structured records. Explain each number through source records and corrections. AI may draft narrative but does not calculate authoritative totals.

| Code | Required report or evidence |
|---|---|
| C1 | Quarterly enrollment, attendance, mentoring, volunteer-hour outcomes with matching totals. |
| C2 | Weekly late-gift list, last gift, usual amount/timing, and failed-gift alerts. |
| C3 | Request status, calendar confirmation, slide version, school approval, and reminder receipts. |
| C4 | Counselor-only note access history and exact funder export manifest. No general-purpose note report. |
| C5 | Weekly unique visit/hour totals and urgent-need delivery evidence. |
| C6 | Grant category balances and reports using each funder's dates. |
| C7 | Colony census, fixed/TNR counts, urgent cases, and last feeding. |
| C8 | Add measures only after the team defines the problem and observable outcomes. |

Scope: deterministic reports, CSV export, drill-through, snapshot metadata, authorized audit views. Non-goals: an analytics warehouse, predictive scoring, invented impact claims, raw counseling-note search, or compliance certification.

## Proposed records and invariants

| Record | Minimum fields |
|---|---|
| ReportDefinition | id, orgId, kind, version, metricDefinitions, requiredPermission |
| ReportSnapshot | id, definitionId, orgId, from, to, timeZone, cutoffAt, generatedAt, recordIds, totals, status |
| MetricLineage | snapshotId, metricKey, contributingRecordIds, exclusions, correctionIds |
| AuditEvent | id, orgId, actorId, action, objectType, objectId, occurredAt, requestId, metadata |
| ExportManifest | id, orgId, snapshotId, fieldAllowlist, recipientRef, approvedBy, sentAt, deliveryId |

- I1. Date intervals are half-open: `from <= occurredAt < to`. Store UTC instants and the selected reporting timezone.
- I2. Sum integer minutes and currency minor units. Never sum different currencies into one balance.
- I3. Approved canonical records count once. Show exclusions for duplicate, void, or pending records.
- I4. A snapshot records cutoff and definition version. Later corrections produce a new snapshot, preserving the old one.
- I5. Audit events are append-only. Capture successful sensitive reads and denied access without logging note bodies, secrets, or full personal data.
- I6. Resolve permissions for drill-through and exports at request time. Aggregate visibility never grants raw-record access.
- I7. Mark stale or incomplete imports and missing receipts. A queued reminder is not a delivered reminder.

## Proposed API contract

Prefix: `/api/v1/orgs/:orgId/reports`. IDs are strings. These routes are proposed.

| Method and route | Contract |
|---|---|
| POST /snapshots | Accept kind, interval, timezone. Return 202, snapshot ID, and job ID. |
| GET /snapshots/:id | Return ready/failed state, totals, exclusions, and definition version. |
| GET /snapshots/:id/lineage?metric=:key | Return permitted contributing references. |
| GET /snapshots/:id/export?format=csv | Return authorized fields and a safe filename. Audit download. |
| GET /audit-events | Return permission-filtered events using cursor pagination. |

Require `Idempotency-Key` on snapshot creation. Return 422 for invalid periods, 403 for forbidden report types, and 404 for another organization's snapshots. Clinical access events require the S6 audit permission.

## Ownership and dependencies

D1. S1–S3, S6–S8 own source records and correction rules. S4 supplies workflow states. S9 supplies import and delivery state.

D2. S11 owns audit persistence, authorization, export storage, and jobs. S10 owns report definitions and lineage presentation.

D3. Agents explain a report using its snapshot and cited facts. Staff approve narratives and external exports. Code computes and checks totals.

## API-first tests

Create a local synthetic fixture through the documented S2 and S7 setup routes before these calls. The fixture contains unique visits of 60 and 90 minutes, one duplicate import, one pending visit, and USD grant spending of 12,500 cents against a 100,000-cent category.

```bash
API=http://localhost:3000/api/v1
curl --fail-with-body -sS "$API/orgs/tidepath-demo/reports/snapshots" \
  -H "Authorization: Bearer $STAFF_TOKEN" -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: s10-week-01' \
  --data '{"kind":"volunteer_week","from":"2026-11-02T05:00:00Z","to":"2026-11-09T05:00:00Z","timeZone":"America/New_York"}'
```

Save the returned ID as `REPORT_ID`. Poll only until ready or failed.

```bash
curl --fail-with-body -sS "$API/orgs/tidepath-demo/reports/snapshots/$REPORT_ID" -H "Authorization: Bearer $STAFF_TOKEN"
curl --fail-with-body -sS "$API/orgs/tidepath-demo/reports/snapshots/$REPORT_ID/lineage?metric=volunteerMinutes" -H "Authorization: Bearer $STAFF_TOKEN"
curl --fail-with-body -sS "$API/orgs/tidepath-demo/reports/snapshots/$REPORT_ID/export?format=csv" -H "Authorization: Bearer $STAFF_TOKEN" -o /tmp/s10-report.csv
curl -sS -o /tmp/s10-denied.json -w '%{http_code}\n' "$API/orgs/tidepath-demo/reports/snapshots/$REPORT_ID" -H "Authorization: Bearer $OTHER_ORG_TOKEN"
```

T1. Assert 150 approved minutes, exactly two contributing visits, one excluded duplicate, and one excluded pending record. Cross-organization read returns 404.

T2. Repeat creation with the same key. Assert the same snapshot ID. Correct a visit and generate a new snapshot. Assert the old snapshot remains unchanged.

T3. Generate a grant report for the funder's July–June year. Assert spent=12,500 and remaining=87,500 cents. A transaction exactly at `to` belongs to the next period.

T4. Request clinical evidence with a volunteer token. Expect 403. Verify the denied event exists without exposing note content.

T5. Fail one source import. Assert the report marks incompleteness and does not invent zero values for missing data.

## UI tests and completion

- U1. Select a quarter and inspect totals, date boundaries, timezone, and source cutoff.
- U2. Open a metric's contributing records. Explain every included and excluded row.
- U3. Export CSV and compare its totals with the screen. Formula-like source names remain safe text.
- U4. Correct a source record. See a new report version and the prior snapshot's unchanged values.
- U5. Change to a restricted account. Confirm clinical data, feeder locations, and donor details are absent where unauthorized.
- U6. Display failed generation, stale imports, and pending delivery without a misleading success label.

Q1. Agree funder templates and metric definitions with their owner. Demo default: explicitly documented synthetic templates, not invented contractual requirements.

Q2. Choose audit retention and external export rules before production. Preserve all demo evidence until review.

Done means API and UI totals match source fixtures, permissions pass, all required reports expose lineage, and sensitive exports show exact fields. Record measured generation time and commands. “Ready in minutes” must have measured evidence.
