# S6. Restricted case management

Status: proposed handoff, not implemented or verified. Complexity: High. Estimate: 20–40 cumulative AI hours for implementation, tests, and fixes with developer review.

## Outcome and challenge coverage

C4 Counseling requires one note entry, a funder-specific field preview, counselor review before export, and records of reads and sends. Demonstrate one synthetic week of five sessions. This module does not establish legal compliance or permission to process real health information.

## Scope and boundaries

- D1: Use only clearly labeled synthetic notes and clients. Never import actual counseling notes.
- D2: Keep notes in a restricted store separate from general CRM search, room messages, and public AI tools.
- D3: Map one funder's explicitly allowed fields. Export only after the counselor approves the exact payload.
- D4: Use a local mock funder sink. Live funder portals, clinical recommendations, billing, and production deployment are excluded.

Private hosting or tenant isolation alone does not prove that a system is approved for health data. Real use requires an independently reviewed deployment, data processing arrangements, access model, retention policy, and integration boundary.

## Records and invariants

All IDs are strings. Timestamps are UTC ISO 8601. Every record is organization-scoped. S11 provides role checks, but S6 additionally checks assignment to the case.

| Record | Minimum fields |
|---|---|
| Case | id, orgId, syntheticClientId, assignedCounselorIds, status |
| Session | id, caseId, occurredAt, funderId, eligible |
| NoteVersion | id, sessionId, revision, structuredFields, restrictedNarrative, contentHash, authorId |
| FunderSchema | id, version, allowedFieldNames, requiredFields, validationRules |
| ExportPreview | id, noteVersionId, schemaVersion, payload, payloadHash, missingFields |
| ExportApproval | id, previewId, payloadHash, counselorId, approvedAt |
| ExportReceipt | id, previewId, destinationId, payloadHash, status, sentAt |
| AccessEvent | id, orgId, actorId, action, resourceId, outcome, occurredAt |

- I1: No unrestricted room, search index, model trace, notification, or error log receives note content.
- I2: An export allowlist is enforced server-side. Unknown fields are rejected, not silently forwarded.
- I3: Editing a note or funder schema invalidates its preview approval.
- I4: Every successful read and denied attempt produces an audit event. Logs record identifiers and actions, not note bodies.
- I5: An agent cannot approve exports. Unassigned staff cannot read a note, even within the same organization.
- I6: Export retries use an idempotency key and receipt reconciliation. An uncertain send cannot trigger a blind duplicate.

## Proposed API contract

Read [the architecture contract](../architecture.md). All mutations require an `Idempotency-Key`. Organization IDs in routes require server-side membership checks.

These routes are proposals, not existing services. Namespace: `/api/v1/orgs/:orgId/cases`.

| Method and path | Behavior |
|---|---|
| POST / | Create a synthetic case and counselor assignments |
| POST /:id/sessions | Create a session and its synthetic structured note |
| GET /notes/:id | Return an authorized note and append an access event |
| POST /notes/:id/previews | Build an allowlisted funder payload |
| POST /previews/:id/approve | Assigned counselor approves the exact payload hash |
| POST /previews/:id/export | Send approved preview to the configured local mock destination |
| GET /:id/audit | Authorized reviewer reads access and export events |

Return 201 for creation, 200 for reads, 403 for an unassigned same-organization actor, 404 for inaccessible cross-organization resources, 409 for stale approval, and 422 for missing funder fields or ineligible sessions. The organization comes from authenticated membership, never a trusted body field.

## Dependencies and responsibilities

- S11 supplies authentication, restricted roles, protected storage, and encryption configuration.
- S9 supplies only the mock export adapter and delivery receipts for this demo.
- S10 consumes content-free audit events. S4 supplies counselor review tasks without note excerpts.
- S1 supplies a minimal synthetic client reference. Do not place clinical narrative in CRM.
- S5 supplies blank funder templates only. Its general knowledge index must not ingest notes.

The agent can propose field mappings from synthetic structured data. The counselor checks each preview. Deterministic code selects permitted fields and sends the approved payload. Human approval cannot expand the funder's allowlist.

## API-first acceptance tests

Seed `case-demo`, assigned counselor token, another counselor token, `note-demo`, and funder schema `funder-demo-v1`. Synthetic note fields: session date, service code `FAMILY`, minutes 50, and narrative `Synthetic private detail excluded from funder export`. Allowed export fields are session date, service code, and minutes.

```bash
API=http://127.0.0.1:3000/api/v1/orgs/tidepath-demo
curl --fail-with-body "$API/cases/notes/note-demo" \
  -H "Authorization: Bearer $COUNSELOR_TOKEN"
curl --fail-with-body -X POST "$API/cases/notes/note-demo/previews" \
  -H "Authorization: Bearer $COUNSELOR_TOKEN" -H 'Content-Type: application/json' -H 'Idempotency-Key: s06-demo-1' \
  -d '{"funderSchemaId":"funder-demo-v1"}'
curl -sS -o /tmp/s06-forbidden.json -w '%{http_code}\n' \
  "$API/cases/notes/note-demo" -H "Authorization: Bearer $UNASSIGNED_TOKEN"
curl -sS -o /tmp/s06-unapproved.json -w '%{http_code}\n' -X POST \
  "$API/cases/previews/preview-demo/export" -H "Authorization: Bearer $COUNSELOR_TOKEN" \
  -H 'Idempotency-Key: clinical-demo-export-1'
curl --fail-with-body "$API/cases/case-demo/audit" -H "Authorization: Bearer $AUDITOR_TOKEN"
```

- T1: Preview contains exactly the three allowed fields. The synthetic private narrative is absent from payload, traces, and mock sink.
- T2: Unassigned read returns 403 and records a denied event. Cross-organization access returns 404.
- T3: Export before approval returns 409 and sends nothing. Approve the returned hash, then export to the local sink.
- T4: Repeat the approved export with the same idempotency key. Verify one sink receipt and one logical export.
- T5: Change the note after approval. Reject the previous preview export with 409.
- T6: Missing minutes or an ineligible session returns 422. A model failure never fills missing data with invented values.

## UI acceptance tests

- U1: Enter five synthetic session notes once. Generate each funder preview without retyping.
- U2: Show internal note and exact outgoing fields separately. Show the destination and require counselor confirmation.
- U3: Confirm that a normal program staff account cannot open notes from a URL, search, or a room link.
- U4: Read the audit view and match note reads and exports to actors and timestamps.
- U5: Simulate export timeout. Show pending reconciliation, preserve the preview, and prevent duplicate sends.

## Decisions before implementation

Q1: Which funder fields are required? Default: the three synthetic fields above. Obtain a real schema before any real integration.

Q2: Which model can process notes? Default: no external note processing. Use deterministic mapping of synthetic structured fields.

Q3: Who may audit case access? Default: a separate audit role with event metadata access and no automatic note access.

## Completion evidence

Save passing API checks, mock sink payloads, denied-access results, and the five-session UI walk. Verify that the private synthetic marker is absent from every general log and export. Label the result a synthetic clinical workflow demo, not a production clinical system.
