# Local Qwen Coder Run Card

| Field | Value |
|---|---|
| Model / run name | Qwen2.5 Coder local CPU benchmark rows |
| Model alias if available | foundry:qwen2.5-coder-* |
| Local/cloud mode | Local |
| Serving layer | Foundry Local evidence from Prototype 3 |
| Benchmark used | LocalSLM-IndustrialRobot-ZT-Bench v0.1 / 30-command benchmark |
| Date/source file if available | `results/prototype5/final_model_comparison.csv` |
| Temperature / max tokens if available | not available in detected evidence |
| Hardware if available | CPU labels in model identifiers; detailed host hardware not available in detected evidence |

| Model | Commands | Schema-valid rate | Execution-eligible rate | Model-level false accepts | False-accept rate | Mean latency |
|---|---:|---:|---:|---:|---:|---:|
| foundry:qwen2.5-coder-0.5b:cpu | 30 | 83.33% | 13.33% | 12 | 40.00% | 2921.7 ms |
| foundry:qwen2.5-coder-1.5b:cpu | 30 | 93.33% | 16.67% | 15 | 50.00% | 8329.5 ms |

| Field | Value |
|---|---|
| Request success | not available in detected evidence |
| JSON-valid rate | not available in detected evidence |
| Pipeline-level false accepts | see Prototype 4 zero-trust comparison |
| Known failure modes | Schema-valid output can still fail execution eligibility; false accepts observed at model level. |
| Caveats | Covers detected Qwen Coder rows only; not a universal model-family result. |
