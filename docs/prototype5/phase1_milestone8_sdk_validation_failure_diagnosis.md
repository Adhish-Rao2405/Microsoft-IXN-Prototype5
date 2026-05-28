# Phase 1 Milestone 8 - SDK Validation Failure Diagnosis

## Purpose

This milestone diagnoses why the Phase 1 Milestone 6 SDK mini-replay produced successful SDK responses that were rejected by the existing deterministic validators in Phase 1 Milestone 7.

## Scope

This is diagnosis only. It makes no new model calls, does not modify validators, does not repair model outputs, does not run the full benchmark, and does not call the final orchestrator.

## Finding

The Milestone 6 prompt requested raw planning proposals rather than the exact action-envelope structure expected by the existing validation pipeline. The resulting responses were JSON-valid, but they parsed as strings rather than validator-compatible action objects or action lists.

## Interpretation

JSON validity does not imply schema validity. SDK success does not imply execution eligibility. Existing zero-trust validators correctly rejected the non-compliant proposals.

## Evidence Outputs

- `results/prototype5/mode_sdk/sdk_mini_replay_failure_diagnosis.json`
- `results/prototype5/mode_sdk/sdk_mini_replay_failure_diagnosis.md`

## Next Step

Milestone 9 should test schema-aligned action-envelope prompting over the same five-command mini replay while keeping validators unchanged.
