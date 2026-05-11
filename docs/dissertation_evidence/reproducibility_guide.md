# Reproducibility Guide

## Repository

`C:\Users\reach\Microsoft-IXN-Prototype5`

## Branch

`master`

## Final Committed State

`d7ef370 Integrate Mode D into final orchestrator`

## Environment

- Python virtual environment used.
- Foundry Local installed and running for local live model tests.
- Required Python packages installed from the project environment.
- API keys are not stored in the repository and must not be committed.

## Test Command

```powershell
python -m pytest tests/prototype5 -v
```

Expected result:

```text
54 passed
```

## Final Orchestrator Command

```powershell
python -m src.prototype5.run_orchestrator
```

Expected summary:

```text
Prototype 5 Final Evidence Orchestrator: COMPLETE
Prototype 3 model evidence: PRESENT
Prototype 4 zero-trust evidence: PRESENT
Prototype 4 extension evidence: PRESENT
Quantisation evidence: COMPLETE_CUSTOM_EVIDENCE
Phi evidence: PRESENT
Mode C status: COMPLETE
Cloud baseline status: COMPLETE
Mode D status: COMPLETE_LIVE_PROFILE
Live Foundry profile: PRESENT
Live Foundry successful requests: 30/30
Live Foundry JSON-valid rate: 0.8
Live Foundry mean latency: 7896.97 ms
Live Foundry normalized mean CPU: 48.31%
Generated outputs: 12
```

## Key Output Files

- `results/prototype5/final_evidence_manifest.json`
- `results/prototype5/final_claims_matrix.csv`
- `results/prototype5/final_dissertation_metrics.md`
- `results/prototype5/mode_c/local_vs_cloud_summary.json`
- `results/prototype5/mode_d/mode_d_final_evidence_summary.json`
- `results/prototype5/mode_d/manual_live_30_command_foundry_process_summary_normalized.json`

## Reproducibility Limits

- Cloud comparison requires valid external API configuration, but keys must not be stored or shared.
- Local results depend on host hardware, Foundry Local version and available model aliases.
- GPU/NPU acceleration was not detected in the final Mode D evidence.
- Live resource profiling is hardware-specific and should not be generalised beyond the measured machine without further runs.
