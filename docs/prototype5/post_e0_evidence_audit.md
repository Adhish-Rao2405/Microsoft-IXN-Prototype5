# Post-E0 Evidence Audit

## Purpose

Mode E0 was added to harden Prototype 5 after supervisor feedback. Its role is not to create a new prototype or broaden the robot-control system. Its role is to make the existing evidence reproducible, repeatable, auditable and bounded.

## E0.1 Role

Mode E0.1 records live Foundry Local request-level repeatability. It covers request success, parse success, JSON validity and latency behaviour. It does not by itself prove full validation-pipeline repeatability.

## E0.2 Role

Mode E0.2 replays deterministic validation over earlier E0.1 raw outputs. It is useful as a compatibility and fail-closed check, but it is explicitly classified as replay over minimal-prompt outputs rather than full action-envelope repeatability.

## E0.4 Role

Mode E0.4 is the repo-local full live pipeline repeatability adapter. It uses the fixed 30-command benchmark, action-envelope prompt, local Phi-3-mini Foundry Local model and deterministic validation policy to repeat the full pipeline three times under the tested conditions.

## Final E0.4 Metrics

- `request_success_rate = 1.0`
- `schema_valid_rate = 0.8667`
- `semantic_valid_rate = 0.2`
- `safety_valid_rate = 0.1`
- `execution_eligible_rate = 0.1`
- `model_false_accepts = 16`
- `pipeline_false_accepts = 0`
- `schema_valid_minus_execution_eligible_gap = 0.7667`
- mean latency approximately 25.38s
- `schema-valid > execution-eligible = STABLE_OBSERVED`
- `pipeline false accepts = STABLE_ZERO`

Latency was not stable in the same way as the categorical validation metrics. The E0.4 summary reports mean latency variability across runs, which should be treated as a deployment concern rather than hidden.

## What Is Now Proven

- Under the tested conditions, the selected local model can produce action-envelope outputs with high schema validity on the fixed benchmark.
- Under the tested conditions, schema validity remains materially higher than execution eligibility across three full live runs.
- Under the tested conditions, deterministic validation prevented measured model-level false accepts from becoming pipeline-level false accepts.
- The repo now contains the benchmark, prompt, repeatability adapter, repeatability summaries and claim traceability needed to audit the E0 evidence.

## What Is Supported

- The local-first architecture is credible for privacy, data locality and offline-resilience discussion when local SLM output is treated as an untrusted proposal.
- The evaluation design supports a zero-trust argument for bounded robot task-planning proposals.
- The project has stronger examiner defensibility because claims are mapped to evidence files and limitations.

## What Remains Limited

- The benchmark is a fixed 30-command benchmark, not an exhaustive industrial command distribution.
- The full live repeatability result uses a single local model alias and one local runtime/machine context.
- The deterministic validation policy is handcrafted and limited.
- Semantic validity, safety validity and execution eligibility remain low despite high schema validity.
- Latency remains high for interactive industrial deployment.

## What Must Not Be Claimed

- Do not claim that the local SLM is safe for production robot execution.
- Do not claim that zero pipeline false accepts prove production robot safety.
- Do not claim statistical generalisation to all local SLMs or all industrial robot tasks.
- Do not claim local inference is universally better than cloud inference.
- Do not claim the benchmark is exhaustive.
- Do not claim E0.4 changes locked Prototype 3/4 evidence.
