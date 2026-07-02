# Phase 2 Milestone 15B.0 Nemotron SDK STT Feasibility Assessment

## Purpose

M15B.0 assesses whether Prototype 5 could adopt a future SDK-based Nemotron Speech Streaming STT route. This milestone is intentionally bounded: it records environment readiness and blockers, but does not attempt transcription or implement voice control.

## Relationship To M15A.2

M15A.2 remains valid as negative HTTP endpoint evidence. Foundry Local exposed `openai-whisper-tiny-generic-cpu:2`, but the tested HTTP transcription routes returned `HTTP 404` and no transcript.

M15B.0 evaluates a different future route: a Foundry Local SDK 1.1.x style audio client/live transcription path with Nemotron Speech Streaming. That route is not treated as current working functionality.

## Assessment Scope

The assessment records:

- whether `foundry_local_sdk` is importable
- installed `foundry-local-sdk` version, if present
- installed `foundry-local-core` version, if present
- whether the SDK version is compatible with a `>= 1.1.0` future-route threshold
- whether local M4A and WAV audio artefacts exist
- whether audio conversion would be required
- whether dependency changes would be required before implementation

The assessment does not install packages, download models, copy a reference repository, add a voice assistant, add TTS, add a web UI, capture microphone input, call the planner, call validators, execute a robot, or fabricate transcripts.

## Current Claim Boundary

Prototype 5 remains a local-first zero-trust validation system for industrial robot task planning. Nemotron STT is a future-extension route, not current working voice control.

Any real implementation would require explicit approval because it may require SDK/dependency changes and WAV/PCM audio handling.
