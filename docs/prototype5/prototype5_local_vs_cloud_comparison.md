# Prototype 5 Local-vs-Cloud Comparison

## Purpose of Mode C
Compare local Foundry Local inference evidence against a cloud/API baseline on the same 30-command benchmark.

## Microsoft Brief Requirement
Mode C directly addresses the requirement to compare local inference against cloud-based inference while preserving the local-first architecture.

## Method
Prototype 5 combines local Phi recovery evidence with a cloud baseline runner over the same benchmark. The final cloud baseline completed 30/30 commands. If no cloud API key is present and no completed checkpoint is available, cloud rows are emitted as an explicit not-run fallback.

## Benchmark Used
Benchmark status: PRESENT. Total commands: 30.

## Metrics Recorded
request_success, parse_success, json_valid, schema_valid, safety_result, semantic_validity, latency, cost estimate, privacy score and offline resilience score.

## Cloud Status
Cloud baseline status: COMPLETE.

## Results Summary
Local baseline status: PRESENT. Local success rate: 1.0. Cloud success rate: 1.0.
Cloud successful requests: 30/30. Cloud mean latency: 1749.28.
Local mean latency: 7028.0. Local JSON-valid rate: 0.7333. Cloud JSON-valid rate: 1.0.

## Final Interpretation
Cloud inference was faster and more JSON-consistent in this benchmark, but it depended on external connectivity, API availability, provider rate limits and account configuration. Local inference was slower and less JSON-consistent, but supported local execution, data retention and offline resilience.

## Cost Scope
Cost comparison was structurally supported but not quantitatively measured because token-level usage/cost accounting was not implemented.

## Limitations
- Mode C is an evaluation/comparison layer, not a replacement for the local-first architecture.
- The final cloud run completed across all 30 commands, but it required API configuration, request pacing, retry/backoff and checkpointed resume.
- This demonstrates that cloud baselines are operationally dependent on provider availability, rate limits and account configuration.
- Semantic validity is only claimed where explicitly evaluated; Mode C marks semantic_validity as NOT_EVALUATED.
- Cost comparison was structurally supported but not quantitatively measured because token-level usage/cost accounting was not implemented.

## Dissertation Wording Unlocked
- The project includes an explicit local-vs-cloud comparison layer.
- The local Foundry Local architecture can be evaluated against cloud inference under identical benchmark prompts.
- The comparison separates latency, validity, safety, cost structure, privacy and offline resilience.
- Prototype 5 Mode C completed a full 30-command cloud baseline and can support final local-vs-cloud benchmark discussion.
- Cloud inference was faster and more JSON-consistent in this benchmark, while local inference preserved stronger privacy and offline-resilience properties.
