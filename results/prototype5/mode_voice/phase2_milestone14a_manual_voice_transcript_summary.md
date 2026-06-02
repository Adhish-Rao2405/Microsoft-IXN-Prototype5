# Phase 2 Milestone 14A Manual Voice Transcript Evaluation

## Purpose

Phase 2 Milestone 14A evaluates manually transcribed spoken-command scenarios using the existing voice transcript policy and typed transcript bridge. It provides bounded evidence that voice-derived transcript candidates can be risk-classified, failed closed, or routed into the zero-trust planner/validator path without bypassing deterministic validation.

This milestone evaluates manually transcribed spoken-command scenarios, not live speech recognition. The evaluation is intended to test the zero-trust voice-intake pathway under controlled transcript inputs before introducing audio-runtime complexity.

## Method

The evaluation loads curated spoken-command scenarios from `data/prototype5/mode_voice/manual_voice_transcript_cases.csv`. Each manual transcript is processed by the existing M12 transcript policy and then passed through the existing M13 typed transcript bridge with the offline mock backend.

RQ-M14A: Can manually transcribed spoken-command scenarios be evaluated through the existing zero-trust voice-intake pathway such that risky, ambiguous, or context-dependent utterances fail closed before planning, while clear candidate commands remain subject to downstream deterministic validation?

## Key Results

- Case count: 15
- Scenario families: ambiguous_reference, clarification_without_context, clear_planning, low_confidence_or_partial_simulated, negation_sensitive, non_command, proceed_context, stop_proceed_conflict, stop_safety, unsafe_request
- Passed expectations: 15/15
- Voice-policy rejections before planning: 13
- Planner calls: 2
- Execution-eligible cases: 0
- Unexpected planner calls: 0
- Unexpected execution-eligible cases: 0

## Fail-Closed Findings

Stop, proceed, ambiguous-reference, negation-sensitive, unsafe, non-command, clarification-without-context, conflict, low-confidence, and partial transcript cases were expected to fail closed before planner invocation. Clear planning transcripts were allowed to reach the bridge, where the mock planner output remained subject to downstream deterministic validation.

## What This Proves

M14A shows that manually transcribed spoken-command candidates can be evaluated through the existing zero-trust voice-intake pathway. Risky or context-dependent transcripts can be rejected before planner calls, while clear planning transcripts can enter the planner pathway without receiving execution authority from the voice layer.

## What This Does Not Prove

M14A does not prove live voice control, speech recognition accuracy, audio capture reliability, emergency-stop capability, production safety, real robot readiness, or deployment readiness.

## Next Possible Step

A later bounded milestone could compare intended spoken commands with transcript text produced by a controlled speech-to-text adapter. That should remain separate from this manual transcript evaluation and should preserve the same zero-trust execution boundary.
