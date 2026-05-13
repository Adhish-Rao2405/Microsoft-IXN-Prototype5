# Key Results Snapshot

## Core finding

Schema validity is not enough.

Across the evaluated evidence, schema-valid outputs were much more common than execution-eligible outputs.

## E0.4 repeatability

| Metric | Value |
|---|---:|
| Runs | 3/3 |
| Schema-valid rate | 0.8667 |
| Execution-eligible rate | 0.1 |
| Gap | 0.7667 |
| Pipeline false accepts | 0 |
| Mean latency | 25377.18 ms |
| Latency std | 1234.60 ms |

Interpretation:

E0.4 shows the central gap and zero pipeline false-accept result were stable under the fixed repeated live configuration.

## Mode E.2 industrial benchmark

| Metric | Value |
|---|---:|
| Total cases | 30 |
| Schema-valid rate | 0.6333 |
| Execution-eligible rate | 0.1 |
| Gap | 0.5333 |
| Pipeline false accepts | 0 |
| Mean latency | 28359.26 ms |
| Median latency | 22588.65 ms |
| Max latency | 66928.25 ms |

Interpretation:

Mode E.2 shows the schema-valid versus execution-eligible gap persisted under a curated industrial benchmark and deterministic policy context.

## Main supported claim

Local SLMs can generate structured industrial robot task proposals, but deterministic zero-trust validation is required before those proposals can be treated as execution-eligible.

## Main boundary

This is pre-execution benchmark evidence. It is not real robot validation or certified industrial safety evidence.

