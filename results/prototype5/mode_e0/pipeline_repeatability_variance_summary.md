# Mode E0.2 Full Validation Pipeline Repeatability Replay

- Status: COMPLETE_PIPELINE_REPLAY_ON_MINIMAL_PROMPT_OUTPUTS
- Runs evaluated: 3
- Commands per run: 30
- Records file: `results/prototype5/mode_e0/pipeline_repeatability_records.jsonl`
- Summary CSV: `results/prototype5/mode_e0/pipeline_repeatability_summary.csv`

## Per-Run Summary

| Run | Schema valid | Semantic valid | Safety valid | Execution eligible | Model false accepts | Pipeline false accepts |
|---|---:|---:|---:|---:|---:|---:|
| e0_1_live_run_01_20260512T015715Z | 0.0 | 0.5667 | 0.0 | 0.0 | 0 | 0 |
| e0_1_live_run_02_20260512T020120Z | 0.0 | 0.5667 | 0.0 | 0.0 | 0 | 0 |
| e0_1_live_run_03_20260512T020509Z | 0.0 | 0.5667 | 0.0 | 0.0 | 0 | 0 |

## Central Finding Stability

- Schema-valid greater than execution-eligible: NOT_OBSERVED
- Pipeline false accepts bounded: STABLE_ZERO

## Caveat

The E0.1 live prompt requested a minimal JSON action object, not necessarily the full Prototype 3 actions envelope. Low schema-valid rates in this replay therefore measure compatibility with the full pipeline contract, not a change to locked Prototype 3 metrics.

E0.2 is an offline deterministic replay over E0.1 live outputs. It does not replace the locked Prototype 3/4 benchmark evidence and does not prove real-world robot safety.
