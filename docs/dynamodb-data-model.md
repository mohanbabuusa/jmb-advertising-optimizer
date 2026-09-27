# DynamoDB data model

Phase 1 uses `backend/local-data/state.json`, not DynamoDB. Its campaigns, recommendations, decisions, actions, idempotency, and audit collections implement the same business responsibilities within one locked, atomically replaced file. The table design below remains future documentation only. No DynamoDB client or infrastructure has been created.

V1's future cloud design uses five on-demand encrypted tables with versioned schemas and optional point-in-time recovery. Owner IDs come from verified identity. Keys are strings; money is integer cents; timestamps are UTC ISO strings; concurrency uses integer versions. No streams, outbox, worker leases, recovery indexes, or scheduled processing exist in V1.

## Tables and access patterns

| Table | Partition key | Sort key | Contents |
|---|---|---|---|
| CampaignState | `OWNER#{sub}` | `PRODUCT#{productId}` | Current campaign and inventory |
| Recommendations | `OWNER#{sub}` | `REC#{recommendationId}` | Immutable proposal/inputs, forecast, checks, status, versions, request deadline |
| Approvals | `OWNER#{sub}` | `REC#{recommendationId}` | One immutable human decision/attempt and its outcome |
| AuditHistory | `OWNER#{sub}` | `AT#{timestamp}#{eventId}` | Append-only chronological history |
| Operations | `OWNER#{sub}` | `IDEMP#{operation}#{targetId}#{key}` or `ACTION#{recommendationId}` | Durable request deduplication and unique mock action receipts |

Indexes support only required UI access:

- Recommendations ProductHistory: PK `OWNER#{sub}#PRODUCT#{productId}`, SK `AT#{createdAt}#{recommendationId}`; project summaries.
- AuditHistory ByRecommendation: PK `OWNER#{sub}#REC#{recommendationId}`, SK `AT#{timestamp}#{eventId}`.
- AuditHistory ByProduct: PK `OWNER#{sub}#PRODUCT#{productId}`, SK `AT#{timestamp}#{eventId}`.

GSIs are eventually consistent navigation aids. Commands use strongly consistent base-table reads and conditional transactions. Decision responses contain authoritative committed results; history lists may briefly lag. Owner-scoped indexes avoid scans and cross-user queries. Five small tables keep responsibilities and IAM boundaries clear without provisioned baseline throughput.

## Important fields

CampaignState: product/campaign IDs, weeklyBudgetCents, currency, simulated metrics/window, onHandUnits, reservedUnits, availableUnits, inventoryVersion, version, updatedAt, simulation=true. Inventory updates also advance campaign version. Setup conditionally seeds five campaigns per owner with initialization audit.

Recommendations: status, version, createdAt, expiresAt, productId, campaignVersion, inventoryVersion, datasetVersion, S3 object/version reference, inputHash, forecast, algorithmVersion, policyVersion, promptVersion, configuredModelId, bounded model output/token usage, proposal, proposalHash, generationChecks, executionChecks, approvalEligible, error metadata, correlationId, requestDeadline. The fixed request deadline is 30 seconds from reservation, beyond the 25-second Lambda lifetime; it is not a renewable worker lease. Completion checks GENERATING and this deadline. No other invocation takes over generation.

Proposal hash is SHA-256 of canonical JSON containing action, target IDs, proposed budget, input hash, campaign/inventory versions, forecast, policy/algorithm versions, reasoning, assumptions, and expiry. Status changes do not alter it. No proposal edits after readiness; corrections require a new recommendation and approval. Retain all model inputs or immutable versioned references, including campaign metrics and inventory; hashes alone cannot reconstruct inputs.

Approvals: decisionId, decision APPROVE/REJECT, actorId, decidedAt, proposalHash, recommendationVersion, outcome EXECUTED/REJECTED/STALE/BLOCKED/EXPIRED, optional comment, schemaVersion. Unique recommendation key prevents competing decisions. APPROVE with a no-op outcome records an attempt and cannot authorize later execution.

AuditHistory: eventId, eventType, actor type/ID, productId, recommendationId when applicable, correlationId, occurredAt, schemaVersion, details. Types include SIMULATION_INITIALIZED, RECOMMENDATION_REQUESTED, RECOMMENDATION_GENERATED, VALIDATION_COMPLETED, RECOMMENDATION_FAILED, DECISION_RECORDED, EXECUTION_VALIDATED, CAMPAIGN_UPDATED, EXECUTION_BLOCKED, and RECOMMENDATION_EXPIRED. Include every validation result, decision, and action with before/after values and policy versions. Keep 90-day history in versioned S3 and bounded references in audit.

Operations request records: requestHash, operation, targetId, resourceId, status IN_PROGRESS/COMPLETED, originalStatusCode, originalResponse, createdAt, requestDeadline for generation. Action receipts: actionId, recommendationId, approvalId/hash, before/after budgets, campaign versions, executedAt. No TTL on audit, approvals, receipts, or deduplication records. Teardown is explicit.

## Synchronous recommendation transactions

1. Validate identity, route/body, and product existence. Atomically reserve the key, put GENERATING recommendation, and append request audit. Existing different request hash conflicts; COMPLETED returns saved response; active IN_PROGRESS returns 409 REQUEST_IN_PROGRESS.
2. In that invocation, read snapshots, forecast, call Bedrock, validate schema, and run guardrails. Commit ready recommendation/checks, generation and validation audit, and completed idempotency response together. Return 201 AWAITING_APPROVAL or BLOCKED. Conditions require GENERATING, matching request identity, and unelapsed deadline.
3. Caught failures atomically set FAILED, append audit, and save a replayable error response. After a hard termination, the next same-key POST beyond requestDeadline finalizes FAILED with GENERATION_INTERRUPTED audit/error. It never repeats Bedrock generation. A new key explicitly requests a new recommendation.

Reads may expose effective FAILED after an abandoned deadline without writing. Untouched abandoned records can remain physically GENERATING, but are never approval-eligible. There is no background recovery promise. Durable state and audit catch up on the next same-key POST.

## Synchronous approval and mock execution

1. Look up the completed same-key response first so retries can recover an already committed result. Strongly read recommendation and current campaign/inventory; verify owner, hash, expected recommendation version, undecided state, and expiry. Recompute forecast from referenced history and re-run deterministic checks, including policy version and freshness. Never trust client policy results or approval flags.
2. Approval Lambda builds a server-validated explicit APPROVE context. The private mock service commits one transaction: conditional campaign update at verified versions, AWAITING_APPROVAL to EXECUTED recommendation transition at expected version/hash, unique immutable decision and ACTION receipt, completed idempotency response, and decision/validation/action audit records. Check expiry immediately before commit; refuse to start a transaction too close to expiry for its bounded deadline. Approval and action become durable together; there is no APPROVED waiting state.
3. REJECT commits decision, REJECTED transition, deduplication response, and audit only. It accepts undecided AWAITING_APPROVAL or generation BLOCKED; it never calls mock mutation.
4. STALE/BLOCKED/EXPIRED outcomes atomically save terminal status, attempted decision with no-op outcome, validation/decision/expiry audit as applicable, and completed response. Campaign remains unchanged. If a campaign version races with a passing check, re-read and finalize STALE against the approved snapshot; do not silently approve a different proposal. Request version/hash mismatches or competing finalized decisions return 409.
5. Concurrent writers use transaction conditions. A loser re-reads its own completed key and returns that result, or returns conflict. Infrastructure failure before commit leaves no decision/mutation, so the identical approval/key can retry. A lost response after commit returns the saved receipt without applying again. Transport timeout alone proves neither success nor failure.

Recommendation/campaign updates carry their own conditions; do not separately ConditionCheck the same item in that transaction. Durable keys extend idempotency beyond DynamoDB's short request-token window. Strict payload limits and S3 references keep items below 400 KiB. Validation snapshots are bound to transaction-checked versions.

## Expiration and audit immutability

expiresAt is min(createdAt + 30 minutes, next UTC midnight). Commands enforce timestamps directly. Reads expose effective EXPIRED for elapsed undecided proposals without writing; a subsequent decision request atomically persists expiration, attempted decision, and audit. EXECUTED/REJECTED records do not expire retroactively. TTL and scheduled jobs are unnecessary for correctness. Read-derived statuses may precede their persisted audit event; the original record already contains the deadline.

Audit IAM omits UpdateItem/DeleteItem; all puts require attribute-not-exists. Existing events are never edited; corrections append events. Every persisted recommendation, validation, decision, and action transition includes audit in the same transaction. Failure to persist audit prevents mutation. This is immutable at the application boundary, not a regulatory tamper-proof archive against administrators.

## Production Scale Evolution

For asynchronous processing, higher throughput, independent scaling, replay, and stronger failure isolation, extend Operations with OUTBOX records and PendingOutbox index, enable DynamoDB Streams, and add work/recovery indexes plus worker claim IDs/leases. Write outbox with business state/audit atomically. A future APPROVED state stores the human decision before a separate worker verifies it and executes.

The stream relay publishes to EventBridge and marks only successful entries delivered. A crash after publication can duplicate delivery; consumers retain durable receipts and conditional transitions. A scheduled reconciler republishes pending entries and re-drives stranded work. Lease-bound completion prevents replaced workers from committing. Bounded retries, separate delivery/processing DLQs, and audited replay improve recovery. These fields, indexes, and processes are excluded from V1.
