# Lee Progress Update - Prototype 5, E0.4 and Mode E

## Project framing

**Working title:**  
Schema Validity Is Not Enough: Zero-Trust Evaluation of Local SLMs for Industrial Robot Task Planning with Microsoft Foundry Local

## Core argument

Local SLM outputs should be treated as **untrusted task proposals**, not executable robot commands.

The project evaluates whether deterministic validation can narrow model outputs from:

```text
schema-valid proposals
```

to:

```text
execution-eligible proposals
```

under a defined benchmark and validation policy.

The work does **not** claim:

- production robot safety
- certified industrial deployment readiness
- real robot validation
- universal local SLM reliability
- low-latency closed-loop robot control

## What changed since the last feedback

The main work since the previous feedback has focused on:

1. repeatability and reproducibility;
2. benchmark representativeness;
3. industrial relevance;
4. claim-to-evidence traceability;
5. bounded dissertation framing.

No new uncontrolled prototype direction was started. Prototype 5 remains the final evidence orchestration and reporting layer.

## 1. E0.4 - full live pipeline repeatability

### Purpose

E0.4 was added to address the question of whether the core result is stable across repeated runs.

### Setup

- fixed benchmark
- fixed prompt/action-envelope setup
- fixed local model alias
- fixed deterministic validation policy
- three full live pipeline runs

### Key result

| Metric | Result |
|---|---:|
| Runs evaluated | 3/3 |
| Request success rate | 1.0 |
| Parse / JSON / schema-valid rate | 0.8667 |
| Semantic-valid rate | 0.2 |
| Safety-valid rate | 0.1 |
| Execution-eligible rate | 0.1 |
| Model false accepts | 16 |
| Pipeline false accepts | 0 |
| Schema-valid minus execution-eligible gap | 0.7667 |
| Overall mean latency | 25377.18 ms |
| Latency standard deviation | 1234.60 ms |

### Interpretation

E0.4 supports the claim that the schema-valid versus execution-eligible gap and zero pipeline false-accept result are stable under the tested fixed configuration.

### Boundary

This is repeatability evidence under fixed benchmark/model/runtime conditions. It does not prove universal local SLM stability.

## 2. Mode E - industrial benchmark extension

### Purpose

Mode E was added to strengthen benchmark representativeness and industrial relevance.

The original benchmark was useful for controlled evaluation, but it needed a broader industrial extension to address whether the central finding persisted outside the original command phrasing.

### Benchmark composition

| Category | Count |
|---|---:|
| Clear commands | 10 |
| Ambiguous commands | 10 |
| Unsafe/invalid commands | 10 |
| Total | 30 |

### Scenario families

1. pick_and_place
2. conveyor_sorting
3. inspection_quality
4. warehouse_transfer
5. human_proximity
6. restricted_zone

### Interpretation

Mode E improves benchmark coverage and industrial relevance, but remains a curated benchmark. It is not claimed to be universally representative of all industrial robot instructions.

## 3. Mode E.1 - deterministic industrial vocabulary and policy context

### Purpose

Mode E.1 makes the industrial benchmark reproducible by adding deterministic vocabulary and policy context.

Without this, Mode E would only be a set of prompts. With E.1, each case has clearer validation assumptions.

### Key result

| Item | Result |
|---|---:|
| Coverage | 30/30 |
| Status | COMPLETE_POLICY_CONTEXT |

### Interpretation

Mode E.1 supports deterministic evaluation of Mode E.

### Boundary

This is a benchmark-validation context, not a certified industrial robot safety policy.

## 4. Mode E.2 - full live Foundry Local industrial evaluation

### Purpose

Mode E.2 evaluates the local model live against the full Mode E industrial benchmark.

### Setup

| Item | Value |
|---|---|
| Runtime | Microsoft Foundry Local |
| Model | Phi-3-mini-4k-instruct-generic-cpu:3 |
| Endpoint | http://127.0.0.1:49313 |
| Benchmark | 30 Mode E industrial cases |
| Policy context | Mode E.1 deterministic policy context |
| Temperature | 0.0 |

### Final metrics

| Metric | Value |
|---|---:|
| Total cases | 30 |
| Request success rate | 1.0 |
| Parse success rate | 0.7667 |
| JSON-valid rate | 0.7667 |
| Schema-valid rate | 0.6333 |
| Semantic-valid rate | 0.7667 |
| Safety-valid rate | 0.6667 |
| Execution-eligible rate | 0.1 |
| Model false accepts | 16 |
| Pipeline false accepts | 0 |
| Schema-valid minus execution-eligible gap | 0.5333 |
| Mean latency | 28359.26 ms |
| Median latency | 22588.65 ms |
| Maximum latency | 66928.25 ms |

### Interpretation

Mode E.2 supports the claim that the schema-valid versus execution-eligible gap persists under a curated industrial benchmark and deterministic policy context.

### Boundary

This is bounded to:

- the curated Mode E benchmark;
- the selected Phi-3-mini local model alias;
- the Foundry Local runtime;
- the local machine context;
- the deterministic Mode E.1 validation policy.

It does not prove production safety or universal industrial generalisation.

## Claim-to-evidence additions

| Claim ID | Claim | Status | Boundary |
|---|---|---|---|
| C15 | A balanced industrial benchmark extension was created. | PROVEN | Benchmark design/audit only. |
| C16 | Deterministic industrial vocabulary and policy context were created. | PROVEN | Curated Mode E policy context only. |
| C17 | Live local Foundry evaluation preserved the schema-valid vs execution-eligible gap and produced zero pipeline false accepts. | PROVEN | Tested benchmark/model/runtime only. |

## Current project status

Prototype 5 now provides:

- final evidence orchestration;
- claims matrix;
- reproducibility documentation;
- E0.4 repeatability evidence;
- Mode E industrial benchmark extension;
- Mode E.1 deterministic policy context;
- Mode E.2 live industrial benchmark evaluation;
- local-vs-cloud comparison;
- resource profiling;
- final dissertation evidence dashboard.

## Next technical step

The next technical step is a final reproducibility/runbook audit.

Goal:

> make it easy for someone else to clone the repo, run the verification commands, regenerate the final evidence pack and understand which live evidence is frozen.

No new modes or experiments are planned unless a specific evidence gap is identified.

