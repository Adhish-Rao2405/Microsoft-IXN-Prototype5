# Post-E0 Dissertation Wording

## A. Methodology Wording

To address repeatability, the final Prototype 5 evidence layer included a repo-local Mode E0.4 repeatability adapter. This adapter used the fixed 30-command benchmark, the action-envelope prompt stored in the repository, a local Phi-3-mini Foundry Local model alias and the deterministic validation policy used by the zero-trust evaluation pipeline. The benchmark was executed three times under the tested conditions. Each model response was parsed and assessed for JSON validity, schema validity, semantic validity, safety validity and execution eligibility. The same replay also recorded model-level false accepts, pipeline-level false accepts, correct rejections and latency.

This repeatability check was designed to test whether the central measured relationship between schema validity and execution eligibility remained stable across repeated live runs. It was not designed to prove production robot safety, certify a controller or establish general reliability for all local SLMs.

## B. Results Wording

Across the three E0.4 live repeatability runs, request success remained stable at `1.0`. Schema validity was stable at `0.8667`, while execution eligibility remained stable at `0.1`, giving a stable schema-valid minus execution-eligible gap of `0.7667`. Semantic validity was `0.2` and safety validity was `0.1`. The model produced `16` model-level false accepts in each run, but the deterministic validation policy reduced measured pipeline-level false accepts to `0` across all three runs.

These results indicate that, within the fixed 30-command benchmark and selected local runtime configuration, schema-valid output substantially overestimated execution eligibility. The E0.4 repeatability check therefore supports the dissertation claim that schema validity is not sufficient evidence of execution eligibility. The result should be read as evidence for a bounded zero-trust evaluation framework, not as evidence that local SLMs are production-safe robot controllers.

Latency remained a limitation. The mean latency across E0.4 runs was approximately 25.38s, with observed run-to-run variability. This supports the resource and deployment caution that local inference can carry meaningful runtime cost even when it offers privacy, data-locality or offline-resilience advantages.

## C. Limitations Wording

The repeatability evidence is bounded in several ways. First, it used a single local model alias rather than a broad family of local SLMs. Second, it was executed in a single local runtime and machine context, so the latency and resource behaviour should not be generalized to all hardware configurations. Third, the benchmark was a fixed 30-command benchmark designed for controlled MSc-level evaluation, not a statistically representative sample of all industrial robot instructions.

The evaluation did not execute plans on a production robot and does not prove production robot safety. The deterministic validation policy is handcrafted and limited, so zero measured pipeline false accepts should be interpreted only within that policy and benchmark. The evidence also shows an important weakness: semantic validity, safety validity and execution eligibility remain low despite high schema validity. This strengthens the dissertation argument, but it also limits any claim that the local model is practically ready for direct robot execution.

Overall, the E0.4 results should not be generalized to all local SLMs, all industrial robot tasks or all deployment environments. They support the narrower claim that local SLM outputs can be evaluated as untrusted robot action proposals and that deterministic validation can prevent schema-valid but execution-ineligible outputs from being treated as executable under the tested conditions.
