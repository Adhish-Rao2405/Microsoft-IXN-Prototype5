# Cloud Baseline Run Card

| Field | Value |
|---|---|
| Model / run name | Cloud baseline |
| Model alias if available | gpt-4o-mini |
| Local/cloud mode | Cloud |
| Serving layer | External API baseline |
| Benchmark used | Same 30-command benchmark as local Mode C comparison |
| Date/source file if available | `results/prototype5/mode_c/local_vs_cloud_summary.json`; checkpoint CSV |
| Temperature / max tokens if available | not available in detected evidence |
| Hardware if available | not applicable / provider-managed |
| Request success | 30/30 |
| JSON-valid rate | 100.00% |
| Schema-valid rate | not available in detected evidence |
| Execution-eligible rate | not available in detected evidence |
| Model-level false accepts | not available in detected evidence |
| Pipeline-level false accepts | not available in detected evidence |
| Mean latency | 1749.28 ms |
| Known failure modes | Requires network/API availability, account configuration, request pacing and retry/backoff. |
| Caveats | Semantic equivalence and quantitative cost are not claimed. |
