# Prototype 5 Mode E Evidence Index

This file provides a supervisor-facing map of the Mode E, E.1 and E.2 evidence.

## Why Mode E exists

Mode E was created to address benchmark scope and industrial relevance.

The original benchmark supported controlled evaluation, but Mode E extends the evaluation with industrially phrased task-planning cases across multiple scenario families.

Mode E is **not** claimed to be universally representative of industry. It is a bounded benchmark extension.

## Evidence map

| Area | File / folder | Purpose |
|---|---|---|
| Mode E benchmark config | `configs/prototype5/mode_e_industrial_benchmark.json` | Defines the 30 industrial benchmark cases. |
| Mode E benchmark audit script | `scripts/prototype5/run_mode_e_benchmark_audit.py` | Audits benchmark balance and composition. |
| Mode E benchmark audit result | `results/prototype5/mode_e/mode_e_benchmark_audit.json` | Machine-readable audit result. |
| Mode E benchmark audit report | `results/prototype5/mode_e/mode_e_benchmark_audit.md` | Human-readable audit report. |
| Mode E benchmark documentation | `docs/prototype5/mode_e_benchmark_representativeness.md` | Explains benchmark scope and representativeness boundary. |
| Mode E final evidence summary | `docs/prototype5/mode_e_final_evidence_summary.md` | Final dissertation-facing Mode E evidence summary. |
| Mode E Lee closure | `docs/prototype5/mode_e_lee_feedback_closure.md` | Maps Mode E to Lee feedback and remaining caveats. |
| Mode E historical evidence summary | `docs/prototype5/mode_e_evidence_summary.md` | Historical/superseded summary; retained for audit trail. |
| Mode E historical dissertation wording | `docs/prototype5/mode_e_dissertation_wording.md` | Historical/superseded wording; retained for audit trail. |

## Mode E.1 evidence

| Area | File / folder | Purpose |
|---|---|---|
| Mode E.1 vocabulary config | `configs/prototype5/mode_e_industrial_vocabulary.json` | Defines deterministic industrial vocabulary terms. |
| Mode E.1 policy rules config | `configs/prototype5/mode_e_industrial_policy_rules.json` | Defines deterministic benchmark validation policy rules. |
| Mode E.1 policy audit script | `scripts/prototype5/run_mode_e_policy_audit.py` | Checks vocabulary/policy coverage over the Mode E benchmark. |
| Mode E.1 audit result | `results/prototype5/mode_e/mode_e_policy_audit.json` | Machine-readable policy coverage result. |
| Mode E.1 audit report | `results/prototype5/mode_e/mode_e_policy_audit.md` | Human-readable policy coverage report. |
| Mode E.1 policy context documentation | `docs/prototype5/mode_e1_industrial_policy_context.md` | Explains vocabulary/policy context and boundaries. |
| README Mode E.1 section | `README.md` | Documents Mode E.1 role in the final evidence stack. |

Expected Mode E.1 status:

```text
COMPLETE_POLICY_CONTEXT
coverage: 30/30
```

## Mode E.2 evidence

| Area | File / folder | Purpose |
|---|---|---|
| Mode E.2 live runner | `scripts/prototype5/run_mode_e_live_evaluation.py` | Runs/resumes live Foundry Local industrial benchmark evaluation. |
| Mode E.2 raw/live outputs | `results/prototype5/mode_e/mode_e2_live_industrial_raw.jsonl` | Frozen raw live evaluation evidence. |
| Mode E.2 result CSV | `results/prototype5/mode_e/mode_e2_live_industrial_results.csv` | Per-case deterministic validation and result records. |
| Mode E.2 summary JSON | `results/prototype5/mode_e/mode_e2_live_industrial_summary.json` | Machine-readable final metric summary. |
| Mode E.2 summary markdown | `results/prototype5/mode_e/mode_e2_live_industrial_summary.md` | Human-readable final summary. |
| Mode E.2 dissertation wording | `docs/prototype5/mode_e2_dissertation_wording.md` | Bounded wording for the live industrial result. |
| Final dashboard | `results/prototype5/final_evidence_dashboard.md` | Consolidated dissertation-facing evidence. |
| Final pack completion report | `results/prototype5/final_pack_completion_report.md` | Shows final evidence pack generation status. |

Expected Mode E.2 status:

```text
COMPLETE_LIVE_INDUSTRIAL_EVALUATION
```

Expected final Mode E.2 metrics:

| Metric | Value |
|---|---:|
| Total cases | 30 |
| Request success rate | 1.0 |
| Parse success rate | 0.7667 |
| JSON-valid rate | 0.7667 |
| Schema-valid rate | 0.6333 |
| Semantic-valid rate | 0.7667 |
| Safety-valid rate | 0.6667 |
| Execution-eligible rate | 0.1 |
| Model false accepts | 16 |
| Pipeline false accepts | 0 |
| Schema-valid minus execution-eligible gap | 0.5333 |
| Mean latency | 28359.26 ms |
| Median latency | 22588.65 ms |
| Max latency | 66928.25 ms |

## Tests

Mode E-related tests are under:

```text
tests/prototype5/
```

Relevant test categories include:

- benchmark configuration checks;
- benchmark audit checks;
- required evidence-file checks;
- final documentation alignment checks;
- final evidence pack checks.

Expected current verification:

```text
python -m pytest tests\prototype5 -v
111 passed
```

## Orchestrator

Final evidence orchestrator:

```powershell
python -m src.prototype5.run_orchestrator
```

Expected result:

```text
Prototype 5 Final Evidence Orchestrator: COMPLETE
```

## Final pack regeneration

Final dissertation pack generator:

```powershell
python -m src.prototype5.generate_final_dissertation_pack
```

Expected generated files include:

```text
results/prototype5/final_evidence_dashboard.md
results/prototype5/final_pack_completion_report.md
```

## Important boundary

The final evidence pack can be regenerated from committed evidence files.

The live Mode E.2 evaluation evidence is frozen. Rerunning live Foundry Local may produce different latency or output behaviour depending on:

- model alias availability;
- Foundry Local runtime state;
- machine load;
- CPU/GPU/NPU availability;
- local service endpoint;
- prompt/runtime version.

Therefore, the dissertation uses the committed Mode E.2 evidence as the auditable record.

