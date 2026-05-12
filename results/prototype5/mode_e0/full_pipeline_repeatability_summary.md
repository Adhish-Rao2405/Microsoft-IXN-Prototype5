# Mode E0.3 Full Live Pipeline Repeatability Under Prototype 3 Prompt

- Status: E0_3_NOT_RUN
- Reason: Prototype 5 does not currently contain a repo-local callable live runner that combines the original Prototype 3 action-envelope prompt, fixed 30-command benchmark and deterministic validation pipeline.

## Missing Repo-Local Integration Points

- `src/prototype5/full_pipeline_live_runner.py`
- `src/prototype5/prototype3_action_envelope_runner.py`
- `configs/prototype5/prototype3_action_envelope_prompt.md`

## External Prototype 3 Hints Detected

- `C:\Users\reach\Microsoft-IXN-Prototype3\prototype3\src\eval\run_benchmark.py`: True
- `C:\Users\reach\Microsoft-IXN-Prototype3\prototype3\src\brain\foundry_planner.py`: True
- `C:\Users\reach\Microsoft-IXN-Prototype3\prototype3\datasets\benchmark_v1.json`: True

## Required Command Interface

`python scripts/prototype5/run_full_pipeline_repeatability_live.py --live --runs 3 --base-url <FOUNDRY_LOCAL_BASE_URL> --model <MODEL_ALIAS> --benchmark <repo-local benchmark_v1.json> --prompt <repo-local Prototype 3 action-envelope prompt>`

## Required Runner Contract

- Use the original Prototype 3 action-envelope prompt/config.
- Run the same fixed 30-command benchmark three times.
- Call Foundry Local with temperature 0 and a fixed model alias/config.
- For each response, parse JSON, validate schema, score semantic validity, apply uncertainty handling, apply safety validation and decide execution eligibility.
- Write per-run metrics for schema_valid_rate, semantic_valid_rate, safety_valid_rate, execution_eligible_rate, model_false_accepts, pipeline_false_accepts and latency.

## Claim Boundary

Schema-valid versus execution-eligible repeatability is not proven by E0.3 because the full action-envelope live runner is not available inside Prototype 5 yet.
