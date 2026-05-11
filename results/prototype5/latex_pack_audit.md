# LaTeX Pack Audit

Generated: 2026-05-11T21:01:38+01:00

## Current Git Status

```text
## master...origin/master [ahead 1]
 M latex/generated/11_appendix_verification_evidence.tex
 M latex/generated/latex_pack_summary.md
 M results/prototype5/latex_pack_audit.md
 M results/prototype5/verification_snapshots/git_status_after_latex_pack.txt
 M results/prototype5/verification_snapshots/pytest_prototype5_output.txt
 M results/prototype5/verification_snapshots/verification_summary.md
 M scripts/prototype5/generate_latex_writing_pack.py
?? figures/final_evidence_claims_summary.png
?? figures/microsoft_brief_alignment_summary.png
?? figures/safety_latency_frontier_summary.png
?? figures/verification_pytest_summary.png
```

## Evidence Files Found

- `results/prototype5/final_evidence_dashboard.md`
- `results/prototype5/microsoft_brief_alignment_matrix.md`
- `results/prototype5/final_claims_matrix.csv`
- `results/prototype5/final_dissertation_metrics.md`
- `results/prototype5/final_evidence_manifest.json`
- `results/prototype5/safety_latency_frontier.md`
- `results/prototype5/safety_latency_frontier.csv`
- `results/prototype5/final_pack_completion_report.md`
- `docs/research_question_mapping.md`
- `docs/metric_taxonomy.md`
- `docs/benchmark_card.md`
- `docs/claim_boundaries.md`
- `docs/industry_use_case_industrial_robotics.md`
- `docs/prototype1_context_note.md`
- `docs/final_architecture_diagram_spec.md`
- `docs/model_run_cards/README.md`
- `figures/final_zero_trust_architecture.mmd`
- `README.md`
- `docs/dissertation_evidence/evidence_index.md`

## Evidence Files Missing

- None

## Current Test Count

- Command: `python -m pytest tests/prototype5 -v`
- Status: PASS
- Key output: `============================= 62 passed in 0.97s ==============================`

## Current Orchestrator Status

- Command: `python -m src.prototype5.run_orchestrator`
- Status: PASS
- Key output: `Prototype 5 Final Evidence Orchestrator: COMPLETE`

## Current Final Pack Generator Status

- Command: `python -m src.prototype5.generate_final_dissertation_pack`
- Status: PASS
- Key output: `Prototype 5 final dissertation pack generated.`

## Changed Or Generated Files Before LaTeX Generation

```text
M latex/generated/11_appendix_verification_evidence.tex
 M latex/generated/latex_pack_summary.md
 M results/prototype5/latex_pack_audit.md
 M results/prototype5/verification_snapshots/git_status_after_latex_pack.txt
 M results/prototype5/verification_snapshots/pytest_prototype5_output.txt
 M results/prototype5/verification_snapshots/verification_summary.md
 M scripts/prototype5/generate_latex_writing_pack.py
?? figures/final_evidence_claims_summary.png
?? figures/microsoft_brief_alignment_summary.png
?? figures/safety_latency_frontier_summary.png
?? figures/verification_pytest_summary.png
```

## Caveats For The LaTeX Pack

- The LaTeX pack is a writing aid and does not create new experimental evidence.
- Prototype 1 is context-only early feasibility evidence, not missing core proof.
- Prototype 5 remains an evidence/reporting layer.
- PyBullet is discussed only as optional future visualisation; no PyBullet or robot-control feature is generated.
- All reported quantitative claims are taken from detected evidence files. Missing values are marked as not available in detected evidence.
- The architecture figure uses the existing Mermaid source; Overleaf may need a manually exported PDF at `figures/final_zero_trust_architecture.pdf`.
- Optional PNG generation is available through matplotlib.
