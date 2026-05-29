# Phase 2 Milestone 11 Non-Goals And Claim Boundaries

## Strict Non-Goals

Milestone 11 explicitly excludes:

- no real robot execution
- no certified emergency-stop system
- no production voice-control claim
- no full speech benchmark
- no full 30-command SDK voice replay
- no physical microphone integration requirement
- no validator mutation
- no orchestrator mutation
- no safety policy weakening
- no dashboard/app work
- no Phase F-J work
- no staging dissertation_drafts/DISS_DRAFT_cleaned.tex

Milestone 11 also excludes dependency changes, package installation, model downloads, audio library integration, frontend work, and environment setup changes.

## Approved Claim Wording

Phase 2 Milestone 11 defines a safety-first voice command intake specification for Prototype 5. It treats speech recognition output as untrusted text input and preserves the existing zero-trust planning architecture. The milestone identifies voice-specific risks such as mistranscription, ambiguity, stop/proceed confusion, negation loss, and noisy input, and defines policy boundaries to ensure that voice commands cannot bypass deterministic validation or directly trigger execution.

## Forbidden Claims

The following claims are forbidden and must not be presented as supported outcomes:

- The system supports safe voice-controlled robot execution.
- The system implements emergency stop.
- The system proves voice control is safe.
- The system is ready for industrial deployment.
- The voice interface improves robot autonomy.

## Boundary Interpretation

Voice is an input modality only. A transcript is untrusted input. A model-generated plan remains an untrusted proposal. Voice must never bypass the existing SDK backend, typed command abstraction, deterministic validators, or execution-eligibility gates. Voice must never directly trigger execution.

Execution eligibility remains controlled only by existing deterministic validators.

Stop/proceed commands are safety-critical intent classes and must not be treated as ordinary task-planning commands. Proceed/continue/resume must never override a prior rejection. Stop/emergency-stop language must be specified conservatively, without claiming certified emergency-stop functionality.
