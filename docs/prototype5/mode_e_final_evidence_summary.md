# Mode E Final Evidence Summary

## Mode E Purpose

Mode E was added to address benchmark representativeness without creating another prototype or new robot-control capability. It extends the dissertation evidence base beyond the original 30-command benchmark and asks whether the schema-valid versus execution-eligible gap remains visible under a curated industrial benchmark.

## Mode E Benchmark Design

The Mode E benchmark adds 30 industrially motivated commands across six scenario families:

- pick-and-place
- conveyor sorting
- inspection and quality control
- warehouse transfer
- human proximity
- restricted-zone movement

The benchmark is balanced across 10 clear commands, 10 ambiguous commands and 10 unsafe or execution-invalid commands. The benchmark audit status is `COMPLETE_BALANCED_EXTENSION`.

## Mode E.1 Policy Context

Mode E.1 introduced a deterministic industrial vocabulary and policy context before live evaluation. This prevented industrial terms such as conveyor, fixture, restricted zone, human work area, tote, inspection station and clearance from being evaluated as undefined language.

The Mode E.1 policy audit status is `COMPLETE_POLICY_CONTEXT`. The policy layer is a deterministic policy context for benchmark validation, not a certified safety system.

## Mode E.2 Live Evaluation Setup

Mode E.2 ran the 30 Mode E commands through the local Foundry Phi-3-mini model using the repository action-envelope prompt and the E.1 deterministic validation context. The live runner recorded raw model responses, deterministic validation decisions and latency. Temperature was fixed at `0.0`.

The tested model alias was `Phi-3-mini-4k-instruct-generic-cpu:3` on one local Foundry runtime and machine. This is single local model evidence, not a cross-model study.

## Final E.2 Metrics

| Metric | Value |
|---|---:|
| request_success_rate | 1.0 |
| parse_success_rate | 0.7667 |
| json_valid_rate | 0.7667 |
| schema_valid_rate | 0.6333 |
| semantic_valid_rate | 0.7667 |
| safety_valid_rate | 0.6667 |
| execution_eligible_rate | 0.1 |
| model_false_accepts | 16 |
| pipeline_false_accepts | 0 |
| schema_valid_minus_execution_eligible_gap | 0.5333 |
| mean_latency_ms | 28359.26 |
| median_latency_ms | 22588.65 |
| max_latency_ms | 66928.25 |

## Descriptive Comparison With E0.4

E0.4 measured the original repo-local 30-command benchmark under repeated full-pipeline live evaluation. Mode E.2 uses a different industrial benchmark condition, so the comparison is descriptive rather than statistically conclusive.

E0.4 reported schema validity of `0.8667`, execution eligibility of `0.1`, a schema-valid minus execution-eligible gap of `0.7667`, zero pipeline false accepts and mean latency of approximately `25377.18 ms`.

Mode E.2 reported schema validity of `0.6333`, execution eligibility of `0.1`, a schema-valid minus execution-eligible gap of `0.5333`, zero pipeline false accepts and mean latency of `28359.26 ms`.

## What This Proves

Mode E proves that a balanced industrial benchmark extension exists and is auditable. Mode E.1 proves that the curated industrial vocabulary and deterministic policy context cover the benchmark. Mode E.2 proves under the tested conditions that the schema-valid versus execution-eligible gap persisted on live local Foundry outputs and that the deterministic pipeline produced zero pipeline false accepts.

## What This Does Not Prove

Mode E.2 provides bounded live evidence under a curated industrial benchmark and deterministic policy context. It does not prove general industrial deployment readiness, production robot safety, or general local SLM reliability.

It also does not prove real-time robot control suitability. Mean latency was 28.36s and maximum latency was 66.93s, which makes CPU-only local inference unsuitable for low-latency closed-loop control in this tested setup.

## Dissertation Significance

Mode E strengthens the dissertation's central claim that schema validity is insufficient for execution eligibility. The industrial benchmark made the evaluation less dependent on the original small command set, while E.1 ensured the industrial terms had explicit validation meaning. E.2 then showed that even when many outputs were parseable, JSON-valid or schema-valid, only 10% were execution-eligible after deterministic validation.

The credible deployment frame is supervisory, offline or local-first task proposal generation with deterministic zero-trust validation, not autonomous production robot execution.
