# Phase 2 Milestone 15A.1 STT Backend Discovery Spike

## Purpose

M15A.1 checks whether the current machine already exposes a usable speech-to-text backend for the local M4A voice artefacts.

This is discovery only. It does not transcribe audio, install packages, download models, capture microphone input, call the planner, run validators, or create robot execution authority.

## Discovery Scope

The discovery probe checks:

- selected STT-related environment variables
- whether `FOUNDRY_LOCAL_BASE_URL` is configured
- whether Foundry Local `/v1/models` is reachable when a base URL is configured
- whether any Foundry model alias contains `whisper`, `speech`, `stt`, or `audio`
- whether `/v1/audio/transcriptions` appears reachable through a controlled endpoint probe
- whether local CLI tools are on PATH: `whisper`, `whisper-cli`, `faster-whisper`, and `ffmpeg`
- whether Python packages are import-discoverable without importing them: `whisper`, `faster_whisper`, and `openai`

The probe uses discovery APIs only. It does not invoke long-running transcription and does not submit local audio files to a transcription endpoint.

## Relationship To M15A

M15A established a bounded STT feasibility adapter and reported backend unavailability without fabricating transcripts.

M15A.1 narrows the blocked point: it determines whether an already-installed or already-configured backend exists. If a candidate is found, M15A.2 can run a one-file controlled smoke test. If none is found, a separate dependency/configuration decision is needed before transcription evidence can be generated.

## Claim Boundary

M15A.1 proves backend discovery status only.

It does not prove speech recognition works, live voice control, emergency-stop capability, production safety, real robot readiness, a production voice interface, real robot execution, or deployment readiness.

## Next Step

If a candidate backend is discovered, M15A.2 should run one local audio file through the selected backend and record the transcript, latency, and failure mode.

If no candidate backend is discovered, the next decision is whether to install or configure Whisper as a separate, documented dependency and runtime step.
