# S1 — Nonprofit CRM

Status: implementation handoff, proposed design. Complexity: **Medium**. Estimate: **12–24 cumulative AI hours** for coding, tests, and fixes, with developer review. This estimate covers synthetic demo scope, not production readiness.

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

C1 requires one record per child, parent, mentor, and volunteer across spelling variants. C2 requires staff-approved donor merges without lost gifts. C3 uses school contacts. C5 identifies volunteers and families. C4 stores only an opaque person reference, never counseling content. C6 and C7 may reference organization contacts. C8 remains unscoped.

## Scope and non-goals

Implement person and organization records, roles, relationships, external identity references, duplicate proposals, and approved merges. A person can hold several roles. Reuse the same identity across modules.

Exclude donation accounting, attendance, clinical notes, animal identities, automated deletion, and a generic sales pipeline. Those belong to their owner modules.

## Minimal records and invariants

| Record | Required fields and rules |
|---|---|
| Person | `id`, `orgId`, `displayName`, aliases, roles, contact methods, `revision`, provenance |
| Organization contact | `id`, name, type, contact-person references |
| Relationship | parent/child or staff-approved relationship, person IDs, effective dates |
| External identity | source system plus source record ID, mapped person ID, import batch ID |
| Merge proposal | candidate IDs, evidence, uncertain fields, source revisions, status |
| Merge decision | approver, timestamp, reason, immutable proposal revision, canonical person ID |

Names are not unique identifiers. An email or phone can be shared by a family. Never merge on a name alone. Preserve original source records, aliases, gifts, and relationships. Merge in one transaction with an old-ID redirect. Check S2/S3 references after each merge. Do not silently overwrite conflicting contact details. Keep a staff-reviewed conflict list.

## Dependencies and responsibilities

S11 owns authentication, permissions, idempotency, and audit infrastructure. S9 supplies provenance and import identities. S4 holds revision-bound approval tasks. S2/S3 reference canonical people. S10 reports from canonical references without counting aliases twice.

Agents suggest matches and explain evidence. Authorized staff approve or reject each proposal. Only the deterministic merge service changes canonical links. Restrict donor information to fundraising staff and family details to assigned staff.

## Proposed API

| Method and route | Contract |
|---|---|
| `POST /crm/people` | Validate fields, create a person, return 201 with `id` and `revision` |
| `GET /crm/people/:id` | Return authorized fields and canonical ID if merged |
| `POST /crm/relationships` | Validate person references and relationship permissions |
| `POST /crm/merge-proposals` | Create evidence-backed proposal without changing either record |
| `POST /crm/merge-proposals/:id/decision` | Staff-only approve/reject against proposal revision |

Reject invalid person references with 422. Return 409 if source records changed after proposal generation. No direct delete API is in demo scope.

## Concrete API tests

```bash
P1=$(curl -fsS "$API_ROOT/crm/people" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H 'Idempotency-Key: crm-person-rosa-1' -d '{"displayName":"Rosa Delgado","roles":["donor"],"contactMethods":[{"type":"email","value":"rosa@example.test"}]}' | jq -er .id)
P2=$(curl -fsS "$API_ROOT/crm/people" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H 'Idempotency-Key: crm-person-rosa-2' -d '{"displayName":"Rosa M. Delgado","roles":["donor"],"contactMethods":[{"type":"email","value":"rosa@example.test"}]}' | jq -er .id)
PROPOSAL=$(curl -fsS "$API_ROOT/crm/merge-proposals" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H 'Idempotency-Key: crm-rosa-proposal' -d "$(jq -nc --arg a "$P1" --arg b "$P2" '{personIds:[$a,$b]}')")
PROPOSAL_ID=$(printf '%s' "$PROPOSAL" | jq -er .id)
REVISION=$(printf '%s' "$PROPOSAL" | jq -er .revision)
curl -fsS "$API_ROOT/crm/people/$P2" -H "Authorization: Bearer $TOKEN" | jq -e '.mergedInto == null'
curl -fsS "$API_ROOT/crm/merge-proposals/$PROPOSAL_ID/decision" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H 'Idempotency-Key: crm-rosa-approval' -d "$(jq -nc --argjson r "$REVISION" '{decision:"approve",revision:$r,reason:"Synthetic matching source identities reviewed"}')" | jq -e '.status == "approved"'
curl -fsS "$API_ROOT/crm/people/$P2" -H "Authorization: Bearer $TOKEN" | jq -e --arg id "$P1" '.canonicalPersonId == $id'
```

The proposal deterministically selects P1 as the oldest canonical record and displays that choice before approval. Add two gifts in S3 before approving. Confirm the donor history retains both gifts and the total is unchanged. Test two unrelated people sharing a name and a family sharing an email. Neither may merge automatically.

## UI verification

- U1. Import synthetic spelling variants. Open the duplicate queue and inspect source evidence side by side.
- U2. Reject a match. Confirm records remain separate and rejection history is visible.
- U3. Approve a match. Confirm one canonical donor and complete giving history.
- U4. Open a child's record. Confirm enrollment, attendance, and mentor links use S2 without duplicated person entry.
- U5. Sign in as a volunteer. Confirm unrelated family contacts and donor details are hidden.

## Open decisions and demo defaults

| Code | Decision | Recommended demo default |
|---|---|---|
| Q1 | Matching thresholds | Suggest matches using multiple evidence fields. Never auto-merge. |
| Q2 | Contact conflicts | Retain all values with provenance. Staff choose a preferred value. |
| Q3 | Merge rollback | Preserve immutable mapping history. Require reviewed repair rather than destructive undo. |

## Completion criteria

One synthetic quarter uses canonical identities across S2 and S3. Approved donor merges preserve every gift. Unauthorized users cannot access unrelated personal records. All API, UI, and regression gates pass.

## Required regression gates

- T1. Repeat a mutation with the same idempotency key. Confirm one record and one audit entry.
- T2. Reuse that key with changed input. Confirm 409 and unchanged stored data.
- T3. Read or modify another organization's object. Confirm 404 without object details.
- T4. Call a protected route without a token. Confirm 401. Use a read-only token for writes and confirm 403.
- T5. Edit a reviewed revision. Confirm stale approvals cannot authorize the new revision.
- T6. Restart a worker during processing. Confirm retries preserve counts and do not duplicate notifications.

Run these gates plus each module's API and UI cases. Record the fixture version, tested commit, requests, responses, screenshots, and results in S12 evidence. Do not mark an unexecuted case passed.
