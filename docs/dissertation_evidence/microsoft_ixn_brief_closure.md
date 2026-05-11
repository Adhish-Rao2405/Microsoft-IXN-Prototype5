# Microsoft IXN Brief Closure

## 1. Purpose

Prototype 5 is the final evidence-orchestration layer for the Microsoft IXN local-first zero-trust robot task-planning dissertation work. It consolidates prior prototype outputs into auditable dissertation evidence, closes the local-vs-cloud and resource-profile requirements, and defines safe claim boundaries for Chapters 4 and 5.

Prototype 5 does not introduce new robot-planning logic. Its role is to organise, verify and document evidence from the completed prototype sequence.

## 2. Locked Technical State

The final technical state is locked as follows:

- Mode A: final evidence orchestrator complete.
- Mode B: custom precision and Phi-family evidence complete.
- Mode C: local-vs-cloud comparison complete.
- Mode D: live Foundry Local resource profile complete.

The final orchestrator reads existing Prototype 1-4 evidence and Prototype 5 recovery/comparison/profile evidence, then exports dissertation-ready tables, summaries, claims matrices and a manifest.

## 3. Modes A-D

| Mode | Role | Final status | Primary evidence |
|---|---|---|---|
| Mode A | Final evidence orchestration | Complete | `results/prototype5/final_evidence_manifest.json` |
| Mode B | Custom precision and Phi recovery evidence | Complete custom precision evidence; Phi evidence present | `results/prototype5/recovery/custom_quantisation/`; `results/prototype5/recovery/phi/` |
| Mode C | Local-vs-cloud comparison | Complete | `results/prototype5/mode_c/local_vs_cloud_summary.json` |
| Mode D | Live Foundry Local resource profile | Complete live profile | `results/prototype5/mode_d/mode_d_final_evidence_summary.json` |

## 4. Microsoft IXN Brief Closure

Prototype 5 closes the Microsoft IXN brief by showing how local-first Foundry Local inference can be evaluated as part of a zero-trust task-planning architecture.

The brief closure is evidence-based:

- Local inference is measured on the same 30-command benchmark used for the cloud comparison.
- Cloud inference is included as an explicit external baseline.
- The evaluation separates request success, JSON validity, latency, privacy posture, offline resilience and resource utilisation.
- Live Foundry Local profiling records the operational cost of local inference on the measured Windows machine.
- The claim matrix records proven, missing and limited claims rather than presenting unsupported conclusions.

## 5. Evidence Files

Core final evidence files:

- `results/prototype5/final_evidence_manifest.json`
- `results/prototype5/final_claims_matrix.csv`
- `results/prototype5/final_dissertation_metrics.md`
- `results/prototype5/final_model_comparison.csv`
- `results/prototype5/final_zero_trust_comparison.csv`
- `results/prototype5/final_safety_latency_summary.csv`
- `results/prototype5/final_limitations_matrix.csv`

Mode-specific evidence:

- `results/prototype5/mode_c/local_vs_cloud_summary.json`
- `results/prototype5/mode_c/local_vs_cloud_results.csv`
- `results/prototype5/mode_d/mode_d_final_evidence_summary.json`
- `results/prototype5/mode_d/manual_live_30_command_foundry_process_summary_normalized.json`
- `results/prototype5/mode_d/manual_live_30_command_foundry_process_profile.csv`
- `results/prototype5/recovery/phi/phi_recovery_summary.csv`
- `results/prototype5/recovery/phi/phi_recovery_results.jsonl`
- `results/prototype5/recovery/custom_quantisation/`

Supporting dissertation documentation:

- `docs/dissertation_evidence/evidence_index.md`
- `docs/dissertation_evidence/metric_taxonomy.md`
- `docs/dissertation_evidence/research_questions_and_claims.md`
- `docs/dissertation_evidence/threats_to_validity.md`
- `docs/dissertation_evidence/reproducibility_guide.md`

## 6. Metric Taxonomy

Prototype 5 avoids using a single broad accuracy metric. The final evidence separates:

- `request_success`: whether a model/API call returned a response.
- `parse_success`: whether structured content could be recovered.
- `json_valid`: whether the response was syntactically valid JSON.
- `schema_valid`: whether the response conformed to the expected schema.
- `semantic_validity`: whether the response matched the intended command meaning, where evaluated.
- `safety_result`: deterministic safety-gate outcome.
- `execution_validity`: whether an action could proceed under prototype constraints.
- `latency_ms`: request or replay latency.
- `throughput_commands_per_min`: measured throughput for the workload.
- `normalized_mean_foundry_cpu_percent_of_total_logical_capacity`: live Foundry process CPU pressure normalised by logical CPU capacity.

The full taxonomy is recorded in `docs/dissertation_evidence/metric_taxonomy.md`.

## 7. Key Mode B/C/D Results

Mode B custom precision and Phi evidence:

- Custom FP16, INT8 and INT4 precision artifacts are present.
- Built-in Foundry Local catalogue precision metadata is still not exposed, so built-in precision is not claimed.
- Phi-family local evidence is present for `Phi-3-mini-4k-instruct-generic-cpu:3`.

Mode C local-vs-cloud comparison:

| Baseline | Successful requests | Mean latency | JSON-valid rate |
|---|---:|---:|---:|
| Cloud | 30/30 | 1749.28 ms | 100% |
| Local | 30/30 | 7028.0 ms | 73.33% |

Mode D live Foundry Local resource profile:

- 30/30 live Foundry requests completed.
- JSON-valid rate: 80%.
- Mean latency: 7896.97 ms.
- Normalized mean CPU: 48.31% of total logical CPU capacity.
- GPU/NPU counters were not detected, so no hardware acceleration claim is made.

## 8. How To Run Final Orchestrator

From the repository root:

```powershell
python -m src.prototype5.run_orchestrator
```

Run the Prototype 5 test suite:

```powershell
python -m pytest tests/prototype5 -v
```

The orchestrator regenerates the final result tables, dissertation metrics file and evidence manifest.

## 9. Claim Boundaries

Prototype 5 supports the following claims:

- A local-first zero-trust task-planning evaluation pipeline was completed across the prototype sequence.
- The final evidence base includes explicit model comparison, zero-trust safety comparison, local-vs-cloud comparison and live local resource profiling.
- The cloud baseline was faster and more JSON-consistent on the measured 30-command benchmark.
- The local baseline preserved local execution, data retention and offline-resilience properties.
- Local model output remains untrusted and requires deterministic validation before execution.
- Custom FP16, INT8 and INT4 precision artifacts are evidenced for Prototype 5 recovery work.

Prototype 5 does not claim:

- Production robot safety.
- Physical robot execution.
- Universal model performance beyond the benchmark scope.
- Built-in Foundry Local precision metadata where the catalogue does not expose it.
- GPU/NPU acceleration, because GPU/NPU counters were not detected.
- Quantitative cloud cost comparison, because token-level usage/cost accounting was not implemented.

## 10. Dissertation Chapter 4-5 Integration

Chapter 4 can use Prototype 5 as the final implementation and evaluation consolidation layer. The recommended structure is:

- Present Prototype 5 after the model-evaluation and zero-trust pipeline prototypes.
- Use Mode A to explain evidence orchestration and traceability.
- Use Mode B to close quantisation/Phi recovery evidence while preserving precision-scope limits.
- Use Mode C to discuss local-vs-cloud trade-offs.
- Use Mode D to discuss resource utilisation and local operational cost.

Chapter 5 can use Prototype 5 to frame final interpretation:

- Local-first inference is viable for the measured workload but slower than the cloud baseline.
- Zero-trust validation is necessary because local model output is not reliably JSON-valid.
- Cloud inference improves speed and JSON consistency in this benchmark but introduces external dependency, privacy and offline-resilience trade-offs.
- The final claim matrix and limitations matrix define which dissertation claims are proven, partial, missing or future work.
