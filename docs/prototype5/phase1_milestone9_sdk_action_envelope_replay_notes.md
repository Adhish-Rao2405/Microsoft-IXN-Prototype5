# Phase 1 Milestone 9 - SDK Action-Envelope Mini Replay Notes

## Purpose

This milestone reruns the same five SDK mini-replay commands using a prompt aligned to the existing deterministic validator's action-envelope contract.

## Scope

This is still a bounded mini replay, not the full 30-command benchmark. It uses existing validators unchanged, does not repair model output, does not modify the orchestrator, and does not implement voice control.

## Validator-Derived Contract

The prompt targets the existing `actions` envelope and the supported action names used by the current repeatability validator: `pick`, `place`, `moveee`, `opengripper`, `closegripper`, `reset`, and `describescene`.

## Evidence Outputs

- `results/prototype5/mode_sdk/sdk_action_envelope_mini_replay_results.json`
- `results/prototype5/mode_sdk/sdk_action_envelope_mini_replay_summary.md`

## Interpretation

Milestone 9 tests whether schema-aligned prompting improves validator compatibility compared with Milestone 7. Any SDK success remains only raw proposal evidence. Execution eligibility still requires JSON, schema, semantic, and safety validation.

## Non-Claims

This milestone does not prove production robot safety, full benchmark performance, universal local SLM reliability, or voice-control readiness.
