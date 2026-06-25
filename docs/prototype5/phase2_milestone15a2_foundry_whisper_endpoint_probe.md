# Phase 2 Milestone 15A.2 Foundry Whisper Endpoint Feasibility Probe

## Purpose

M15A.2 determines whether the Whisper model visible through Foundry Local can transcribe one existing local M4A audio artefact through a usable HTTP endpoint.

This milestone is manual-first and endpoint-focused. It does not install packages, download models, change dependencies, capture microphone input, call the planner, run validators, execute a robot, or implement emergency-stop behavior.

## Manual Probe

The shortest local recording, `v14a_006_continue.m4a`, was submitted through multipart HTTP POST requests to:

- `/v1/audio/transcriptions`
- `/v1/transcriptions`
- `/v1/models/openai-whisper-tiny-generic-cpu:2/transcriptions`

All three routes returned `HTTP 404` with no transcript body.

## Automated Evidence Wrapper

The M15A.2 script repeats the same bounded route set using Python standard-library HTTP and multipart handling. It first checks `/v1/models` to record whether the candidate model is visible, then submits one local M4A file to the three fixed transcription routes.

A route is considered usable only when it returns a 2xx response containing transcript-like JSON text. Non-2xx responses, empty bodies, and non-transcript JSON do not count as STT success.

## Current Finding

Foundry Local exposes `openai-whisper-tiny-generic-cpu:2` in `/v1/models`, but the current runtime does not expose any of the tested transcription routes. Therefore no usable Foundry Whisper STT endpoint is confirmed.

This is a bounded negative feasibility result, not evidence that Whisper itself is invalid or unavailable in every Foundry Local configuration.

## Claim Boundary

M15A.2 proves only that the tested Foundry Local runtime, model alias, audio file, and three candidate endpoint routes did not yield a usable transcription response.

It does not prove speech recognition accuracy, live voice control, planner integration, validator integration, emergency-stop capability, production safety, real robot readiness, robot execution, or deployment readiness.
