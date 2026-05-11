# Resource Profile Run Card

| Field | Value |
|---|---|
| Model / run name | Mode D live Foundry Local resource profile |
| Model alias if available | Phi-3-mini-4k-instruct-generic-cpu:3 |
| Local/cloud mode | Local |
| Serving layer | Foundry Local serving process |
| Benchmark used | 30-command benchmark |
| Date/source file if available | `results/prototype5/mode_d/mode_d_final_evidence_summary.json`; live profile CSV |
| Temperature / max tokens if available | not available in detected evidence |
| Hardware if available | 16 logical CPU cores; GPU/NPU not detected in Mode D |
| Request success | 30/30 |
| JSON-valid rate | 80.00% |
| Schema-valid rate | not available in detected evidence |
| Execution-eligible rate | not available in detected evidence |
| Model-level false accepts | not available in detected evidence |
| Pipeline-level false accepts | not available in detected evidence |
| Mean latency | 7896.97 ms |
| Known failure modes | JSON validity below 100%; CPU pressure observed; GPU/NPU counters not detected. |
| Caveats | Hardware-specific operational profile, not a general hardware benchmark. |
