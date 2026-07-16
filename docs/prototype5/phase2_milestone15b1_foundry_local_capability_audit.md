# Phase 2 Milestone 15B.1 Foundry Local Capability Audit

## Purpose

M15B.1 records the Foundry Local runtime, CLI, SDK, endpoint, and model-catalog capability state available on the local machine at evaluation time. It exists because Foundry Local is evolving quickly, so Prototype 5 must record version and capability evidence instead of assuming that the latest runtime, SDK, or model catalog is present.

This milestone is discovery only. It does not implement speech recognition, voice control, live microphone capture, robot execution, emergency-stop behaviour, planner changes, or validator changes.

## Microsoft-Aligned Context

Microsoft Learn describes Foundry Local as a local AI runtime with SDK support, a curated model catalog, automatic hardware acceleration, optional local server/CLI workflows, and on-device execution where data stays local and no Azure subscription is required:

https://learn.microsoft.com/en-us/azure/foundry-local/what-is-foundry-local

Microsoft's recorded-audio transcription guide shows an SDK/audio-client route using `foundry_local_sdk`, `FoundryLocalManager`, a model selected from the catalog, and `get_audio_client()` / transcription calls:

https://learn.microsoft.com/en-us/azure/foundry-local/how-to/how-to-transcribe-audio

Microsoft's live-transcription guide shows the relevant future Nemotron route using `nemotron-speech-streaming-en-0.6b` and an SDK live transcription session:

https://learn.microsoft.com/en-us/azure/foundry-local/how-to/how-to-live-transcribe-audio

Prototype 5 uses these references to justify a future local STT input route only:

```text
voice sample -> Foundry Local SDK -> Nemotron Speech Streaming -> transcript -> existing zero-trust validation pipeline
```

Foundry Local provides the local model runtime. Prototype 5 provides the deterministic validation boundary.

## What The Audit Records

The M15B.1 script records:

- operating system and Python version
- whether the `foundry` CLI is present
- `foundry --version` output
- `foundry --help` output
- `foundry model list` output
- `foundry service status` output
- `FOUNDRY_LOCAL_BASE_URL`
- whether the base URL came from the environment or from the bounded project fallback
- whether `/v1/models` is reachable
- whether `/openai/status` is reachable
- HTTP status for `/v1/models`
- model IDs returned from `/v1/models`
- chat/planning model candidates
- strict STT/audio model candidates
- whether `openai-whisper-tiny-generic-cpu:2` is visible
- whether `nemotron-speech-streaming-en-0.6b` is visible
- whether `foundry_local_sdk` is importable
- installed `foundry-local-sdk-winml` version in the active interpreter
- installed `foundry-local-sdk` version in the active interpreter
- installed `foundry-local-core` version
- SDK version compatibility as tri-state evidence
- whether an SDK catalog route could be attempted
- whether an audio-client route appears discoverable without model download or model load
- CLI process status separately from CLI catalogue semantic status
- CLI catalogue aliases, task labels, model IDs, parse warnings and output completeness
- observed runtime gap codes
- separate capabilities not tested by M15B.1

If `FOUNDRY_LOCAL_BASE_URL` is not configured, the audit uses the previously evidenced Prototype 5 localhost endpoint:

```text
http://127.0.0.1:53402/v1/models
```

This is a bounded project-specific fallback, not a claim that port `53402` is universal across Foundry Local installations.

If `foundry service status` reports the same endpoint, the audit records that the project fallback was subsequently confirmed by CLI service-status evidence. This still does not make the port stable across service restarts.

## Safety Boundary

The audit never:

- installs packages
- updates packages
- modifies requirements, config, CI, Docker, setup, or environment files
- downloads models
- loads models
- transcribes audio
- uses the microphone
- calls the planner
- calls validators
- executes robot actions
- fabricates transcripts

## Claim Boundary

M15B.1 does not prove working voice control, real STT, live microphone capability, production voice interaction, real robot readiness, emergency-stop functionality, or production safety.

It proves only that Prototype 5 can record the local Foundry Local runtime and capability state as evidence. This keeps the zero-trust pipeline independent of Foundry SDK churn.

The audit reports capability surfaces separately:

- Python distribution metadata
- Python module importability
- CLI executable visibility
- CLI invocation usability
- REST endpoint reachability
- service-visible models
- CLI catalogue aliases
- CLI catalogue task labels
- CLI catalogue model IDs
- CLI catalogue warnings and completeness
- Whisper visibility
- Nemotron visibility
- observed runtime gaps
- capabilities intentionally not tested by M15B.1

Runtime inference usability and runtime transcription usability remain `NOT_TESTED_BY_M15B1`.

The audit may issue a non-invasive `OPTIONS /v1/audio/transcriptions` probe. The documented transcription operation uses `POST` with an audio payload and model field, so an `OPTIONS` 404 is recorded as non-conclusive and must not be interpreted as proof that transcription is unavailable.

## Next Step

If the audit shows SDK/catalog readiness, the next bounded milestone would be an SDK upgrade or SDK catalog readiness decision. Any dependency change, model download, WAV/PCM conversion, or transcription attempt must be approved and documented as a separate milestone.

M15B.2 may proceed as a separate bounded local audio-conversion-readiness audit. This does not mean conversion tools are present or conversion has succeeded.

M15B.3 must remain on hold until SDK/catalogue/audio readiness and runtime transcription prerequisites are explicitly satisfied in separate bounded evidence milestones.
