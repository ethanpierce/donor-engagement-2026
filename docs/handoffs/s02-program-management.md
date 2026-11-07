# S2 — Program management

Status: implementation handoff, proposed design. Complexity: **Medium**. Estimate: **10–20 cumulative AI hours** for coding, tests, and fixes, with developer review. This estimate covers synthetic demo scope, not production readiness.

## Shared contract and boundaries

Follow [the architecture contract](../architecture.md). All routes below are proposed, not implemented. IDs are strings. Timestamps are UTC. The server checks organization membership and object access on every request. Cross-organization objects return 404. Missing authentication returns 401. A forbidden action returns 403. Revision conflicts return 409. Business mutations require `Idempotency-Key`; retries return the original result and conflicting payloads return 409.

Use synthetic data and local delivery simulators. BeWize reuse is a candidate integration, not a verified dependency. Do not deploy or modify another repository or environment from this handoff. Agents propose changes. Deterministic services validate, authorize, calculate, commit, and audit them. Never treat chat or an agent answer as the authoritative record.

## API-first verification setup

Run these proposed tests only after the implementation exists. Commands specify expected behavior, not passing evidence. `jq` is required. S12 provisions `tidepath-demo`, the synthetic actors, and resettable data. Tokens below are supplied by the local test harness, never committed secrets.

```bash
export API_ROOT='http://localhost:3000/api/v1/orgs/tidepath-demo'
export TOKEN='replace-with-local-authorized-token'
export VIEWER_TOKEN='replace-with-local-read-only-token'
```

## Outcome and challenge mapping

C1 needs linked sign-ups, attendance, mentor matches, volunteer hours, same-week follow-up, and a quarterly report. C5 needs deduplicated volunteer visits, hours, observations, photos, and urgent needs. C2–C4 and C6–C8 are not directly implemented here.

## Scope and non-goals

Implement programs, enrollments, sessions, attendance, mentor assignments, and volunteer activities. Detect missing sessions and missing mentor contact. Route follow-up to S4 and deliver through S9. Exclude donor histories, clinical notes, and a replacement school calendar.

## Minimal records and invariants

| Record | Required fields and rules |
|---|---|
| Program | `id`, name, reporting timezone, active dates |
| Enrollment | program ID, S1 child ID, start/end dates, status |
| Session | program ID, scheduled UTC time, expected enrollment IDs |
| Attendance | session ID, enrollment ID, present/absent/excused/unknown, source |
| Mentor assignment | child ID, mentor ID, effective dates, contact expectation |
| Volunteer activity | volunteer ID, visit time, integer duration minutes, permitted participant references, observations, photo references, source identity |
| Follow-up signal | rule version, subject, reporting week, evidence, owner, S4 task ID |

Unique attendance key is session plus enrollment. An unknown mark is not an absence. Missing mentor contact is a rule result, not an agent guess. Use approved activity records for totals. Two volunteers at one visit can each have valid hours. Detect duplicates per volunteer and source, then send ambiguous cross-source matches for review. Never sum unreviewed extraction twice.

## Dependencies and responsibilities

S1 supplies person identities. S9 supplies forms, imports, attachments, and delivery receipts. S4 owns tasks and escalation. S10 computes report views from authoritative attendance and activities. S11 supplies permissions, jobs, and event infrastructure.

Agents extract activity proposals and draft follow-ups. Services calculate minutes, attendance totals, and rule results. Staff resolve ambiguous identities, approve corrections, and own urgent follow-up. Volunteers may submit their own activities but cannot inspect other families.

## Proposed API

| Method and route | Contract |
|---|---|
| `POST /programs` | Create program |
| `POST /programs/:id/enrollments` | Link an existing S1 child |
| `POST /programs/:id/sessions` | Create session and expected enrollments |
| `PUT /programs/:id/sessions/:sessionId/attendance/:enrollmentId` | Record one attendance mark with revision checks |
| `POST /programs/:id/mentor-assignments` | Link a mentor and child with effective dates |
| `POST /programs/volunteer-activities` | Validate activity or create review state for ambiguous source |
| `POST /programs/follow-up-runs` | Evaluate rules at explicit synthetic clock and create deduplicated S4 tasks |
| `GET /programs/:id/summary?start=...&end=...` | Derived approved totals with source IDs |

Return 422 for negative duration, invalid enrollment dates, unsupported attendance values, and foreign-person references. Disallow overlapping active mentor assignments unless staff explicitly select a supported group-mentoring model.

## Concrete API tests

S12 seeds `child-demo`, `mentor-demo`, `enrollment-demo`, and `session-demo` under `program-demo`, plus a weekly missing-session rule.

```bash
curl -fsS -X PUT "$API_ROOT/programs/program-demo/sessions/session-demo/attendance/enrollment-demo" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H 'Idempotency-Key: attendance-demo-absent' -d '{"status":"absent","revision":0,"sourceId":"paper-demo-1"}' | jq -e '.status == "absent"'
curl -fsS "$API_ROOT/programs/volunteer-activities" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H 'Idempotency-Key: activity-demo-1' -d '{"volunteerId":"mentor-demo","participantIds":["child-demo"],"occurredAt":"2026-11-02T17:00:00Z","durationMinutes":60,"sourceId":"export-demo-message-1","observations":"Synthetic school laptop need","urgency":"same_day"}' | jq -e '.durationMinutes == 60'
curl -fsS "$API_ROOT/programs/follow-up-runs" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H 'Idempotency-Key: program-followups-demo' -d '{"asOf":"2026-11-06T17:00:00Z"}' | jq -e '.createdTaskCount >= 1'
curl -fsS "$API_ROOT/programs/program-demo/summary?start=2026-10-01T04:00:00Z&end=2027-01-01T05:00:00Z" -H "Authorization: Bearer $TOKEN" | jq -e '.volunteerMinutes == 60 and .absentCount == 1'
```

Replay the activity with the same source ID and a new idempotency key. Confirm no extra approved minutes. A second volunteer's distinct activity remains countable. Confirm the S4 urgent task has an assigned owner and an S9 simulator delivery receipt. Simulated delivery does not prove a live recipient received it.

## UI verification

- U1. Import a synthetic quarter and open a child's linked enrollment, attendance, and mentor record.
- U2. Submit a one-minute phone form with a photo. Confirm a proposed activity becomes one approved entry.
- U3. Review missing sessions and mentor contact during the same reporting week.
- U4. Open an urgent need and its delivery status. Reassign it and verify ownership history.
- U5. Generate a quarterly report in under two minutes on the documented demo fixture. Reconcile counts to source records.

## Open decisions and demo defaults

| Code | Decision | Recommended demo default |
|---|---|---|
| Q1 | Missed-session threshold | One unexcused absence triggers review during the same week. |
| Q2 | Mentor-contact interval | Weekly expectation, configured per program. |
| Q3 | Urgent routing | Staff-owned queue plus same-day escalation using organization timezone. |

These thresholds are demo policy choices, not organizer requirements. Record them visibly in settings.

## Completion criteria

A complete synthetic quarter produces consistent counts and completed follow-up evidence. A synthetic volunteer week counts every approved activity once and routes urgent needs the same day. All API, UI, and regression gates pass.

## Required regression gates

- T1. Repeat a mutation with the same idempotency key. Confirm one record and one audit entry.
- T2. Reuse that key with changed input. Confirm 409 and unchanged stored data.
- T3. Read or modify another organization's object. Confirm 404 without object details.
- T4. Call a protected route without a token. Confirm 401. Use a read-only token for writes and confirm 403.
- T5. Edit a reviewed revision. Confirm stale approvals cannot authorize the new revision.
- T6. Restart a worker during processing. Confirm retries preserve counts and do not duplicate notifications.

Run these gates plus each module's API and UI cases. Record the fixture version, tested commit, requests, responses, screenshots, and results in S12 evidence. Do not mark an unexecuted case passed.
