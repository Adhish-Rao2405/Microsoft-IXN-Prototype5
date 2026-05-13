# Microsoft IXN Prototype 5

## Prototype 5: Final Dissertation Evidence Orchestrator

This repository contains the final dissertation-focused evidence orchestration layer for the Microsoft IXN Foundry Local zero-trust SLM robot task-planning project.

Prototype 5 does not introduce new robot-planning logic. It consolidates and audits existing evidence from Prototypes 1–4 into dissertation-ready tables, summaries, and claim matrices.

## Role

Prototype 5 reads evidence from:

- Prototype 3 model-comparison results
- Prototype 4 zero-trust execution-grounded evidence
- Prototype 4 optional extension summaries
- Prototype 1–4 audit outputs

It produces:

- final model comparison table
- final zero-trust comparison table
- final safety-latency summary
- final extension summary
- final dissertation claims matrix
- final limitations matrix
- final evidence manifest

## Core rule

Prototype 5 is an orchestration and reporting prototype only.

It must not modify Prototypes 1–4.
It must not invent missing quantisation evidence.
It must explicitly distinguish proven, partial, missing, and future-work claims.

## Final Dissertation Evidence

Prototype 5 is the final evidence-orchestration layer for the UCL Microsoft IXN Foundry Local dissertation.

The final state includes:

- Mode A: final evidence orchestration.
- Mode B: quantisation and Phi-family recovery.
- Mode C: local-vs-cloud comparison.
- Mode D: live Foundry Local resource profiling.

Run tests:

```powershell
python -m pytest tests/prototype5 -v
```

Run final orchestrator:

```powershell
python -m src.prototype5.run_orchestrator
```

Generate final dissertation evidence pack:

```powershell
python -m src.prototype5.generate_final_dissertation_pack
```

## Mode E0 — Reproducibility and Evaluation Rigour

Mode E0 hardens Prototype 5 in response to supervisor feedback about practical reproducibility, evaluation justification, repeatability and claim-to-evidence traceability. It does not add new robot-control functionality, rerun cloud APIs, or change locked metrics.

Mode E0 files:

- `docs/prototype5/reproducibility_guide.md`
- `docs/prototype5/evaluation_design_justification.md`
- `docs/prototype5/benchmark_representativeness.md`
- `docs/prototype5/repeatability_and_variance_plan.md`
- `docs/prototype5/claim_to_evidence_traceability.md`
- `results/prototype5/mode_e0/reproducibility_check_summary.json`
- `results/prototype5/mode_e0/claim_to_evidence_traceability.csv`
- `results/prototype5/mode_e0/repeatability_summary.csv`
- `results/prototype5/mode_e0/repeatability_live_runs.csv`
- `results/prototype5/mode_e0/repeatability_variance_summary.json`
- `results/prototype5/mode_e0/repeatability_variance_summary.md`
- `results/prototype5/mode_e0/pipeline_repeatability_summary.csv`
- `results/prototype5/mode_e0/pipeline_repeatability_variance_summary.json`
- `results/prototype5/mode_e0/pipeline_repeatability_variance_summary.md`
- `results/prototype5/mode_e0/full_pipeline_repeatability_live_runs.csv`
- `results/prototype5/mode_e0/full_pipeline_repeatability_summary.json`
- `results/prototype5/mode_e0/full_pipeline_repeatability_summary.md`

Run Mode E0:

```powershell
python scripts/prototype5/run_reproducibility_check.py
```

Run Mode E0.1 repeatability summary refresh:

```powershell
python scripts/prototype5/run_repeatability_analysis.py
```

Run Mode E0.2 pipeline replay:

```powershell
python scripts/prototype5/run_pipeline_repeatability_analysis.py
```

Run Mode E0.3 full live pipeline gate:

```powershell
python scripts/prototype5/run_full_pipeline_repeatability_live.py
```

Mode E0 documents the clone-and-run path, explains why the 30-command benchmark and metrics are appropriate for bounded MSc evaluation, defines a repeatability protocol, and checks that major claims point to evidence files. Live Foundry Local reproduction remains machine-dependent; retained evidence artefacts are used when live reproduction is not available.

Mode E0.1 adds explicit repeatability/variance artefacts. If live repeated benchmark runs are not available, the artefacts are marked `NOT_RUN` and metric fields remain blank. This prevents the dissertation from claiming cross-run stability until repeated-run evidence exists.

Mode E0.2 replays deterministic validation over recorded E0.1 raw outputs. It is classified as `COMPLETE_PIPELINE_REPLAY_ON_MINIMAL_PROMPT_OUTPUTS`, not full live pipeline repeatability.

Mode E0.3 checks whether Prototype 5 has a repo-local callable original Prototype 3 action-envelope live runner. In the current repo it is `E0_3_NOT_RUN`; this is intentional and prevents overclaiming schema-valid versus execution-eligible repeatability until that full live path exists.

## Post-E0 Consolidation

The post-E0 audit layer consolidates supervisor-facing and dissertation-facing evidence after repeatability hardening. It summarises how Lee's reproducibility concerns were addressed, what E0.4 proves under the tested conditions, what should be written in the dissertation, and which gaps should remain bounded rather than turned into feature creep.

- `docs/prototype5/post_e0_supervisor_feedback_response.md`
- `docs/prototype5/post_e0_evidence_audit.md`
- `docs/prototype5/post_e0_dissertation_wording.md`
- `docs/prototype5/post_e0_gap_register.md`

## Prototype 5 Mode E — Industrial Benchmark Extension

Mode E extends the original 30-command benchmark with 30 additional industrially motivated commands across pick-and-place, conveyor/sorting, inspection, warehouse transfer, human-proximity, and restricted-zone scenarios. Its purpose is to test whether the schema-valid vs execution-eligible gap remains observable beyond the original benchmark.

Mode E is bounded: it improves benchmark coverage but does not prove production robot safety, full industrial generalisation, or general local SLM reliability.

Mode E/E.1/E.2 complete:

- Mode E benchmark audit: `COMPLETE_BALANCED_EXTENSION`
- Mode E.1 policy audit: `COMPLETE_POLICY_CONTEXT`
- Mode E.2 live industrial evaluation: `COMPLETE_LIVE_INDUSTRIAL_EVALUATION`
- Tests: 104 passed

- `configs/prototype5/mode_e_industrial_benchmark.json`
- `configs/prototype5/mode_e_industrial_vocabulary.json`
- `configs/prototype5/mode_e_industrial_policy_rules.json`
- `docs/prototype5/mode_e_final_evidence_summary.md`
- `docs/prototype5/mode_e_lee_feedback_closure.md`
- `docs/prototype5/mode_e_final_dissertation_wording.md`
- `docs/prototype5/mode_e_benchmark_representativeness.md`
- `docs/prototype5/mode_e_evidence_summary.md`
- `docs/prototype5/mode_e_dissertation_wording.md`
- `docs/prototype5/mode_e1_industrial_policy_context.md`
- `docs/prototype5/mode_e1_evidence_summary.md`
- `docs/prototype5/mode_e2_live_evaluation_summary.md`
- `docs/prototype5/mode_e2_dissertation_wording.md`
- `results/prototype5/mode_e/mode_e_benchmark_audit.json`
- `results/prototype5/mode_e/mode_e_benchmark_audit.md`
- `results/prototype5/mode_e/mode_e_policy_audit.json`
- `results/prototype5/mode_e/mode_e_policy_audit.md`
- `results/prototype5/mode_e/mode_e2_live_industrial_summary.json`
- `results/prototype5/mode_e/mode_e2_live_industrial_results.csv`

Run Mode E benchmark audit:

```powershell
python scripts/prototype5/run_mode_e_benchmark_audit.py
```

Run Mode E.1 policy audit:

```powershell
python scripts/prototype5/run_mode_e_policy_audit.py
```

### Mode E.1 — Industrial Policy Context

Mode E.1 adds a minimal deterministic industrial vocabulary and policy layer for the Mode E benchmark. This prevents industrial commands from being evaluated against undefined terms. It is a benchmark-validation context, not a certified robot safety system.

### Mode E.2 — Bounded Live Industrial Evaluation

Mode E.2 runs the Mode E benchmark through the live local Foundry model only after the E.1 policy context is complete. Its purpose is to test whether the schema-valid vs execution-eligible gap remains observable under the expanded industrial benchmark. Results are bounded to the curated benchmark, local model/runtime, and deterministic policy context.

Run Mode E.2 live evaluation:

```powershell
python scripts/prototype5/run_mode_e_live_evaluation.py --base-url http://127.0.0.1:49313 --model Phi-3-mini-4k-instruct-generic-cpu:3
```

Key documentation:

- `docs/dissertation_evidence/microsoft_ixn_brief_closure.md`
- `results/prototype5/final_evidence_dashboard.md`
- `results/prototype5/microsoft_brief_alignment_matrix.md`
- `results/prototype5/final_pack_completion_report.md`
- `docs/dissertation_evidence/lee_feedback_closure.md`
- `docs/dissertation_evidence/prototype_io_contracts.md`
- `docs/dissertation_evidence/evaluation_pipeline.md`
- `docs/dissertation_evidence/metric_taxonomy.md`
- `docs/dissertation_evidence/reproducibility_guide.md`
- `docs/dissertation_evidence/research_questions_and_claims.md`
- `docs/dissertation_evidence/threats_to_validity.md`
- `docs/dissertation_evidence/evidence_index.md`
