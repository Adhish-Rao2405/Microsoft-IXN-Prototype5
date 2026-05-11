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

Key documentation:

- `docs/dissertation_evidence/microsoft_ixn_brief_closure.md`
- `docs/dissertation_evidence/lee_feedback_closure.md`
- `docs/dissertation_evidence/prototype_io_contracts.md`
- `docs/dissertation_evidence/evaluation_pipeline.md`
- `docs/dissertation_evidence/metric_taxonomy.md`
- `docs/dissertation_evidence/reproducibility_guide.md`
- `docs/dissertation_evidence/research_questions_and_claims.md`
- `docs/dissertation_evidence/threats_to_validity.md`
- `docs/dissertation_evidence/evidence_index.md`
