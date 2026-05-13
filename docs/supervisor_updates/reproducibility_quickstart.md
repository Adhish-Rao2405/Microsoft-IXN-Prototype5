# Prototype 5 Reproducibility Quickstart

This quickstart explains how to verify the final Prototype 5 evidence stack.

## Repository

```text
C:\Users\reach\Microsoft-IXN-Prototype5
```

## Setup

From PowerShell:

```powershell
cd C:\Users\reach\Microsoft-IXN-Prototype5
.\.venv\Scripts\Activate.ps1
```

If dependencies need to be installed:

```powershell
pip install -r requirements.txt
```

If there is no `requirements.txt`, use the existing project environment.

## 1. Run tests

```powershell
python -m pytest tests\prototype5 -v
```

Expected result:

```text
111 passed
```

## 2. Run final evidence orchestrator

```powershell
python -m src.prototype5.run_orchestrator
```

Expected result:

```text
Prototype 5 Final Evidence Orchestrator: COMPLETE
```

The orchestrator verifies the presence and consistency of the final evidence stack.

## 3. Regenerate final dissertation evidence pack

```powershell
python -m src.prototype5.generate_final_dissertation_pack
```

Expected generated files:

```text
results/prototype5/final_evidence_dashboard.md
results/prototype5/final_pack_completion_report.md
```

## 4. Evidence files to inspect

Start with:

```text
results/prototype5/final_evidence_dashboard.md
results/prototype5/final_pack_completion_report.md
docs/supervisor_updates/prototype5_mode_e_evidence_index.md
```

Then inspect Mode E evidence under:

```text
results/prototype5/mode_e/
```

And Mode E config under:

```text
configs/prototype5/mode_e_industrial_benchmark.json
```

## 5. What does not require Foundry Local

The final evidence dashboard and final pack can be regenerated from committed evidence files.

The following commands should not require a live Foundry Local service:

```powershell
python -m pytest tests\prototype5 -v
python -m src.prototype5.run_orchestrator
python -m src.prototype5.generate_final_dissertation_pack
```

## 6. What originally required Foundry Local

Live evidence such as E0.4 and Mode E.2 originally required Foundry Local and a local model endpoint.

The relevant live model context was:

```text
Foundry Local endpoint: http://127.0.0.1:49313
Model: Phi-3-mini-4k-instruct-generic-cpu:3
```

The committed result files are treated as frozen evidence.

## 7. Why not rerun live evidence by default

Live Foundry Local reruns may produce different latency or output behaviour due to:

- model availability;
- runtime version;
- machine load;
- local service state;
- endpoint changes;
- hardware acceleration availability.

For dissertation evidence, the committed raw outputs and summaries are the auditable record.

## 8. Expected final status

```text
Tests: 111 passed
Orchestrator: COMPLETE
Final pack generation: passed
Mode E.2: COMPLETE_LIVE_INDUSTRIAL_EVALUATION
E0.4: COMPLETE_FULL_LIVE_PIPELINE_REPEATABILITY
```

## 9. Claim boundary

This reproducibility quickstart verifies the evidence stack and final reporting pipeline.

It does not claim:

- production robot safety;
- certified industrial deployment;
- universal local SLM reliability;
- real robot execution;
- low-latency closed-loop robot control.

