# Dissertation Argument Map

## Core Thesis

This dissertation evaluates whether local small language models, deployed through Microsoft Foundry Local, can produce robot task plans that are not merely syntactically valid but also safe, semantically grounded and execution-eligible under deterministic zero-trust validation.

The central claim is that schema validity is necessary but insufficient for industrial robot task planning. Local SLM outputs must be treated as untrusted proposals and filtered through deterministic validation before they can be considered execution-eligible.

This should not be framed as a product claim that a local robot planner has been built. The contribution is a bounded evaluation framework and evidence base for local-first robot task-proposal generation.

## Research Questions

| RQ | Question | Primary answer |
|---|---|---|
| RQ1 | Can a local SLM deployed through Microsoft Foundry Local generate structured robot task proposals from natural-language commands? | Yes, but only at proposal level. Structured output does not imply execution readiness. |
| RQ2 | To what extent does schema validity differ from true execution eligibility in local SLM-generated robot task plans? | Substantially. E0.4 showed schema_valid_rate `0.8667` versus execution_eligible_rate `0.1`; Mode E.2 showed schema_valid_rate `0.6333` versus execution_eligible_rate `0.1`. |
| RQ3 | Can deterministic zero-trust validation reduce unsafe or ambiguous model proposals before execution? | Yes under the tested benchmark and policy assumptions. Pipeline false accepts remained `0` in the key evaluated settings. |
| RQ4 | What are the practical trade-offs of local-first SLM planning compared with cloud or unconstrained model use, particularly in latency, privacy, reproducibility and reliability? | Local-first deployment supports privacy/offline control and reproducibility, but CPU latency and model reliability constrain the deployment framing to supervisory or offline proposal generation. |
| RQ5 | Does the schema-valid versus execution-eligible gap persist under a broader industrial benchmark with domain-specific vocabulary and policy context? | Yes under Mode E.2 tested conditions. The gap was `0.5333` and pipeline_false_accepts remained `0`, bounded to the curated industrial benchmark and deterministic policy context. |

## Prototype Evidence Chain

| Prototype or mode | Dissertation role | Evidence contribution |
|---|---|---|
| Prototype 1 | Early feasibility context | Demonstrates early local model-to-action direction, but should not be used as a core proof dependency. |
| Prototype 2 / 2.1 | Contract and validation design | Establishes schema contracts and deterministic validation direction. |
| Prototype 3 | Main local model benchmark | Provides the original benchmark basis for structured proposal generation and validity-gap measurement. |
| Prototype 4 | Zero-trust validation evidence | Shows model-level false accepts can be blocked before becoming pipeline-level false accepts under tested conditions. |
| Prototype 5 Mode A-D | Final evidence orchestration and deployment trade-offs | Consolidates prior evidence, adds quantisation/Phi recovery, local-vs-cloud comparison and resource profiling. |
| Prototype 5 Mode E0/E0.4 | Reproducibility and repeatability hardening | Adds three-run full live repeatability evidence for the original action-envelope path. |
| Prototype 5 Mode E/E.1/E.2 | Industrial benchmark extension | Adds balanced industrial benchmark coverage, deterministic vocabulary/policy context and bounded live industrial evaluation. |

## Main Results To Anchor Chapter 4

| Evidence block | Key result | Dissertation use |
|---|---|---|
| E0.4 full live repeatability | request_success_rate `1.0`, schema_valid_rate `0.8667`, execution_eligible_rate `0.1`, gap `0.7667`, pipeline_false_accepts `0`, mean latency `25377.18 ms` | Shows the central validation gap is stable across three live runs under the original benchmark conditions. |
| Mode E.2 live industrial benchmark | request_success_rate `1.0`, schema_valid_rate `0.6333`, execution_eligible_rate `0.1`, gap `0.5333`, pipeline_false_accepts `0`, mean latency `28359.26 ms`, max latency `66928.25 ms` | Shows the validation gap persists under a curated industrial benchmark and deterministic policy context. |
| Prototype 4 zero-trust comparison | baseline model false accepts `76`, zero-trust pipeline false accepts `0` | Supports the argument that deterministic validation prevents unsafe proposals from being treated as execution-eligible under tested conditions. |
| Mode C and Mode D | Local-vs-cloud/resource trade-off and live resource profile | Supports the deployment discussion: local-first has privacy and control benefits, but latency/resource costs constrain the use case. |

## Chapter Argument Flow

### Chapter 1 - Introduction

Open with the practical problem: local SLMs can generate robot task proposals, but a syntactically valid plan may still be unsafe, ambiguous or semantically wrong. Define the aim as evaluating local Foundry Local SLM task planning under deterministic validation, not building a production robot controller.

Use the five RQs above. State the contribution as a zero-trust evaluation framework with benchmark, validation, repeatability and industrial-extension evidence.

### Chapter 2 - Background And Related Work

Organise the review around the argument, not around a list of papers:

- LLM/SLM robot task planning can produce plans but requires grounding.
- Schema validation is useful but insufficient.
- Robot safety and verification require deterministic constraints before execution.
- Local AI and Foundry Local matter for privacy, offline operation and deployment control.
- Industrial robotics raises the cost of unsafe or ambiguous action proposals.
- Benchmark-driven evaluation is appropriate when claims are bounded and traceable.

### Chapter 3 - Methodology

Explain the evaluation design:

- engineering evaluation plus benchmark-driven empirical study
- prototype evolution from feasibility to final evidence orchestration
- original 30-command benchmark and Mode E 30-command industrial extension
- Foundry Local model/runtime setup, fixed prompts and temperature `0.0` where live runners apply
- parse, schema, semantic, ambiguity, safety and pre-execution validation gates
- metrics: request success, parse success, JSON validity, schema validity, execution eligibility, false accepts and latency
- reproducibility controls: configs, scripts, results, tests and final evidence exports

### Chapter 4 - Results

Present results by research question rather than by build chronology:

- structured local proposal generation
- schema-valid versus execution-eligible gap
- deterministic zero-trust false-accept reduction
- local-vs-cloud/resource/latency trade-offs
- E0.4 repeatability
- Mode E/E.1/E.2 industrial extension

### Chapter 5 - Discussion

Answer each RQ directly. The strongest discussion point is that local generation is feasible but insufficient: the model output remains an untrusted proposal until deterministic validation accepts it. Discuss latency honestly as a deployment boundary. Discuss Mode E as bounded industrial relevance, not universal generalisation.

### Chapter 6 - Conclusion

Conclude that local SLM-based robot task planning is feasible as proposal generation, but schema-valid output should not be interpreted as execution-ready output. Across the tested benchmarks, deterministic zero-trust validation narrowed a larger set of schema-valid proposals into a much smaller execution-eligible subset, with zero pipeline false accepts observed under tested conditions.

## Examiner-Safe Contribution Narrative

The contribution of this dissertation is not a new robot controller or a claim that local SLMs are ready for autonomous industrial deployment. Instead, the contribution is a zero-trust evaluation framework for local SLM-generated robot task proposals. The framework demonstrates that schema validity alone is an insufficient measure of readiness, since many schema-valid outputs remain semantically invalid, unsafe, ambiguous or otherwise unsuitable for execution. By combining Foundry Local deployment, benchmark-based evaluation, deterministic validation, repeatability analysis and industrial benchmark extension, the dissertation provides bounded evidence that local-first task planning becomes more credible when model outputs are treated as untrusted proposals rather than executable commands.

## Implementation Decision

No further implementation is needed for the dissertation argument at this stage. Remaining weaknesses should be handled as limitations and future work unless a supervisor explicitly requests new experiments.

