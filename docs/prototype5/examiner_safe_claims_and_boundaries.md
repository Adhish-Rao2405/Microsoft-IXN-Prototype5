# Examiner-Safe Claims And Boundaries

## Purpose

This file defines the wording discipline for the dissertation. The project has enough evidence for a strong bounded claim; the main remaining risk is overclaiming.

## Core Claim

Schema validity is necessary but insufficient for local SLM-based robot task planning. Model outputs should be treated as untrusted proposals and passed through deterministic validation before being considered execution-eligible.

## Safe Claims

| Claim area | Examiner-safe wording | Evidence |
|---|---|---|
| Local feasibility | Foundry Local can support local generation of structured robot task proposals under the tested benchmark conditions. | Prototype 3 evidence; Prototype 5 Mode B; final model comparison outputs. |
| Validity gap | Across the tested benchmarks, schema-valid output rates were substantially higher than execution-eligible rates. | E0.4 gap `0.7667`; Mode E.2 gap `0.5333`. |
| Zero-trust validation | Deterministic validation prevented measured model-level false accepts from becoming pipeline-level false accepts under the tested policy and benchmark conditions. | Prototype 4 false-accept comparison; E0.4 pipeline_false_accepts `0`; Mode E.2 pipeline_false_accepts `0`. |
| Local deployment | Local-first evaluation is relevant for privacy, offline operation and reproducibility, but CPU latency constrains the use case. | Mode C, Mode D, E0.4 and Mode E.2 latency/resource evidence. |
| Industrial relevance | Mode E improves scenario coverage and supports bounded industrial relevance by adding curated industrial commands plus deterministic vocabulary/policy context. | Mode E, E.1 and E.2 final evidence. |

## Unsafe Claims To Avoid

| Do not write | Use instead |
|---|---|
| The system guarantees safe robot execution. | The pipeline observed zero pipeline false accepts under the tested benchmark and policy conditions. |
| The local model is ready for industrial robot deployment. | The local model can generate task proposals that require deterministic validation before any execution decision. |
| Mode E proves industrial generalisation. | Mode E improves scenario coverage and supports bounded industrial relevance under a curated benchmark. |
| Foundry Local solves robot planning. | Foundry Local enables local SLM proposal generation, but validation and deployment constraints remain central. |
| The benchmark is comprehensive. | The benchmark is curated and balanced for dissertation evaluation, not exhaustive industrial coverage. |
| The safety policy is certified. | The safety policy is deterministic benchmark-validation context, not a certified industrial robot safety system. |

## Latency Boundary

The latency profile constrains the deployment interpretation. E0.4 mean latency was `25377.18 ms`. Mode E.2 mean latency was `28359.26 ms` and maximum latency was `66928.25 ms` on the tested CPU local runtime. Therefore, the credible deployment framing is local-first supervisory task proposal and validation, not low-latency closed-loop robot control.

## Limitations To Handle In Writing Only

| Limitation | Dissertation treatment |
|---|---|
| Single local model family / alias | State as model coverage limitation. |
| Single machine/runtime | State as deployment context limitation. |
| Curated benchmark | State as benchmark representativeness limitation. |
| No real robot execution | State that this is pre-execution validation evidence. |
| No certified safety standard compliance | State that the policy is deterministic but not certified. |
| High CPU latency | Frame as supervisory/offline planning only. |
| No large-scale statistical significance | State comparisons are descriptive. |
| Prompt sensitivity | Mention as future work. |
| No human operator study | Mention as future work. |
| No formal verification proof | Mention as future work. |

## Final Implementation Decision

Do not add more implementation now. More modes would increase reproducibility burden and narrative complexity without improving the core dissertation argument. The remaining work is writing, figure/table preparation and consistency checking.

