# RQ To Evidence Matrix

## Purpose

This matrix connects the five dissertation research questions to prototype evidence, final results, figures/tables and claim boundaries. It is intended to stop the dissertation becoming a build log.

## Matrix

| RQ | Evidence source | Core result | Figures/tables to include | Safe answer | Boundary |
|---|---|---|---|---|---|
| RQ1 - Feasibility | Prototype 1 context; Prototype 2/2.1 contracts; Prototype 3 benchmark; Prototype 5 Mode A/B | Local models can produce structured robot action proposals under benchmark conditions. | System evolution diagram; prototype contribution matrix; Foundry Local model benchmark summary; local SLM planning pipeline figure | Foundry Local can support local structured proposal generation. | Proposal-level feasibility only; not execution readiness. |
| RQ2 - Validity gap | Prototype 3; Prototype 4; Prototype 5 E0.4; Prototype 5 E.2 | E0.4 schema_valid_rate `0.8667` vs execution_eligible_rate `0.1`; Mode E.2 schema_valid_rate `0.6333` vs execution_eligible_rate `0.1`. | Bar chart: schema-valid vs execution-eligible; E0.4 repeatability metrics table; E0.4 vs E.2 descriptive comparison; validation funnel | Schema validity substantially overestimates execution eligibility. | Descriptive benchmark evidence only; not statistically conclusive across all models/tasks. |
| RQ3 - Zero-trust validation | Prototype 2.1; Prototype 3; Prototype 4; Prototype 4.7-4.10; Prototype 5 final claims | Baseline model false accepts `76`; zero-trust pipeline false accepts `0`; E0.4 pipeline_false_accepts `0`; Mode E.2 pipeline_false_accepts `0`. | Zero-trust architecture diagram; model false accepts vs pipeline false accepts table; gate ordering table; fail-closed decision flow | Deterministic validation reduced unsafe/ambiguous proposal acceptance under tested conditions. | Not a certified robot safety system and not a guarantee of safe execution. |
| RQ4 - Local deployment trade-offs | Prototype 3; Prototype 5 Mode B; Mode C; Mode D; E0.4; Mode E.2 | Local-first supports privacy/offline control and reproducibility, but CPU latency is high. E0.4 mean latency `25377.18 ms`; Mode E.2 mean latency `28359.26 ms`, max `66928.25 ms`. | Local-vs-cloud comparison table; resource profiling table; latency distribution figure; deployment suitability matrix | Local deployment is credible for supervisory/offline proposal generation, not low-latency closed-loop control. | Single local runtime/machine context; no cost model; no GPU/NPU deployment proof. |
| RQ5 - Industrial generalisation boundary | Mode E benchmark; Mode E.1 policy context; Mode E.2 live evaluation; final Mode E claims C15-C17 | Mode E adds 30 industrial commands across six scenario families; Mode E.2 gap `0.5333`; pipeline_false_accepts `0`. | Mode E benchmark composition table; Mode E.1 policy/vocabulary coverage table; E0.4 vs E.2 bar chart; C15-C17 claims table | The central gap persists under a curated industrial benchmark and deterministic policy context. | Does not prove general industrial deployment readiness, production robot safety or universal local SLM reliability. |

## Exact Metrics To Reuse

### E0.4 Repeatability Evidence

| Metric | Value |
|---|---:|
| Runs | 3/3 |
| Request success rate | 1.0 |
| Parse / JSON / schema-valid rate | 0.8667 |
| Semantic-valid rate | 0.2 |
| Safety-valid rate | 0.1 |
| Execution-eligible rate | 0.1 |
| Model false accepts | 16 |
| Pipeline false accepts | 0 |
| Schema-valid minus execution-eligible gap | 0.7667 |
| Overall mean latency | 25377.18 ms |
| Latency standard deviation | 1234.60 ms |

### Mode E.2 Industrial Evidence

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

## Writing Rule

Each results subsection should end by saying what the result supports and what it does not support. The dissertation should not leave boundaries to a final limitations paragraph only.

