# Phase 2 Milestone 11 Voice Safety Policy

## Policy Position

Voice is an input modality only. A transcript is untrusted input, and a model-generated plan remains an untrusted proposal. Voice must never directly trigger execution and must never bypass the existing SDK backend, typed command abstraction, deterministic validators, or execution-eligibility gates.

Execution eligibility remains controlled only by existing deterministic validators.

## Voice-Specific Risks

Milestone 11 recognises these voice-specific risks:

- mistranscription
- partial transcription
- word insertion
- word deletion
- homophones
- accent sensitivity
- background noise
- overlapping speakers
- low-volume speech
- negation loss
- object confusion
- zone confusion
- coordinate/number mishearing
- casual speech mistaken as command
- stop/start confusion
- proceed/continue ambiguity

These risks apply before planning and must be handled as input uncertainty. They are not evidence that a voice-derived command is safe or executable.

## Fail-Closed Handling

Misheard, low-confidence, ambiguous, partial, contradictory, noisy, or context-free commands must fail closed. Fail-closed handling means the transcript is rejected or held for clarification before planner handoff when the voice layer cannot establish a bounded, auditable candidate command.

Fail-closed outcomes must preserve a rejection reason and voice risk flags for evidence logging.

## Low-Confidence Handling

Low-confidence transcripts must not be passed to planning by default. A low-confidence transcript may be logged for analysis, but it must not be treated as a command candidate unless a future policy explicitly defines a stricter clarification flow.

Low confidence must never produce execution eligibility.

## Ambiguity Handling

Ambiguous references must fail closed or require clarification. Examples include "it", "there", "that one", missing object identifiers, missing target zones, contradictory object references, and context-free commands that depend on state not present in the voice record.

Ambiguity must not be resolved by guessing. If a future implementation uses context, that context must be explicit, current, evidence-loggable, and still subject to deterministic validation.

## Unsafe Keyword Handling

Unsafe keywords and phrases must trigger conservative handling. Examples include requests to ignore safety, disable checks, go as fast as possible without constraints, enter restricted zones, collide with objects, or bypass validation.

Stop, abort, cancel, emergency stop, and halt language must be classified as safety-critical stop intent rather than ordinary task-planning content. This policy does not claim certified emergency-stop functionality.

Proceed, continue, resume, and go ahead language must be classified as context-dependent proceed intent rather than ordinary task-planning content.

## Human/Operator Uncertainty Handling

Casual speech, overlapping speakers, background conversation, uncertain speaker intent, or unclear operator identity must not be promoted into a robot task plan. Human/operator uncertainty must fail closed or require clarification.

The voice layer must not infer authority from speech alone. A transcript cannot grant execution authority, override a prior rejection, or bypass deterministic validators.

## Planning And Validation Boundary

If a transcript passes voice intake policy, it may become a text command candidate for the existing SDK planner backend. That planning handoff is not execution approval.

The resulting model-generated plan remains an untrusted proposal. Existing deterministic validators retain sole control over execution eligibility.

Every future voice-stage decision must be evidence-loggable, including acceptance for planning, rejection, clarification, and any stop/proceed classification.
