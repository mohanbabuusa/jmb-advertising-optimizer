# API contract v1

## Phase 1 local contract

The implemented API is FastAPI on http://127.0.0.1:8000, with interactive OpenAPI at `/docs`. It uses a fixed `local-demo-user` identity and must remain loopback-only; Cognito, JWT ownership, and the cloud deadline/recovery behavior below are future work. APP_MODE must be local, and FixtureReasoner never calls a network service.

All listed routes are implemented. Local recommendation creation completes in one locked JSON transaction, returning 201 with AWAITING_APPROVAL, BLOCKED, or FAILED plus audited failure details. There is no intermediate GENERATING reservation. A failed disk write rolls back state/audit; same-key retries return a saved committed result. Approval returns its final outcome synchronously and uses hash/version guards plus current deterministic checks. Direct attempts to approve generation-blocked proposals return a persisted BLOCKED no-op with audit. FastAPI schema errors return its standard 422 `detail` envelope; domain errors use the `error` envelope below.

Local audit pagination uses `before=<last eventId>` returned as nextCursor, with limit 1-100; the cursor must belong to the selected filter. Recommendation lists return all records for that product in this small prototype. Local reads derive EXPIRED without writes; an attempted decision persists it. Local schemas additionally expose demoNote, demandChangePercent, previousWeekUnits, guardrail label, reasoner, and immutable inputSnapshot to explain the demonstration. Cloud cursor/auth/reservation details below remain the planned contract, not claims of implemented AWS behavior.

Base path `/v1`. HTTPS JSON; UTC RFC3339 timestamps; dates `YYYY-MM-DD`; UUID identifiers; USD integer cents; unit counts nonnegative integers. All routes require Cognito JWT bearer authentication in AWS. Server derives owner from JWT `sub`. All returned simulation resources include `simulation: true`. Local identity is available only in explicit local mode and never honored by cloud handlers.

## Routes

| Method and path | Response | Purpose |
|---|---|---|
| GET /v1/products | 200 `{items: Product[]}` | Five catalog products plus owned simulation summaries |
| GET /v1/products/{productId}/history | 200 `History` | Exactly 90 observations and immutable dataset version |
| GET /v1/products/{productId}/forecast | 200 `Forecast` | Seven-day deterministic prediction and validation metrics |
| GET /v1/products/{productId}/campaign | 200 `Campaign` | Current simulated campaign and inventory |
| POST /v1/products/{productId}/recommendations | 201 `Recommendation` | Generate, validate, persist, and return synchronously; body `{}` |
| GET /v1/recommendations/{recommendationId} | 200 `Recommendation` | Retrieve state, reasoning, checks, decision, action |
| GET /v1/products/{productId}/recommendations | 200 `Page<RecommendationSummary>` | Newest first |
| POST /v1/recommendations/{recommendationId}/decision | 200 `DecisionResult` | Explicit APPROVE or REJECT |
| GET /v1/audit | 200 `Page<AuditEvent>` | Owned history; optional productId or recommendationId filter |

No public campaign mutation endpoint. The UI calls the decision endpoint, handled by the Approval Lambda, which calls the private mock campaign service within the same invocation. Successful approval returns the committed EXECUTED action; rejection returns REJECTED. There is no queued approval or normal workflow polling.

Both POST routes require `Idempotency-Key` (UUID) and reject missing/invalid keys. Scope keys to user, operation, and target resource; store canonical request hashes. A completed same-key/body retry returns the original saved status and response, even if the resource has since advanced (GET retrieves latest). Same key/different body returns 409 IDEMPOTENCY_CONFLICT. Concurrent recommendation duplicates return 409 REQUEST_IN_PROGRESS with Retry-After and recommendationId. They cannot start a second model call. After the fixed request deadline, a same-key retry finalizes an abandoned generation as FAILED and saves a 503 GENERATION_INTERRUPTED response; creating another proposal requires an explicit new key. Concurrent decision requests resolve through atomic conditions; a loser re-reads the completed same-key result or returns 409 DECISION_CONFLICT for a different key. Keys remain for the simulation lifetime; do not depend on DynamoDB's short transaction-token window.

Pagination: optional `limit` integer 1–100 (default 25), and opaque `cursor`. Bind cursor to owner, filters, and index; reject mismatches. Return `{items, nextCursor: string|null}`. Audit filters productId and recommendationId are mutually exclusive. Validate product ownership and existence before generating recommendations. Unknown or other-owner IDs return 404.

## Resource schemas

Required fields unless marked optional:

- `Product`: `productId`, `name`, `description`, `currency: "USD"`, `simulation: true`.
- `History`: `productId`, `datasetVersion`, `startDate`, `endDate`, `observations: [{date, units}]`, `simulation: true`.
- `Forecast`: `productId`, `datasetVersion`, `algorithmVersion`, `generatedAt`, `horizon: [{date, predictedUnits}]` (7), `totalUnits`, `requiredInventoryUnits`, `confidenceScore: number|null` (0–1), `confidenceMeaning: "backtest_accuracy_proxy"`, `backtest: {holdoutDays: 28, wape: number|null}`, `simulation: true`.
- `Campaign`: `campaignId`, `productId`, `weeklyBudgetCents`, `currency: "USD"`, `version`, `inventory: {availableUnits, version}`, `metrics: {windowStart, windowEnd, impressions, clicks, conversions, spendCents, revenueCents}`, `simulation: true`. Windows cover the previous seven complete UTC days. Derived CTR/ROAS are nullable for zero denominators. Synthetic metrics are descriptive and do not imply measured future impact.
- `GuardrailResult`: `checkId`, `phase: "GENERATION"|"EXECUTION"`, `status: "PASS"|"FAIL"|"PENDING"`, `observed` (typed JSON value), `limit` (typed JSON value), `message`, `policyVersion`, `checkedAt`.
- `Recommendation`: `recommendationId`, `productId`, `status`, `version`, `createdAt`, `expiresAt`, `simulation: true`; optional until ready: `proposalHash`, `proposal`, `forecast`, `generationChecks`, `executionChecks`, `approvalEligible`, `decision`, `action`, `error`. `proposal` contains `action: "SET_WEEKLY_BUDGET"`, `currentWeeklyBudgetCents` (server supplied), `proposedWeeklyBudgetCents`, `reasoning` (max 4000 characters), `assumptions` (max 10 strings of 300 characters). Server supplies trusted IDs, current budget, forecast, and hash; the model cannot override them. Status values follow architecture.md.
- `RecommendationSummary`: `recommendationId`, `productId`, `status`, `createdAt`, `expiresAt`, `simulation: true`.
- `DecisionResult`: `recommendationId`, `status: "EXECUTED"|"REJECTED"|"STALE"|"BLOCKED"|"EXPIRED"`, `decision: {decisionId, decision, actorId, decidedAt, proposalHash, outcome, comment?}`, `executionChecks` (array; empty for rejection), `action?`, `simulation: true`. Action is present only for EXECUTED. Decision outcome equals the resulting status; an APPROVE attempt with BLOCKED/STALE/EXPIRED outcome is not authorization for later execution.
- `Action`: `actionId`, `recommendationId`, `campaignId`, `beforeWeeklyBudgetCents`, `afterWeeklyBudgetCents`, `executedAt`, `campaignVersion`, `simulation: true`.
- `AuditEvent`: `eventId`, `occurredAt`, `eventType`, `actor: {type: "HUMAN"|"SYSTEM", id}`, `productId`, `recommendationId?`, `correlationId`, `details`, `simulation: true`. Details contain versioned before/after values, validation results, decision references, or error metadata as applicable.

## Explicit decision example

```json
{
  "decision": "APPROVE",
  "expectedVersion": 2,
  "proposalHash": "sha256:example-placeholder",
  "comment": "Reviewed demand, inventory, and budget checks."
}
```

`decision` is APPROVE or REJECT; `expectedVersion` is a positive integer; `proposalHash` must match the ready immutable proposal; optional comment max 1000 characters. Disallow unknown request fields. APPROVE requires an eligible, unexpired `AWAITING_APPROVAL` proposal and fresh execution checks. REJECT accepts undecided `AWAITING_APPROVAL` or generation `BLOCKED`. A committed decision is final; competing decisions or changed recommendation version/hash return 409. Current campaign/inventory version changes instead finalize STALE with an audited no-op. Revalidation failure finalizes BLOCKED; elapsed expiry finalizes EXPIRED. These accepted decision attempts return 200 DecisionResult with no action, so clients must inspect status rather than treat every 200 as execution. Attempts against already finalized decisions return 409 except completed same-key retries. Successful approval returns EXECUTED only after its atomic commit.

Reads calculate effective EXPIRED for elapsed undecided records and effective FAILED for abandoned GENERATING records without writing. `version` remains the stored version; the next applicable POST persists the terminal state and audit. There is no periodic expiry job, and expiration never relies on DynamoDB TTL. A read-derived status therefore need not yet have its own audit event; the original record contains the deadline.

## Internal contracts

`ReasoningService.recommend(context)` receives product, 90 observations, deterministic forecast, campaign metrics/current budget, and available inventory. It returns only proposed budget, action, reasoning, and assumptions under the strict proposal schema. It cannot return trusted approval or validation results.

`MockCampaignService.apply_approved_budget(validatedDecisionContext)` is private to the Approval Lambda. The context is built server-side from authenticated identity, explicit APPROVE, immutable proposal/hash, current versions, expiry, and passing revalidation results. It cannot be deserialized directly from an HTTP or AI payload. The service atomically persists approval, campaign change, recommendation transition, action receipt, idempotent response, and audit events; no effect can commit without its human decision. Returns DecisionResult; duplicate committed requests return the saved result. AWS permissions prevent the Recommendation Lambda from invoking this handler or writing campaigns/decisions.

## Errors and interaction

Error envelope: `{error: {code, message, requestId, retryable, recommendationId?}}`. Statuses: 400 malformed request; 401 invalid authentication; 403 missing operation permission; 404 resource unavailable; 409 state/version/idempotency conflict or request in progress; 422 unusable dataset; 429 throttled; 503 dependency unavailable or interrupted generation. Avoid disclosing other users' records. A valid but unsafe generated proposal returns 201 with BLOCKED and explicit checks. Caught generation failures save FAILED, failure audit, and a replayable 422/503 response. Hard termination leaves a request record for the next same-key POST to finalize. A gateway-generated 504 or network failure may not contain this envelope and is an unknown outcome.

UI shows a loading state while each POST runs, renders its returned result, and disables repeated decision clicks while pending. Preserve key/body across transport retries; honor Retry-After and use bounded backoff, then offer manual retry. Refresh GET after unknown decision outcomes and replay the same POST key if needed. Do not create a new recommendation key automatically after a failure. No background polling loop is needed. Plan 20-second application work deadline, 25-second Lambda timeout, and 30-second gateway integration; bound Bedrock/network retries inside that budget. Request body limit 16 KiB; enforce schema and string limits. Mutations and authenticated reads use `Cache-Control: no-store`.

## Production Scale Evolution

If asynchronous processing, higher throughput, independent scaling, replay, or stronger failure isolation become necessary, introduce a versioned asynchronous contract: 202 recommendation acceptance, APPROVED/queued decision responses, status polling, and persisted human approval checked by a separate execution worker. Do not silently change V1's completed-result semantics.

Future EventBridge source `portfolio.advertising`; detail types `RecommendationRequested.v1` and `RecommendationApproved.v1`; detail `{eventId, ownerId, recommendationId, correlationId, schemaVersion: 1}`. IDs identify stored records and never authorize mutations. Workers independently verify state, identity scope, hashes, expiry, and approval. Outbox delivery can repeat; consumers must deduplicate. No event contract is implemented in V1.
