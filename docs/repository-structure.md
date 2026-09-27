# Repository structure

Phase 1 now contains working local code alongside unused future directory placeholders. Actual entry points are `backend/src/optimizer/handlers/main.py` and `frontend/src/main.tsx`; local adapters live in `backend/src/optimizer/adapters/local/`. Backend tests cover domain functions and transactional HTTP/application workflows. `frontend/tests/workflow.spec.ts` verifies the dashboard in an isolated simulation. `scripts/export_synthetic.py` writes the five committed 90-day JSON fixtures; `scripts/browser_backend.py` starts isolated browser-test state. `backend/local-data/`, dependency folders, and project-local runtimes are ignored. No AWS adapter or Terraform module has implementation code. The tree below retains future module destinations alongside current ones.

```text
/
  architecture.md
  README.md
  docs/
    api-contract.md
    dynamodb-data-model.md
    terraform-resource-plan.md
    implementation-plan.md
    repository-structure.md
  frontend/
    src/
      app/                 # Routing, authentication, dashboard composition
      components/          # Accessible reusable UI, simulation banner
      features/
        products/          # Selector and product summary
        demand/            # History chart, seven-day forecast and method
        campaigns/         # Metrics, inventory, simulated budget
        recommendations/   # Reasoning, validation, explicit decisions
        audit/             # Paginated timeline and detail
      api/                 # Typed client, synchronous requests, safe retries, auth
    tests/                 # Component and browser workflow tests
  backend/
    src/optimizer/
      domain/              # Entities, money, state machine, forecast, policies
      application/         # Use cases; orchestrates ports and transactions
      ports/               # Repositories, reasoning, history, mock campaign
      adapters/
        aws/               # DynamoDB, S3, Bedrock Converse
        local/             # Local storage, fixture reasoner, fixture history
      handlers/            # Read, recommendation, approval/rejection HTTP handlers
    tests/
      unit/
      integration/
      contract/
  data/
    synthetic/             # Later: five 90-day histories, products, manifest
    scenarios/             # Later: cap, confidence, inventory, stale fixtures
  scripts/                 # Later: seed generator, local runner, packaging
  infra/
    bootstrap/             # Terraform state bucket; separate lifecycle
    environments/dev/      # Composition, input variables, backend config
    modules/
      hosting/
      auth/
      api/
      compute/
      storage/
      observability/
      dns/
  .github/workflows/       # Later: checks only; no automatic deployment
```

Dependency direction: handlers -> application -> domain/ports. Adapters implement ports and are wired at composition roots. Domain code imports no AWS SDK, web framework, or model client. Forecast and policy functions accept typed values and return deterministic results. Transactional repository methods represent complete use cases, avoiding independent writes that could omit audit history. Mock campaign service is a private Python interface, not a public browser endpoint.

Planned tooling: React/TypeScript with Vite; Python 3.12 with pytest and Ruff; Terraform with pinned provider constraints and committed dependency lock file. Versions and lock files will be selected and verified during implementation. Local tooling must not default to cloud credentials or live Bedrock calls.

V1 deploys three request handlers: Read Lambda, Recommendation Lambda, and Approval Lambda. Forecasting, guardrails, and mock execution are in-process services; they are not separate workers. Seeding is an explicit setup script, not an additional workflow Lambda. There is no events module in the V1 scaffold.

## Production Scale Evolution

When asynchronous processing, higher throughput, independent scaling, replay, and stronger failure isolation justify the extra components, add an `infra/modules/events/` module, EventBridge adapter, outbox repository, relay and reconciler handlers, and separate reasoning/execution worker handlers. Add delivery/replay integration tests then. Preserve the domain ports and deterministic services so this orchestration change does not alter policy or human approval requirements. No future module or worker is implemented in V1.
