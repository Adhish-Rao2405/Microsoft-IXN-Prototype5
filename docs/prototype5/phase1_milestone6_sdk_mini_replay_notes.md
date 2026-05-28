# Phase 1 Milestone 6 - SDK Mini Replay Notes

## Purpose

This milestone adds a bounded SDK mini-replay runner for Prototype 5. The goal is to test whether the Foundry SDK backend path can be invoked across a tiny representative command subset while preserving the zero-trust validation boundary.

## Scope

This is raw proposal evidence only. It does not perform schema validation, semantic validation, safety validation, execution eligibility checks, output repair, benchmark scoring, or orchestrator integration.

## Command Subset

The mini replay uses a deliberately small set of commands covering clear, ambiguous, unsafe, and unsupported instruction patterns. This is not the full 30-command benchmark.

## Architectural Boundary

Model outputs remain untrusted proposals. Deterministic validators remain the only execution authority. This milestone does not alter validators, benchmark logic, or final evidence orchestration.

## Evidence Outputs

- `results/prototype5/mode_sdk/sdk_mini_replay_results.json`
- `results/prototype5/mode_sdk/sdk_mini_replay_summary.md`

## Non-Claims

This milestone does not prove model safety, execution eligibility, benchmark performance, production readiness, robot safety, or voice-control readiness.

## Correct Interpretation

The correct interpretation is that the SDK backend path can run a bounded mini replay and record raw proposal evidence without violating the zero-trust architecture.
