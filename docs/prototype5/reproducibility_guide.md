# Prototype 5 Mode E0 Reproducibility Guide

## 1. Repository Purpose

This repository is the Prototype 5 evidence orchestration layer for the UCL Microsoft IXN dissertation on Microsoft Foundry Local and zero-trust evaluation of local SLM-generated robot task-planning proposals. It consolidates evidence from earlier prototypes and generates dissertation-facing evidence tables, claims matrices, limitations and verification artefacts.

Prototype 5 is not a new robot-control prototype. It is an evidence/reporting layer.

## 2. Prototype Hierarchy

| Prototype | Role |
|---|---|
| Prototype 1 | Optional early robot/PyBullet feasibility context only. |
| Prototype 2 | Deterministic validation and fail-closed foundation. |
| Prototype 3 | Core Foundry Local benchmark and local model evaluation evidence. |
| Prototype 4 | Zero-trust execution, false-accept and safety-latency evidence. |
| Prototype 5 | Final evidence orchestration, local-vs-cloud comparison, resource profiling and reporting layer. |

## 3. System Requirements

- Windows PowerShell is the tested shell environment for the retained evidence pack.
- Python 3.12 is the current working interpreter used by the repository tests.
- A virtual environment is recommended.
- Foundry Local is required only for live reproduction of local model calls. It is not required to inspect retained evidence or regenerate final reporting outputs.

## 4. Python Version

Repository validation has been run with Python 3.12. To check:

```powershell
python --version
```

## 5. Virtual Environment Setup

```powershell
cd C:\Users\reach\Microsoft-IXN-Prototype5
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If the environment already exists, activate it only.

## 6. Dependency Installation

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Optional plotting for dissertation figures uses `matplotlib` and `pillow`:

```powershell
python -m pip install matplotlib pillow
```

## 7. Foundry Local Assumptions

Live Foundry Local reproduction depends on the local machine having Foundry Local installed, the relevant model available and the service reachable. The final evidence pack can be regenerated from retained evidence files without a live Foundry Local service.

## 8. Local Model Alias / Configuration Assumptions

Detected retained evidence references local Qwen-family benchmark rows and Phi-family Foundry Local response evidence. Exact live aliases depend on the local Foundry Local catalogue and may vary by machine. Do not infer model precision from CPU/GPU labels; custom precision evidence is recorded separately under `results/prototype5/recovery/custom_quantisation/`.

## 9. Environment Variables

- `OPENAI_API_KEY`: needed only for live cloud baseline execution. The retained Mode C evidence can be inspected without rerunning cloud calls.
- Foundry Local service/model environment variables, if used locally, should be documented in any new live run card.

## 10. Benchmark Dataset Locations

The retained final pack references prior Prototype 3 benchmark evidence and final Prototype 5 summaries. Key local files include:

- `results/prototype5/final_model_comparison.csv`
- `results/prototype5/final_zero_trust_comparison.csv`
- `results/prototype5/final_safety_latency_summary.csv`
- `results/prototype5/mode_c/local_vs_cloud_summary.json`
- `results/prototype5/mode_d/mode_d_final_evidence_summary.json`

Prior-prototype raw benchmark files may be outside this repository on the original development machine. Missing prior raw files should be recorded as evidence-availability caveats, not inferred.

## 11. Prompt and Configuration Locations

Current final evidence is generated from retained CSV/JSON/JSONL/Markdown artefacts and Python reporting modules. Prompt/configuration details for live prior-prototype runs are expected to live in their source prototype repositories or run cards where available. If a prompt/configuration file is not present in this repository, it should be marked as not available in detected evidence.

## 12. Run Tests

```powershell
python -m pytest tests/prototype5 -v
```

Expected behaviour for the frozen baseline is a passing Prototype 5 test suite.

## 13. Run Prototype 5 Orchestrator

```powershell
python -m src.prototype5.run_orchestrator
```

This regenerates final reporting outputs from retained evidence files. It should not require a cloud API call or a live Foundry Local service.

## 14. Regenerate Final Evidence Summaries

```powershell
python -m src.prototype5.generate_final_dissertation_pack
```

This regenerates dissertation-facing documentation such as the final evidence dashboard, Microsoft brief alignment and safety-latency frontier notes.

## 15. Run Mode E0 Reproducibility Check

```powershell
python scripts\prototype5\run_reproducibility_check.py
```

This checks Mode E0 documentation, generates the traceability CSV, generates the repeatability placeholder CSV and writes `results/prototype5/mode_e0/reproducibility_check_summary.json`.

## 16. Expected Output Files

- `results/prototype5/final_evidence_manifest.json`
- `results/prototype5/final_claims_matrix.csv`
- `results/prototype5/final_dissertation_metrics.md`
- `results/prototype5/final_evidence_dashboard.md`
- `results/prototype5/mode_e0/reproducibility_check_summary.json`
- `results/prototype5/mode_e0/claim_to_evidence_traceability.csv`
- `results/prototype5/mode_e0/repeatability_summary.csv`

## 17. Expected Pass/Fail Behaviour

The core reporting path should pass if retained evidence files are present. Live reproduction of prior benchmark runs may require external local setup and should be treated separately from evidence-pack regeneration.

## 18. Troubleshooting

- If Python imports fail, confirm the virtual environment is active and dependencies are installed.
- If Foundry Local live calls fail, inspect the service state and model catalogue; retained evidence can still be regenerated.
- If `OPENAI_API_KEY` is absent, do not rerun cloud calls; use retained Mode C outputs.
- If prior-prototype evidence paths are unavailable on a different machine, mark them as missing or contextual instead of fabricating values.

## 19. Known Limitations

This guide describes the expected reproducibility path for the evidence pack. Some live Foundry Local steps depend on local machine setup. Where live reproduction is not possible, the repository preserves evidence artefacts generated from prior runs.
