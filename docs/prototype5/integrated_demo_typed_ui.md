# Prototype 5 typed demonstrator UI

## Milestone

`U1 - Typed Fluent UI and FastAPI boundary`

## Runtime

The application uses:

* FastAPI for the server-side HTTP boundary;
* the H1 `HybridInferenceRouter`;
* the A2.2 `CanonicalGovernanceRunner`;
* React, TypeScript, Vite, and Fluent UI React v9;
* server-side local and cloud credentials only.

The browser never calls a model provider directly. It submits a bounded typed
command to:

```text
POST /api/v1/governance/typed
```

The API returns the proposal, all governance gates, routing evidence, final
decision, latency fields, trace identifier, and simulation state.

## Development startup

Install the locked Python dependencies in an external virtual environment:

```powershell
python -m pip install `
    --require-hashes `
    -r requirements-win-py312.lock
```

Install the exact frontend dependency tree:

```powershell
Set-Location frontend
npm ci
```

Start both processes:

```powershell
powershell -ExecutionPolicy Bypass `
    -File scripts/prototype5/start_integrated_demo.ps1
```

The Vite UI uses `http://127.0.0.1:5173` and proxies `/api` to the FastAPI
process on `http://127.0.0.1:8000`.

## Provider configuration

Local:

```text
FOUNDRY_LOCAL_BASE_URL
FOUNDRY_LOCAL_MODEL
```

Cloud:

```text
OPENAI_API_KEY
OPENAI_BASE_URL
OPENAI_MODEL
OPENAI_TIMEOUT_SECONDS
```

Credentials remain server-side and are not represented in API schemas or
responses.

## Build and qualification

```powershell
Set-Location frontend
npm run typecheck
npm test
npm run build
npm run test:e2e
```

```powershell
python -m pytest `
    tests/prototype5/test_cloud_planner_backend.py `
    tests/prototype5/test_demo_api.py `
    -q
```

No test contacts Foundry Local or a cloud service. Provider responses,
availability, and fallback conditions are injected.

## Current boundaries

U1 supports typed manufacturing input. The healthcare option is visible but
disabled until its separate policy milestone. The microphone and simulator stop
controls are present in explicit unavailable states; U1 does not fabricate
speech or simulation behavior.

No execution permit is issued and PyBullet is not invoked in U1.
