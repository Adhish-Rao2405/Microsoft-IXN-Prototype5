# Dissertation Chapter Build Plan

## Purpose

This is the writing-control plan for converting the Prototype 5 evidence stack into the dissertation. It is not a new experiment plan and does not introduce new modes, benchmarks, Foundry runs or implementation work.

The dissertation should read as a coherent evaluation of local SLM-generated robot task proposals under deterministic validation. It should not read as a chronological build log.

## Core Writing Thesis

Local SLM planning is feasible at the proposal-generation level, but schema validity is not enough. The real contribution is the deterministic zero-trust evaluation framework that treats local model outputs as untrusted proposals and only considers them execution-eligible after parse, schema, semantic, ambiguity, safety and pre-execution checks.

## Recommended Writing Order

| Order | Chapter or section | Reason |
|---:|---|---|
| 1 | Chapter 1 introduction | Locks the thesis, RQs, contribution and scope before detail expands. |
| 2 | Chapter 3 methodology | Controls the system description and prevents a prototype-by-prototype build log. |
| 3 | Chapter 4 results | Inserts evidence after the method is stable. |
| 4 | Chapter 5 discussion | Answers RQs using the evidence already presented. |
| 5 | Chapter 2 literature review | Can then be written to support the actual argument rather than becoming a detached survey. |
| 6 | Chapter 6 conclusion | Final concise synthesis. |

Start with Chapter 1 and Chapter 3.

## Chapter 1 - Introduction

### Argument Flow

1. Introduce the practical setting: local AI and industrial robot task planning.
2. State the problem: model-generated robot plans can be syntactically valid while still being unsafe, ambiguous or semantically invalid.
3. Identify the research gap: local SLM robot planning needs execution-grounded, deterministic validation rather than schema-only evaluation.
4. Define the aim: evaluate local SLM task-proposal generation through Foundry Local under deterministic zero-trust validation.
5. Present RQ1-RQ5.
6. State contributions: benchmark evaluation, zero-trust validation pipeline, local-vs-cloud/resource evidence, repeatability evidence and industrial benchmark extension.
7. Declare scope boundaries early: no real robot execution, no certified safety, no universal industrial deployment claim.

### Evidence To Use

| Evidence item | File |
|---|---|
| RQ-to-evidence map | `docs/prototype5/rq_to_evidence_matrix.md` |
| Core argument map | `docs/prototype5/dissertation_argument_map.md` |
| Examiner-safe claims | `docs/prototype5/examiner_safe_claims_and_boundaries.md` |
| Final evidence dashboard | `results/prototype5/final_evidence_dashboard.md` |
| Claim matrix | `results/prototype5/final_claims_matrix.csv` |

### Figures And Tables

| Figure/table | Purpose |
|---|---|
| Table: Research questions and evidence map | Show the dissertation is structured around RQs, not prototypes. |
| Figure: System evolution diagram | Show Prototype 1 to 5 as one evidence-building sequence. |
| Table: Contributions and boundaries | Pair each contribution with what it does not prove. |

### Allowed Claims

- Foundry Local can support local structured robot task-proposal generation under the tested benchmark conditions.
- Schema-valid outputs are not necessarily execution-ready.
- The dissertation contributes a bounded zero-trust evaluation framework, not a production robot controller.

### Claims To Avoid

- Do not claim that the project built a deployable autonomous robot planner.
- Do not claim production robot safety.
- Do not claim general industrial deployment readiness.
- Do not imply that Mode E makes the benchmark comprehensive.

## Chapter 2 - Background And Related Work

### Argument Flow

1. Explain why language models are attractive for robot task planning.
2. Distinguish plan generation from executable robot control.
3. Review structured output and schema validation as useful but incomplete mechanisms.
4. Position deterministic validation, runtime verification and safety filters as necessary pre-execution controls.
5. Discuss local AI and Foundry Local in terms of privacy, offline operation, reproducibility and deployment control.
6. Connect industrial robotics to the cost of unsafe or ambiguous action proposals.
7. Close with the evaluation gap this dissertation addresses: local SLM outputs need benchmarked, deterministic, execution-grounded validation.

### Evidence To Use

| Evidence item | File |
|---|---|
| Metric taxonomy | `docs/metric_taxonomy.md` |
| Claim boundaries | `docs/claim_boundaries.md` |
| Industry use-case framing | `docs/industry_use_case_industrial_robotics.md` |
| Benchmark card | `docs/benchmark_card.md` |

### Figures And Tables

| Figure/table | Purpose |
|---|---|
| Table: Evaluation concepts | Define parse success, JSON validity, schema validity, semantic validity, safety validity and execution eligibility. |
| Table: Related-work gap mapping | Link literature themes to the dissertation's evaluation framework. |

### Allowed Claims

- Existing model-planning approaches motivate local task-proposal generation but do not remove the need for grounding and validation.
- Schema validation is an important intermediate check, not an execution-readiness guarantee.
- Local deployment has privacy/offline benefits but creates model, latency and hardware constraints.

### Claims To Avoid

- Do not use the literature review as proof that this system is safe.
- Do not present Foundry Local as uniquely solving local robot planning.
- Do not turn Chapter 2 into an annotated bibliography detached from the RQs.

## Chapter 3 - Methodology

### Argument Flow

1. Define the research design as an engineering evaluation plus benchmark-driven empirical study.
2. Explain prototype evolution by research function:
   - Prototype 1: early feasibility context
   - Prototype 2/2.1: schema and deterministic contract
   - Prototype 3: main benchmark and Foundry Local integration
   - Prototype 4: zero-trust execution-grounded validation
   - Prototype 5: final evidence orchestration, repeatability and industrial extension
3. Describe the benchmark design:
   - original 30-command benchmark
   - Mode E 30-command industrial extension
   - clear, ambiguous and unsafe/invalid cases
4. Describe the model/runtime setup:
   - Foundry Local
   - fixed model aliases where tested
   - temperature `0.0` for live evaluation runners where applicable
5. Describe the validation pipeline:
   - request
   - parse
   - JSON validity
   - schema validity
   - semantic validity
   - ambiguity/safety checks
   - execution eligibility
6. Define metrics and false-accept categories.
7. Explain reproducibility controls:
   - configs
   - prompts
   - scripts
   - retained outputs
   - tests
   - final exports
8. State methodological boundaries before results:
   - curated benchmarks
   - single local runtime/machine for key live results
   - no real robot execution
   - deterministic benchmark policy, not certified safety.

### Evidence To Use

| Evidence item | File |
|---|---|
| Evaluation design justification | `docs/prototype5/evaluation_design_justification.md` |
| Reproducibility guide | `docs/prototype5/reproducibility_guide.md` |
| Benchmark representativeness | `docs/prototype5/benchmark_representativeness.md` |
| Mode E benchmark representativeness | `docs/prototype5/mode_e_benchmark_representativeness.md` |
| Mode E.1 policy context | `docs/prototype5/mode_e1_industrial_policy_context.md` |
| Final evaluation protocol | `docs/prototype5/prototype5_final_evaluation_protocol.md` |
| Final figures/tables plan | `docs/prototype5/final_figures_and_tables_plan.md` |

### Figures And Tables

| Figure/table | Purpose |
|---|---|
| Figure: Local SLM planning pipeline | Show natural language to model proposal to deterministic validation. |
| Figure: Zero-trust architecture | Show fail-closed gate structure. |
| Table: Prototype contribution matrix | Explain each prototype's research role. |
| Table: Benchmark composition | Compare original benchmark and Mode E benchmark. |
| Table: Metrics and definitions | Define every metric before Chapter 4 uses it. |

### Allowed Claims

- The methodology evaluates model outputs as untrusted proposals.
- The benchmarks are curated and bounded but sufficient for the dissertation's defined claims.
- Mode E.1 prevents industrial terms from being evaluated as undefined vocabulary.

### Claims To Avoid

- Do not claim the benchmark is representative of all industrial robotics.
- Do not claim the deterministic policy is a certified safety system.
- Do not describe the prototype chain as feature accumulation.
- Do not imply real robot execution was performed.

## Chapter 4 - Results

### Argument Flow

1. Present local structured-output feasibility for RQ1.
2. Present the schema-valid versus execution-eligible gap for RQ2.
3. Present zero-trust false-accept reduction for RQ3.
4. Present local-vs-cloud/resource/latency evidence for RQ4.
5. Present E0.4 repeatability evidence.
6. Present Mode E/E.1/E.2 industrial benchmark evidence for RQ5.
7. End each section with what the result supports and what it does not support.

### Evidence To Use

| Evidence item | File |
|---|---|
| Final model comparison | `results/prototype5/final_model_comparison.csv` |
| Final zero-trust comparison | `results/prototype5/final_zero_trust_comparison.csv` |
| Final safety-latency summary | `results/prototype5/final_safety_latency_summary.csv` |
| Final dissertation metrics | `results/prototype5/final_dissertation_metrics.md` |
| E0.4 repeatability summary | `results/prototype5/mode_e0/full_pipeline_live_repeatability_summary.json` |
| Mode E.2 live industrial summary | `results/prototype5/mode_e/mode_e2_live_industrial_summary.json` |
| Mode E final evidence summary | `docs/prototype5/mode_e_final_evidence_summary.md` |
| Final evidence dashboard | `results/prototype5/final_evidence_dashboard.md` |

### Figures And Tables

| Figure/table | Purpose |
|---|---|
| Table: Foundry Local model benchmark summary | Support RQ1. |
| Figure: Schema-valid vs execution-eligible bar chart | Show the central RQ2 gap. |
| Table: E0.4 repeatability metrics | Show three-run repeatability. |
| Table: Mode E.2 industrial metrics | Show industrial benchmark results. |
| Table: E0.4 vs Mode E.2 descriptive comparison | Show the gap persists without claiming statistical generality. |
| Table: Model false accepts vs pipeline false accepts | Support zero-trust validation. |
| Figure: Validation funnel | Show narrowing from request success to execution eligibility. |
| Table: Local-vs-cloud/resource trade-offs | Support RQ4. |

### Exact Metrics To Use

| Evidence block | Metrics |
|---|---|
| E0.4 | request_success_rate `1.0`; schema_valid_rate `0.8667`; execution_eligible_rate `0.1`; schema_valid_minus_execution_eligible_gap `0.7667`; model_false_accepts `16`; pipeline_false_accepts `0`; mean_latency_ms `25377.18`; latency_std_ms `1234.60`. |
| Mode E.2 | request_success_rate `1.0`; parse_success_rate `0.7667`; json_valid_rate `0.7667`; schema_valid_rate `0.6333`; semantic_valid_rate `0.7667`; safety_valid_rate `0.6667`; execution_eligible_rate `0.1`; model_false_accepts `16`; pipeline_false_accepts `0`; schema_valid_minus_execution_eligible_gap `0.5333`; mean_latency_ms `28359.26`; median_latency_ms `22588.65`; max_latency_ms `66928.25`. |

### Allowed Claims

- Schema-valid rates were substantially higher than execution-eligible rates in both E0.4 and Mode E.2.
- Pipeline false accepts remained `0` under the tested deterministic validation conditions.
- Mode E.2 provides bounded live evidence under a curated industrial benchmark and deterministic policy context.
- Latency constrains deployment interpretation.

### Claims To Avoid

- Do not claim statistical generality across all SLMs or robot tasks.
- Do not claim the zero-trust pipeline guarantees safe execution.
- Do not hide the CPU latency weakness.
- Do not compare E0.4 and Mode E.2 as if they were identical benchmark conditions.

## Chapter 5 - Discussion

### Argument Flow

1. Answer RQ1: local SLM proposal generation is feasible but bounded.
2. Answer RQ2: schema validity overestimates execution eligibility.
3. Answer RQ3: deterministic validation reduces unsafe proposal acceptance under tested conditions.
4. Answer RQ4: local-first deployment has privacy/offline/reproducibility benefits but high latency and model reliability constraints.
5. Answer RQ5: the validation gap persists under Mode E's curated industrial benchmark and deterministic policy context.
6. Explain Microsoft IXN relevance: Foundry Local, local-first deployment and evidence harness.
7. State the contribution: zero-trust evaluation framework for local SLM-generated robot task proposals.
8. Treat limitations as boundaries, not defects.
9. Place future work after the bounded contribution is already clear.

### Evidence To Use

| Evidence item | File |
|---|---|
| Examiner-safe claims and boundaries | `docs/prototype5/examiner_safe_claims_and_boundaries.md` |
| Lee feedback closure map | `docs/prototype5/lee_feedback_closure_map.md` |
| Post-E0 supervisor response | `docs/prototype5/post_e0_supervisor_feedback_response.md` |
| Mode E Lee feedback closure | `docs/prototype5/mode_e_lee_feedback_closure.md` |
| Final limitations matrix | `results/prototype5/final_limitations_matrix.csv` |
| Safety-latency frontier | `results/prototype5/safety_latency_frontier.md` |

### Figures And Tables

| Figure/table | Purpose |
|---|---|
| Table: RQ answers and evidence | Close each RQ explicitly. |
| Table: Deployment suitability matrix | State offline/supervisory fit and closed-loop limitation. |
| Table: Limitations and writing treatment | Show no hidden overclaiming. |
| Table: Lee feedback closure | Show supervisor concerns were addressed. |

### Allowed Claims

- The evidence supports local-first supervisory task-proposal generation, not low-latency closed-loop robot control.
- Deterministic zero-trust validation is the dissertation's central contribution.
- Mode E strengthens benchmark representativeness but remains curated and bounded.

### Claims To Avoid

- Do not claim production readiness.
- Do not claim general local SLM reliability.
- Do not claim certified safety.
- Do not treat high latency as a minor implementation detail; it is a deployment boundary.

## Chapter 6 - Conclusion

### Argument Flow

1. Restate the problem and central claim.
2. Summarise answers to RQ1-RQ5.
3. State the contribution in one paragraph.
4. State the strongest result: schema-valid output rates exceeded execution-eligible rates, and deterministic validation observed zero pipeline false accepts under tested conditions.
5. State final boundaries: curated benchmarks, one local model/runtime context for key live evidence, no real robot execution and no certified safety.
6. End with future work: more models, larger benchmarks, real logs, real robot validation, formal verification and latency-optimised hardware.

### Evidence To Use

| Evidence item | File |
|---|---|
| Dissertation argument map | `docs/prototype5/dissertation_argument_map.md` |
| RQ-to-evidence matrix | `docs/prototype5/rq_to_evidence_matrix.md` |
| Final evidence dashboard | `results/prototype5/final_evidence_dashboard.md` |

### Figures And Tables

No new figure is required in the conclusion. Use this chapter to synthesise, not introduce evidence.

### Allowed Claims

- Local SLM-based robot task planning is feasible as proposal generation under tested conditions.
- Schema-valid output should not be interpreted as execution-ready output.
- The work contributes a bounded, reproducible zero-trust evaluation framework.

### Claims To Avoid

- Do not introduce new evidence.
- Do not soften the limitations.
- Do not end with a product-style deployment claim.

## Final Cross-Chapter Claim Control

| Claim | Where to make it | Where to bound it |
|---|---|---|
| Local structured proposal generation is feasible. | Chapter 1, Chapter 4, Chapter 6 | Chapter 1 scope, Chapter 5 limitations |
| Schema validity is insufficient for execution eligibility. | Chapter 1, Chapter 4, Chapter 5, Chapter 6 | Chapter 4 benchmark caveats, Chapter 5 limitations |
| Deterministic zero-trust validation reduces false accepts under tested conditions. | Chapter 4 and Chapter 5 | Chapter 3 methodology, Chapter 5 limitations |
| Local-first deployment has privacy/offline/reproducibility value. | Chapter 2, Chapter 4, Chapter 5 | Chapter 5 latency/resource discussion |
| Mode E improves industrial benchmark coverage. | Chapter 3, Chapter 4, Chapter 5 | Chapter 5 benchmark limitations |

## Final Stop Rule

No new implementation is needed unless a supervisor explicitly requests it. Any missing item discovered while drafting should first be classified as one of:

1. writing fix
2. table/figure preparation
3. limitation statement
4. future work

Only after that classification should implementation be considered. The default decision is writing-only treatment.

