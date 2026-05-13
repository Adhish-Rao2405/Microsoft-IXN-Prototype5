# Lee Feedback Closure Map

## Purpose

This document maps Lee's feedback themes to the final dissertation evidence. It should be used to make the dissertation read as a coherent research system rather than a sequence of disconnected prototypes.

| Lee feedback | Where addressed | Evidence | Dissertation handling |
|---|---|---|---|
| Project should read as a coherent system, not disconnected prototypes | Chapter 1 and Chapter 3 | Prototype evolution diagram; prototype contribution matrix; `docs/prototype5/dissertation_argument_map.md` | Present prototypes as stages in one evaluation system: feasibility, contract, benchmark, validation, evidence orchestration and industrial extension. |
| Need reproducibility | Chapter 3 methodology and appendix | `docs/prototype5/reproducibility_guide.md`; scripts/configs/results; `python -m pytest tests/prototype5 -v`; `python -m src.prototype5.run_orchestrator` | Explain fixed configs, retained outputs, tests and generated evidence exports. |
| Need benchmark justification | Chapter 3 and Chapter 5 limitations | original 30-command benchmark; `docs/prototype5/benchmark_representativeness.md`; Mode E 30-command industrial extension | State that the benchmark is curated and bounded, then show how Mode E improves coverage without claiming comprehensiveness. |
| Need repeatability/variance discussion | Chapter 4 results | E0.4 three full live runs; `results/prototype5/mode_e0/full_pipeline_live_repeatability_summary.json` | Use E0.4 metrics to show stable observed gap and zero pipeline false accepts under tested conditions. |
| Need claim-to-evidence traceability | Chapter 4/5 and appendix | final claims matrix; final evidence dashboard; C15-C17 Mode E claims | Link every major claim to an evidence file and boundary. |
| Avoid overclaiming local models | Chapter 5 limitations | bounded claim language; Mode E final docs; examiner-safe claims document | Use "proposal generation" and "execution-eligible under tested conditions", not "safe robot controller". |
| Link each claim to evidence | Throughout results and discussion | `results/prototype5/final_claims_matrix.csv`; `results/prototype5/final_evidence_manifest.json`; `results/prototype5/final_evidence_dashboard.md` | Put evidence references in text, tables and appendices. |
| Address industrial representativeness | Chapter 3 benchmark design; Chapter 4 Mode E results; Chapter 5 boundaries | Mode E benchmark audit, Mode E.1 policy audit, Mode E.2 live industrial summary | Say Mode E improves coverage and tests bounded industrial relevance; it does not make the benchmark comprehensive. |
| Discuss deployment practicality | Chapter 4 resource/latency; Chapter 5 RQ4 | Mode C, Mode D, E0.4 latency, Mode E.2 latency | Frame the credible deployment as supervisory/offline proposal generation, not low-latency closed-loop control. |

## Closure Summary

Lee's core methodological concerns are addressed by E0 repeatability/reproducibility hardening, Mode E benchmark extension, Mode E.1 deterministic vocabulary/policy context and Mode E.2 bounded live industrial evaluation. The dissertation should use these as evidence that the project matured from a prototype sequence into a controlled evaluation system.

## Remaining Gaps

The remaining gaps do not require implementation now:

- real industrial logs
- more model aliases
- additional hardware/runtime contexts
- physical robot execution
- certified safety standard compliance
- formal verification
- human operator study

These are limitations and future work, not blockers for the dissertation's bounded claim.

