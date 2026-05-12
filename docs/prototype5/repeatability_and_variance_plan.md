# Repeatability And Variance Plan

## 1. Why Repeatability Matters

Repeatability matters because a single model run can be affected by generation variability, runtime conditions and local host load. Dissertation claims should distinguish stable deterministic pipeline behaviour from live model-output variability.

## 2. Deterministic Pipeline Components

The retained validation and reporting components are deterministic when given the same evidence files:

- fixed benchmark evidence
- fixed parser/validator outputs in retained files
- fixed claims matrix generation
- fixed final pack generator
- fixed Mode E0 traceability check

## 3. Variable Components

Variability may arise from:

- model generation
- Foundry Local runtime state
- host CPU/memory contention
- cloud API latency and provider conditions
- model catalogue or alias changes

## 4. Current Controls

Current controls include:

- fixed benchmark where available
- retained prompts/configs where available
- fixed validators
- temperature 0 where used by prior evidence or future live runs
- fixed model alias where available
- retained CSV/JSON/JSONL evidence for final reporting

## 5. Proposed Repeated-Run Protocol

Run the same 30-command benchmark three times using the same model alias and configuration. Each run should be written to a separate result folder and then summarised into a single repeatability table.

## 6. Metrics To Compare

- request success count/rate
- parse success count/rate
- JSON-valid count/rate
- schema-valid count/rate
- semantic-valid count/rate where available
- safety-valid count/rate where available
- execution-eligible count/rate
- model-level false accepts
- pipeline-level false accepts
- mean latency
- latency standard deviation

## 7. Latency Variance Considerations

Latency should be interpreted cautiously because local host load, model warm-up, service state and cloud provider conditions can affect timing. Report mean and standard deviation rather than only one latency number.

## 8. Interpretation Boundaries

If live repeated runs are not immediately possible, the project should preserve a planned repeatability protocol rather than inventing variance values. The current `repeatability_summary.csv` is therefore marked `PLANNED` until repeated-run evidence exists.
