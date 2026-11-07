# S7. Grant and budget management

Status: proposed handoff, not implemented or verified. Complexity: High. Estimate: 20–40 cumulative AI hours for implementation, tests, and fixes with developer review. Scope: synthetic demo.

## Outcome and challenge coverage

C6 Grants needs a complete application drafted from approved facts, answers within word limits, source references, flagged missing information, and spending reports by each funder's categories and dates. QuickBooks remains the accounting source. A person submits applications.

## Scope and boundaries

- D1: Complete one synthetic grant application and one fiscal year's category accounting.
- D2: Import a synthetic QuickBooks-style CSV through S9. Preserve external transaction IDs and provenance.
- D3: Draft with S5 approved facts. Keep staff review before any export.
- D4: Exclude grant discovery, live bank access, automated applications, payments, and automatic accounting changes.

BeWize may supply agents and review rooms. Verify its actual integration contract. Its language model must not calculate authoritative financial totals.

## Records and invariants

Use string IDs, UTC timestamps, and authenticated organization scope. Store money as integer minor units and currency. Fiscal dates use the organization's timezone and half-open intervals `[start, end)`.

| Record | Minimum fields |
|---|---|
| Grant | id, orgId, funderName, currency, fiscalStart, fiscalEnd, spendBy, status |
| BudgetCategory | id, grantId, name, allocatedMinor, restrictionText |
| AccountingTransaction | id, orgId, externalId, sourceBatchId, postedAt, amountMinor, currency, revision |
| Allocation | id, transactionId, categoryId, amountMinor, approvedBy, revision |
| Question | id, grantId, text, wordLimit, required |
| Answer | id, questionId, documentVersionId, wordCount, missingFields, approvalId |
| FiscalReport | id, grantId, interval, sourceRevisions, categoryTotals, createdAt |

- I1: Reimporting an external transaction does not count it twice. Changed source rows enter review rather than overwrite history silently.
- I2: Allocations cannot exceed the transaction's allocatable amount. Reject currency mismatches and unknown categories.
- I3: Deterministic arithmetic computes category balances. An overspend is visible, never hidden by negative-value clamping.
- I4: Reports use the funder's dates, independently of the nonprofit's fiscal year. Exclude transactions at the interval end.
- I5: Missing approved facts block answer completion. Generated answers include evidence and deterministic word counts.
- I6: Approved answers bind to immutable S5 versions. Editing a fact, question, or answer requires review again.

## Proposed API contract

Read [the architecture contract](../architecture.md). These endpoints are proposals, not implemented services. Namespace: `/api/v1/orgs/:orgId/grants`.

| Method and path | Behavior |
|---|---|
| POST / | Create a grant, fiscal dates, budget categories, and questions |
| POST /:id/allocations | Allocate imported accounting transactions with a revision check |
| GET /:id/balances | Return category budget, spent, remaining, spend-by date, and warnings |
| POST /:id/application-drafts | Ask S5 to draft each question using selected approved fact IDs |
| GET /:id/application | Return questions, answers, citations, missing fields, and approval states |
| GET /:id/reports?start=...&end=... | Produce a reconciled report for an explicit fiscal interval |
| POST /:id/application-exports | Export approved answers for manual submission |

Use 422 for invalid dates, missing application facts, over-allocation, or currency mismatch. Use shared 401/403/404/409 semantics. All mutations require idempotency keys. Exports never submit to a funder's website.

## Dependencies and responsibilities

- S5 owns facts, generated text, source citations, and document versions.
- S9 owns accounting import batches, column mappings, and source receipts.
- S4 owns review tasks and due-date reminders. S10 owns derived presentation of reports.
- S11 owns organization roles, idempotency, audit events, and durable jobs.

The agent drafts answers and suggests transaction categories. The bookkeeper approves allocations. The director approves application text. Deterministic services validate word limits, compute totals, and enforce approval.

## API-first acceptance tests

Seed `grant-demo` with USD category `supplies-demo`, budget 100000 minor units, fiscal interval `2026-07-01T04:00:00Z` to `2027-07-01T04:00:00Z`, and a required 50-word question. Seed imported transactions: 20000 inside the interval, 30000 just before the start, and 40000 exactly at the end. Approve only the inside allocation. Seed one approved fact stating 120 synthetic families served.

```bash
API=http://127.0.0.1:3000/api/v1/orgs/tidepath-demo
curl --fail-with-body -X POST "$API/grants/grant-demo/allocations" \
  -H "Authorization: Bearer $BOOKKEEPER_TOKEN" -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: grant-allocation-demo-1' \
  -d '{"transactionId":"transaction-inside","categoryId":"supplies-demo","amountMinor":20000,"currency":"USD","expectedRevision":1}'
curl --fail-with-body "$API/grants/grant-demo/balances" -H "Authorization: Bearer $BOOKKEEPER_TOKEN"
curl --fail-with-body -X POST "$API/grants/grant-demo/application-drafts" \
  -H "Authorization: Bearer $DIRECTOR_TOKEN" -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: grant-application-demo-1' -d '{"approvedFactIds":["fact-approved"]}'
curl --fail-with-body "$API/grants/grant-demo/reports?start=2026-07-01T04:00:00Z&end=2027-07-01T04:00:00Z" \
  -H "Authorization: Bearer $BOOKKEEPER_TOKEN"
```

- T1: Balances show spent 20000 and remaining 80000. Repeat the allocation request with the same key and verify unchanged totals.
- T2: The fiscal report excludes the pre-start and exact-end transactions. Its total matches the accounting reconciliation.
- T3: Draft uses 120, includes its source, and stays within 50 words. Missing required facts remain flagged and block export with 422.
- T4: Allocate more than the transaction amount or a different currency. Return 422 and preserve balances.
- T5: Reuse an idempotency key with different input or approve a stale revision. Return 409.
- T6: A volunteer cannot approve allocations. Cross-organization reads return 404. An agent cannot approve or submit an application.

## UI acceptance tests

- U1: Import the fixture CSV, review suggested categories, approve an allocation, and inspect the updated balance.
- U2: Change the displayed fiscal year and confirm category totals follow funder dates rather than calendar years.
- U3: Open an application answer, inspect each citation, and see the word count and missing fields.
- U4: Revise an approved answer and confirm export requires new review.
- U5: Show an overspending warning and spend-by date. Confirm that totals remain visible during an AI service failure.

## Decisions before implementation

Q1: What accounting export format is required? Default: a documented synthetic CSV with external ID, posting date, amount, and currency.

Q2: How does the organization allocate shared costs and refunds? Default: manual reviewed allocation, signed accounting amounts, and no currency conversion.

Q3: Which word-count rule do funders use? Default: whitespace token count for the demo, displayed explicitly. Add provider-specific rules only after confirmation.

## Completion evidence

Retain the fixture CSV, exact expected totals, passing boundary tests, complete sourced application, and UI results. A local CSV import does not prove a live QuickBooks integration. Do not claim that AI validates funder eligibility or legal spending compliance.
