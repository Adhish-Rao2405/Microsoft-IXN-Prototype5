# Post-E0 Gap Register

This register identifies remaining risks after Mode E0. The purpose is to prevent feature creep and keep the dissertation examiner-safe before any new implementation mode is considered.

| Gap | Severity | Why it matters | Current mitigation | Whether to address before dissertation submission | Decision |
|---|---|---|---|---|---|
| 30-command benchmark is small. | HIGH | A small benchmark limits statistical generalisation. | The benchmark is explicitly framed as fixed, controlled and exploratory. | Address in writing. | ADDRESS IN WRITING |
| Benchmark may not cover full industrial task diversity. | HIGH | Industrial robot workcells have wider command and safety variation than the benchmark. | Command categories include clear, moderate and high ambiguity cases. | Address in writing and future work. | ADDRESS IN WRITING |
| Single model alias. | HIGH | E0.4 repeatability uses one local Phi-3-mini model alias. | Other Prototype 5 evidence includes broader model and local-vs-cloud context. | Address in writing; do not add more live model runs now unless required. | ADDRESS IN WRITING |
| Single machine/runtime context. | MEDIUM | Latency/resource results are host-specific. | Mode D and E0.4 record local resource/runtime caveats. | Address in writing. | ADDRESS IN WRITING |
| No real robot execution. | HIGH | Execution eligibility is not equivalent to physical robot safety. | The dissertation frames execution as eligibility under deterministic validation, not physical actuation. | Address strongly in limitations. | ADDRESS IN WRITING |
| Deterministic safety policy is handcrafted and limited. | HIGH | A limited policy can miss hazards outside its rules. | Claim boundaries restrict conclusions to the defined validation policy. | Address in writing and future work. | ADDRESS IN WRITING |
| Semantic validity remains low. | HIGH | The model often produces structurally valid but semantically unsuitable outputs. | This is central evidence for zero-trust validation. | Address in results and discussion. | ADDRESS IN WRITING |
| Execution eligibility remains low. | HIGH | Low eligibility limits practical usefulness of direct local SLM proposals. | The architecture treats outputs as proposals, not commands. | Address in results and discussion. | ADDRESS IN WRITING |
| Local latency is high. | MEDIUM | Mean latency around 25.38s is problematic for interactive deployment. | Latency is reported as a deployment trade-off rather than hidden. | Address in results; no new optimisation implementation now. | ADDRESS IN WRITING |
| Cloud/local comparison may be affected by API/model differences. | MEDIUM | Differences may reflect model/provider/API conditions, not only local-vs-cloud deployment. | Mode C is bounded to current benchmark and model/API conditions. | Address in writing. | ADDRESS IN WRITING |
| Resource profiling is useful but not full deployment benchmarking. | MEDIUM | CPU/memory snapshots do not prove deployability across factory hardware. | Mode D reports host-specific resource evidence and missing GPU/NPU limits. | Address in writing; defer hardware matrix. | DEFER AS FUTURE WORK |
