# Phase 2 Milestone 11 Voice Baseline Specification

## Milestone Purpose

Phase 2 Milestone 11 defines a safety-first baseline specification for adding voice command intake to Prototype 5 while preserving the existing zero-trust robot task planning architecture.

The milestone frames the work as voice command intake for zero-trust robot task planning. It is not a claim of voice-controlled robot execution. Voice is an input modality only.

This milestone is documentation and specification only. It does not implement microphone capture, speech recognition runtime, voice-to-planner runtime code, dashboard/app code, benchmark expansion, validator changes, orchestrator changes, or real robot execution.

## Why Phase 2 Follows Phase 1

Phase 1 established a bounded SDK planner backend path and reaffirmed the frozen zero-trust boundary: model output is an untrusted proposal and deterministic validation remains the only source of execution eligibility.

Phase 2 can begin only as a voice intake specification because speech introduces additional uncertainty before the existing planner backend is reached. Mistranscription, ambiguity, noisy input, and stop/proceed confusion must be treated as new input risks, not as reasons to weaken the Phase 1 validation boundary.

## System Architecture

```text
audio input
-> transcription adapter
-> transcript normalisation
-> voice intent classification
-> text command candidate
-> existing SDK planner backend
-> existing deterministic validators
-> execution eligibility decision
-> evidence logging
```

The voice path may produce only a candidate transcript and candidate text command. The existing SDK planner backend remains the planning entry point. The existing deterministic validators remain the execution-eligibility authority.

## Trust Boundary

A transcript is untrusted input. It may be incomplete, misheard, noisy, ambiguous, contradictory, low confidence, or unrelated casual speech. A transcript must never be treated as a verified command.

A model-generated plan remains an untrusted proposal. It must not be treated as executable merely because it originated from a voice command.

Voice must never bypass the existing SDK backend, typed command abstraction, deterministic validators, or execution-eligibility gates. Voice must never directly trigger execution.

## Integration Boundary

Milestone 11 does not change the existing Prototype 5 execution path. Future voice intake must integrate by producing a text command candidate that can be passed into the existing SDK planner backend under the same zero-trust assumptions as typed input.

The voice layer must not mutate deterministic validators, orchestrator logic, benchmark logic, or execution eligibility rules. Any future adapter must fail closed before planner handoff when the transcript is low confidence, partial, contradictory, noisy, context-free, or safety-critical in a way that requires special handling.

## What Voice Produces

Voice may produce:

- an audio intake record
- a raw transcript
- a normalised transcript
- transcript confidence metadata
- voice risk flags
- a detected voice intent class
- a candidate text command for planner consideration
- evidence records for each stage decision

`eligible_for_planning` means only that a transcript may be passed into the existing planner backend. It does not mean execution eligible.

## What Voice Does Not Produce

Voice does not produce:

- execution authority
- validator approval
- safety approval
- real robot execution readiness
- certified emergency-stop behaviour
- permission to override a prior rejection

Stop/proceed commands are safety-critical intent classes and must not be treated as ordinary task-planning commands.

## Relationship To Existing SDK Backend

The SDK planner backend remains the only allowed planning backend for future voice-derived command candidates within this milestone framing. A voice transcript may become a candidate text command only after transcript normalisation and intent classification have produced an auditable decision.

The backend must continue to receive untrusted text and return untrusted planning proposals. Backend success, JSON validity, or schema compatibility must not imply execution eligibility.

## Relationship To Deterministic Validators

Execution eligibility remains controlled only by existing deterministic validators. Voice must never bypass deterministic validation. No voice-stage decision may relax schema, semantic, safety, or execution gates.

Proceed, continue, and resume language must never override a prior validator rejection. Rejected plans remain rejected unless a new valid command enters through the normal validated path and independently satisfies the existing deterministic validators.

## Evidence Logging Expectations

Every future voice-stage decision must be evidence-loggable. Evidence should identify the input, transcript backend, raw transcript, normalised transcript, confidence, intent class, risk flags, planning handoff decision, rejection reason, planner response linkage, validation result, and final execution eligibility decision.

Evidence must be sufficient to explain why a voice input was rejected, held for clarification, passed to planning, or blocked after planning.

## Future Implementation Sequence

Future work should proceed only after this specification is accepted:

1. Static mocked transcript fixtures, with no microphone or speech model runtime.
2. Transcript contract tests and fail-closed policy tests.
3. Bounded transcript normalisation and intent classification.
4. Planner handoff using the existing SDK backend, with voice metadata preserved.
5. Deterministic validation using existing validators without weakening policy.
6. Evidence logging for each stage decision.
7. Only after fixture evidence exists, a bounded transcription adapter spike may be considered.

This sequence preserves the frozen Phase 1 boundary and prevents voice intake from becoming an execution shortcut.
