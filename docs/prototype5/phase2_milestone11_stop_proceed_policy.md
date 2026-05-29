# Phase 2 Milestone 11 Stop/Proceed Policy

## Policy Position

Stop/proceed commands are safety-critical intent classes and must not be treated as ordinary task-planning commands. Voice is an input modality only, and voice must never directly trigger execution.

A transcript is untrusted input. A model-generated plan remains an untrusted proposal. Existing deterministic validators remain the only source of execution eligibility.

## Stop Intent

Examples of safety-critical stop-intent language include:

- stop
- abort
- cancel
- emergency stop
- halt

Stop commands must not be converted into ordinary robot task plans. A future voice layer may classify stop language as a stop intent for evidence and control-flow handling, but Milestone 11 makes no certified emergency-stop claim.

Stop or emergency-stop language must be specified conservatively. This milestone does not implement, certify, or validate an emergency-stop system.

## Proceed Intent

Examples of context-dependent proceed-intent language include:

- proceed
- continue
- resume
- go ahead

Proceed commands must not override rejection. Proceed, continue, resume, and go ahead must never convert a rejected transcript, rejected planner output, or failed validator result into an executable task.

Proceed requires a valid pending context. A valid pending context must be explicit, current, evidence-loggable, and already within the normal zero-trust planning and validation flow.

Missing, stale, ambiguous, contradictory, or low-confidence context must reject or require clarification.

## Stop/Proceed Conflict Handling

Commands containing both stop and proceed intent, or unclear stop/start language, must fail closed. A future implementation must preserve a `stop_proceed_conflict` risk flag and avoid planner handoff unless a bounded clarification policy is defined.

Stop/proceed classification must be logged as a voice-stage decision. It must not bypass the existing SDK backend, typed command abstraction, deterministic validators, or execution-eligibility gates.

## Claim Boundary

Milestone 11 defines policy only. It does not implement real robot execution, certified emergency stop, production robot safety, or production voice control.
