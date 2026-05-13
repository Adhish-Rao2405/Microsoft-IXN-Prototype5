# Prototype 5 Final Dissertation Metrics

Prototype 5 consolidates existing evidence only. It does not introduce new inference, planning, or robot execution.

Prototype 1 is treated as optional early feasibility/context evidence. Missing Prototype 1 audit files are not counted as missing core proof and do not change the final model, zero-trust, local-vs-cloud, resource, quantisation, or physical-execution metrics below.

- Proven claims: 14
- Context-only claims: 1
- Missing evidence claims: 2
- Quantisation evidence: COMPLETE_CUSTOM_EVIDENCE
- Phi-family evidence: PRESENT
- Mode C local-vs-cloud status: COMPLETE
- Cloud baseline status: COMPLETE
- Mode D resource profiling status: COMPLETE_LIVE_PROFILE

## Final Model Comparison
| model                          | commands_evaluated | schema_valid_rate | execution_eligible_rate | false_accept_count | false_accept_rate | false_reject_count | false_reject_rate | correct_reject_count | mean_latency_ms | evidence_status |
| ------------------------------ | ------------------ | ----------------- | ----------------------- | ------------------ | ----------------- | ------------------ | ----------------- | -------------------- | --------------- | --------------- |
| foundry:qwen2.5-0.5b:cpu       | 30                 | 0.4667            | 0.0667                  | 8                  | 0.2667            | 0                  | 0.0               | 9                    | 3616.5          | PRESENT         |
| foundry:qwen2.5-1.5b:cpu       | 30                 | 0.7667            | 0.1                     | 10                 | 0.3333            | 0                  | 0.0               | 7                    | 8299.1          | PRESENT         |
| foundry:qwen2.5-coder-0.5b:cpu | 30                 | 0.8333            | 0.1333                  | 12                 | 0.4               | 0                  | 0.0               | 5                    | 2921.7          | PRESENT         |
| foundry:qwen2.5-coder-1.5b:cpu | 30                 | 0.9333            | 0.1667                  | 15                 | 0.5               | 0                  | 0.0               | 2                    | 8329.5          | PRESENT         |

## Final Zero-Trust Comparison
| pipeline_mode        | execution_records | unsafe_false_accepts | unsafe_false_accept_rate | safety_interpretation                                            | evidence_status |
| -------------------- | ----------------- | -------------------- | ------------------------ | ---------------------------------------------------------------- | --------------- |
| baseline_trust_model | 120               | 76                   | 0.6333                   | Unsafe false accepts observed in available execution records.    | PRESENT         |
| zero_trust_pipeline  | 120               | 0                    | 0.0                      | No unsafe false accepts observed in available execution records. | PRESENT         |

## Final Safety-Latency Summary
| configuration               | false_accepts | mean_latency_ms   | safety_interpretation               | evidence_status |
| --------------------------- | ------------- | ----------------- | ----------------------------------- | --------------- |
| schema_only                 | 76            | 5785.788888888889 | Unsafe false accepts observed.      | PRESENT         |
| schema_semantic             | 4             | 6148.833333333333 | Unsafe false accepts observed.      | PRESENT         |
| schema_semantic_uncertainty | 0             | 6152.357142857143 | Zero unsafe false accepts observed. | PRESENT         |
| full_zero_trust             | 0             | 6152.357142857143 | Zero unsafe false accepts observed. | PRESENT         |

## Final Extension Summary
| phase | extension_name                    | key_metric              | key_result                                         | evidence_status |
| ----- | --------------------------------- | ----------------------- | -------------------------------------------------- | --------------- |
| 4.7   | Ambiguity-adaptive gating         | commands and decisions  | 30 commands; EXECUTE 24; CLARIFY 4; REJECT 2       | PRESENT         |
| 4.8   | Simulated clarification recovery  | recovery rate           | 5 clarification cases; recovery rate 1.00          | PRESENT         |
| 4.9   | Formal safety specification audit | unsafe rejection rate   | 18 formal safety cases; unsafe rejection rate 1.00 | PRESENT         |
| 4.10  | Extension audit and freeze        | audit and freeze status | audit PASS; freeze PASS                            | PRESENT         |

## Quantisation Evidence
Complete custom precision evidence was recovered for FP16, INT8 and INT4 when `quantisation_status` is `COMPLETE_CUSTOM_EVIDENCE`. Built-in Foundry Local catalogue precision metadata remains missing.

## Mode D Resource Profiling
- Mode D status: COMPLETE_LIVE_PROFILE
- Live Foundry profile: PRESENT
- Live Foundry successful requests: 30/30
- Live Foundry JSON-valid rate: 0.8
- Live Foundry mean latency: 7896.97 ms
- Live Foundry normalized mean CPU: 48.31%

## Mode E.2 Live Industrial Benchmark
- Mode E.2 status: COMPLETE_LIVE_INDUSTRIAL_EVALUATION
- schema_valid_rate = 0.6333
- execution_eligible_rate = 0.1
- schema_valid_minus_execution_eligible_gap = 0.5333
- pipeline_false_accepts = 0
- mean_latency_ms = 28359.26
- Boundary: Mode E.2 is bounded to a curated industrial benchmark, deterministic policy context, single local model/runtime and single machine. It is not proof of general industrial deployment readiness and does not prove production robot safety.

## Limitations
| limitation                                | status  | safe_interpretation                                                                                                              |
| ----------------------------------------- | ------- | -------------------------------------------------------------------------------------------------------------------------------- |
| custom FP16/INT8/INT4 precision artifacts | PRESENT | Explicit Prototype 5 custom metadata proves FP16, INT8, and INT4 precision artifacts.                                            |
| built-in Foundry Local precision metadata | MISSING | Built-in Foundry catalogue precision metadata is still not proven.                                                               |
| Phi-family evaluation                     | PRESENT | Phi-family Foundry Local response evidence is present; semantic validity remains NOT_EVALUATED.                                  |
| cloud-vs-local comparison                 | PRESENT | Mode C local-vs-cloud benchmark evidence is present; semantic equivalence is not claimed.                                        |
| GPU/NPU profiling                         | LIMITED | Mode D records hardware visibility, but GPU/NPU counters were NOT_DETECTED/NOT_DETECTED; no hardware acceleration claim is made. |
| memory footprint measurement              | PRESENT | Mode D live Foundry profiling records process memory deltas for the measured local run.                                          |
| physical robot execution                  | MISSING | Prototype 5 consolidates simulation and execution-record evidence only.                                                          |
