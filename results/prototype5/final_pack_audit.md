# Prototype 5 Final Pack Audit

Audit date: 2026-05-11

## 1. Current Git Status

Current `git status --short` at audit time:

```text
 M results/prototype5/final_claims_matrix.csv
 M results/prototype5/final_dissertation_metrics.md
 M results/prototype5/final_evidence_manifest.json
```

These modified result files existed before the final-pack implementation phase. They appear to be generated evidence artefacts and must not be mixed into unrelated documentation commits unless deliberately regenerated and reviewed.

## 2. Existing Directory Tree Summary

Top-level directories detected:

| Directory | Role observed |
|---|---|
| `data/` | Local data inputs. |
| `docs/` | Dissertation and Prototype 5 documentation. |
| `models_custom/` | Custom model/precision artefacts. |
| `results/` | Prototype 5 result and evidence outputs. |
| `scripts/` | Supporting scripts. |
| `src/` | Prototype 5 Python source. |
| `tests/` | Prototype 5 test suite. |

Additional environment/cache directories are present: `.olive-cache/`, `.pytest_cache/`, `.sixth/`, `.venv/`.

## 3. Existing Prototype 5 Modes Detected

| Mode | Evidence detected | Status |
|---|---|---|
| Mode A final orchestrator | `src/prototype5/run_orchestrator.py`, `results/prototype5/final_evidence_manifest.json`, final CSV/Markdown outputs | Present |
| Mode B model precision / Phi evidence | `src/prototype5/quantisation_evidence.py`, `src/prototype5/phi_recovery_metrics.py`, `results/prototype5/recovery/custom_quantisation/`, `results/prototype5/recovery/phi/` | Present |
| Mode C local-vs-cloud | `src/prototype5/local_cloud_comparison.py`, `src/prototype5/mode_c_cloud_baseline.py`, `results/prototype5/mode_c/local_vs_cloud_summary.json` | Present |
| Mode D resource profile | `src/prototype5/mode_d_summary.py`, `src/prototype5/resource_profiler.py`, `results/prototype5/mode_d/mode_d_final_evidence_summary.json` | Present |

No PyBullet execution visualiser was detected.

## 4. Existing Result Files Detected Under `results/prototype5`

Final result files:

- `results/prototype5/final_claims_matrix.csv`
- `results/prototype5/final_dissertation_metrics.md`
- `results/prototype5/final_evidence_manifest.json`
- `results/prototype5/final_extension_summary.csv`
- `results/prototype5/final_limitations_matrix.csv`
- `results/prototype5/final_model_comparison.csv`
- `results/prototype5/final_safety_latency_summary.csv`
- `results/prototype5/final_zero_trust_comparison.csv`

Mode C files:

- `results/prototype5/mode_c/cloud_baseline_checkpoint.csv`
- `results/prototype5/mode_c/local_vs_cloud_results.csv`
- `results/prototype5/mode_c/local_vs_cloud_summary.json`

Mode D files:

- `results/prototype5/mode_d/manual_live_30_command_foundry_process_profile.csv`
- `results/prototype5/mode_d/manual_live_30_command_foundry_process_summary_normalized.json`
- `results/prototype5/mode_d/manual_live_30_command_foundry_process_summary.json`
- `results/prototype5/mode_d/manual_live_5_command_profile.csv`
- `results/prototype5/mode_d/mode_d_final_evidence_summary.json`
- `results/prototype5/mode_d/mode_d_summary.json`
- `results/prototype5/mode_d/resource_profile_metadata.json`
- `results/prototype5/mode_d/resource_profile_samples.csv`
- `results/prototype5/mode_d/resource_profile_summary.csv`
- `results/prototype5/mode_d/throughput_stability.csv`

Mode B recovery files:

- `results/prototype5/recovery/custom_quantisation/qwen2_5_0_5b_fp16_inference_model.json`
- `results/prototype5/recovery/custom_quantisation/qwen2_5_0_5b_int4_inference_model.json`
- `results/prototype5/recovery/custom_quantisation/qwen2_5_0_5b_int8_ort_dynamic_inference_model.json`
- `results/prototype5/recovery/phi/foundry_model_inventory.json`
- `results/prototype5/recovery/phi/phi_recovery_manifest.json`
- `results/prototype5/recovery/phi/phi_recovery_results.jsonl`
- `results/prototype5/recovery/phi/phi_recovery_summary.csv`

## 5. Existing Docs Detected

Existing dissertation evidence docs:

- `docs/dissertation_evidence/evaluation_pipeline.md`
- `docs/dissertation_evidence/evidence_index.md`
- `docs/dissertation_evidence/lee_feedback_closure.md`
- `docs/dissertation_evidence/metric_taxonomy.md`
- `docs/dissertation_evidence/microsoft_ixn_brief_closure.md`
- `docs/dissertation_evidence/prototype_io_contracts.md`
- `docs/dissertation_evidence/reproducibility_guide.md`
- `docs/dissertation_evidence/research_questions_and_claims.md`
- `docs/dissertation_evidence/threats_to_validity.md`

Existing Prototype 5 docs:

- `docs/prototype5/prototype5_dissertation_results_summary.md`
- `docs/prototype5/prototype5_final_evaluation_protocol.md`
- `docs/prototype5/prototype5_limitations_and_scope.md`
- `docs/prototype5/prototype5_local_vs_cloud_comparison.md`
- `docs/prototype5/prototype5_mode_d_final_live_profile.md`
- `docs/prototype5/prototype5_phi_evidence_summary.md`
- `docs/prototype5/prototype5_quantisation_metadata_check.md`
- `docs/prototype5/prototype5_resource_profile.md`

Related docs exist, but the target final-pack paths requested in the baseline spec mostly do not yet exist.

## 6. Existing Tests Detected

Tests detected under `tests/prototype5`:

- `test_benchmark_cases.py`
- `test_claims_matrix.py`
- `test_cloud_baseline_runner.py`
- `test_cloud_status.py`
- `test_evidence_manifest.py`
- `test_evidence_paths.py`
- `test_foundry_discovery.py`
- `test_loaders.py`
- `test_local_cloud_comparison.py`
- `test_mode_c_cloud_baseline.py`
- `test_mode_d_summary.py`
- `test_phi_claims_matrix.py`
- `test_phi_recovery_metrics.py`
- `test_quantisation_evidence.py`
- `test_report_exports.py`
- `test_resource_profiler.py`
- `test_throughput_runner.py`

No final-pack-specific tests were detected yet.

## 7. Missing Final-Pack Artefacts From Target List

The following requested target artefacts are missing at the specified paths:

| Target artefact | Required path | Audit status |
|---|---|---|
| Final evidence dashboard | `results/prototype5/final_evidence_dashboard.md` | Missing |
| Microsoft brief alignment matrix | `results/prototype5/microsoft_brief_alignment_matrix.md` | Missing |
| Research question mapping | `docs/research_question_mapping.md` | Missing |
| Root metric taxonomy | `docs/metric_taxonomy.md` | Missing |
| Benchmark card | `docs/benchmark_card.md` | Missing |
| Model/run cards README | `docs/model_run_cards/README.md` | Missing |
| Local Qwen/Coder run card | `docs/model_run_cards/local_qwen_coder_run_card.md` | Missing |
| Local Phi/Mode B run card | `docs/model_run_cards/local_phi_or_mode_b_run_card.md` | Missing |
| Cloud baseline run card | `docs/model_run_cards/cloud_baseline_run_card.md` | Missing |
| Resource profile run card | `docs/model_run_cards/resource_profile_run_card.md` | Missing |
| Industry use-case document | `docs/industry_use_case_industrial_robotics.md` | Missing |
| Claim boundaries document | `docs/claim_boundaries.md` | Missing |
| Architecture diagram specification | `docs/final_architecture_diagram_spec.md` | Missing |
| Mermaid architecture diagram | `figures/final_zero_trust_architecture.mmd` | Missing |
| Safety-latency frontier CSV | `results/prototype5/safety_latency_frontier.csv` | Missing |
| Safety-latency frontier Markdown | `results/prototype5/safety_latency_frontier.md` | Missing |
| Final-pack generator script | `src/prototype5/generate_final_dissertation_pack.py` | Missing |
| Final-pack completion report | `results/prototype5/final_pack_completion_report.md` | Missing |

PyBullet visual demonstrator artefacts are also missing, but they are explicitly optional and should not be implemented before the core evidence pack is complete.

## 8. Risk Assessment: What Should Not Be Changed

Do not change or refactor:

- Existing Prototype 1-4 repositories.
- Existing Prototype 5 benchmark semantics or metric definitions unless a verified bug is found.
- Existing generated result files without deliberately rerunning and reviewing the generator.
- Mode C cloud execution paths in a way that triggers network calls or requires API keys for documentation generation.
- Mode D live Foundry Local profiling in a way that requires the service to be running for offline evidence-pack generation.
- Any file containing secrets or environment-specific credentials.
- Core orchestrator behaviour unless integration is minimal and safe.

Specific current risk:

- `results/prototype5/final_claims_matrix.csv`, `results/prototype5/final_dissertation_metrics.md`, and `results/prototype5/final_evidence_manifest.json` are already modified in the working tree. They should be reviewed separately and not silently included in final-pack changes.

## 9. Proposed Implementation Sequence

Phase 1: Static dissertation evidence docs.

- Create `docs/research_question_mapping.md`.
- Create `docs/metric_taxonomy.md`.
- Create `docs/benchmark_card.md`.
- Create `docs/industry_use_case_industrial_robotics.md`.
- Create `docs/claim_boundaries.md`.

Phase 2: Evidence tables and run cards.

- Create `results/prototype5/final_evidence_dashboard.md`.
- Create `results/prototype5/microsoft_brief_alignment_matrix.md`.
- Create `docs/model_run_cards/README.md`.
- Create detected run cards for Qwen/Coder, Phi/Mode B, cloud baseline and resource profile.

Phase 3: Architecture and safety-latency frontier.

- Create `docs/final_architecture_diagram_spec.md`.
- Create `figures/final_zero_trust_architecture.mmd`.
- Create `results/prototype5/safety_latency_frontier.csv`.
- Create `results/prototype5/safety_latency_frontier.md`.

Phase 4: Safe generation integration.

- Prefer a separate deterministic script, `src/prototype5/generate_final_dissertation_pack.py`, rather than expanding `run_orchestrator.py` immediately.
- The script should read existing evidence, mark missing fields as `MISSING` or "not available in detected evidence", and avoid network/live Foundry calls.

Phase 5: Tests.

- Add non-brittle tests for required final-pack files, required claims, required brief rows, required metrics and main research question.
- Tests must pass offline with no cloud API key and no live Foundry Local dependency.

Phase 6: Optional PyBullet.

- Defer until the core evidence pack is complete.
- If added later, keep it isolated under `src/prototype5/pybullet_execution_visualiser/` and use dry-run output when PyBullet is unavailable.

Phase 7: Completion report.

- Create `results/prototype5/final_pack_completion_report.md` after implementation and verification.

## 10. Assumptions

- Prototype 5 remains the final evidence orchestration and dissertation-reporting layer, not Prototype 6.
- Prototypes 1-4 are source evidence only and must not be modified.
- Missing source evidence should be recorded as missing rather than inferred or fabricated.
- Existing Mode C and Mode D evidence should be reused from local result files, not regenerated through live cloud or Foundry calls.
- Existing `docs/dissertation_evidence/metric_taxonomy.md` can inform the new requested root-level `docs/metric_taxonomy.md`, but the requested path should still be created for final-pack completeness.
- PyBullet is optional and should not block final dissertation evidence-pack completion.
