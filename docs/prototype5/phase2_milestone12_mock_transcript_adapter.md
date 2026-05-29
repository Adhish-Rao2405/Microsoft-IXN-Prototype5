# Phase 2 Milestone 12 Mock Transcript Adapter

## Scope

Phase 2 Milestone 12 implements a mocked transcript contract and deterministic voice-intent policy for future voice command intake. It does not process audio; instead, it treats transcript text as untrusted input and applies conservative fail-closed checks before any planning stage.

This milestone does not implement microphone capture, Whisper runtime, Foundry transcription runtime, audio-file transcription, planner calls, validator calls, benchmark expansion, real robot execution, or certified emergency-stop behaviour.

## Transcript Contract

The transcript object records the voice input identifier, timestamp, mocked source type, mock transcription backend, raw transcript, normalised transcript, confidence, language, partial flag, detected intent, voice risk flags, planning eligibility, and rejection reason.

`eligible_for_planning` does not mean execution eligible. It only means a transcript may enter a later planner stage. A model-generated plan remains an untrusted proposal and execution eligibility remains controlled only by existing deterministic validators.

## Deterministic Policy

Milestone 12 uses deterministic keyword and phrase checks. It does not use an LLM for normalisation, classification, risk flagging, or repair.

The policy recognises these intent classes:

- `planning_command`
- `stop_command`
- `proceed_command`
- `clarification`
- `non_command`
- `unknown`

Stop and proceed language is not converted into ordinary planning commands. Proceed language requires a valid pending context, which Milestone 12 does not implement, so proceed transcripts fail closed.

## Risk Flags

The policy can flag low confidence, partial transcript, empty transcript, ambiguous references, negation, unsafe keywords, background noise markers, stop intent, proceed intent, context requirement, non-command input, unknown intent, safety-critical intent, stop/proceed conflict, coordinate or number presence, zone reference, and object reference.

Disqualifying risks make the transcript ineligible for planning. This is intentionally conservative and may reject some commands that a human could understand.

## Claim Boundary

Milestone 12 proves the project can represent and conservatively classify transcript text as untrusted input before planning. It does not prove speech recognition, voice control, production safety, emergency-stop capability, or execution readiness.
