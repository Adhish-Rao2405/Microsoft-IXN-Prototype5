# Evaluation Design Justification

## 1. Evaluation Aim

The evaluation is not designed to prove that a local SLM is a safe robot controller. It is designed to measure whether a local SLM can generate structured robot action proposals and whether deterministic validation can prevent schema-valid but unsafe or semantically invalid proposals from being treated as execution-eligible.

## 2. Why Local SLM Structured-Output Reliability Is Evaluated

Industrial robot task planning needs machine-readable action proposals before any downstream validation can occur. A local SLM that cannot reliably produce parseable structured output is not useful for this workflow, regardless of later safety logic.

## 3. Why Request Success, Parse Success and JSON Validity Are Separated

Request success measures whether an inference call returned. Parse success measures whether candidate structured content can be extracted. JSON validity measures syntax. These are different failure modes and should not be collapsed into one broad accuracy score.

## 4. Why Schema Validity Is Necessary But Insufficient

Schema validity checks whether required fields and types are present. It does not prove that the action matches the user intent, respects the scene state, avoids restricted zones or satisfies safety constraints.

## 5. Why Semantic Validity and Safety Validity Are Separated

A proposal can be semantically aligned with the command but still unsafe. Conversely, a safe-looking action can be semantically wrong. Separating these metrics makes the evaluation more auditable.

## 6. Why Execution Eligibility Is The Final Decision Metric

Execution eligibility is the final gate because it represents the system-level decision after parsing, schema validation, semantic checks where available, ambiguity handling and deterministic safety validation.

## 7. Why False Accepts Are Central

False accepts matter because the project studies whether unsafe or invalid model proposals could reach downstream execution contexts. In this domain, accepting an unsafe proposal is more serious than rejecting an uncertain one.

## 8. Why Model-Level and Pipeline-Level False Accepts Must Be Separated

Model-level false accepts describe failures in model output. Pipeline-level false accepts describe failures that survive the full validation stack. The dissertation claim depends on showing that deterministic validation can block model-level failures before execution eligibility.

## 9. Why Local-vs-Cloud Comparison Is Included

The Microsoft IXN project concerns local-first AI and Foundry Local. A cloud comparison provides deployment context: latency, JSON consistency, privacy, offline resilience and operational dependency should be discussed together rather than framed as a universal winner.

## 10. Why Resource Profiling Is Included

Local inference shifts work onto the local host. Resource profiling records CPU, memory and latency pressure so local deployment feasibility is discussed with operational evidence.

## 11. Why The Safety-Latency Frontier Matters

Stricter validation may reduce unsafe accepts but can introduce latency, rejection or clarification costs. The safety-latency frontier records this trade-off while keeping missing per-gate data caveated.

## 12. Claim Boundaries

The evaluation supports bounded prototype and benchmark claims only. It does not prove real-world robot safety, factory deployment readiness, certified safety, or statistical generalisation beyond the evaluated command set.
