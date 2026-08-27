# D4.3 Typed vs Operator-Reviewed Voice Modality Invariance

## Method

This controlled paired metamorphic experiment holds typed command text and operator-reviewed voice command text equal. Six semantic/review conditions are crossed with LOCAL, CLOUD and AUTO routing modes, yielding 18 pairs. Raw ASR is retained as untrusted provenance. Test-scoped deterministic providers hold proposal generation fixed and require no real network or model service.

## Results

- Overall invariance: 18/18 pairs.
- Divergence: 0/18 pairs.
- Negative controls: 10/10 passed.
- Identity review: 9/9 pairs invariant.
- Material operator review: 9/9 pairs invariant.
- LOCAL: 6/6 invariant.
- CLOUD: 6/6 invariant.
- AUTO: 6/6 invariant.
- ACCEPT: 6/6 invariant.
- REJECT: 6/6 invariant.
- CLARIFY: 6/6 invariant.

## Raw vs Reviewed Authority

B1 changes an ambiguous raw transcript to the clear ACCEPT command. B2 changes a clear raw transcript to the unsafe REJECT command. B3 changes a clear raw transcript to the ambiguous CLARIFY command. In every material-review pair, the governance outcome follows the operator-reviewed command; raw-transcript authority violations observed: 0.

## Governance Projection

P1 compares governance-effective canonical input. P2 proves controlled provider and proposal identity. P3 is the primary governance outcome projection across parse, JSON, schema, semantic, ambiguity, safety, authority, reason and decision fields. P4 compares execution, simulation, exact-scenario replay and physical-authority state. P5 is operational diagnostic evidence only.

## Authority Boundary

Execution eligibility is a governance result. Qualification replay access is a separate exact-scenario presentation policy. Simulation permits, where present, are not physical execution authority. Physical execution authority remains `NOT_IMPLEMENTED`.

## Claim Boundary

No modality-induced divergence was observed across 18 controlled paired requests when typed command text and operator-reviewed voice command text were held equal.

This experiment evaluates downstream governance-path invariance after operator review. It does not evaluate microphone capture fidelity, ASR accuracy, real Nemotron transcription quality, model stochasticity, downstream geometric validity or physical execution safety.

## Provenance

- Frozen base repository SHA: `f8d8894e2c6fd7d1076da02ecef3018b04a5f9fa`
- Dataset SHA256: `03bed446d96184a12e67123c177783aabbfe8df6ae9f6629446f13fab6b8cf51`
- Qualified test SHA256: `4b6fc92c1ce2fc604a25564151e4eee7875fc8134103075f44d4bd729daf5422`
- Evaluator SHA256: `808d87f4ad353a60472ca2811ba1ee43b560754c13371f25d0ea0412835c0bbc`
- Source-input manifest SHA256: `89c5df7eb28b898db100f69c56c06b0ac33caedf3e888c0d1af72c1f474ac827`
- Pair JSONL SHA256: `a2fc09eb72a776416aadc496ee99fc89b4e7f44cec80cfbd4c10f0a9f061971d`

The frozen base SHA is not presented as containing the uncommitted D4.3 files. A later Git release SHA will externally seal these evidence bytes.
