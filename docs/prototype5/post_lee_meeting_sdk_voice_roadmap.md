# Post-Lee Meeting SDK and Voice Roadmap

## Baseline Decision

Prototype 5 remains the final dissertation platform. All future development must be additive, testable, and evidence-producing inside Prototype 5.

The immediate priority is SDK migration followed by bounded voice-control evaluation. Modes F-J are deferred until the SDK/voice layer is stable. The 2 June presentation should focus on the problem, architecture, and demo, not a full technical history.

## Updated Priority Order

Do not start Modes F-J yet.

First stabilise Prototype 5 as the final working platform, migrate from CLI to SDK/API, add bounded voice-control capability, then prepare the 2 June pitch/demo. Modes F-J become controlled extensions after the SDK/voice layer is working.

Required order:

```text
SDK -> Voice -> Presentation/Demo -> Mode H -> Mode I -> Mode F -> Mode G -> Mode J
```

## Phase 1 - SDK Migration

### Goal

Replace CLI-dependent Foundry Local interaction with an SDK/API-based integration.

### Why This Matters

- Lower runtime and memory overhead than shelling out through the CLI.
- Cleaner programmatic model calls.
- Easier access to newer/local model variants.
- More professional Microsoft-aligned engineering story.
- Better demo reliability.

### Deliverables

- `src/prototype5/sdk_client.py` or the final agreed SDK client module name.
- SDK-backed planner interface.
- Compatibility wrapper so old evidence/orchestrator code still works.
- Tests proving CLI and SDK outputs are handled through the same validation pipeline.
- Evidence note: "SDK migration improves integration robustness but does not change the zero-trust validation claim."

### Constraint

This must be done without rewriting Prototype 5. Treat it as a backend adapter, not a new prototype.

## Phase 2 - Voice Control Layer

### Goal

Add a bounded voice-command interface on top of the existing zero-trust planner.

The dissertation value is not "voice robot assistant." The value is:

> Voice input introduces additional ambiguity and transcription risk, therefore zero-trust validation becomes even more necessary.

### Core Voice Scenarios

- "Stop job"
- "Proceed"
- "Pause"
- "Resume"
- "Move the red block to the inspection zone"
- Ambiguous/unsafe examples such as "put that over there" or "go near the operator"

### Deliverables

- Voice input capture/transcription path.
- Typed vs voice command comparison.
- Transcription confidence / ambiguity handling.
- Voice command safety gate.
- Demo script showing a safe stop/proceed workflow.

### Evidence Metrics

- Transcription success rate.
- Command parse rate.
- Schema-valid rate.
- Execution-eligible rate.
- Clarification/rejection rate.
- Latency: speech -> transcript -> model -> gate decision.

### Constraint

Voice control only strengthens the dissertation if the failure modes are evaluated. A polished voice demo with no evaluation is weaker than a simple typed demo with strong evidence.

## Phase 3 - 2 June Presentation and Demo Prep

The 5-minute pitch should stay simple.

### 1. Problem

Local SLMs can produce plausible robot plans, but schema-valid output is not enough for safe execution.

### 2. Approach

Prototype 5 treats model outputs as untrusted proposals and passes them through deterministic zero-trust gates.

### 3. Demo

Show a command passing through the pipeline, then show an unsafe/ambiguous command being rejected before execution.

### 4. Result

The key finding is not that the model is perfect. The key finding is that the validation pipeline prevents unsafe acceptance under tested conditions.

### 5. Next Step

SDK migration and voice-control testing extend the same zero-trust architecture without resetting the project.

Do not overload the presentation with Prototypes 1-5 history. Mention them only as the development path that led to Prototype 5.

## Modes F-J: Add Later, Inside Prototype 5

These remain future additive modes, not immediate work.

| Mode | Name | Purpose | Priority |
| --- | --- | --- | --- |
| Mode F | Adversarial Robustness Benchmark | Test prompt injection, unsafe phrasing, misleading commands | High after SDK/voice |
| Mode G | Policy Complexity Evaluation | Test how validation behaves as rules become more complex | Medium |
| Mode H | Ambiguity / Clarification Recovery | Evaluate clarification loops and reject/ask decisions | High |
| Mode I | Human-in-the-Loop Decision Tiering | Add operator approval tiers: auto-reject, clarify, human review, executable | High |
| Mode J | Local Foundry Zero-Trust App/Dashboard | Demo-facing UI for evidence, gating decisions, and model outputs | Medium-high |

Mode J is presentation polish unless it visualises already-validated pipeline results. It should not be started before the SDK/voice layer is stable.

## Immediate Working Order

```text
1. Freeze current Prototype 5 baseline
2. Create Phase 1 spec document
3. Run SDK/API discovery spike
4. Implement SDK client
5. Add backend adapter
6. Run smoke pipeline
7. Run 30-command SDK benchmark
8. Integrate into orchestrator
9. Full audit and commit
10. Only then begin Phase 2 voice control
```

## Governance Rule

All future development must follow:

```text
controlled migration
measurable gates
no scope creep
evidence-first implementation
no new claims without reproducible artefacts
```
