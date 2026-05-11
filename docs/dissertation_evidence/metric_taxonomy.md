# Metric Taxonomy

The project avoids using a single vague "accuracy" metric. Instead, it separates model/API behaviour, syntactic validity, schema validity, semantic validity, safety validity and execution eligibility.

| Metric | Meaning | What it does not prove |
|---|---|---|
| `request_success` | The model/API returned a response. | Does not prove JSON validity, schema validity or safety. |
| `parse_success` | JSON/action content could be recovered. | Does not prove the recovered action is valid. |
| `json_valid` | The response is syntactically valid JSON. | Does not prove the action matches the schema or task. |
| `schema_valid` | The action conforms to the formal schema. | Does not prove semantic correctness or safety. |
| `semantic_validity` | The action matches the intended task meaning. | Does not prove safety. |
| `safety_result` | Deterministic safety gate result. | Does not automatically mean execution should occur without final eligibility checks. |
| `execution_validity` | The action can safely proceed to execution under the defined prototype constraints. | Does not prove production-level robot safety. |
| `latency_ms` | Request or replayed evidence latency in milliseconds. | Does not prove throughput stability or resource efficiency by itself. |
| `throughput_commands_per_min` | Commands processed per minute under the measured workload. | Does not prove general performance on larger or different task sets. |
| `normalized_mean_foundry_cpu_percent_of_total_logical_capacity` | Approximate Foundry process CPU pressure normalised by logical CPU count. | Does not prove GPU/NPU acceleration or hardware-independent performance. |

## Baselines

### Local Baseline
The local baseline uses Foundry Local/local model inference on the same 30-command benchmark.

### Cloud Baseline
The cloud baseline uses `gpt-4o-mini` on the same 30-command benchmark.

### Resource Baseline
Mode D separates replay profiling from live Foundry Local profiling. Replay profiling measures the evidence-processing harness. Live profiling measures the local Foundry serving process for the final 30-command run.

### Comparison Principle
Local and cloud results are compared using the same benchmark scope. The comparison is used to evaluate deployment trade-offs, not to claim universal superiority of either approach.
