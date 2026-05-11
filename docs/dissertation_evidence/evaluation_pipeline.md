# Evaluation Pipeline

The evaluation pipeline is designed to prevent model response completion from being mistaken for task validity or execution safety.

## Pipeline Stages

1. Benchmark command selected.
2. Prompt generated.
3. Local or cloud model called.
4. Raw response captured.
5. JSON/action content recovered.
6. JSON validity checked.
7. Formal schema validation applied.
8. Semantic validity assessed where applicable.
9. Deterministic safety gate applied.
10. Execution eligibility determined.
11. Metrics written to result files.
12. Prototype 5 orchestrator consolidates evidence.

## Key Principle

A response can pass an earlier stage and fail a later stage. Therefore, the pipeline does not collapse all metrics into a single accuracy score.

## Metric Progression

`request_success` -> `parse_success` -> `json_valid` -> `schema_valid` -> `semantic_validity` -> `safety_result` -> `execution_validity`

## Evidence Outputs

- Prototype 3 produces local model benchmark evidence.
- Prototype 4 produces safety-latency and execution-grounded evidence.
- Prototype 5 consolidates final evidence through Modes A-D.

## Reproducibility Boundary

Prototype 5 can rerun its final orchestrator from retained evidence files. It does not need to rerun cloud calls or live Foundry Local profiling to regenerate final claims and summaries.
