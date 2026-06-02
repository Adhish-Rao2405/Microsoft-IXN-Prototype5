# Phase 2 Milestone 14A Manual Recorded-Voice Transcript Evaluation

## Scope

Phase 2 Milestone 14A evaluates manually transcribed spoken-command scenarios using the existing voice transcript policy and typed transcript bridge. It provides bounded evidence that voice-derived transcript candidates can be risk-classified, failed closed, or routed into the zero-trust planner/validator path without bypassing deterministic validation.

This is a research evidence milestone, not a product feature. It uses manually recorded or spoken-command scenarios represented as text transcripts. It does not add microphone input, audio-file parsing, Whisper, Azure Speech, Foundry speech transcription, speech model loading, real robot execution, emergency-stop implementation, dashboard work, validator changes, orchestrator changes, benchmark rewrites, dependency changes, or production voice-control behaviour.

## Research Question

RQ-M14A: Can manually transcribed spoken-command scenarios be evaluated through the existing zero-trust voice-intake pathway such that risky, ambiguous, or context-dependent utterances fail closed before planning, while clear candidate commands remain subject to downstream deterministic validation?

Supporting sub-questions:

- SQ1: Do stop/proceed/conflict utterances avoid backend calls?
- SQ2: Do ambiguous references fail closed before the planner?
- SQ3: Do unsafe or negation-sensitive utterances fail closed before the planner?
- SQ4: Can clear planning utterances reach the bridge while remaining distinct from execution eligibility?
- SQ5: Can the evaluation produce reproducible evidence outputs suitable for dissertation discussion?

## Method

The evaluation path is:

```text
manual/spoken command case list
-> transcript text input
-> M12 transcript contract and policy
-> M13 typed transcript bridge
-> mock backend by default
-> existing validators already used by the bridge
-> CSV, JSON, and Markdown evidence outputs
```

The case file is `data/prototype5/mode_voice/manual_voice_transcript_cases.csv`. It includes `spoken_command` and `manual_transcript` fields even when they are identical, so later milestones can compare intended spoken commands with speech-to-text output without changing the M14A evidence shape.

The runner is `scripts/prototype5/run_manual_voice_transcript_evaluation.py`. It defaults to an offline mock backend and has no audio runtime path.

## Evidence Outputs

The committed outputs are:

- `results/prototype5/mode_voice/phase2_milestone14a_manual_voice_transcript_results.csv`
- `results/prototype5/mode_voice/phase2_milestone14a_manual_voice_transcript_summary.json`
- `results/prototype5/mode_voice/phase2_milestone14a_manual_voice_transcript_summary.md`

The results CSV compares expected and actual voice-policy outcomes and records downstream bridge fields. For clear planning commands, `expected_rejection_stage=none` means no voice-policy/pre-planner rejection occurred. Any deterministic validator rejection after the mock planner call is preserved separately as `bridge_rejection_stage` and `bridge_rejection_reason`.

## Claim Boundary

M14A can support this claim: manually transcribed spoken-command candidates can be evaluated through the existing zero-trust voice-intake pathway, risky utterances can fail closed before planner invocation, and clear planning utterances can enter the planner path without receiving execution authority from the voice layer.

M14A does not prove live voice control, speech recognition reliability, production safety, certified emergency-stop capability, deployment readiness, or real robot readiness.
