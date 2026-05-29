# Phase 2 Milestone 11 Transcript Contract

## Contract Purpose

This document defines the baseline transcript object for future Prototype 5 voice command intake. The contract is documentation-only in Milestone 11 and does not implement microphone capture, transcription runtime, planner runtime, validator changes, or real robot execution.

Voice is an input modality only. A transcript is untrusted input. A model-generated plan remains an untrusted proposal. Voice must never directly trigger execution and must never bypass deterministic validation.

## Baseline Transcript Object

```json
{
  "voice_input_id": "string",
  "timestamp_utc": "string",
  "audio_source_type": "microphone | audio_file | mocked_transcript",
  "transcription_backend": "mock | foundry_whisper | other_local_stt",
  "raw_transcript": "string",
  "normalised_transcript": "string",
  "transcript_confidence": 0.0,
  "language": "en",
  "is_partial": false,
  "detected_intent": "planning_command | stop_command | proceed_command | clarification | non_command | unknown",
  "voice_risk_flags": [
    "low_confidence",
    "ambiguous_reference",
    "negation_detected",
    "unsafe_keyword",
    "partial_transcript",
    "background_noise",
    "stop_proceed_conflict"
  ],
  "eligible_for_planning": false,
  "rejection_reason": "string | null"
}
```

## Field Semantics

`voice_input_id` is the stable identifier for one voice intake event.

`timestamp_utc` records when the voice intake event was created.

`audio_source_type` records whether the transcript came from a future microphone path, an audio file, or a mocked transcript fixture. Milestone 11 requires no physical microphone integration.

`transcription_backend` records the source of transcription. Milestone 11 does not run Whisper, Foundry transcription, or any local speech-to-text runtime.

`raw_transcript` is the untrusted transcript exactly as produced or mocked.

`normalised_transcript` is the untrusted normalised text candidate after documented cleanup. Normalisation must not invent missing objects, zones, coordinates, or negation.

`transcript_confidence` records confidence metadata when available. Low confidence must fail closed.

`language` is the detected or configured language.

`is_partial` marks incomplete transcription. Partial transcripts must fail closed.

`detected_intent` separates planning commands from stop, proceed, clarification, non-command, and unknown intent classes. Stop/proceed commands are safety-critical intent classes and must not be treated as ordinary task-planning commands.

`voice_risk_flags` records input risks that affected the decision.

`eligible_for_planning` means only that the transcript may be passed into the existing planner backend. It does not mean execution eligible.

`rejection_reason` records why a transcript was not eligible for planning.

## Planning Boundary

A transcript object can only produce a text command candidate. It cannot produce execution authority, validator approval, safety approval, or real robot execution readiness.

If `eligible_for_planning` is true, the next step is the existing SDK planner backend. The backend result remains an untrusted proposal and must pass through existing deterministic validators before any execution eligibility decision.

## Evidence Requirements

Every future voice-stage decision must be evidence-loggable. At minimum, evidence should preserve the transcript object, planner handoff decision, planner response reference if any, validator result if any, and final execution eligibility decision.

Proceed/continue/resume must never override a prior rejection. Stop/emergency-stop language must be handled conservatively without claiming certified emergency-stop functionality.
