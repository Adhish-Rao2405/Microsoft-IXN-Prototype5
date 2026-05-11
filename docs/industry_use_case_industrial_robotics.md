# Industry Use Case: Industrial Robotics and Manufacturing Automation

## Industry

The project is positioned in industrial robotics and manufacturing automation.

## Scenario

A factory operator gives natural-language commands to a local robot workcell assistant. A local SLM served through Microsoft Foundry Local proposes structured robot actions. A deterministic zero-trust validation layer decides whether the proposal is parseable, JSON-valid, schema-valid, semantically valid, safety-valid and execution-eligible.

## Stakeholders

| Stakeholder | Interest |
|---|---|
| Factory operator | Fast and understandable command interface. |
| Automation engineer | Reliable mapping from commands to structured robot actions. |
| Safety engineer | Fail-closed behaviour and auditable rejection reasons. |
| IT/edge deployment team | Local deployment, maintainability, privacy and resource management. |

## Why Local AI Matters

Local AI matters because manufacturing environments may require data locality, reduced cloud dependency, offline resilience, predictable deployment boundaries and cost control. Foundry Local provides an on-device serving route for evaluating these properties.

## Why Zero-Trust Matters

Schema-valid output can still be semantically wrong, unsafe, ambiguous or unsupported. The model must therefore be treated as a proposal generator, not as an authority. Deterministic validation is required before any downstream execution context receives an action.

## Evidence Mapping

| Industrial requirement | Evidence mapping |
|---|---|
| Local deployment feasibility | Foundry Local local inference evidence and Mode D live profile. |
| Reliability of structured actions | Prototype 3 model comparison and Phi recovery evidence. |
| Safety-oriented gating | Prototype 4 zero-trust comparison and safety-latency summary. |
| Deployment trade-off analysis | Mode C local-vs-cloud comparison and Mode D resource profiling. |
| Auditability | Final evidence manifest, claims matrix, limitations matrix and final dashboard. |

## Role of PyBullet If Added

PyBullet should be used only as an optional visual execution-context demonstrator. It can show eligible proposals causing simulated movement and rejected proposals causing no movement with a logged rejection reason. It must not be treated as the core safety proof or as physical robot validation.

## Deployment Limitations Before Real Factory Use

- Larger and more representative benchmarks are required.
- Real robot safety certification is not provided.
- Physical workcell integration and emergency-stop logic are outside the current evidence.
- Human factors and operator feedback loops need further study.
- Hardware-specific resource profiling must be repeated across deployment targets.

## Future Work

- Safety policy DSL.
- Clarification recovery with operator-in-the-loop validation.
- Hybrid local/cloud router with explicit privacy and resilience policies.
- Hardware matrix across CPU, GPU and NPU local targets.
- Expanded industrial benchmark with richer scene states.
