# Mode E0.1 Live Repeatability and Variance Evidence

- Status: COMPLETE_LIVE_OUTPUT_REPEATABILITY
- Completed live repeated runs: 3/3
- Ideal run count: 5
- Live runs file: `results/prototype5/mode_e0/repeatability_live_runs.csv`
- Summary file: `results/prototype5/mode_e0/repeatability_summary.csv`
- Foundry Local discovery probe: unavailable

## Scope

This E0.1 repeatability check evaluates live Foundry Local request-level stability, JSON validity stability and latency variance across three repeated runs. It does not evaluate repeatability of the full deterministic validation pipeline, including schema validity, semantic validity, safety validity, execution eligibility, model-level false accepts or pipeline-level false accepts. Those metrics are handled separately by Mode E0.2 when raw live-output artefacts are available.

## Central Finding Stability

- Schema-valid greater than execution-eligible: NOT_EVALUATED
- Pipeline false accepts bounded: NOT_EVALUATED

## Metric Variance

| Metric | Values | Mean | Std | Stable? |
|---|---:|---:|---:|---|
| request_success_rate | 1.0, 1.0, 1.0 | 1.0 | 0.0 | STABLE |
| parse_success_rate | 0.7333, 0.7333, 0.7333 | 0.7333 | 0.0 | STABLE |
| json_valid_rate | 0.7333, 0.7333, 0.7333 | 0.7333 | 0.0 | STABLE |
| schema_valid_rate | not available | not available | not available | NOT_EVALUATED |
| semantic_valid_rate | not available | not available | not available | NOT_EVALUATED |
| safety_valid_rate | not available | not available | not available | NOT_EVALUATED |
| execution_eligible_rate | not available | not available | not available | NOT_EVALUATED |
| model_false_accepts | not available | not available | not available | NOT_EVALUATED |
| pipeline_false_accepts | not available | not available | not available | NOT_EVALUATED |
| mean_latency_ms | 8164.26, 7644.35, 8043.13 | 7950.58 | 272.0307 | STABLE |
| std_latency_ms | 2329.34, 1515.74, 1472.02 | 1772.3667 | 482.8481 | VARIABLE |

## E0.3 Full Live Pipeline Status

- Status: E0_3_NOT_RUN
- Claim boundary: Schema-valid versus execution-eligible repeatability is not proven by E0.3 because the full action-envelope live runner is not available inside Prototype 5 yet.

## Claim Boundary

E0.1 does not support full zero-trust pipeline repeatability or a general model-reliability claim. It supports only live Foundry output repeatability for request success, parse success, JSON validity and latency under the tested benchmark and configuration.

No repeatability metrics are inferred from single-run evidence. If live repeated runs are unavailable, this file records that limitation rather than fabricating stability values.
