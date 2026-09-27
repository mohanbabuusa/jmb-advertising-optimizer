# Implementation plan

Phase 1 local prototype is implemented with Python 3.12/FastAPI, React/TypeScript, deterministic histories, forecasting, FixtureReasoner, guardrails, explicit decisions, JSON state, and audit. The user's Phase 1 instruction supersedes the earlier SQLite suggestion: local transactions use a file lock and atomic snapshot replacement. Tests cover the local workflow; cloud adapters, Cognito, Bedrock, Lambda packaging, and Terraform remain unimplemented and require the next authorized phase. The original roadmap below is retained as a future build guide, not a claim that AWS work is complete.

## 1. Contracts, domain, and synthetic data

Translate the API contract into OpenAPI and typed Python/TypeScript schemas. Implement money types, immutable proposals, state transitions, owner scoping, canonical hashing, and domain errors. Generate a manifest and exactly 450 history rows: 90 per product. Product IDs are `wireless-headphones`, `smart-tv`, `streaming-device`, `gaming-controller`, and `bluetooth-speaker`.

Seed deterministic seven-day campaign metrics and campaign budgets of $1,000, $4,500, $600, $800, and $700 respectively; inventory defaults derive from buffered forecast plus sufficient headroom. Explicit scenario fixtures exercise insufficient inventory, poor forecast accuracy, 20% boundary, $5,000 boundary, stale versions, and expired proposals. Dates are anchored by an explicit generator argument and persisted in the manifest. Include reproducible demo regeneration instructions.

Acceptance: identical seed/end date produces byte-identical fixtures; valid continuous dates and integer quantities; all five named products; no external product dependencies. Synthetic sample history and executable generator are produced in this implementation phase, not claimed as present in the design scaffold.

## 2. Forecast and guardrails

Implement weekday mean forecast, rolling-origin backtest, confidence proxy, inventory buffer, and complete result reporting as pure functions. Test known hand-calculated predictions, no future-data leakage, zero denominator, malformed/missing history, 79.99% versus 80%, exact 20% versus above, exact $5,000 versus above, insufficient inventory, expiry, and pending approval. Compare raw values rather than UI-rounded values.

Acceptance: repeatable seven-day forecasts with documented calculations; every named guardrail visible; blocked proposals cannot become approved or execute.

## 3. Local application and repository ports

Implement application use cases and local adapters with transactional behavior sufficient to exercise races and durable idempotency across local process restarts. Provide an explicit local runner using fixture reasoning, synthetic data, and local identity, with no AWS calls. Implement the private mock campaign interface and APIs. Serialize its state changes transactionally (for example using SQLite), rather than assuming a dictionary emulates DynamoDB concurrency.

Acceptance: recommendation POST returns a ready proposal/checks; explicit decision POST returns committed execution or rejection/no-op. Approval, mock action, idempotency response, and audit commit together. Duplicate requests change budget once; rejection leaves it unchanged. Test lost responses, concurrent decisions, and lazy expiry without background processes. Local deadlines use an injectable clock so interruption/expiry scenarios are easy to demonstrate.

## 4. AWS adapters and Bedrock

Implement S3 snapshot reads, DynamoDB transactions, Bedrock Converse abstraction, and Read/Recommendation/Approval HTTP handlers. Recommendation performs forecast -> Bedrock -> schema validation -> guardrails -> persistence -> response in one invocation. Approval verifies identity/state/hash/expiry, re-runs guardrails against current state, and invokes the private mock service for the atomic commit. Enforce strict model schema and separate IAM roles. Preserve exact approved proposal and inputs. No separate reasoning/execution workers, event publishing, outbox, scheduled reconciler, or workflow queues.

Acceptance: mocked SDK tests verify Converse model ID from environment, strict output validation, and no model execution tools. Failed audit persistence prevents mutation. Test same-key concurrent generation (one model call), hard termination followed by request-driven failure finalization (no automatic regeneration), changed-body conflicts, lost response after commit, stale campaign/inventory, changed policy, low confidence, expired approval, and competing approve/reject requests. Verify Recommendation IAM cannot mutate campaigns/decisions or invoke Approval. Budget the request for a 20-second work deadline, 25-second Lambda timeout, and 30-second HTTP API integration; bound SDK retries and test timeout handling. DynamoDB Local integration tests do not prove full AWS parity. Actual model latency and cloud smoke tests remain deferred until deployment is requested.

## 5. React dashboard

Build dashboard, selector, historical chart, forecast with backtest explanation, campaign metrics, inventory, recommendation/rationale, all generation/execution guardrails, explicit Approve and Reject actions, and paginated audit history. Keep the simulation banner visible. Include empty/loading/error/blocked/stale/expired/submitting states, keyboard-accessible controls, focus handling, and text/table equivalents of chart data. Auth integration uses PKCE. Render completed POST responses directly; no routine background polling.

Acceptance: browser workflow tests cover approve, reject, blocked/no-op result, timeout/unknown outcome, same-key retry, double click, user isolation, and stale decision conflict. Preserve key/body across retries and inspect status before showing success. Explicit new generation after terminal failure uses a new key. The browser never calls a raw mock mutation endpoint. Button gating is a UX aid; independently test server enforcement.

## 6. Terraform and documentation

Implement only V1 modules in the resource plan: private hosting, Cognito, synchronous API, three Lambdas, S3/DynamoDB, scoped IAM, optional custom domains, and basic monitoring/cost controls. Assert the plan has no streams, event bus, workflow DLQs, scheduled reconciler, or asynchronous workers. Seed through an explicit setup script. Add packaging instructions, environment examples without secrets, local commands, architectural decisions, and portfolio walkthrough. CI runs Python checks, frontend checks/build, OpenAPI consistency, and Terraform formatting/validation without applying resources.

Acceptance: clean-checkout local workflow is documented and exercised; all automated checks pass; default configuration cannot invoke a real advertising provider; no automatic deployment; cloud prerequisites and service costs described accurately. Any AWS plan or deployed smoke test is reported as not run until actually performed.

## Completion evidence for the eventual application

Demonstrate one synchronous approved action with matching approval/hash and atomic audit records, one rejection with unchanged budget, each guardrail failure, one repeated HTTP request with a single action receipt, expired approval, and one stale snapshot requiring a fresh recommendation. Save a demo walkthrough and meaningful test results. Current design stage is complete when the six updated documents agree, links resolve, and module directories match V1. No application tests are claimed before implementation.

## Production Scale Evolution

Only introduce the former asynchronous design when measured needs include longer recommendation/execution processing, higher throughput, independent scaling, replay, and stronger failure isolation. A later milestone would add transactional outbox, DynamoDB Streams relay, EventBridge custom bus, scheduled reconciliation, separate reasoning/execution workers, and delivery/processing SQS DLQs.

That migration also requires versioned 202/polling API semantics, durable APPROVED state, worker verification of persisted approval, leases, duplicate/out-of-order event tests, partial publication failure tests, replay controls, backlog alarms, and recovery documentation. Preserve deterministic policies, expiry, immutable audit, and durable action idempotency. Do not implement or provision these components as part of V1.
