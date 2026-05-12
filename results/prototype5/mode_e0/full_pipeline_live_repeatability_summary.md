# Mode E0.4 Repo-Local Full Pipeline Repeatability Adapter

- Status: COMPLETE_FULL_LIVE_PIPELINE_REPEATABILITY
- Runs evaluated: 3/3
- Benchmark: `configs/prototype5/benchmark_v1.json`
- Prompt: `configs/prototype5/action_envelope_prompt.txt`
- Runs CSV: `results/prototype5/mode_e0/full_pipeline_live_repeatability_runs.csv`

## Per-Run Metrics

| Run | Request | JSON | Schema | Semantic | Safety | Execution eligible | Model false accepts | Pipeline false accepts | Gap | Mean latency ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| e0_4_full_pipeline_run_01_20260512T094618Z | 1.0 | 0.8667 | 0.8667 | 0.2 | 0.1 | 0.1 | 16 | 0 | 0.7667 | 26434.28 |
| e0_4_full_pipeline_run_02 | 1.0 | 0.8667 | 0.8667 | 0.2 | 0.1 | 0.1 | 16 | 0 | 0.7667 | 25676.98 |
| e0_4_full_pipeline_run_03 | 1.0 | 0.8667 | 0.8667 | 0.2 | 0.1 | 0.1 | 16 | 0 | 0.7667 | 24020.29 |

## Central Finding Stability

- Schema-valid greater than execution-eligible: STABLE_OBSERVED
- Pipeline false accepts bounded: STABLE_ZERO

## Boundary

E0.4 measures full live pipeline repeatability only for the repo-local 30-command benchmark, action-envelope prompt, selected Foundry Local model and deterministic validation policy. It does not change locked Prototype 3/4 evidence and does not prove real-world robot safety or general model reliability.
