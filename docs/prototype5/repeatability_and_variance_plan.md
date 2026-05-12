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

## 9. Mode E0.1 Live Repeatability Status

Mode E0.1 adds explicit repeatability artefacts so that repeatability is not only a prose plan:

- `results/prototype5/mode_e0/repeatability_live_runs.csv`
- `results/prototype5/mode_e0/repeatability_variance_summary.json`
- `results/prototype5/mode_e0/repeatability_variance_summary.md`
- `results/prototype5/mode_e0/repeatability_summary.csv`

The intended minimum is three repeated runs of the same 30-command benchmark under the same local model alias, prompt, temperature/configuration, validation policy and host machine. Five runs would be preferable if time and local runtime availability allow it.

In the current checked repository state, live repeatability is recorded from `repeatability_live_runs.csv` if repeated-run rows are available. If live rows are absent, the output is marked `NOT_RUN`. This is deliberate. The project should not infer variance from a single evidence run, and it should not claim that the central schema-valid versus execution-eligible finding is stable across repeated live runs unless those repeated live metrics exist.

## 10. Stability Claims After E0.1

The central stability checks are:

- whether `schema_valid_rate` remains greater than `execution_eligible_rate` across repeated runs
- whether `pipeline_false_accepts` remains zero or bounded under the same deterministic validation policy
- whether latency varies substantially across repeated runs

If repeated live rows are unavailable, these checks are marked `NOT_EVALUATED`. This does not weaken the existing single-run evidence pack; it simply keeps repeatability claims separate from the already validated evidence baseline.

The current Mode E0.1 live runner measures request success, parse success, JSON validity and latency across repeated local Foundry calls. It does not re-run the full schema, semantic, safety or execution-eligibility gates. Therefore, even when live request/JSON repeatability is `COMPLETE_LIVE_OUTPUT_REPEATABILITY`, the central schema-valid versus execution-eligible stability check remains `NOT_EVALUATED` until a full repeated validation run is recorded.

## 11. How To Refresh E0.1 Artefacts

Run:

```powershell
python scripts\prototype5\run_repeatability_analysis.py
python scripts\prototype5\run_reproducibility_check.py
```

These commands update the Mode E0.1 repeatability summaries from recorded repeatability rows. They do not start Foundry Local, run cloud calls or change locked metrics.

## 12. Future Live Protocol

When Foundry Local is available, live repeated output-level runs should be recorded as separate rows in `repeatability_live_runs.csv` with status `COMPLETE_LIVE_OUTPUT_REPEATABILITY` or `AVAILABLE`. Only then should the variance summary report means, standard deviations and stable/variable decisions for the output-level metrics.

## 13. Mode E0.2 Full Validation Replay

Mode E0.2 adds an offline deterministic replay over the three E0.1 raw JSONL files:

- `results/prototype5/mode_e0/pipeline_repeatability_records.jsonl`
- `results/prototype5/mode_e0/pipeline_repeatability_summary.csv`
- `results/prototype5/mode_e0/pipeline_repeatability_variance_summary.json`
- `results/prototype5/mode_e0/pipeline_repeatability_variance_summary.md`

This replay evaluates the recorded live outputs against Prototype 3-style schema, uncertainty, semantic, safety and pre-execution eligibility gates. It does not make new model calls and does not change locked Prototype 3 or Prototype 4 metrics.

Important boundary: the E0.1 live prompt requested a minimal JSON action object, whereas the full Prototype 3 schema expects an action-plan envelope or list compatible with the deterministic validator. Therefore, E0.2 is classified as `COMPLETE_PIPELINE_REPLAY_ON_MINIMAL_PROMPT_OUTPUTS` and is best read as a pipeline-compatibility and fail-closed repeatability replay over the recorded E0.1 outputs, not as a replacement for the original Prototype 3 benchmark evidence.

## 14. Mode E0.3 Full Live Pipeline Status

Mode E0.3 is reserved for full live pipeline repeatability under the original Prototype 3 action-envelope prompt. It should only be marked complete if Prototype 5 can run the same fixed 30-command benchmark three times with:

- the original Prototype 3 action-envelope prompt/config
- a fixed Foundry Local model alias/configuration
- JSON parsing
- schema validation
- semantic scoring
- uncertainty handling
- deterministic safety validation
- execution-eligibility decisions
- model-level and pipeline-level false-accept metrics

In the current Prototype 5 repo, the original Prototype 3 prompt and benchmark runner are not available as a repo-local callable interface. Mode E0.3 is therefore recorded as `E0_3_NOT_RUN` rather than inferred from E0.1/E0.2. This prevents the dissertation from claiming schema-valid versus execution-eligible repeatability until the full live action-envelope path is actually executable and measured.

## 15. Mode E0.4 Repo-Local Full Pipeline Repeatability Adapter

Mode E0.4 adds the missing repo-local adapter rather than moving to a new benchmark mode. It stores the action-envelope prompt and fixed 30-command benchmark inside Prototype 5:

- `configs/prototype5/action_envelope_prompt.txt`
- `configs/prototype5/benchmark_v1.json`
- `scripts/prototype5/run_full_pipeline_repeatability.py`

When Foundry Local and the selected model are available, this script can run the same 30-command benchmark three times with the action-envelope prompt and then evaluate every live response through the deterministic validation pipeline. The resulting files are:

- `results/prototype5/mode_e0/full_pipeline_live_repeatability_runs.csv`
- `results/prototype5/mode_e0/full_pipeline_live_repeatability_summary.json`
- `results/prototype5/mode_e0/full_pipeline_live_repeatability_summary.md`

E0.4 should be interpreted only according to its recorded status:

- `COMPLETE_FULL_LIVE_PIPELINE_REPEATABILITY` means three complete live runs were measured through the repo-local action-envelope prompt and deterministic validator.
- `PARTIAL_FULL_LIVE_PIPELINE_REPEATABILITY` means at least one live full-pipeline run exists, but the minimum three-run target was not met.
- `E0_4_NOT_RUN` means the adapter exists but live execution was unavailable or not requested.

The key stability checks are `schema_valid_minus_execution_eligible_gap` and `pipeline_false_accepts`. The dissertation may only describe schema-valid versus execution-eligible repeatability as measured if E0.4 records complete live runs and the summary reports the central finding as observed. Even then, the claim remains bounded to the fixed benchmark, prompt, model/configuration and validation policy.

E0.4 is resume-safe. A long run can be completed one repeat slot at a time:

```powershell
python scripts\prototype5\run_full_pipeline_repeatability.py --live --run-id 2 --skip-existing
python scripts\prototype5\run_full_pipeline_repeatability.py --live --run-id 3 --skip-existing
python scripts\prototype5\run_full_pipeline_repeatability.py
```

Alternatively, resume all missing slots up to the three-run target:

```powershell
python scripts\prototype5\run_full_pipeline_repeatability.py --live --runs 3 --resume --skip-existing
```

The `--max-commands` option is for debugging only. If it is lower than the benchmark size, the run is marked `DEBUG_PARTIAL_RUN` and is not counted toward the three completed repeatability runs.
