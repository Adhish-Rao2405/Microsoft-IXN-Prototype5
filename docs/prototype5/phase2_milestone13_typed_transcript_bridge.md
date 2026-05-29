# Phase 2 Milestone 13 Typed Transcript Bridge

## Scope

Phase 2 Milestone 13 implements a typed transcript bridge into the existing SDK planner and deterministic validation pipeline. It demonstrates that a voice-derived text candidate can enter the same zero-trust pathway as typed commands without bypassing parser, schema, semantic, safety, or execution-eligibility checks.

This milestone does not implement microphone capture, audio-file transcription, Whisper runtime, Foundry transcription runtime, speech recognition, real robot execution, production voice control, or certified emergency stop.

## Bridge Path

```text
manual transcript text
-> M12 transcript adapter/policy
-> reject before planner if not eligible_for_planning
-> existing planner backend
-> existing deterministic validation wrapper
-> evidence result
```

The bridge accepts a backend object so tests can use a fake backend. The live probe script remains optional and fails gracefully when Foundry SDK environment variables are missing.

## Zero-Trust Boundary

Voice-stage eligibility is not execution eligibility. `voice_eligible_for_planning` only means the normalised transcript may be passed to the planner backend.

The planner response remains an untrusted proposal. Execution eligibility is derived only from the existing deterministic validation path. Schema-valid output can still fail semantic validation, safety validation, or execution eligibility.

If M12 rejects the transcript, the bridge does not call the backend and does not call validators. If the backend fails, the bridge fails closed. If validators reject the proposal, the bridge reports the deterministic validator rejection without repair.

## Evidence Fields

The bridge result preserves the raw transcript, normalised transcript, detected intent, voice risk flags, voice planning eligibility, planner call status, raw planner response, JSON validity, schema validity, semantic validity, safety validity, execution eligibility, rejection stage, rejection reason, and error if present.

Unknown or unavailable values are represented as `false`, `null`, or a rejection reason rather than guessed success.

## Claim Boundary

Milestone 13 proves that transcript-derived command candidates can be routed into the existing zero-trust planning and validation pathway without bypassing deterministic validators. It does not prove live voice control, speech recognition reliability, production safety, emergency-stop capability, or real robot readiness.
