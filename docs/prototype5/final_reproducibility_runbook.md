# Prototype 5 Final Reproducibility Runbook

## 1. Purpose

This runbook defines the final clone-to-run path for Prototype 5 after Mode E/E.1/E.2 completion. It is intended to answer whether another reader can regenerate the dissertation-facing evidence pack from committed evidence files without rerunning live Foundry Local experiments.

Prototype 5 is the final evidence orchestration layer. It is not a new robot controller, simulator or additional experiment mode.

## 2. Repository Path

Tested working path:

```powershell
C:\Users\reach\Microsoft-IXN-Prototype5
```

On another machine, clone the repository and run the same commands from the repository root.

## 3. Environment Setup

The retained evidence pack was developed and tested on Windows PowerShell with Python 3.12.

```powershell
cd C:\Users\reach\Microsoft-IXN-Prototype5
python --version
```

Expected Python family:

```text
Python 3.12.x
```

## 4. Python Virtual Environment

Create a virtual environment if one is not already present:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If `.venv` already exists, only activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

## 5. Required Dependencies

Install repository dependencies:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Optional dissertation figure tooling may require additional packages such as `matplotlib` or `pillow`, but the final evidence-pack regeneration path does not depend on new live model inference.

## 6. Core Verification Commands

Run the final Prototype 5 test suite:

```powershell
python -m pytest tests\prototype5 -v
```

Run the final evidence orchestrator:

```powershell
python -m src.prototype5.run_orchestrator
```

Regenerate the final dissertation evidence pack:

```powershell
python -m src.prototype5.generate_final_dissertation_pack
```

## 7. Expected Outputs

Expected current verification state:

```text
python -m pytest tests\prototype5 -v: 111 passed
python -m src.prototype5.run_orchestrator: Prototype 5 Final Evidence Orchestrator: COMPLETE
python -m src.prototype5.generate_final_dissertation_pack: Prototype 5 final dissertation pack generated
```

Expected regenerated evidence outputs include:

- `results/prototype5/final_evidence_dashboard.md`
- `results/prototype5/final_pack_completion_report.md`
- `results/prototype5/final_claims_matrix.csv`
- `results/prototype5/final_evidence_manifest.json`
- `results/prototype5/final_dissertation_metrics.md`
- `results/prototype5/microsoft_brief_alignment_matrix.md`
- `results/prototype5/safety_latency_frontier.md`

## 8. Final Evidence Status

The final evidence state is:

| Evidence area | Expected status |
|---|---|
| E0.4 full live pipeline repeatability | `COMPLETE` |
| Mode E benchmark audit | `COMPLETE_BALANCED_EXTENSION` |
| Mode E.1 policy audit | `COMPLETE_POLICY_CONTEXT` |
| Mode E.2 live industrial evaluation | `COMPLETE_LIVE_INDUSTRIAL_EVALUATION` |
| Prototype 5 orchestrator | `COMPLETE` |
| Prototype 5 tests | `111 passed` |

## 9. Frozen Evidence That Does Not Require Foundry Local

The final evidence pack can be regenerated from committed evidence files without rerunning live Foundry Local experiments.

The following retained evidence is treated as frozen dissertation evidence:

- `results/prototype5/final_model_comparison.csv`
- `results/prototype5/final_zero_trust_comparison.csv`
- `results/prototype5/final_safety_latency_summary.csv`
- `results/prototype5/mode_c/local_vs_cloud_summary.json`
- `results/prototype5/mode_d/mode_d_final_evidence_summary.json`
- `results/prototype5/mode_e0/full_pipeline_live_repeatability_summary.json`
- `results/prototype5/mode_e/mode_e_benchmark_audit.json`
- `results/prototype5/mode_e/mode_e_policy_audit.json`
- `results/prototype5/mode_e/mode_e2_live_industrial_summary.json`
- `results/prototype5/mode_e/mode_e2_live_industrial_results.csv`
- `results/prototype5/mode_e/mode_e2_live_industrial_raw.jsonl`

These files support the final dashboard, claims matrix, dissertation metrics and Mode E claim traceability.

## 10. Live Evidence That Originally Required Foundry Local

Some retained evidence was originally produced by live local Foundry Local runs. These should not be rerun casually during dissertation writing.

| Evidence | Original live dependency | Rerun guidance |
|---|---|---|
| Mode D live resource profile | Foundry Local service and local model | Use retained evidence unless explicitly re-profiling hardware. |
| E0.4 full live pipeline repeatability | Foundry Local action-envelope live path | Frozen as repeatability evidence; reruns may vary by runtime/model state. |
| Mode E.2 live industrial benchmark | Foundry Local Phi-3-mini model alias and E.1 policy context | Frozen as final industrial benchmark evidence. |
| Mode C cloud comparison | Cloud API key for cloud baseline, retained local/cloud outputs | Use retained evidence unless explicitly reproducing cloud cost/latency. |

Live Mode E.2 raw evaluation is frozen as evidence; rerunning it may produce different latency or model-output behaviour depending on runtime, model alias and machine state.

## 11. Expected Pass Condition

The final reproducibility pass is considered successful when:

1. `python -m pytest tests\prototype5 -v` passes.
2. `python -m src.prototype5.run_orchestrator` reports `Prototype 5 Final Evidence Orchestrator: COMPLETE`.
3. `python -m src.prototype5.generate_final_dissertation_pack` regenerates the final dissertation evidence pack.
4. Generated dashboard and completion-report files include Mode E/E.1/E.2 final status.
5. No new live Foundry Local run is required.

## 12. Known Caveats

- The final evidence pack is reproducible from committed artefacts; live model behaviour is not guaranteed to be identical across machines or time.
- Mode E.2 is bounded to a curated 30-case industrial benchmark, E.1 deterministic policy context, one local Phi-3-mini model alias, one Foundry Local runtime/machine context and no real robot execution.
- E0.4 provides repeatability evidence for the original action-envelope benchmark; Mode E.2 provides industrial benchmark extension evidence. They should not be blurred into one statistical condition.
- The deterministic validation policy is benchmark-validation context, not certified industrial robot safety.
- High CPU latency remains a deployment boundary. The credible deployment framing is supervisory/offline task proposal and validation, not low-latency closed-loop control.
- If a regenerated file changes only timestamp fields, treat that as generation noise rather than new evidence.
- If Foundry Local or cloud credentials are unavailable, use retained evidence artefacts rather than fabricating or partially rerunning results.

## 13. Final Stop Rule

Do not create Mode F/G/H/I/J/K, new live benchmarks or new Foundry runs for dissertation writing unless a specific examiner or supervisor request requires new evidence. The default treatment for remaining weaknesses is:

```text
writing fix / figure preparation / limitation / future work
```

