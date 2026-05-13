# Prototype 5 Mode E.2 Live Industrial Evaluation

- Run status: COMPLETE_LIVE_INDUSTRIAL_EVALUATION
- Model alias: `Phi-3-mini-4k-instruct-generic-cpu:3`
- Base URL: `http://127.0.0.1:49313`
- Benchmark ID: `prototype5_mode_e_industrial_v1`
- Policy ID: `prototype5_mode_e_industrial_policy_v1`
- Vocabulary ID: `prototype5_mode_e_industrial_vocabulary_v1`
- Total cases: 30

## Metrics

- Request success rate: 1.0
- Parse success rate: 0.7667
- JSON-valid rate: 0.7667
- Schema-valid rate: 0.6333
- Semantic-valid rate: 0.7667
- Safety-valid rate: 0.6667
- Execution-eligible rate: 0.1
- Model false accepts: 16
- Pipeline false accepts: 0
- Schema-valid minus execution-eligible gap: 0.5333
- Mean latency ms: 28359.26
- Median latency ms: 22588.65
- Max latency ms: 66928.25

## E0.4 Descriptive Comparison

- E0.4 schema-valid rate: 0.8667
- E0.4 execution-eligible rate: 0.1
- E0.4 schema-valid minus execution-eligible gap: 0.7667
- E0.4 pipeline false accepts: 0
- E0.4 mean latency ms: 25377.18

E0.4 and E.2 are different benchmark conditions, so differences are descriptive rather than statistically conclusive.

## Boundary

The Mode E.2 result is evidence under a curated industrial benchmark and deterministic policy context, not proof of general industrial deployment readiness.


