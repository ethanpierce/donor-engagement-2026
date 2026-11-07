# S11. Shared data and access foundation

Status: proposed handoff, not implemented or tested. Complexity: High. Estimate: 20–40 cumulative AI hours for demo implementation, tests, and fixes.

## Outcome and scope

Every module uses one organization and authorization model, stable records, durable jobs, protected files, and reviewable changes. Follow [the shared architecture](../architecture.md). BeWize identity, room membership, and runtime services are reuse candidates. Verify each service contract before using it.

| Code | Challenge acceptance supported |
|---|---|
| C1 | Family records stay private and imported records count once. |
| C2 | Donor changes require approval and retain gift history. |
| C3 | A person can take control of a workflow and approve an exact slide version. |
| C4 | Only permitted clinicians see notes. Every note access and funder export is recorded. |
| C5 | Volunteer intake cannot expose children's details. Urgent routing survives retries. |
| C6 | Staff approve sourced drafts. Budget calculations preserve authoritative accounting data. |
| C7 | Tidepath cannot see Mangrove data. Only rescue members see locations and feeder contacts. |
| C8 | The same controls apply after the open-track problem is selected. |

Scope: organization membership, role and record permissions, agent service identities, protected storage, idempotency, transactional outbox, durable jobs, audit infrastructure, and a tested synthetic backup/restore path.

Non-goals: selecting a new application framework, building a general IAM product, production health-data authorization, compliance certification, public sharing of restricted data, or automatic production deployment.

## Proposed records and invariants

| Record | Minimum fields |
|---|---|
| Organization | id, name, timeZone, status |
| Membership | id, orgId, principalId, roles, status, revision |
| Principal | id, type human/agent, identityProviderRef, status |
| PermissionGrant | id, orgId, principalId, action, resourceScope, expiresAt |
| IdempotencyRecord | orgId, principalId, route, key, requestHash, responseRef, state |
| Approval | id, orgId, resourceType, resourceId, revisionHash, approverId, decision, decidedAt |
| Job | id, orgId, kind, inputRef, state, attempts, nextAttemptAt, lastErrorCode |
| OutboxEvent | id, orgId, aggregateId, type, payloadRef, occurredAt, deliveryState |
| StoredObject | id, orgId, sensitivity, contentHash, mediaType, sizeBytes, storageRef |
| AuditEvent | id, orgId, actorId, action, objectType, objectId, occurredAt, requestId, metadata |

- I1. Authenticate every private request. Authorize against current membership and resource ownership on the server.
- I2. IDs are strings and timestamps use UTC ISO 8601. Organization IDs in paths are not authorization evidence.
- I3. Deny by default. Restrict agents to explicit capabilities. Agent access never exceeds its delegated user and service grant.
- I4. General organization administration does not imply counseling-note access. S6 uses a separate restricted storage and processing boundary.
- I5. Bind approvals to immutable revision hashes. A changed payload requires new approval. Agents cannot approve their own sensitive proposals.
- I6. Commit business changes and outbox events atomically. Persist retries and expose terminal failure or unknown external outcome.
- I7. Scope idempotency to organization, principal, and route. Same key/body returns the same result. Changed body returns 409.
- I8. Record sensitive reads, writes, approvals, permission changes, exports, and denied access. Never store secrets or raw notes in ordinary logs.
- I9. Signed object access is short-lived and permission-checked. A copied file URL cannot bypass organization or sensitivity rules.
- I10. Backups preserve organization boundaries and protected data. Demonstrate restore using synthetic fixtures before claiming recovery works.

## Demo permission defaults

| Role | Allowed scope | Explicit limits |
|---|---|---|
| Organization admin | Membership and configuration | No default counseling-note access |
| Program manager | Participant programs and outcome reports | No donor finances or clinical notes without separate grant |
| Fundraising coordinator | Donors, gifts, outreach drafts | No clinical notes or rescue locations |
| Workshop coordinator | Requests, schedules, slide approval workflow | No clinical records |
| Counselor | Assigned synthetic cases and export preview | No unassigned cases |
| Clinical reviewer | Explicit S6 review and access audit | No unrelated organization's data |
| Bookkeeper | Grants, accounting imports, balances | No counseling-note body |
| Volunteer | Own intake receipts and allowed tasks | No roster-wide child or donor details |
| Rescue coordinator | Mangrove cats, colonies, feeders | No Tidepath family records |
| Agent service | Explicit module actions | No role escalation or sensitive self-approval |

Staff can hold multiple roles. Review resource-level assignment separately from module-level permissions. These defaults are a proposal, not an existing BeWize guarantee.

## Proposed API contract

Prefix: `/api/v1/orgs/:orgId/foundation`. Authentication token issuance belongs to the chosen identity service, not an invented password endpoint.

| Method and route | Behavior |
|---|---|
| GET /session | Return principal, organization membership, and effective capability summaries. |
| GET /memberships | Return permitted membership summaries. |
| PATCH /memberships/:id | Change roles using expected revision and audit the change. |
| POST /objects | Create a staged, sensitivity-labelled upload with scoped upload instructions. |
| GET /objects/:id/content | Authorize and stream content or issue short-lived access. |
| GET /jobs/:id | Return state and safe error information. |
| GET /audit-events | Return permission-filtered cursor-paginated events. |

All proposed business mutations require `Idempotency-Key`. Return 401 without authentication, 403 for known forbidden actions, 404 for inaccessible cross-organization objects, 409 for revision conflicts, and 422 for invalid input. S4 owns approval workflow APIs. S11 validates approval identity, revision binding, and audit persistence.

## Responsibilities and dependencies

D1. Build this foundation before domain writes. S1–S10 consume it rather than duplicating permission and job infrastructure.

D2. S4 owns approval state transitions and human takeover. S6 defines clinical assignments and export field limits. S10 presents audit views.

D3. Agents may propose grants and role changes in text. Authorized humans decide them. Deterministic code enforces access and persists changes.

D4. S12 owns synthetic tokens and two-organization fixture setup. Keep local fixture creation unavailable in deployed environments.

## API-first tests

Prepare local synthetic identities with tokens for admin, volunteer, assigned counselor, agent service, and another organization. Never commit real tokens. The fixture defines `tidepath-demo`, `mangrove-demo`, and volunteer membership `member-demo-volunteer` at revision 1.

```bash
API=http://localhost:3000/api/v1
curl --fail-with-body -sS "$API/orgs/tidepath-demo/foundation/session" -H "Authorization: Bearer $ADMIN_TOKEN"
curl -sS -o /tmp/s11-anonymous.json -w '%{http_code}\n' "$API/orgs/tidepath-demo/foundation/session"
curl -sS -o /tmp/s11-cross-org.json -w '%{http_code}\n' "$API/orgs/tidepath-demo/foundation/session" -H "Authorization: Bearer $OTHER_ORG_TOKEN"
curl --fail-with-body -sS -X PATCH "$API/orgs/tidepath-demo/foundation/memberships/member-demo-volunteer" \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: s11-role-change-01' \
  --data '{"expectedRevision":1,"roles":["volunteer"],"status":"active"}'
```

T1. Expect 200, 401, 404, and an audited successful update. Repeat the update with the same key. Assert the same response and one mutation event.

T2. Change the body while keeping the key. Expect 409. Repeat with a stale revision and a new key. Expect 409.

```bash
curl -sS -o /tmp/s11-escalation.json -w '%{http_code}\n' -X PATCH \
  "$API/orgs/tidepath-demo/foundation/memberships/member-demo-volunteer" \
  -H "Authorization: Bearer $VOLUNTEER_TOKEN" -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: s11-escalation-01' \
  --data '{"expectedRevision":2,"roles":["organization_admin"]}'
curl --fail-with-body -sS "$API/orgs/tidepath-demo/foundation/audit-events?objectId=member-demo-volunteer" -H "Authorization: Bearer $ADMIN_TOKEN"
```

T3. Expect 403 and an audit denial. Test the same escalation with an agent token. Expect 403.

T4. Create a synthetic protected upload. Copy its URL into another organization's session. Expect denial. Verify expiration and revocation behavior.

T5. Kill the worker between commit and dispatch. Restart locally. Assert one completed business action, one outbox event, and no duplicate delivery.

T6. Back up both demo organizations. Restore into a new local database. Compare record counts, source hashes, permissions, and audit references. A failed restore blocks completion.

## UI tests and completion

- U1. Sign in as each demo role. Verify navigation and server responses match permissions.
- U2. Revoke a role while its browser session remains open. Its next protected action must fail.
- U3. Open a copied protected file or record link as another organization. Verify no private metadata appears.
- U4. Open a clinical note as an admin without clinical access. Verify denial and a restricted audit event.
- U5. Edit an approved proposal. Verify its approval becomes invalid and execution is blocked.
- U6. Simulate a failed job. Show status, safe error, and allowed retry without displaying secrets.

Q1. Choose identity mapping and implementation stack before coding. Do not infer BeWize organization membership from room names.

Q2. Agree retention, encryption key ownership, recovery targets, audit access, and operating costs before live use. Demo defaults do not establish production policy.

Done means T1–T6 and U1–U6 pass with recorded evidence. Permission checks must cover APIs, file access, search, exports, agent calls, and background jobs.
