# S5. Document and knowledge management

Status: proposed handoff, not implemented or verified. Complexity: Medium. Estimate: 12–24 cumulative AI hours for coding, tests, and fixes with developer review. Estimate covers a synthetic demo, not production readiness.

## Outcome and challenge coverage

| Challenge | Required evidence from this module |
|---|---|
| C3 Workshops | Slides fit the class's age, topic, language, and format. Staff approve before school review. School approval names one immutable version. |
| C4 Counseling | S6 owns restricted notes. S5 provides templates only and never indexes counseling content into general search. |
| C6 Grants | Drafts use approved facts with source references. Missing facts remain flagged. Staff approve the exact outgoing version. |

Read the original challenge document before implementation. BeWize rooms and agents can host collaboration. Their document storage, citations, and approval integration must be verified before reuse.

## Scope and boundaries

- D1: Store source documents, approved fact records, reusable templates, and immutable draft versions.
- D2: Generate one workshop deck and one grant answer from synthetic approved sources.
- D3: Support English, Spanish, and Haitian Creole workshop output. Keep the language explicit on every version.
- D4: Exclude general-purpose file editing, public sharing, and unattended external publication.

## Records and invariants

All IDs are strings. Timestamps are UTC ISO 8601. Each record has an organization ID, creator, and revision. The server derives organization access from authenticated membership.

| Record | Minimum fields |
|---|---|
| Source | id, orgId, title, classification, objectKey, checksum, createdAt |
| Fact | id, orgId, text, sourceId, sourceLocator, status, approvedBy, approvedAt |
| Template | id, orgId, kind, language, requiredFields, version |
| Document | id, orgId, kind, ownerId, workflowId |
| Version | id, documentId, revision, content, language, factIds, unresolvedFields, contentHash |
| Approval | id, versionId, contentHash, actorId, role, decision, createdAt |

- I1: New content creates a new version. Approval never transfers to edited content.
- I2: Unapproved or revoked facts cannot support a new draft. Existing drafts show stale-source warnings.
- I3: References resolve to immutable source versions and locators. AI text without evidence is marked unsupported.
- I4: School access is limited to one approved deck through an expiring scoped link. It cannot browse internal facts.
- I5: Embedded instructions in uploaded documents remain source data, never tool authorization.

## Proposed API contract

Read [the architecture contract](../architecture.md). All mutations require an `Idempotency-Key`. Organization IDs in routes require server-side membership checks.

These endpoints do not exist yet. Use `/api/v1/orgs/:orgId/documents` as the module namespace. Return 201 for creation, 200 for reads, 400 for invalid input, 403 for forbidden actions, and 409 for stale versions. Use 404 for inaccessible cross-organization records.

| Method and path | Behavior |
|---|---|
| POST /sources | Register a synthetic uploaded source and checksum |
| POST /facts | Create a fact linked to a source locator |
| POST /facts/:id/approve | Authorized staff approve a fact revision |
| POST /drafts | Generate a version from explicit approved fact IDs and template inputs |
| GET /versions/:id | Read content, citations, missing fields, and approval state |
| POST /versions/:id/approve | Approve the exact content hash for the given staff or school stage |
| POST /versions/:id/revise | Create a new version and invalidate downstream approval |

Draft generation returns structured `unresolvedFields`, not invented values. Word limits use a documented deterministic tokenizer shared with S7.

## Dependencies and ownership

- S4 owns workshop stages, reminders, and school-review routing.
- S7 owns grant questions, word limits, and application completeness.
- S9 owns uploads and delivery adapters. S11 owns organization roles and object storage permissions.
- S10 owns audit export. S6 owns all clinical-note content and restricted exports.

Agents propose drafts and translations. Staff check factual claims and slide suitability. Schools approve a specific deck version. The server enforces approvals and permissions.

## API-first acceptance tests

Run only against a local synthetic environment. Supply local role tokens through environment variables. Seed `source-demo`, an approved fact `fact-approved`, a draft fact `fact-unapproved`, template `grant-short`, and template `workshop-demo`. A draft source says Tidepath served 120 synthetic families. The unapproved source claims 999.

```bash
API=http://127.0.0.1:3000/api/v1/orgs/tidepath-demo
curl --fail-with-body -X POST "$API/documents/drafts" \
  -H "Authorization: Bearer $STAFF_TOKEN" -H 'Content-Type: application/json' -H 'Idempotency-Key: s05-demo-1' \
  -d '{"kind":"grant-answer","templateId":"grant-short","factIds":["fact-approved"],"wordLimit":50,"question":"How many families did you serve?"}'
curl -sS -o /tmp/s05-denied.json -w '%{http_code}\n' -X POST "$API/documents/drafts" \
  -H "Authorization: Bearer $STAFF_TOKEN" -H 'Content-Type: application/json' -H 'Idempotency-Key: s05-demo-2' \
  -d '{"kind":"grant-answer","templateId":"grant-short","factIds":["fact-unapproved"],"wordLimit":50,"question":"How many families did you serve?"}'
curl --fail-with-body "$API/documents/versions/version-demo" -H "Authorization: Bearer $STAFF_TOKEN"
curl -sS -o /tmp/s05-cross-org.json -w '%{http_code}\n' \
  "$API/documents/versions/version-demo" -H "Authorization: Bearer $OTHER_ORG_TOKEN"
```

- T1: First response cites `fact-approved`, uses 120, stays within 50 words, and has no invented claims. Unapproved fact returns 400.
- T2: Generate the workshop for grade 8, Spanish, in-person delivery. Inspect the rendered deck and required inputs.
- T3: Approve a seeded version, revise it, then attempt school review using the old approval. Return 409. Require staff approval again.
- T4: Cross-organization read returns 404. A school token cannot read sources or grant documents.
- T5: Model failure preserves inputs and exposes retry. Retrying with an idempotency key creates one draft job.

## UI acceptance tests

- U1: Open a source citation from a draft and locate its evidence. Display unsupported and missing facts clearly.
- U2: Edit approved slides. Confirm that the new version needs staff review before school access.
- U3: Open a school review link without installing an app. Approve one version and verify its version label in staff view.
- U4: Generate and inspect all three workshop languages. Keep long text readable and preserve citations.
- U5: Revoke a source fact and confirm affected drafts display a warning. Confirm clinical notes never appear in global search.

## Decisions before implementation

Q1: Which file formats must the first demo export? Recommended default: a browser deck plus PDF and grant text export.

Q2: Which school approval identity is acceptable? Recommended default: an expiring one-recipient demo link with an explicit reviewer name.

Q3: Which BeWize storage and approval interfaces exist? Verify them first. Use adapters only where an existing capability is confirmed.

## Completion evidence

Record passing API checks, rendered slide review, citation checks, stale-approval checks, and permission failures. Deliver one approved workshop deck and one sourced grant answer. Do not report production integration or privacy certification from these demo results.
