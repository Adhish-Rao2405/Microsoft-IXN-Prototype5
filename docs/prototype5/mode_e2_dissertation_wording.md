# Prototype 5 Mode E.2 Dissertation Wording

## Methodology Wording

Prototype 5 Mode E.2 extended the live evidence path to the curated Mode E industrial benchmark. The live runner was gated by the Mode E.1 policy audit and refused to run unless the deterministic industrial vocabulary and policy context reached `COMPLETE_POLICY_CONTEXT`.

The runner loaded the Mode E benchmark, the Mode E.1 vocabulary, the Mode E.1 policy rules and the repository-local action-envelope prompt. Model temperature was fixed at `0.0`. Each model response was recorded before deterministic validation was applied.

## Results Wording

Where live Foundry Local was available, Mode E.2 reported request success, JSON validity, schema validity, deterministic policy decisions, execution eligibility, false accepts and latency for the curated industrial benchmark. Where Foundry Local was unavailable, the run was recorded as `NOT_RUN_FOUNDRY_UNAVAILABLE` rather than treated as negative model evidence.

## Discussion Wording

Mode E.2 tests whether the schema-valid versus execution-eligible gap remains visible when the benchmark moves from the original controlled command set to industrially motivated commands. The comparison with E0.4 is descriptive because the two evaluations use different benchmark conditions.

## Limitations Wording

The limitations are:

- Curated benchmark rather than real industrial logs.
- Minimal handcrafted industrial vocabulary.
- Single local model unless more are explicitly tested.
- Single runtime/machine setup unless more are explicitly tested.
- No real robot execution.
- No certified safety layer.
- Descriptive comparison only.

Mode E.2 should not be used to claim production safety, general industrial deployment readiness or universal local model reliability.
