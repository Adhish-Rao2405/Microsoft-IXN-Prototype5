# Prototype 5 Mode E.2 Live Evaluation Summary

## Purpose

Mode E.2 runs the Mode E industrial benchmark through a live local Foundry model only after the Mode E.1 deterministic policy context is complete. Its purpose is to test whether the schema-valid versus execution-eligible gap remains observable under the expanded industrial benchmark.

The Mode E.2 result is evidence under a curated industrial benchmark and deterministic policy context, not proof of general industrial deployment readiness.

## Precondition From E.1

Mode E.2 is gated by `results/prototype5/mode_e/mode_e_policy_audit.json`. The live runner fails closed unless the E.1 audit status is `COMPLETE_POLICY_CONTEXT`.

## Live Evaluation Setup

The runner loads:

- `configs/prototype5/mode_e_industrial_benchmark.json`
- `configs/prototype5/mode_e_industrial_vocabulary.json`
- `configs/prototype5/mode_e_industrial_policy_rules.json`
- `configs/prototype5/action_envelope_prompt.txt`

The runner fixes model temperature at `0.0`, records raw model responses, applies deterministic validation decisions, and reports latency from the measured local requests.

## Model And Runtime Used

The model alias and base URL are recorded in the generated Mode E.2 summary. If Foundry Local is unavailable, the run is classified as `NOT_RUN_FOUNDRY_UNAVAILABLE` rather than failure evidence.

## Metrics

The generated summary reports request success, parse success, JSON validity, schema validity, semantic validity, safety validity, execution eligibility, false accepts, schema-valid minus execution-eligible gap, latency, difficulty distribution, scenario-family distribution and policy-decision distribution.

## Comparison With E0.4

The summary compares descriptively against the retained E0.4 values:

- schema-valid rate: `0.8667`
- execution-eligible rate: `0.1`
- schema-valid minus execution-eligible gap: `0.7667`
- pipeline false accepts: `0`
- mean latency: approximately `25377.18 ms`

E0.4 and E.2 are different benchmark conditions, so differences are descriptive rather than statistically conclusive.

## What The Result Supports

When live outputs are present, Mode E.2 supports a bounded claim that the schema-valid versus execution-eligible gap was evaluated on the curated Mode E industrial benchmark under the E.1 deterministic policy context.

## What The Result Does Not Support

Mode E.2 does not prove production robot safety, real industrial deployment readiness, universal model reliability, certified safety compliance or generalisation beyond the tested benchmark, model alias, runtime and machine setup.
