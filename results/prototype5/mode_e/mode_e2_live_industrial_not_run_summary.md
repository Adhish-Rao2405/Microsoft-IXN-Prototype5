# Prototype 5 Mode E.2 Live Industrial Evaluation

- Run status: NOT_RUN_FOUNDRY_UNAVAILABLE
- Model alias: `Phi-3-mini-4k-instruct-generic-cpu:3`
- Base URL: `http://127.0.0.1:49313`
- Benchmark ID: `prototype5_mode_e_industrial_v1`
- Policy ID: `prototype5_mode_e_industrial_policy_v1`
- Vocabulary ID: `prototype5_mode_e_industrial_vocabulary_v1`
- Total cases: 0

## Metrics

- Request success rate: NOT_EVALUATED
- Parse success rate: NOT_EVALUATED
- JSON-valid rate: NOT_EVALUATED
- Schema-valid rate: NOT_EVALUATED
- Semantic-valid rate: NOT_EVALUATED
- Safety-valid rate: NOT_EVALUATED
- Execution-eligible rate: NOT_EVALUATED
- Model false accepts: NOT_EVALUATED
- Pipeline false accepts: NOT_EVALUATED
- Schema-valid minus execution-eligible gap: NOT_EVALUATED
- Mean latency ms: NOT_EVALUATED
- Median latency ms: NOT_EVALUATED
- Max latency ms: NOT_EVALUATED

## E0.4 Descriptive Comparison

- E0.4 schema-valid rate: 0.8667
- E0.4 execution-eligible rate: 0.1
- E0.4 schema-valid minus execution-eligible gap: 0.7667
- E0.4 pipeline false accepts: 0
- E0.4 mean latency ms: 25377.18

E0.4 and E.2 are different benchmark conditions, so differences are descriptive rather than statistically conclusive.

## Boundary

The Mode E.2 result is evidence under a curated industrial benchmark and deterministic policy context, not proof of general industrial deployment readiness.

Reason: Foundry Local model discovery succeeded, but the first chat completion did not complete: timed out
