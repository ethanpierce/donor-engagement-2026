# S9. Integration and intake

Status: proposed handoff, not implemented or tested. Complexity: High. Estimate: 24–48 cumulative AI hours for demo implementation, tests, and fixes.

## Outcome and scope

Import synthetic files and phone-friendly submissions once. Preserve provenance and route validated records to the owning system. Reuse BeWize execution and workspace features only after verifying their contracts. Do not treat a room message as an authoritative business record.

| Code | Challenge acceptance supported |
|---|---|
| C1 | Sign-up and attendance CSVs populate one participant history without repeated entry. |
| C2 | Donation spreadsheets preserve gifts and support staff-approved duplicate resolution. |
| C3 | One synthetic incoming request reaches the workshop workflow. Calendar confirmation has an adapter receipt. |
| C4 | Synthetic approved fields reach a funder sandbox sink. Raw notes never enter this general intake pipeline. |
| C5 | A phone submission containing text and a photo becomes one visit candidate and urgent need. |
| C6 | QuickBooks-shaped CSVs preserve transaction IDs, categories, and funder dates. |
| C7 | A synthetic export containing messages, photos, and locations reaches the cat registry. |
| C8 | Reuse supported adapters only after choosing a specific open-track problem. |

Demo defaults: CSV upload, responsive web form, synthetic WhatsApp Export chat archive, and local delivery/calendar sinks. Label simulated channels visibly. A real phone, email, calendar, or accounting integration is not complete until tested with that provider.

Non-goals: live WhatsApp scraping, browser session collection, real payment processing, automatic grant submission, production clinical connectors, or promising all channels from a single mocked adapter.

## Proposed records and invariants

| Record | Minimum fields |
|---|---|
| IntakeBatch | id, orgId, channel, sourceId, contentHash, status, createdAt, actorId |
| SourceItem | id, batchId, externalId, occurredAt, rawObjectRef, attachmentRefs, sensitivity |
| MappingVersion | id, orgId, destinationType, fieldMap, schemaVersion, approvedBy |
| ImportRow | id, batchId, sourceItemId, normalizedPayload, validationErrors, destinationId |
| DeliveryAttempt | id, orgId, actionId, channel, recipientRef, status, providerReceipt, attemptedAt |

- I1. IDs are strings. Stored timestamps are UTC. Organization scope comes from authenticated membership, not a submitted orgId alone.
- I2. Deduplicate transport delivery by `(orgId, channel, externalId)` and file content hash. Different visits need domain-level matching in S2 or S8.
- I3. Preview mapping and invalid rows before commit. Commit accepted rows transactionally, with a durable outbox for downstream work.
- I4. Preserve original source references. Restrict raw uploads separately from normalized business records.
- I5. Quarantine unsafe files. Enforce size/type limits. Parse CSV as data and neutralize formula injection on export.
- I6. Uncertain extraction creates a review item. It never silently invents hours, money, identity, or consent.
- I7. Retry a delivery with the same action ID. A timeout means unknown delivery until reconciled, not permission to send twice.
- I8. Public forms use scoped, expiring intake capabilities, rate limits, and restricted upload access. They cannot read internal records.

## Proposed API contract

These endpoints do not exist yet. Prefix: `/api/v1/orgs/:orgId/intake`.

| Method and route | Behavior |
|---|---|
| POST /batches | Create a staged JSON or multipart upload. Return 201 with batch ID. |
| GET /batches/:id/preview | Return mapped rows, row errors, and likely duplicates. |
| POST /batches/:id/commit | Commit validated rows once. Return 202 and job ID. |
| GET /batches/:id | Return progress, counts, and source-linked errors. |
| POST /deliveries | Create an approved action in the local sink. Return 202. |
| GET /deliveries/:id | Distinguish queued, delivered, failed, and unknown. |

Use `Idempotency-Key` for mutations. Reject the same key with a different body using 409. Return 422 for invalid input, 403 for known forbidden actions, and 404 for inaccessible cross-organization objects.

## Ownership and dependencies

- D1. S11 provides authentication, object storage controls, idempotency, jobs, and outbox delivery.
- D2. S1–S3 and S6–S8 own domain validation and authoritative writes. Intake does not implement a second CRM or ledger.
- D3. S4 owns approvals and reminders. S5 owns document references. S10 consumes committed records and delivery receipts.
- D4. Agents extract and propose mappings. Staff approve ambiguous identities, destinations, and external messages. Deterministic code validates and commits records.

## API-first test recipe

Prepare local synthetic tokens and organization `tidepath-demo`. `$STAFF_TOKEN` has intake permission. `$OTHER_ORG_TOKEN` belongs to `mangrove-demo`. These are shell placeholders, never repository secrets.

```bash
API=http://localhost:3000/api/v1
cat > /tmp/s09-batch.json <<'JSON'
{"channel":"web_form","sourceId":"synthetic-week-01","items":[{"externalId":"visit-01","occurredAt":"2026-11-02T15:00:00Z","text":"Demo volunteer spent 60 minutes with demo family. Needs diapers today.","synthetic":true}]}
JSON
curl --fail-with-body -sS "$API/orgs/tidepath-demo/intake/batches" \
  -H "Authorization: Bearer $STAFF_TOKEN" -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: s09-batch-01' --data-binary @/tmp/s09-batch.json
```

Save the returned ID as `BATCH_ID`.

```bash
curl --fail-with-body -sS "$API/orgs/tidepath-demo/intake/batches/$BATCH_ID/preview" -H "Authorization: Bearer $STAFF_TOKEN"
curl --fail-with-body -sS -X POST "$API/orgs/tidepath-demo/intake/batches/$BATCH_ID/commit" \
  -H "Authorization: Bearer $STAFF_TOKEN" -H 'Idempotency-Key: s09-commit-01'
curl --fail-with-body -sS "$API/orgs/tidepath-demo/intake/batches/$BATCH_ID" -H "Authorization: Bearer $STAFF_TOKEN"
curl -sS -o /tmp/s09-denied.json -w '%{http_code}\n' "$API/orgs/tidepath-demo/intake/batches/$BATCH_ID" -H "Authorization: Bearer $OTHER_ORG_TOKEN"
```

T1. Expect 201, a preview with 60 proposed minutes and an urgent-need candidate, then 202 and a completed batch. Expect 404 for cross-organization access.

T2. Repeat create and commit with the same keys. Assert identical IDs and exactly one downstream visit. Change the body with the same key. Expect 409.

T3. Submit an invalid negative duration, malformed CSV, duplicate external ID, and oversized attachment. Assert row errors or upload rejection without partial duplicate writes.

T4. Disconnect the local delivery sink after acceptance. Assert retry/reconciliation preserves one action and exposes unknown delivery. Do not claim an urgent need reached staff until the sink records delivery.

## UI test cases

- U1. Submit the form on a phone-sized viewport without installing an app. Attach a synthetic photo and see a receipt.
- U2. Preview a CSV mapping, correct an invalid row, commit, and open its destination record through the source link.
- U3. Repeat an upload. Show an already-imported result rather than duplicate records.
- U4. Reject an uncertain person match. Confirm that no unrelated person's record changes.
- U5. Verify empty, loading, failed, retrying, and unknown-delivery states. Preserve entered text after a failure.
- U6. Attempt another organization's upload URL and source-object URL. Verify denial without filename or content leakage.

## Choices and completion

Q1. Choose real provider adapters and account ownership before external integration. Default to local sinks for the demo.

Q2. Choose retention and attachment limits before production. Demo default: synthetic-only files, 10 MB per file, manual cleanup after export.

Done means T1–T4 and U1–U6 pass, duplicate counts remain stable, every result has provenance, and simulated adapters are identified. Record commands, outputs, screenshots, delivery receipts, and costs. No real participant, donor, clinical, or rescue data enters the demo.
