# Prototype 5 Dissertation Results Summary

This summary is generated from existing evidence files and should be cited with the accompanying evidence manifest.

## Prototype 3 Model Evidence
| model                          | commands_evaluated | schema_valid_rate | execution_eligible_rate | false_accept_count | false_accept_rate | false_reject_count | false_reject_rate | correct_reject_count | mean_latency_ms | evidence_status |
| ------------------------------ | ------------------ | ----------------- | ----------------------- | ------------------ | ----------------- | ------------------ | ----------------- | -------------------- | --------------- | --------------- |
| foundry:qwen2.5-0.5b:cpu       | 30                 | 0.4667            | 0.0667                  | 8                  | 0.2667            | 0                  | 0.0               | 9                    | 3616.5          | PRESENT         |
| foundry:qwen2.5-1.5b:cpu       | 30                 | 0.7667            | 0.1                     | 10                 | 0.3333            | 0                  | 0.0               | 7                    | 8299.1          | PRESENT         |
| foundry:qwen2.5-coder-0.5b:cpu | 30                 | 0.8333            | 0.1333                  | 12                 | 0.4               | 0                  | 0.0               | 5                    | 2921.7          | PRESENT         |
| foundry:qwen2.5-coder-1.5b:cpu | 30                 | 0.9333            | 0.1667                  | 15                 | 0.5               | 0                  | 0.0               | 2                    | 8329.5          | PRESENT         |

## Prototype 4 Zero-Trust Evidence
| pipeline_mode        | execution_records | unsafe_false_accepts | unsafe_false_accept_rate | safety_interpretation                                            | evidence_status |
| -------------------- | ----------------- | -------------------- | ------------------------ | ---------------------------------------------------------------- | --------------- |
| baseline_trust_model | 120               | 76                   | 0.6333                   | Unsafe false accepts observed in available execution records.    | PRESENT         |
| zero_trust_pipeline  | 120               | 0                    | 0.0                      | No unsafe false accepts observed in available execution records. | PRESENT         |

## Prototype 4 Extension Evidence
| phase | extension_name                    | key_metric              | key_result                                         | evidence_status |
| ----- | --------------------------------- | ----------------------- | -------------------------------------------------- | --------------- |
| 4.7   | Ambiguity-adaptive gating         | commands and decisions  | 30 commands; EXECUTE 24; CLARIFY 4; REJECT 2       | PRESENT         |
| 4.8   | Simulated clarification recovery  | recovery rate           | 5 clarification cases; recovery rate 1.00          | PRESENT         |
| 4.9   | Formal safety specification audit | unsafe rejection rate   | 18 formal safety cases; unsafe rejection rate 1.00 | PRESENT         |
| 4.10  | Extension audit and freeze        | audit and freeze status | audit PASS; freeze PASS                            | PRESENT         |
