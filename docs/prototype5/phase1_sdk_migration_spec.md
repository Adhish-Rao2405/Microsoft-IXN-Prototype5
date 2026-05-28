# Prototype 5 Phase 1 SDK Migration Baseline Spec

## 0. Executive Decision

Phase 1 is not a new prototype. It is a controlled infrastructure migration inside Prototype 5.

The objective is to replace fragile CLI-dependent model execution with a cleaner SDK/API-backed planner interface while preserving the existing zero-trust validation pipeline, evidence contracts, test harness, and dissertation claims.

The phase succeeds only if Prototype 5 can call the local Foundry model through the new SDK/API path, produce raw model responses, pass them through the existing deterministic validation gates, generate comparable evidence artefacts, and preserve all existing Prototype 5 tests/orchestrator behaviour.

## 1. Sprint Definition

### Sprint Name

Phase 1 - SDK Migration and Backend Adapter Hardening

### Sprint Purpose

Move Prototype 5 from CLI-based model invocation to a clean SDK/API integration layer.

### Scope Control

Do not expand this sprint into:

- Voice control.
- UI/dashboard.
- Modes F-J.
- New benchmark design.
- New dissertation writing.
- New robotics simulation.
- New model leaderboard.

## 2. Business-Style Outcome

By the end of Phase 1, the project should be able to state:

> Prototype 5 now supports an SDK/API-backed Foundry Local planner path. The existing zero-trust validation pipeline remains unchanged. The SDK path has been tested through representative commands, produces structured evidence, and can be used as the stable base for Phase 2 voice-control evaluation.

## 3. Non-Negotiable Engineering Rules

### Rule 1 - Do Not Break Locked Prototype 5

Prototype 5 is the dissertation evidence platform. Existing evidence, tests, and orchestrator outputs must remain valid.

### Rule 2 - Adapter Pattern Only

The SDK migration must be implemented as a backend adapter. The validation pipeline should not care whether the raw model response came from CLI, SDK/API, mock/fake backend, or replayed evidence.

### Rule 3 - Evidence Before Claims

No claim should enter the dissertation unless it has a generated artefact behind it.

### Rule 4 - Fail Closed

If SDK/API model invocation fails, times out, returns malformed output, or returns non-JSON content, the pipeline must reject safely and log the failure.

### Rule 5 - One Source of Truth

The existing deterministic validator remains the execution authority. The model never decides execution eligibility.

## 4. Phase 1 Scope

### A. Foundry SDK/API Client

Expected file:

```text
src/prototype5/foundry_sdk_client.py
```

Responsibilities:

- Connect to local Foundry endpoint.
- Submit prompt/messages.
- Record latency.
- Return raw model text.
- Handle timeout/failure.
- Expose a clean response object.

### B. Planner Backend Adapter

Expected files may include:

```text
src/prototype5/planner_backends.py
src/prototype5/planner.py
configs/prototype5/sdk_backend_config.json
```

Supported backends:

```text
mock
replay
cli
sdk
```

Minimum required for this phase:

```text
sdk
cli compatibility retained
mock/replay tests still pass
```

### C. Evidence Logging

SDK runs must generate evidence artefacts comparable to existing CLI/live runs.

Expected output folder:

```text
results/prototype5/mode_sdk/
```

Suggested artefacts:

```text
sdk_run_raw.jsonl
sdk_run_validated.jsonl
sdk_run_summary.json
sdk_run_summary.md
sdk_latency_summary.csv
sdk_failure_cases.json
```

### D. Test Coverage

Add tests proving:

- SDK response object structure is valid.
- Timeout/failure is handled fail-closed.
- SDK output passes into the existing parser.
- Schema validation still runs.
- Safety validation still runs.
- Orchestrator still completes.
- CLI route remains available or safely deprecated behind config.

Expected test files:

```text
tests/prototype5/test_foundry_sdk_client.py
tests/prototype5/test_sdk_backend_adapter.py
tests/prototype5/test_sdk_pipeline_integration.py
tests/prototype5/test_sdk_evidence_outputs.py
```

### E. Documentation

Create an implementation note and audit record:

```text
docs/prototype5/phase1_sdk_migration_spec.md
docs/prototype5/phase1_sdk_migration_audit.md
docs/prototype5/phase1_sdk_migration_evidence_summary.md
docs/prototype5/phase1_sdk_migration_dissertation_wording.md
```

## 5. Out of Scope

These are blocked until Phase 1 is complete:

```text
Voice command interface
Whisper/Demotron integration
Mode F adversarial benchmark
Mode G policy complexity
Mode H clarification recovery
Mode I human-in-the-loop tiering
Mode J dashboard/app
New dissertation chapter writing
New research claims
New model comparison claims
```

Reason: adding voice before SDK stability creates a messy system where failures could come from the voice layer, transcription, SDK, prompt, model, validator, or evidence logger.

## 6. Architecture Target

### Current Likely Architecture

```text
Natural language command
        |
CLI model call
        |
Raw model output
        |
JSON parse
        |
Schema validation
        |
Semantic validation
        |
Safety validation
        |
Execution eligibility decision
        |
Evidence logs
```

### Target Architecture

```text
Natural language command
        |
Planner backend interface
        |
Backend selected by config
        |-- mock
        |-- replay
        |-- cli
        `-- sdk/api
                |
Raw model output
        |
Existing zero-trust validation pipeline
        |
Evidence logs
```

The only thing Phase 1 changes is the model invocation layer. Everything after raw model output should remain structurally consistent.

## 7. Required Interface Contract

Create a common model response object:

```python
from dataclasses import dataclass


@dataclass
class ModelBackendResponse:
    backend: str
    model_alias: str
    prompt_id: str
    raw_text: str | None
    success: bool
    latency_ms: float | None
    error_type: str | None
    error_message: str | None
    timestamp_utc: str
```

Minimum accepted fields:

```text
backend
model_alias
raw_text
success
latency_ms
error_type
timestamp_utc
```

The pipeline must not deal with arbitrary SDK response formats directly. The SDK client normalizes everything into this internal contract.

## 8. Milestones

### Milestone 1 - Baseline Freeze

Objective: record the current state before touching SDK code.

Commands:

```powershell
cd C:\Users\reach\Microsoft-IXN-Prototype5
.\.venv\Scripts\Activate.ps1
git status --short
python -m pytest tests\prototype5 -v
python -m src.prototype5.run_orchestrator
```

Evidence to save:

```text
results/prototype5/phase1_baseline_test_output.txt
results/prototype5/phase1_baseline_orchestrator_output.txt
```

Audit gate:

- Tests pass.
- Orchestrator completes.
- Git status is understood.
- Unrelated dissertation draft remains untouched.
- Evidence state is clear.

### Milestone 2 - SDK/API Discovery Spike

Objective: determine exactly how Foundry Local should be called programmatically.

Create:

```text
docs/prototype5/phase1_sdk_discovery_notes.md
scripts/prototype5/spike_foundry_sdk_call.py
```

The notes must answer:

```text
What SDK/API endpoint is being used?
What request format is required?
What response format is returned?
Does it support streaming?
Does it support non-streaming?
How is the model alias selected?
How are timeouts handled?
How are errors returned?
What is the minimum viable integration?
```

Audit gate: do not integrate until one standalone SDK/API call works outside the main pipeline.

### Milestone 3 - Implement SDK Client

Objective: create the clean SDK/API client.

Expected file:

```text
src/prototype5/foundry_sdk_client.py
```

Minimum behaviour:

```text
model alias
base URL / endpoint
timeout seconds
prompt/messages
non-streaming response
latency measurement
error handling
structured return object
```

Required failure handling:

```text
success = false
raw_text = null
error_type = meaningful category
error_message = bounded diagnostic
```

Suggested error categories:

```text
connection_error
timeout
http_error
empty_response
malformed_response
sdk_exception
unknown_error
```

Audit gate:

```powershell
python -m pytest tests\prototype5\test_foundry_sdk_client.py -v
```

### Milestone 4 - Add Backend Adapter

Objective: connect the SDK client to Prototype 5 through a backend abstraction.

Expected design:

```python
class PlannerBackend(Protocol):
    def generate(self, command: str, context: dict) -> ModelBackendResponse:
        ...
```

Backends:

```text
CLIBackend
SDKBackend
ReplayBackend
MockBackend
```

The validator should receive only raw text and metadata. It should not know whether the output came from CLI or SDK.

Audit gate:

```powershell
python -m pytest tests\prototype5\test_sdk_backend_adapter.py -v
```

### Milestone 5 - Pipeline Integration

Objective: run SDK-generated responses through the existing zero-trust pipeline.

Required flow:

```text
command
-> SDK backend
-> raw model output
-> parse
-> schema validation
-> semantic validation
-> safety validation
-> execution eligibility
-> evidence output
```

Minimum 5-command smoke set:

```text
1. Clear safe pick-and-place command
2. Clear safe stop command
3. Ambiguous "move it there" command
4. Unsafe human-proximity command
5. Unsupported action command
```

Evidence must include:

```text
raw response
parse result
schema result
semantic result
safety result
execution eligibility
failure mode
latency
```

### Milestone 6 - 30-Command SDK Evaluation

Objective: run the existing Prototype 5 benchmark through the SDK backend.

Required output:

```text
results/prototype5/mode_sdk/sdk_30_command_results.jsonl
results/prototype5/mode_sdk/sdk_30_command_summary.json
results/prototype5/mode_sdk/sdk_30_command_summary.md
```

Required metrics:

```text
request_success_rate
parse_success_rate
json_valid_rate
schema_valid_rate
semantic_valid_rate
safety_valid_rate
execution_eligible_rate
pipeline_false_accept_count
mean_latency_ms
median_latency_ms
max_latency_ms
timeout_count
failure_mode_distribution
```

### Milestone 7 - Orchestrator Integration

Expected change:

```text
src/prototype5/run_orchestrator.py
```

The orchestrator should report:

```text
SDK mode present / absent
SDK benchmark status
SDK request success rate
SDK execution eligibility rate
SDK false accepts
SDK latency summary
```

Audit gate:

```powershell
python -m src.prototype5.run_orchestrator
```

Expected:

```text
Prototype 5 Final Evidence Orchestrator: COMPLETE
SDK migration evidence: PRESENT
```

SDK failure must not corrupt older evidence summaries.

### Milestone 8 - Regression Test Full Suite

Commands:

```powershell
python -m pytest tests\prototype5 -v
python -m compileall -q src scripts
python -m src.prototype5.run_orchestrator
```

Pass conditions:

```text
All Prototype 5 tests pass
Compile check passes
Orchestrator complete
SDK evidence present
Existing evidence not overwritten incorrectly
No unrelated dissertation files staged
```

### Milestone 9 - Documentation Pack

Required docs:

```text
docs/prototype5/phase1_sdk_migration_spec.md
docs/prototype5/phase1_sdk_migration_audit.md
docs/prototype5/phase1_sdk_migration_evidence_summary.md
docs/prototype5/phase1_sdk_migration_dissertation_wording.md
```

`phase1_sdk_migration_audit.md` should include:

```text
What changed
What did not change
Tests run
Evidence generated
Known limitations
Risks carried forward
Decision: pass / conditional pass / fail
```

`phase1_sdk_migration_evidence_summary.md` should include:

```text
Run date
Model alias
Endpoint/runtime
Benchmark size
Request success
JSON/schema/semantic/safety metrics
Execution eligibility
False accepts
Latency
Failure modes
```

`phase1_sdk_migration_dissertation_wording.md` should include cautious wording:

> Phase 1 migrated Prototype 5 from a CLI-mediated local model invocation route to an SDK/API-backed planner interface. This improved the engineering structure of the local inference layer while preserving the dissertation's central zero-trust design: model outputs continued to be treated as untrusted proposals and were passed through deterministic validation before execution eligibility was assigned.

## 9. Definition of Done

Phase 1 is complete only when all of this is true:

```text
[ ] SDK/API client implemented
[ ] Backend adapter implemented
[ ] Existing CLI/replay/mock path not broken
[ ] SDK path runs at least 5-command smoke test
[ ] SDK path runs existing 30-command benchmark
[ ] Evidence artefacts generated
[ ] Orchestrator detects SDK evidence
[ ] Full Prototype 5 test suite passes
[ ] Compile check passes
[ ] Documentation pack created
[ ] Audit file written
[ ] Git commit created
[ ] No unrelated dissertation draft changes staged
```

## 10. Exit Metrics

| Metric | Minimum Target | Notes |
| --- | ---: | --- |
| SDK request success | >= 80% | For local runtime; failures must be explained |
| Pipeline crash rate | 0% | Failures must be logged, not crash |
| Pipeline false accepts | 0 | Non-negotiable under deterministic gate |
| Evidence completeness | 100% for completed cases | Every case needs trace |
| Full test suite | Pass | Required |
| Orchestrator | COMPLETE | Required |
| Existing evidence regression | 0 known regressions | Required |

The model itself does not need to perform better than CLI. The phase is about integration reliability and evidence discipline.

## 11. Risk Register

| Risk | Severity | Mitigation |
| --- | ---: | --- |
| SDK/API response format differs from CLI | High | Normalize via `ModelBackendResponse` |
| Streaming response complicates parsing | Medium | Use non-streaming first |
| Foundry endpoint/model alias changes | High | Config-driven endpoint/model |
| SDK migration breaks existing tests | High | Adapter pattern and full regression |
| Latency worsens unexpectedly | Medium | Log but do not overclaim |
| Evidence schema diverges from older modes | High | Maintain common evidence fields |
| Phase expands into voice too early | High | Explicitly block Phase 2 until exit criteria met |
| Dissertation claims become inflated | High | Use bounded wording only |

## 12. Commit Strategy

Use small commits.

### Commit 1 - Spec Only

```powershell
git add docs/prototype5/phase1_sdk_migration_spec.md
git commit -m "Add Phase 1 SDK migration baseline spec"
```

### Commit 2 - SDK Discovery

```powershell
git add scripts/prototype5/spike_foundry_sdk_call.py docs/prototype5/phase1_sdk_discovery_notes.md
git commit -m "Add Foundry SDK discovery spike"
```

### Commit 3 - SDK Client

```powershell
git add src/prototype5/foundry_sdk_client.py tests/prototype5/test_foundry_sdk_client.py
git commit -m "Add Foundry SDK client"
```

### Commit 4 - Backend Adapter

```powershell
git add src/prototype5/planner_backends.py tests/prototype5/test_sdk_backend_adapter.py
git commit -m "Add SDK planner backend adapter"
```

### Commit 5 - Pipeline/Evidence Integration

```powershell
git add scripts/prototype5/run_sdk_benchmark.py results/prototype5/mode_sdk tests/prototype5/test_sdk_pipeline_integration.py
git commit -m "Add SDK pipeline benchmark evidence"
```

### Commit 6 - Orchestrator/Docs

```powershell
git add src/prototype5/run_orchestrator.py docs/prototype5/phase1_sdk_migration_*.md tests/prototype5
git commit -m "Integrate SDK evidence into Prototype 5 orchestrator"
```

## 13. Senior Audit

Phase 1 fails if:

- SDK code is hard-coded into the orchestrator.
- Existing tests are skipped.
- Old evidence gets overwritten.
- The SDK path produces output but bypasses validation.
- Failures crash the pipeline instead of being logged.
- Performance improvement is claimed without measurement.
- Voice starts before SDK is validated.
- A demo exists without evidence artefacts.
- The team cannot explain exactly what changed and what stayed the same.

Phase 1 passes if:

- The architecture is cleaner.
- The validator remains unchanged or minimally touched.
- SDK output flows through the same zero-trust gates.
- Evidence is comparable to previous modes.
- Tests prove no regression.
- The orchestrator reports SDK evidence.
- The documentation makes the claim defensible.

## 14. Final Phase 1 Decision

Start with Milestone 1 and Milestone 2 only. Do not code the full adapter until the SDK/API discovery spike proves the correct call format.

Immediate working order:

```text
1. Freeze current Prototype 5 baseline
2. Create Phase 1 spec document
3. Run SDK/API discovery spike
4. Implement SDK client
5. Add backend adapter
6. Run smoke pipeline
7. Run 30-command SDK benchmark
8. Integrate into orchestrator
9. Full audit and commit
10. Only then begin Phase 2 voice control
```

The sprint framing is controlled migration, measurable gates, no scope creep, evidence-first implementation, and no new claims without reproducible artefacts.
