# JMB Advertising Demand & Campaign Optimizer

A working Phase 1 local portfolio application: React + TypeScript, Python 3.12 + FastAPI, deterministic forecasting, FixtureReasoner, guardrails, explicit human decisions, and persistent mock campaigns.

**SIMULATION — No real advertising spend.** No AWS SDK, credentials, Bedrock calls, Terraform implementation, or cloud resources are used. Bedrock integration is deferred until explicitly approved.

## Run on this Windows workspace

Project-local Python 3.12.10 and Node 22.16.0 are available under the ignored `.tools` directory in this workspace. Dependencies are already installed. No PowerShell execution-policy change or environment activation is necessary. Use two PowerShell terminals.

Terminal 1 — backend:

```powershell
Set-Location C:\projects\agentic-advertising-forecast
$env:APP_MODE = 'local'
& .\.tools\python\python.exe -m uvicorn optimizer.handlers.main:app --app-dir backend\src --host 127.0.0.1 --port 8000
```

Terminal 2 — frontend:

```powershell
Set-Location C:\projects\agentic-advertising-forecast\frontend
$env:Path = 'C:\projects\agentic-advertising-forecast\.tools\node-v22.16.0-win-x64;' + $env:Path
& ..\.tools\node-v22.16.0-win-x64\node.exe ..\.tools\node-v22.16.0-win-x64\node_modules\npm\bin\npm-cli.js run dev
```

Open **http://127.0.0.1:5173**. API documentation: **http://127.0.0.1:8000/docs**. Health: **http://127.0.0.1:8000/health**. Keep both terminals running; Ctrl+C stops each server. If a port is already occupied by the running prototype, use the existing page or stop that server first.

## Fresh checkout on Windows

The portable runtimes and installed dependencies are not committed. Install Python 3.12 and Node.js 22 (22.12 or later), then use:

```powershell
Set-Location C:\projects\agentic-advertising-forecast
py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r backend\requirements.lock.txt
$env:APP_MODE = 'local'
& .\.venv\Scripts\python.exe -m uvicorn optimizer.handlers.main:app --app-dir backend\src --host 127.0.0.1 --port 8000
```

In a second terminal:

```powershell
Set-Location C:\projects\agentic-advertising-forecast\frontend
npm.cmd ci
npm.cmd run dev
```

Dependency installation requires internet access. After installation, the app runs without network access beyond localhost. It has no external fonts, data APIs, or model calls. The local identity is fixed to `local-demo-user`; this is not a public authenticated deployment. Bind only to loopback. Cognito and domain deployment remain future work.

## Interview walkthrough

1. Select **Wireless Headphones**. Review 90 days of history, seven daily predictions, backtest accuracy, inventory, and campaign metrics.
2. Click **Generate recommendation**. FixtureReasoner proposes $1,000 → $1,150 when demand is increasing. All checks pass except human approval, which remains PENDING.
3. Click **Approve**. The server revalidates the proposal and current campaign, then commits approval, the mock budget update, action receipt, and audit records together. Only the budget changes; historical performance is not fabricated.
4. Generate another recommendation and **Reject** it. The budget stays unchanged. Expand the audit records to inspect the decision and validations.
5. Select **Smart TV** and generate: the proposed $5,175 exceeds the $5,000 cap. Approval is disabled, and direct API approval also cannot execute.
6. Select **Bluetooth Speaker** and generate: insufficient inventory blocks execution.
7. Refresh the page to show persisted state. Explain that the reasoner only returns a proposal; deterministic application code controls execution.

Streaming Device and Gaming Controller provide additional approval-ready campaigns. Forecast growth/accuracy are calculated from the synthetic data, not hardcoded UI percentages. For the committed 2026-09-19 history, Headphones shows approximately +20.9% demand and 92.6% backtest accuracy.

## Forecasting and policy

Each of the next seven days uses the average of the last four observations for the matching weekday, rounded half up. Four non-overlapping seven-day holdouts use only earlier training data. Confidence is `max(0, 1 - WAPE)` across 28 held-out days: an accuracy proxy, not a probability. A zero denominator means unavailable confidence and blocks execution.

Budget increase must be <=20%, weekly budget <=$5,000 per campaign, confidence >=80%, and inventory >=110% of predicted weekly demand. Money uses integer cents. All budget changes require human approval. Recommendations expire after 30 minutes or at the next UTC midnight, whichever is earlier. Execution checks hash, version, expiry, forecast, policy, inventory, and campaign state again. A second accepted recommendation that changed the campaign makes older proposals stale.

## State, audit, and a fresh demo

First startup seeds `backend/local-data/state.json` with all five products and 450 observations ending yesterday UTC. Every transaction takes a cross-process file lock, writes a temporary snapshot, flushes it, and atomically replaces the state file. Campaign state, immutable application audit, and durable idempotency receipts commit together. Repeated same-key requests return the saved result; different decisions cannot execute twice. An interrupted write leaves the prior snapshot intact. This is a small local-file design, not a distributed storage system; an administrator can edit the file outside the app.

Restarts preserve the same history and decisions. On a later UTC day, old history fails freshness checks. To start a new demo **without deleting prior audit history**, stop the backend and, from the repository root, select a new file before starting it again:

```powershell
$env:LOCAL_STATE_PATH = Join-Path (Get-Location) ('backend\local-data\demo-' + [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss') + '.json')
& .\.tools\python\python.exe -m uvicorn optimizer.handlers.main:app --app-dir backend\src --host 127.0.0.1 --port 8000
```

For the virtual-environment setup, replace the Python executable with `.\.venv\Scripts\python.exe`. The old state remains untouched. To resume the default state in a later terminal, leave LOCAL_STATE_PATH unset. Do not manually edit live state.

Committed reference fixtures are in `data/synthetic/`. Regenerate them reproducibly with an explicit end date; this does not modify live state:

```powershell
& .\.tools\python\python.exe scripts\export_synthetic.py --end-date 2026-09-19
```

## Tests and build

Using the workspace runtimes, from the repository root:

```powershell
& .\.tools\python\python.exe -m pytest backend\tests -q
Set-Location frontend
$env:Path = 'C:\projects\agentic-advertising-forecast\.tools\node-v22.16.0-win-x64;' + $env:Path
& ..\.tools\node-v22.16.0-win-x64\node.exe ..\.tools\node-v22.16.0-win-x64\node_modules\npm\bin\npm-cli.js run build
& ..\.tools\node-v22.16.0-win-x64\node.exe ..\.tools\node-v22.16.0-win-x64\node_modules\npm\bin\npm-cli.js test
```

For a fresh checkout with installed Node/Python:

```powershell
Set-Location C:\projects\agentic-advertising-forecast
& .\.venv\Scripts\python.exe -m pytest backend\tests -q
Set-Location frontend
$env:LOCAL_PYTHON = 'C:\projects\agentic-advertising-forecast\.venv\Scripts\python.exe'
npm.cmd run build
npm.cmd test
```

Browser tests use installed Microsoft Edge headlessly and start isolated servers on 8001/5174. They use a new state file under `backend/local-data/browser-tests/` each run, never the main demo state. Screenshots are saved to `frontend/test-results/`. The main 8000/5173 servers can remain running. Do not reuse occupied test ports. If Edge is absent, install Edge or change the Playwright channel to an installed browser.

The sandbox used for verification restricts the shared Windows temp directory. Its test invocation uses a unique project-local temporary directory instead:

```powershell
$testTemp = Join-Path (Get-Location) ('.tools\pytest-' + [Guid]::NewGuid().ToString())
& .\.tools\python\python.exe -m pytest backend\tests -q --basetemp $testTemp
```

Verified: 36 Python unit/integration tests, the full browser workflow including mobile layout and page refresh, and TypeScript/Vite build. Tests cover forecasting, policy boundaries, approval/rejection, duplicates, blocked proposals, stale/expired approvals, schema tampering, disk-write rollback, audit immutability, and persistent idempotency. A dependency deprecation warning from Starlette/AnyIO and terminal color warnings are non-failing; no application/browser runtime errors remain. See [verification notes](docs/local-verification.md).

## Code map and next phase

`backend/src/optimizer/domain/` holds pure forecasts, policies, and input schemas. `ports/reasoner.py` defines the proposal-only interface. `adapters/local/` holds synthetic data, FixtureReasoner, and JSON persistence. `application/` controls decisions and private mock execution. `handlers/` wires FastAPI. The React dashboard, typed API client, and accessible SVG chart are under `frontend/src/`.

The FixtureReasoner has no storage or execution handle. A future BedrockConverseReasoner can implement the same proposal interface, but network request deadlines and orchestration must be added outside the local file lock. **Stop at Phase 1: do not add Bedrock or infrastructure until approved.**

Start with [architecture.md](architecture.md) for the current local design and future cloud architecture. No EventBridge, Streams, SQS, containers, database servers, analytics clusters, workflow engines, or NAT infrastructure are implemented.

Supporting design documents:

For a shareable explanation of the implemented prototype, see the [end-to-end wiki document](docs/wiki-end-to-end.md).

1. [Architecture](architecture.md)
2. [Repository structure](docs/repository-structure.md)
3. [API contract](docs/api-contract.md)
4. [DynamoDB data model](docs/dynamodb-data-model.md)
5. [Terraform resource plan](docs/terraform-resource-plan.md)
6. [Implementation plan](docs/implementation-plan.md)
