# Lee Feedback Closure Matrix

This document maps supervisor feedback received after the Prototype 3 progress update to the final Prototype 5 evidence state. Its purpose is to demonstrate how the project incorporated feedback around reproducibility, maintainability, evaluation methodology, traceability and academic framing.

| Feedback point | Action taken | Evidence location | Status |
|---|---|---|---|
| Prototype 3 role should be clearly defined within the larger system | Prototype 3 is documented as the model-evaluation layer feeding Prototype 4 safety-latency analysis and Prototype 5 final orchestration. | `docs/dissertation_evidence/prototype_io_contracts.md`; `results/prototype5/final_evidence_manifest.json` | Closed |
| Inputs and outputs should be more explicit | Added prototype input/output contracts for Prototypes 1-5. | `docs/dissertation_evidence/prototype_io_contracts.md` | Closed |
| Evaluation pipeline should be clearer | Added benchmark-to-evidence pipeline description showing command input, model response, parsing, JSON validity, schema validation, safety checks and final metrics. | `docs/dissertation_evidence/evaluation_pipeline.md` | Closed |
| Reproducibility and maintainability should improve | Added reproducibility guide with environment assumptions, commands, test suite and generated outputs. | `docs/dissertation_evidence/reproducibility_guide.md`; `README.md` | Closed |
| Data schemas and experiment configurations should be documented | Added metric taxonomy and prototype I/O contracts; benchmark/result schemas are described at evidence level. | `docs/dissertation_evidence/metric_taxonomy.md`; `docs/dissertation_evidence/prototype_io_contracts.md` | Mostly closed |
| Research questions and hypotheses should be explicit | Added final research questions, evaluation questions and claim boundaries. | `docs/dissertation_evidence/research_questions_and_claims.md` | Closed |
| Metrics and baselines should be clearer | Added local/cloud baseline definitions and metric separation. | `docs/dissertation_evidence/metric_taxonomy.md`; `docs/prototype5/prototype5_local_vs_cloud_comparison.md` | Closed |
| Statistical significance and validity should be considered | Added threats-to-validity document explaining benchmark size, deterministic evaluation, lack of statistical generalisation and appropriate claim boundaries. | `docs/dissertation_evidence/threats_to_validity.md` | Closed |
| Results should link clearly to research claims | Added evidence index mapping claims to files. | `docs/dissertation_evidence/evidence_index.md`; `results/prototype5/final_claims_matrix.csv` | Closed |

## Final Closure Statement

Supervisor feedback after Prototype 3 identified the need for clearer documentation of inputs, outputs, evaluation pipelines, reproducibility, baseline definitions and research claims. These concerns were addressed in the final prototype sequence by extending the work into Prototype 4 and Prototype 5. Prototype 4 introduced execution-grounded safety evaluation, while Prototype 5 consolidated the final evidence base through an evidence manifest, claims matrix, local-vs-cloud comparison and live Foundry Local resource profiling. The final documentation layer records prototype input/output contracts, metric definitions, evaluation stages, validity threats and evidence-to-claim traceability.
