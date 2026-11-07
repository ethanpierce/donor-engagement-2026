# S4 — Request and workflow management

Status: implementation handoff, proposed design. Complexity: **High**. Estimate: **20–40 cumulative AI hours** for coding, tests, and fixes, with developer review. This estimate covers synthetic demo scope, not production readiness.

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

C3 requires a request-to-workshop workflow with missing-information collection, planning calls, staff-approved slides, version-specific school sign-off, and reminders. C1/C2/C5 use follow-up tasks. C4/C6 use revision-bound export/document approvals. C7 uses urgent animal-care tasks and approved status changes. C8 can reuse primitives only after its scope is chosen.

## Scope and non-goals

Implement tasks, owners, due dates, explicit state transitions, human approvals, reminders, and resumable workflows. Provide a concrete workshop workflow using existing staff calendar adapters through S9. Exclude a generic workflow designer, a new calendar product, unreviewed external sends, and arbitrary agent-defined state transitions.

## Minimal records and invariants

| Record | Required fields and rules |
|---|---|
| Workflow instance | type, subject reference, stage, revision, owner, source intake ID |
| Task | type, subject, assignee, due timestamp, state, escalation owner |
| Approval | target reference, immutable revision/hash, authorized approver, decision, time |
| Scheduled action | workflow revision, due timestamp, action type, deduplication key, attempt state |
| Workshop request | school S1 ID, age group, topic, language, format, preferred dates, room, contact, stage |
| Calendar link | provider reference, event revision, confirmed time, sync state |
| Workshop document link | S5 slide version ID, staff approval ID, school approval receipt |

Workshop stages are intake → needs_information → planning_scheduled → slides_draft → staff_review → school_review → confirmed → completed. Support cancelled and needs_attention. Staff may pause or reassign at every stage. Reject transitions that skip required checks. Edits to slides invalidate both approvals. Date changes invalidate affected reminders and calendar confirmation. A delivery attempt is not proof of receipt.

## Dependencies and responsibilities

S1 owns school contacts and staff references. S5 owns immutable slide versions and draft sources. S9 owns channel intake, authorized school approval links, calendar adapter calls, sends, receipts, and retries. S11 owns reliable jobs, transactions, authentication, and audit. S2/S3/S6/S7/S8 create domain-specific tasks here. S10 reads state and history.

Agents extract missing details, ask all missing questions together, draft slides, and suggest routing. Deterministic rules enforce transitions and approval gates. Staff approve slides before school access. The school's authorized contact approves a specific version through an expiring scoped link without installing an app. Staff authorize any clinical export within S6's restricted boundary. S4 stores only opaque references and approval metadata for those cases.

## Proposed API

| Method and route | Contract |
|---|---|
| `POST /workflows/workshops` | Create request from S9 normalized intake |
| `GET /workflows/:id` | Authorized stage, outstanding information, tasks, document and calendar references |
| `POST /workflows/:id/transitions` | Validate requested state and expected workflow revision |
| `POST /workflows/:id/approvals` | Decide on a specific immutable target revision |
| `POST /workflows/tasks` | Create typed, domain-referenced task with assigned owner |
| `POST /workflows/tasks/:id/transitions` | Claim, complete, reassign, pause, or reopen with revision checks |
| `POST /workflows/scheduler-runs` | Demo-only authorized clock-driven scheduler invocation |

Return 422 for missing assignee, invalid stage, unsupported language, or an incomplete request proposed as confirmed. Return 409 for stale revision or approval. External approvals enter through S9's scoped approval-link flow and call the same authorization and revision checks. Never expose internal bearer tokens in external links.

## Concrete API tests

S12 seeds school `school-demo`, staff `staff-coordinator`, verified calendar simulator configuration, and a staff-reviewed S5 document `slides-demo` revision 1.

```bash
WORKFLOW=$(curl -fsS "$API_ROOT/workflows/workshops" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H 'Idempotency-Key: workshop-intake-1' -d '{"schoolId":"school-demo","ownerId":"staff-coordinator","sourceIntakeId":"intake-demo-1","topic":"Safety","language":"es","ageGroup":"grade_8","format":"in_person"}')
WORKFLOW_ID=$(printf '%s' "$WORKFLOW" | jq -er .id)
curl -fsS "$API_ROOT/workflows/$WORKFLOW_ID" -H "Authorization: Bearer $TOKEN" | jq -e '.missingFields | index("preferredDates") != null'
curl -sS -o /tmp/workshop-rejected.json -w '%{http_code}
' "$API_ROOT/workflows/$WORKFLOW_ID/transitions" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H 'Idempotency-Key: workshop-invalid-confirm' -d '{"to":"confirmed","expectedRevision":1}'
# Expect HTTP 422. No calendar event or notification may be created.
curl -fsS "$API_ROOT/workflows/tasks" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H 'Idempotency-Key: urgent-demo-task' -d '{"type":"urgent_need","subject":{"module":"programs","id":"activity-demo"},"assigneeId":"staff-coordinator","dueAt":"2026-11-07T22:00:00Z","escalationOwnerId":"staff-manager"}' | jq -e '.state == "open"'
curl -fsS "$API_ROOT/workflows/scheduler-runs" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H 'Idempotency-Key: scheduler-demo-1' -d '{"asOf":"2026-11-07T23:00:00Z"}' | jq -e '.escalatedCount >= 1'
```

For the full API path, S12 seeds a second workflow in `staff_review`, revision 4, with attached `slides-demo` revision 1. Approve that exact target, transition to school review, and record the S9 school receipt. Confirm only then. Create slide revision 2 and verify confirmation is blocked until both reviews recur. Scheduler replay must create one reminder per workflow revision and scheduled action.

## UI verification

- U1. Submit one synthetic workshop request from an external phone form. Confirm no installation is required.
- U2. Show one response asking every missing question. Complete details and schedule the planning call on the calendar simulator.
- U3. Produce age-, topic-, language-, and format-specific slides through S5. Staff review precedes school access.
- U4. Approve through the school link. Show the approved slide version and coordinator's stage list.
- U5. Change the date and slides. Confirm stale approvals and reminders cannot apply.
- U6. Pause, reassign, and resume the request. Confirm history and a visible owner throughout.
- U7. Test English, Spanish, and Haitian Creole text. Label unimplemented phone/email/SMS adapters incomplete rather than claiming full C3 coverage.

## Open decisions and demo defaults

| Code | Decision | Recommended demo default |
|---|---|---|
| Q1 | External channels and calendars | Responsive form plus local mail/calendar sinks first. Clearly mark simulation. |
| Q2 | Same-day response policy | Due before end of local operating day, explicit timezone and late-arrival handling. |
| Q3 | School approval authority | One named synthetic school contact with an expiring revision-scoped link. |
| Q4 | Escalation ownership | Required staff-manager fallback. No unowned urgent task. |

## Completion criteria

One request reaches a confirmed workshop with version-specific staff and school approval. Follow-ups retain ownership, delivery state, and retry safety. Full C3 coverage additionally requires all requested channels, languages, and the existing-calendar integration. All API, UI, and regression gates pass.

## Required regression gates

- T1. Repeat a mutation with the same idempotency key. Confirm one record and one audit entry.
- T2. Reuse that key with changed input. Confirm 409 and unchanged stored data.
- T3. Read or modify another organization's object. Confirm 404 without object details.
- T4. Call a protected route without a token. Confirm 401. Use a read-only token for writes and confirm 403.
- T5. Edit a reviewed revision. Confirm stale approvals cannot authorize the new revision.
- T6. Restart a worker during processing. Confirm retries preserve counts and do not duplicate notifications.

Run these gates plus each module's API and UI cases. Record the fixture version, tested commit, requests, responses, screenshots, and results in S12 evidence. Do not mark an unexecuted case passed.
