# S8. Animal and colony registry

Status: proposed handoff, not implemented or verified. Complexity: Medium. Estimate: 12–24 cumulative AI hours for implementation, tests, and fixes with developer review. Scope: synthetic C7 demo.

## Outcome and challenge coverage

C7 Cat rescue requires phone messages, photos, and locations to update the correct colony and cat. Staff see colony counts, TNR status, veterinary needs, and last feeding. Duplicate sightings count once. Urgent cases stand out the same day.

Mangrove Mews Cat Rescue is a separate fictional organization from Tidepath Family Alliance. Preserve that boundary in fixtures, authorization, and reports.

## Scope and boundaries

- D1: Process one synthetic batch containing messages, photos, shared locations, and feeder notes.
- D2: Store canonical cat records, colony membership, observations, feeding visits, and status history.
- D3: Require human approval before merging cats or marking a cat adopted or missing.
- D4: Exclude live WhatsApp scraping, veterinary diagnosis, real locations, public colony maps, and automatic identity merges.

BeWize may supply room collaboration and agent execution. Verify the interfaces first. A photo match is a suggestion, not proof of animal identity.

## Records and invariants

All IDs are strings and timestamps UTC ISO 8601. Operational dates display in America/New_York. Every record belongs to `mangrove-demo`, enforced through authenticated membership.

| Record | Minimum fields |
|---|---|
| Colony | id, orgId, label, restrictedLocation, activeFeederIds, status |
| Cat | id, orgId, colonyId, name, markings, photoIds, tnrStatus, presenceStatus, canonicalId |
| Observation | id, colonyId, catId, sourceItemId, observedAt, symptoms, urgency, attachmentIds |
| FeedingVisit | id, colonyId, feederId, occurredAt, sourceItemId |
| MatchProposal | id, catIds, evidenceRefs, confidence, revision, decision |
| StatusProposal | id, catId, requestedStatus, evidenceRefs, revision, decision |
| AnimalHistory | id, catId, action, actorId, sourceRefs, occurredAt |

- I1: A source item contributes once. Replaying an intake batch cannot duplicate cats, visits, or alerts.
- I2: Matching can use appearance, location, and history. Uncertain identity requires review instead of a silent merge.
- I3: Merging preserves source records, photos, observations, and audit history. Census counts canonical cats only.
- I4: Adoption, missing status, and merges require a rescue staff approval bound to a revision.
- I5: Locations and feeder contacts are restricted to rescue members. Sponsor reports expose aggregates only.
- I6: Urgency rules flag reported injury, pregnancy, kittens, and lost feeder coverage. They do not make medical diagnoses.

## Proposed API contract

Read [the architecture contract](../architecture.md). Routes below are proposals, not existing services. Namespace: `/api/v1/orgs/:orgId/animals`.

| Method and path | Behavior |
|---|---|
| POST /colonies | Create a colony with a synthetic restricted location |
| POST /intake-batches/:id/process | Convert reviewed S9 observations into records and review proposals |
| GET /colonies/:id | Return authorized colony state and latest feeding |
| GET /colonies/:id/census | Return canonical counts, TNR counts, and reported urgent needs |
| POST /match-proposals/:id/approve | Staff approve an exact merge proposal revision |
| POST /cats/:id/status-proposals | Propose adoption or missing status |
| POST /status-proposals/:id/approve | Staff approve the exact status proposal revision |
| GET /cats/:id/history | Return photos, sightings, approved changes, and source links |

All mutations require idempotency keys. Return 422 for invalid location data or inconsistent status, 409 for stale proposals, and shared 401/403/404 responses for authorization failures. Never trust organization IDs without membership checks.

## Dependencies and responsibilities

- S9 owns synthetic message/photo/location ingestion and source-item deduplication.
- S1 owns authorized feeder person references. S8 owns cats and colonies, not a second person database.
- S4 owns urgent tasks and approval routing. S10 owns aggregate sponsor report views.
- S11 owns access control, protected attachments, durable processing, and idempotency.

Agents extract observations, propose cat matches, and suggest urgency. Rescue staff resolve uncertain identity and protected status changes. Deterministic services maintain census totals and enforce approvals.

## API-first acceptance tests

Seed `colony-demo` and two proposed cat records for the same synthetic calico. Provide two generated images, fictional coordinates, two independent sightings, a pregnant-cat observation, and a feeding visit. Set the test clock to `2026-11-07T18:00:00Z`. Seed S9 batch `cat-batch-demo` and merge proposal `match-demo`.

```bash
API=http://127.0.0.1:3000/api/v1/orgs/mangrove-demo
curl --fail-with-body -X POST "$API/animals/intake-batches/cat-batch-demo/process" \
  -H "Authorization: Bearer $RESCUE_STAFF_TOKEN" -H 'Idempotency-Key: cat-batch-process-1'
curl --fail-with-body "$API/animals/colonies/colony-demo/census" \
  -H "Authorization: Bearer $RESCUE_STAFF_TOKEN"
curl --fail-with-body -X POST "$API/animals/match-proposals/match-demo/approve" \
  -H "Authorization: Bearer $RESCUE_STAFF_TOKEN" -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: cat-merge-demo-1' -d '{"expectedRevision":1,"decision":"approve"}'
curl --fail-with-body "$API/animals/colonies/colony-demo/census" \
  -H "Authorization: Bearer $RESCUE_STAFF_TOKEN"
curl -sS -o /tmp/s08-cross-org.json -w '%{http_code}\n' \
  "$API/animals/colonies/colony-demo" -H "Authorization: Bearer $TIDEPATH_TOKEN"
```

- T1: Before approval, show two unresolved cat records with a duplicate warning. After approval, show one canonical cat and two retained sightings.
- T2: Retry intake and merge requests with the same keys. Counts, sightings, feeding visits, and logical alerts remain unchanged.
- T3: The pregnancy observation creates a same-day urgent task. Confirm source, recipient, and visible local delivery receipt through S4/S9.
- T4: An agent or feeder cannot approve merges or protected status changes. Stale revision returns 409.
- T5: Tidepath token returns 404. Public and sponsor responses omit coordinates and feeder contacts.
- T6: An invalid photo or ambiguous location remains in review. Processing other valid batch entries continues without dropping evidence.

## UI acceptance tests

- U1: Submit a short synthetic message, photo, and location using a phone-width form without installing an app.
- U2: Review the extracted colony and cat suggestion without retyping source data. Correct a wrong match before commit.
- U3: Compare duplicate photos, approve a merge, and verify preserved history with one census entry.
- U4: Inspect current cat count, TNR counts, veterinary flags, and last feeder and time on the colony view.
- U5: Open urgent pregnancy, injury, kittens, and lost-feeder cases from the dashboard. Confirm each reaches the assigned reviewer.
- U6: Switch to a sponsor or other-organization account and confirm locations and feeder contacts are inaccessible.

## Decisions before implementation

Q1: Which location precision is needed? Default: fictional coordinates visible only to rescue members. No public map.

Q2: Who can approve identity and status changes? Default: rescue staff only, excluding agents and feeder-only accounts.

Q3: How long without feeding triggers an alert? Default: a configurable 24-hour synthetic-demo threshold, confirmed by rescue staff before live use.

## Completion evidence

Retain the synthetic batch, approved merge history, census before and after replay, urgent task receipts, permission checks, and phone UI walk. A local notification receipt proves routing logic only. No real cat locations or feeder contact data may enter the demo.
