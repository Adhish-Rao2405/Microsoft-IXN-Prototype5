# Mode E Final Dissertation Wording

## Methodology Insertion

A further benchmark-extension evaluation was added to address representativeness. The original 30-command benchmark was extended with 30 industrially motivated commands across six scenario families and three difficulty classes. A deterministic industrial vocabulary and policy context was introduced before live evaluation, so industrial commands were not evaluated against undefined terms.

The live evaluation used the local Foundry `Phi-3-mini-4k-instruct-generic-cpu:3` model alias, the repository action-envelope prompt and the Mode E.1 deterministic policy context. No real robot execution was performed.

## Results Insertion

On the Mode E.2 live industrial benchmark, request success was 1.0, schema validity was 0.6333, and execution eligibility was 0.1. The schema-valid minus execution-eligible gap was therefore 0.5333, while pipeline false accepts remained 0.

Parse success and JSON validity were both 0.7667. Semantic validity was 0.7667 and safety validity was 0.6667. Model-level false accepts were 16, but the deterministic policy context prevented these from becoming pipeline false accepts.

## Discussion Insertion

The result strengthens the central argument that schema validity is insufficient for execution eligibility. However, the lower schema-valid rate compared with E0.4 suggests that industrially phrased commands remain harder for the local model to express in the required action-envelope format.

The result also supports the fail-closed zero-trust framing: model outputs could be parseable, JSON-valid or schema-valid while still not being execution-eligible after deterministic validation.

## Limitations Insertion

The benchmark is curated rather than sampled from real industrial logs.

The policy layer is handcrafted and deterministic.

Only one local model alias was evaluated.

Only one runtime/machine context was used.

No real robot execution was performed.

The result does not constitute safety certification.

CPU latency was high, with mean latency 28.36s and maximum latency 66.93s.

The result is not proof of general industrial deployment readiness and should not be used to claim production robot safety or general local SLM reliability.
