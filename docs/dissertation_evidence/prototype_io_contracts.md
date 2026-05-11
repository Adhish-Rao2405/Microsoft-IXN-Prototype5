# Prototype Input/Output Contracts

This document defines the role, inputs, outputs and downstream consumers for each prototype in the dissertation sequence.

## Prototype 1 - Local Model-to-Action Feasibility

### Purpose
Establish whether a local model can produce action-like task-planning outputs.

### Inputs
- User task command.
- Local model prompt.
- Foundry/local model interface.

### Outputs
- Initial action-like model response.
- Feasibility notes.
- Early model-to-action behaviour evidence.

### Downstream Consumer
Prototype 2 uses this feasibility result to justify adding deterministic validation.

## Prototype 2 / 2.1 - Deterministic Zero-Trust Safety Architecture

### Purpose
Introduce deterministic schema validation, safety gating and reject-before-execution logic.

### Inputs
- Candidate model action.
- Formal action schema.
- Safety rules.
- Validation tests.

### Outputs
- Schema validation result.
- Safety validation result.
- Execution eligibility decision.
- Unit test evidence.

### Downstream Consumer
Prototype 3 uses the validation structure to evaluate model outputs against a benchmark.

## Prototype 3 - Benchmark and Local Model Evaluation

### Purpose
Evaluate local model outputs using a fixed 30-command benchmark.

### Inputs
- 30-command benchmark dataset.
- Foundry Local model alias.
- Prompt template.
- Parser/recovery logic.
- Schema/safety validation pipeline.

### Outputs
- Per-command response logs.
- Request success.
- Parse success.
- JSON validity.
- Schema/action validity.
- Safety-gate outcome.
- Summary CSV/JSON results.

### Downstream Consumer
Prototype 4 consumes Prototype 3 evidence for execution-grounded safety and latency analysis. Prototype 5 consumes Prototype 3 evidence for final orchestration.

## Prototype 4 - Safety-Latency Frontier

### Purpose
Evaluate the safety and latency implications of deterministic validation.

### Inputs
- Prototype 3 evidence outputs.
- Deterministic validation rules.
- Adversarial/unsafe cases.
- Execution eligibility evaluator.

### Outputs
- False-accept comparison.
- Safety-latency frontier.
- Extension evidence.
- Safety validation summaries.

### Downstream Consumer
Prototype 5 consumes Prototype 4 results for final claims and brief-closure evidence.

## Prototype 5 - Final Evidence Orchestration and Brief Closure

### Purpose
Consolidate all prior evidence and close the Microsoft IXN brief requirements.

### Inputs
- Prototype 3 model evidence.
- Prototype 4 safety evidence.
- Mode B custom precision/Phi evidence.
- Mode C local-vs-cloud evidence.
- Mode D live Foundry Local profiling evidence.

### Outputs
- `results/prototype5/final_evidence_manifest.json`
- `results/prototype5/final_claims_matrix.csv`
- `results/prototype5/final_dissertation_metrics.md`
- Mode B quantisation/Phi evidence.
- Mode C local-vs-cloud comparison.
- Mode D live resource profile.
