# D4.3 Typed vs Operator-Reviewed Voice Modality Invariance

## Research Question

When typed command text and operator-reviewed voice command text are held equal under controlled conditions, does input modality induce divergence in governance-relevant downstream outcomes?

This is a controlled post-review governance-path question. It is not a claim that typed and voice input are universally equivalent.

## Architectural Boundary

The typed path supplies operator text to a server-constructed canonical governance request. The reviewed-voice path retains the raw transcript as untrusted provenance, separately accepts the operator-reviewed command, and supplies that reviewed command to a server-constructed canonical governance request. Both paths resolve the authoritative scenario context on the server and enter the same `HybridInferenceRouter.route_with_execution_context` path and canonical governance runner.

The raw transcript is not the voice-side governance command and cannot override the operator-reviewed text.

## Experimental Design

The experiment crosses six semantic/review conditions with the `LOCAL`, `CLOUD`, and `AUTO` requested routing modes, producing 18 paired comparisons:

- Three identity-review conditions cover `ACCEPT`, `REJECT`, and `CLARIFY`, with raw transcript, reviewed voice command, and typed command held equal.
- Three material-operator-review conditions cover `ACCEPT`, `REJECT`, and `CLARIFY`, with raw transcript deliberately different while reviewed voice command remains equal to typed command.

This yields 9 identity-review pairs, 9 material-review pairs, 6 pairs per routing mode, and 6 pairs per expected outcome.

## Deterministic Provider Control

The qualified harness uses isolated test-scoped deterministic providers and freshly initialized service/router state for each typed and reviewed-voice side. Proposal generation is held fixed. The observed controlled network-call counts were zero for `LOCAL`, `CLOUD`, and `AUTO`; `AUTO` began from controlled fresh state. No real model or cloud service was used.

## Operator-Reviewed Voice Boundary

Each voice pair follows the normal controlled route: controlled transcription fixture, `transcribe_recorded`, READY transcript registration, atomic transcript claim, reviewed voice submission, canonical request construction, and the shared router. Each pair uses a fresh transcription identity. The harness does not insert records directly into private transcript-registry state and does not bypass the canonical router.

The material-review conditions test the authority boundary directly:

- B1 changes ambiguous raw provenance to the clear reviewed `ACCEPT` command.
- B2 changes clear raw provenance to the unsafe reviewed `REJECT` command.
- B3 changes clear raw provenance to the ambiguous reviewed `CLARIFY` command.

## P1 — Canonical Governance Input

P1 compares governance-effective canonical input, including normalized command, authoritative domain and scene, requester, requested inference mode, evaluation mode, and applicable benchmark/oracle fields. Modality-specific transcript provenance is excluded explicitly rather than recursively discarded.

## P2 — Controlled Provider / Proposal

P2 compares selected provider and model, fallback behavior, raw controlled-response identity, and the structured proposal action sequence. It establishes that each typed/reviewed-voice pair received the same controlled proposal evidence.

## P3 — Governance Outcome

P3 is the primary semantic invariant. It compares parse, JSON, schema, plan-semantic, ambiguity, safety, and authority states; gate reasons; decision reason codes; final decision; and execution eligibility. Volatile identifiers, timestamps, and latency do not enter P3.

## P4 — Authority

P4 separately compares governance and session execution eligibility, permit identity/state, simulation state, exact-scenario qualification replay access, and physical execution authority. Replay policy is resolved by the matrix's exact `scenario_id`, with fail-closed uniqueness checks. A separate qualified regression control demonstrates retrieval of `SERVER_REGISTERED_ONLY` for the frozen B2 replay scenario, preventing a hard-coded `PROHIBITED` interpretation.

Simulation permits and qualification replay access are not physical execution authority. Physical execution authority remains `NOT_IMPLEMENTED`.

## Negative Controls

The qualified 36-test D4.3 suite runtime-captured ten negative controls:

1. PARTIAL transcription cannot enter governance.
2. Expired READY transcription fails closed.
3. Unknown transcription identity fails closed.
4. Sequential reuse of a consumed identity fails.
5. Concurrent duplicate claim produces exactly one winner.
6. Provider failure after destructive claim does not restore the identity.
7. Raw transcript content cannot substitute for required reviewed text.
8. Whitespace-only reviewed text is rejected before provider execution.
9. Typed client authority-field injection is rejected.
10. Reviewed-voice client authority-field injection is rejected.

All 10 controls passed.

## Results

The generated evidence reports:

- Overall invariance: 18/18 pairs.
- Divergence: 0/18 pairs.
- P1, P2, P3, and P4: 18/18 matches each.
- Decision, gate-vector, execution-eligibility, and replay-policy scenario identity: 18/18 matches each.
- Identity review: 9/9 pairs invariant.
- Material operator review: 9/9 pairs invariant.
- `LOCAL`: 6/6 invariant.
- `CLOUD`: 6/6 invariant.
- `AUTO`: 6/6 invariant.
- `ACCEPT`: 6/6 invariant.
- `REJECT`: 6/6 invariant.
- `CLARIFY`: 6/6 invariant.
- Negative controls: 10/10 passed.
- Raw-transcript authority violations: 0.
- Unexpected difference paths: 0.
- Unknown canonical fields: 0.
- Unknown result fields: 0.

## Raw Transcript vs Reviewed Command

All nine material-review pairs retained raw transcript text that differed from the reviewed voice command, while the reviewed voice command equalled the typed command. In every evaluated pair, the governance outcome followed the reviewed command. This establishes no correctness claim about the operator's edit; it demonstrates only that the raw transcript did not seize downstream governance authority in the evaluated cases.

## Authority Boundary

Execution eligibility is a governance result. An execution permit and simulation status are separate bounded session concepts. Qualification replay access is an exact-scenario evidence policy. None of these establishes physical execution authority. Physical execution authority is `NOT_IMPLEMENTED`.

## Claim

No modality-induced divergence was observed across 18 controlled paired requests when typed command text and operator-reviewed voice command text were held equal.

## Claim Boundary

This experiment evaluates downstream governance-path invariance after operator review. It does not evaluate microphone capture fidelity, ASR accuracy, real Nemotron transcription quality, model stochasticity, downstream geometric validity or physical execution safety.

## Limitations

- A controlled transcription fixture was used; real microphone capture was not evaluated.
- Real Nemotron transcription and ASR accuracy were not evaluated.
- Operator-review correctness was not evaluated.
- A deterministic provider proposal fixture controlled model stochasticity; stochastic model equivalence was not evaluated.
- Downstream geometric validity, physical execution, and physical safety were not evaluated or established.
- The transcript record itself is not server-bound to a scenario at transcription time. Reviewed submission is bound to the current authoritative server-resolved scenario.
- The findings apply only to the 18 controlled evaluated pairs.

## Reproducibility

The evidence uses the frozen D4.2 repository SHA as its base identity and hashes every uncommitted D4.3 scientific input. It does not claim that the frozen base commit contains the D4.3 files, and it does not invent a future D4.3 release SHA.

- Base repository SHA: `f8d8894e2c6fd7d1076da02ecef3018b04a5f9fa`
- Dataset SHA-256: `03bed446d96184a12e67123c177783aabbfe8df6ae9f6629446f13fab6b8cf51`
- Qualified test SHA-256: `4b6fc92c1ce2fc604a25564151e4eee7875fc8134103075f44d4bd729daf5422`
- Evaluator SHA-256: `808d87f4ad353a60472ca2811ba1ee43b560754c13371f25d0ea0412835c0bbc`
- Source-input manifest SHA-256: `89c5df7eb28b898db100f69c56c06b0ac33caedf3e888c0d1af72c1f474ac827`
- Pair JSONL SHA-256: `a2fc09eb72a776416aadc496ee99fc89b4e7f44cec80cfbd4c10f0a9f061971d`
- Summary JSON SHA-256: `d91111f0182d1adf4404025666892621c0d161655a7da519c81439354c09b9eb`
- Summary Markdown SHA-256: `6bd0d994ebfded6e3760a5befb09b306324e0e5b4e83dfcf4cf86b4aecf1f264`
- Evidence manifest SHA-256: `3d491070667752e273a2f8aeee265d1c894c26d03d3a8fb5152f2a8899ada801`

The final D4.3 Git commit will externally seal these bytes after the separate staging and release review.
