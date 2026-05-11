# Benchmark Card: LocalSLM-IndustrialRobot-ZT-Bench v0.1

## Purpose

LocalSLM-IndustrialRobot-ZT-Bench v0.1 is a controlled ambiguity-stratified benchmark for evaluating whether local SLMs can generate reliable industrial robot action proposals and whether zero-trust validation prevents unsafe or semantically invalid proposals from reaching execution.

## Scope

| Field | Value |
|---|---|
| Benchmark size | 30 commands in the detected final local/cloud and Phi evidence. |
| Difficulty bands | clear, moderate ambiguity, high ambiguity. |
| Domain | Industrial robot task planning. |
| Command scope | Natural-language workcell commands converted into structured action proposals. |
| Action scope | Move/place-style industrial workcell actions, rejection, clarification or no-execution decisions depending on validity. |
| Objects/zones assumed | Workcell objects such as cubes/parts/trays/zones as represented by the benchmark and prototype evidence. |
| Gold labels / gold intent concept | Expected command intent and allowed execution outcome as defined by prior-prototype benchmark evidence. |

## Scoring Rules

The benchmark is scored through layered checks rather than one aggregate accuracy number:

- request success
- parse success
- JSON validity
- schema validity
- semantic validity where evaluated
- safety validity
- execution eligibility
- false accepts, false rejects and correct rejects where available
- latency and resource metrics where measured

## Validation Layers

The intended validation chain is:

1. raw model response
2. parser
3. JSON validity check
4. schema validator
5. semantic validator
6. uncertainty/ambiguity gate
7. deterministic safety gate
8. execution eligibility decision
9. evidence logger

## Known Limitations

- The benchmark is small and controlled.
- The benchmark is designed for failure-mode discovery and comparative engineering evaluation, not population-level statistical inference.
- Semantic validity is only claimed where source evidence explicitly evaluates it.
- Physical robot execution is not proven by this benchmark.
- Local-vs-cloud results are tied to the measured models, API baseline and host conditions.

## Extension Path

Future benchmark extensions should add more object types, richer manipulation tasks, explicit scene-state variation, operator clarification turns, larger ambiguity strata, hardware matrix coverage and repeat runs across more model families.

## Statistical Humility

The benchmark is not statistically powered for population-level inference. Its purpose is controlled engineering comparison and failure-mode discovery. Multi-model consistency strengthens the observed pattern but does not remove the need for larger future benchmarks.
