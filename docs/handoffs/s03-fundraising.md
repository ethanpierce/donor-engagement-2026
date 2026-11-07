# S3 — Fundraising management

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

C2 requires complete donor giving history, staff-approved deduplication, weekly late-gift detection, personal suggested notes, and failed monthly gifts noticed within days. C1 and C3–C8 are not directly implemented here. S7 remains the grant-accounting owner.

## Scope and non-goals

Import gifts from synthetic donation-page, ticket, auction, and check exports. Link donors through S1. Track recurring commitments and late gifts. Draft outreach with staff approval. Exclude payment collection, card storage, refunds, automatic solicitation, and replacement accounting software.

## Minimal records and invariants

| Record | Required fields and rules |
|---|---|
| Gift | `id`, S1 donor ID, source transaction ID, source system, received date, integer minor-unit amount, currency, status, provenance |
| Recurring commitment | donor ID, cadence, expected amount, next expected date, grace days, source, active status |
| Payment event | source event ID, commitment ID, success/failure status, observed timestamp |
| Late-gift signal | donor ID, expected date, last gift, usual timing/amount, evidence, rule version |
| Outreach draft | signal ID, S5 document revision or immutable text revision, source references, S4 approval/task ID |

The source-system plus transaction-ID pair is unique. Donor merges redirect references and never duplicate gifts. Keep separate currencies. Only received/settled gifts contribute to received totals. Failed attempts are not gifts. Corrections preserve the original and an audited adjustment. Deterministic services calculate totals and overdue intervals. Inferred annual giving patterns are suggestions, visibly separate from confirmed commitments.

## Dependencies and responsibilities

S1 owns donor identity and merge approval. S9 owns import receipts and delivery. S4 owns review and contact tasks. S5 may own note versions. S10 supplies reporting. S11 supplies permissions, job retries, audit, and idempotency.

Agents suggest donation patterns and personal drafts using approved donor context. Fundraising staff approve schedules, merges, and outgoing notes. Services ingest and calculate. Do not expose donor data to general volunteers or public rooms.

## Proposed API

| Method and route | Contract |
|---|---|
| `POST /fundraising/gifts` | Validate source identity, amount, currency, donor and status |
| `GET /fundraising/donors/:personId/history` | Return complete authorized history and per-currency totals |
| `POST /fundraising/commitments` | Create staff-confirmed expected giving schedule |
| `POST /fundraising/payment-events` | Ingest synthetic provider failure/success event |
| `POST /fundraising/signal-runs` | Calculate overdue and failed-gift signals at explicit clock |
| `POST /fundraising/signals/:id/outreach-drafts` | Create a source-linked draft without sending |
| `GET /fundraising/signals` | Return review queue with last gift, usual amount, timing, and freshness |

Return 422 for negative gift amounts, unsupported currency, invalid cadence, or missing source identity. Return 409 for conflicting versions of one source transaction. A payment failure cannot be inferred from absent donations alone. If provider failure data is missing, show “unknown,” not “failed.”

## Concrete API tests

S12 seeds S1 donor `donor-rosa`, authorized fundraising roles, and a controllable clock.

```bash
curl -fsS "$API_ROOT/fundraising/gifts" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H 'Idempotency-Key: gift-rosa-october' -d '{"donorId":"donor-rosa","sourceSystem":"synthetic-provider","sourceTransactionId":"gift-oct-1","receivedAt":"2026-10-01T16:00:00Z","amountMinor":5000,"currency":"USD","status":"settled"}' | jq -e '.amountMinor == 5000'
COMMITMENT=$(curl -fsS "$API_ROOT/fundraising/commitments" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H 'Idempotency-Key: commitment-rosa' -d '{"donorId":"donor-rosa","cadence":"monthly","amountMinor":5000,"currency":"USD","nextExpectedDate":"2026-11-01","graceDays":3}' | jq -er .id)
curl -fsS "$API_ROOT/fundraising/payment-events" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H 'Idempotency-Key: payment-rosa-failed' -d "$(jq -nc --arg c "$COMMITMENT" '{commitmentId:$c,sourceSystem:"synthetic-provider",sourceEventId:"fail-nov-1",status:"failed",observedAt:"2026-11-01T16:00:00Z"}')" | jq -e '.status == "failed"'
curl -fsS "$API_ROOT/fundraising/signal-runs" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H 'Idempotency-Key: fundraising-run-demo' -d '{"asOf":"2026-11-05T17:00:00Z"}' | jq -e '.lateGiftCount >= 1 and .failedPaymentCount >= 1'
curl -fsS "$API_ROOT/fundraising/donors/donor-rosa/history" -H "Authorization: Bearer $TOKEN" | jq -e '.totals.USD.receivedMinor == 5000'
```

Reimport the same source transaction under a different request key. Confirm one gift. In S1, merge a duplicate donor with a second gift and confirm both gifts remain. Ingest a later success event and confirm the failure signal resolves without erasing its history. Run daily and weekly schedules using a controlled clock. Detect a known failure within one day of its receipt, while displaying source freshness.

## UI verification

- U1. Import all four synthetic source types and inspect source-linked donor history.
- U2. Approve duplicate identities in S1. Confirm unchanged received totals and preserved gift details.
- U3. Open the weekly late-gift queue. Confirm last gift, usual amount, usual timing, and reason.
- U4. Generate a personal note. Review and edit it before simulated sending. Confirm no automatic send.
- U5. Inspect failed monthly gift and stale-source warnings. Confirm a volunteer cannot access the queue.

## Open decisions and demo defaults

| Code | Decision | Recommended demo default |
|---|---|---|
| Q1 | Grace period | Three days for confirmed monthly commitments, staff-configurable. |
| Q2 | Annual patterns | Staff-confirmed schedules before automatic overdue classification. |
| Q3 | Outreach channel | Local email sink with explicit simulated-delivery label. |

## Completion criteria

The synthetic donor list has approved canonical identities and complete history. Weekly late gifts have evidence and suggested notes. Known payment failures surface within the stated freshness target. All API, UI, and regression gates pass.

## Required regression gates

- T1. Repeat a mutation with the same idempotency key. Confirm one record and one audit entry.
- T2. Reuse that key with changed input. Confirm 409 and unchanged stored data.
- T3. Read or modify another organization's object. Confirm 404 without object details.
- T4. Call a protected route without a token. Confirm 401. Use a read-only token for writes and confirm 403.
- T5. Edit a reviewed revision. Confirm stale approvals cannot authorize the new revision.
- T6. Restart a worker during processing. Confirm retries preserve counts and do not duplicate notifications.

Run these gates plus each module's API and UI cases. Record the fixture version, tested commit, requests, responses, screenshots, and results in S12 evidence. Do not mark an unexecuted case passed.
