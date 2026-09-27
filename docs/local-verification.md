# Phase 1 local verification

Verified on Windows using Python 3.12.10, Node.js 22.16.0, React 19.1.0, Vite 6.4.3, FastAPI 0.115.12, and headless Microsoft Edge. No AWS resources or model calls were used.

## Results

- 36 Python tests passed: deterministic forecasts/seeds, missing/invalid inputs, no backtest leakage, rounding and zero denominator, policy boundaries, explicit approval, rejection, duplicate/concurrent decisions, blocked proposals, stale/expired approvals, hash/schema tampering, persistence, failed disk commit rollback, append-only audit, and origin rejection.
- TypeScript checking and Vite production build passed.
- Browser workflow passed against isolated local state: generate, inspect pending human approval, approve $1,000 to $1,150, reload and retain execution, generate/reject with unchanged budget, block Smart TV cap and Speaker inventory scenarios, inspect audit, and generate another eligible proposal.
- Desktop and mobile screenshots inspected; 390-pixel viewport had no document overflow. Chart has a full text/table alternative. No browser page errors were recorded.
- npm installation audit reported zero known vulnerabilities after updating Vite to 6.4.3.
- Main demo servers started at 127.0.0.1:8000 (FastAPI) and 127.0.0.1:5173 (React). Test servers use different ports and files.

## Issues resolved during verification

The machine lacked usable Python 3.12/Node commands, so project-local runtimes were downloaded into ignored .tools. Restricted temp/build-directory permissions required a workspace-local pytest temp directory and running frontend tooling outside that restriction. A stale Vite advisory was resolved by a patch update. A CSS import build error and a decorative arrow in a button's accessible name were corrected before successful verification.

Remaining non-failing tooling output: Starlette/AnyIO emits a deprecation warning; the environment's simultaneous NO_COLOR/FORCE_COLOR variables produce Node color warnings. These did not fail tests. The local app uses a fixed demo identity, not Cognito, and whole-file locking is intended for a small single-machine demonstration. No cloud behavior has been tested or claimed.

Future Bedrock and custom-domain deployment require the user's next approval; no automatic migration or deployment is configured.
