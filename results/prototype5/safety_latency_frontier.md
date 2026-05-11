# Safety-Latency Frontier

This artefact summarises the conceptual and evidence-backed trade-off between validation strictness, latency overhead, rejection behaviour and false-accept risk.

Measured per-gate latency overhead is not available in the detected final evidence. Where only mean configuration latency is available, the table records that value and labels missing values as `MISSING`.

| Configuration | Gates enabled | Expected safety effect | False accept rate if available | Rejection rate if available | Latency overhead if available | Evidence source | Caveat |
|---|---|---|---|---|---|---|---|
| schema_only | schema validator | Lowest validation strictness; unsafe false accepts remain possible. | MISSING | MISSING | 5785.788888888889 | results/prototype5/final_safety_latency_summary.csv | Mean latency is available, but per-gate overhead is not separated. |
| schema_plus_semantic | schema validator; semantic validator | Reduces semantically invalid accepts compared with schema alone. | MISSING | MISSING | 6148.833333333333 | results/prototype5/final_safety_latency_summary.csv | False-accept count exists in source summary, but rate/rejection data are not fully available here. |
| schema_plus_semantic_plus_uncertainty | schema validator; semantic validator; uncertainty/ambiguity gate | Blocks ambiguous proposals that should not proceed directly to execution. | MISSING | MISSING | 6152.357142857143 | results/prototype5/final_safety_latency_summary.csv | Measured mean latency is available; rejection rate is not available in this final CSV. |
| full_zero_trust | schema validator; semantic validator; uncertainty gate; safety gate; execution eligibility | Highest evaluated strictness; zero unsafe false accepts observed in available records. | 0.0 where mapped to zero-trust pipeline evidence | MISSING | 6152.357142857143 | results/prototype5/final_safety_latency_summary.csv; results/prototype5/final_zero_trust_comparison.csv | This is prototype evidence, not production robot safety certification. |
| full_zero_trust_plus_clarification_future_work | full zero-trust; clarification recovery loop | Expected to recover some ambiguous valid commands without relaxing safety gates. | MISSING | MISSING | MISSING | Prototype 4 clarification recovery summary where available | Future-work configuration; do not treat as measured final frontier. |
