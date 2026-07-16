# Phase 2 Milestone 15B.1 Foundry Local Capability Audit

## Purpose

M15B.1 records the local Foundry Local runtime, CLI, SDK, endpoint, and model-catalog capability state for the Nemotron future-extension route. It is version and capability discovery only.

## Current Result

- Status: `COMPLETE_FOUNDRY_LOCAL_CAPABILITY_AUDIT_WITH_RUNTIME_GAPS`
- Foundry CLI present: true
- Foundry CLI visibility: `CLI_SHIM_PRESENT`
- Foundry CLI invocation usable: true
- Foundry CLI version output: `0.8.119`
- Base URL: `http://127.0.0.1:53402`
- Base URL source: `PROJECT_PREVIOUSLY_EVIDENCED_FALLBACK`
- Endpoint selected through project fallback: true
- Service-status reported base URL: `http://127.0.0.1:53402`
- Base URL confirmed by CLI service status: true
- Environment override present: false
- `FOUNDRY_LOCAL_BASE_URL` configured: false
- `/openai/status` reachable: true
- `/openai/status` HTTP status: `200`
- Models endpoint: `http://127.0.0.1:53402/v1/models`
- `/v1/models` reachable: true
- `/v1/models` HTTP status: `200`
- `/v1/models` failure classification: `REST_MODELS_ENDPOINT_REACHABLE`
- `foundry_local_sdk` importable: false
- Active Python executable: `%LOCALAPPDATA%\Programs\Python\Python312\python.exe`
- Current SDK distribution detected in active interpreter: false
- SDK version: `None`
- SDK version compatibility: `NOT_ASSESSABLE_SDK_NOT_DETECTED`
- Minimum required SDK version: `None`
- SDK requirement basis: `NO_PROJECT_SPECIFIC_MINIMUM_ESTABLISHED`
- Whisper candidate `openai-whisper-tiny-generic-cpu:2` visible: true
- Nemotron candidate `nemotron-speech-streaming-en-0.6b` visible: false
- OpenAI-compatible audio transcription route probe: `OPTIONS_PROBE_HTTP_404_NON_CONCLUSIVE`
- SDK catalog route could be attempted: false
- SDK audio client route discoverable: false
- Runtime inference usability: `NOT_TESTED_BY_M15B1`
- Runtime transcription usability: `NOT_TESTED_BY_M15B1`

## Python Package Surface

- `foundry-local-sdk-winml`: `None`
- `foundry-local-sdk`: `None`
- `foundry-local-core`: `None`

The SDK distribution result is scoped to the Python interpreter used to run Prototype 5. It is not a system-wide package audit.

## Observed Runtime Gap Codes

- `CLI_CATALOGUE_PARTIAL_OR_DEGRADED`
- `CURRENT_PYTHON_SDK_DISTRIBUTION_NOT_DETECTED_IN_ACTIVE_INTERPRETER`
- `NEMOTRON_VISIBILITY_NOT_CONFIRMED`
- `PYTHON_SDK_MODULE_NOT_IMPORTABLE`

## Capabilities Not Tested By M15B.1

- `RUNTIME_INFERENCE_USABILITY`
- `RUNTIME_TRANSCRIPTION_USABILITY`

## Canonical CLI Probes

- `version`: attempted `true`, return code `0`, process status `CLI_PROCESS_EXITED_ZERO`, classification `CLI_COMMAND_SUCCEEDED`
- `help`: attempted `true`, return code `0`, process status `CLI_PROCESS_EXITED_ZERO`, classification `CLI_COMMAND_SUCCEEDED`
- `model_list`: attempted `true`, return code `0`, process status `CLI_PROCESS_EXITED_ZERO`, classification `CLI_COMMAND_SUCCEEDED`
- `service_status`: attempted `true`, return code `0`, process status `CLI_PROCESS_EXITED_ZERO`, classification `CLI_COMMAND_SUCCEEDED`

## CLI Catalogue Parse

- Semantic status: `CLI_CATALOGUE_COMPLETED_WITH_PROCESSING_WARNINGS`
- Output complete: false
- Output truncated: true

Aliases:

- `qwen2.5-coder-0.5b`
- `phi-4-mini-reasoning`
- `qwen2.5-0.5b`
- `qwen2.5-1.5b`
- `qwen2.5-coder-1.5b`
- `phi-4-mini`
- `qwen2.5-14b`
- `qwen2.5-coder-14b`
- `qwen2.5-coder-7b`
- `qwen2.5-7b`
- `gpt-oss-20b`
- `phi-3-mini-128k`
- `phi-3.5-mini`
- `phi-4`
- `deepseek-r1-7b`
- `phi-3-mini-4k`
- `mistral-7b-v0.2`
- `deepseek-r1-14b`
- `qwen3-14b`
- `qwen3-1.7b`
- `qwen3-vl-2b-instruct`
- `qwen3-4b`
- `qwen3-0.6b`
- `qwen3-8b`
- `qwen3-vl-8b-instruct`
- `qwen3.5-0.8b`
- `qwen3.5-2b`
- `qwen3.5-4b`
- `qwen3.5-9b`
- `olmo-3-7b-instruct`
- `smollm3-3b`
- `mistral-nemo-12b-instruct`
- `qwen3.5-2b-text`
- `qwen3-vl-4b-instruct`
- `ministral-3-3b-instruct-2512`

Task labels:

- `chat`
- `tools`
- `vision-language-chat`

Model IDs:

- `qwen2.5-coder-0.5b-instruct-generic-gpu:4`
- `qwen2.5-coder-0.5b-instruct-generic-cpu:4`
- `Phi-4-mini-reasoning-generic-gpu:3`
- `Phi-4-mini-reasoning-generic-cpu:3`
- `qwen2.5-0.5b-instruct-generic-gpu:4`
- `qwen2.5-0.5b-instruct-generic-cpu:4`
- `qwen2.5-1.5b-instruct-generic-gpu:4`
- `qwen2.5-1.5b-instruct-generic-cpu:4`
- `qwen2.5-coder-1.5b-instruct-generic-gpu:4`
- `qwen2.5-coder-1.5b-instruct-generic-cpu:4`
- `Phi-4-mini-instruct-generic-gpu:5`
- `Phi-4-mini-instruct-generic-cpu:5`
- `qwen2.5-14b-instruct-generic-gpu:4`
- `qwen2.5-14b-instruct-generic-cpu:4`
- `qwen2.5-coder-14b-instruct-generic-gpu:4`
- `qwen2.5-coder-14b-instruct-generic-cpu:4`
- `qwen2.5-coder-7b-instruct-generic-gpu:4`
- `qwen2.5-coder-7b-instruct-generic-cpu:4`
- `qwen2.5-7b-instruct-generic-gpu:4`
- `qwen2.5-7b-instruct-generic-cpu:4`
- `gpt-oss-20b-generic-cpu:1`
- `gpt-oss-20b-generic-gpu:1`
- `Phi-3-mini-128k-instruct-generic-gpu:2`
- `Phi-3-mini-128k-instruct-generic-cpu:3`
- `Phi-3.5-mini-instruct-generic-gpu:2`
- `Phi-3.5-mini-instruct-generic-cpu:2`
- `Phi-4-generic-gpu:2`
- `Phi-4-generic-cpu:2`
- `deepseek-r1-distill-qwen-7b-generic-gpu:4`
- `deepseek-r1-distill-qwen-7b-generic-cpu:4`
- `Phi-3-mini-4k-instruct-generic-gpu:2`
- `Phi-3-mini-4k-instruct-generic-cpu:3`
- `mistralai-Mistral-7B-Instruct-v0-2-generic-gpu:2`
- `mistralai-Mistral-7B-Instruct-v0-2-generic-cpu:3`
- `deepseek-r1-distill-qwen-14b-generic-gpu:4`
- `deepseek-r1-distill-qwen-14b-generic-cpu:4`
- `qwen3-14b-generic-gpu:2`
- `qwen3-14b-generic-cpu:2`
- `qwen3-1.7b-generic-gpu:2`
- `qwen3-1.7b-generic-cpu:2`
- `qwen3-vl-2b-instruct-generic-cpu:2`
- `qwen3-4b-generic-gpu:2`
- `qwen3-4b-generic-cpu:3`
- `qwen3-0.6b-generic-gpu:2`
- `qwen3-0.6b-generic-cpu:4`
- `qwen3-8b-generic-gpu:2`
- `qwen3-8b-generic-cpu:2`
- `qwen3-vl-8b-instruct-generic-cpu:2`
- `qwen3.5-0.8b-generic-gpu:2`
- `qwen3.5-0.8b-generic-cpu:2`
- `qwen3.5-2b-generic-gpu:2`
- `qwen3.5-2b-generic-cpu:2`
- `qwen3.5-4b-generic-gpu:2`
- `qwen3.5-4b-generic-cpu:2`
- `qwen3.5-9b-generic-gpu:2`
- `qwen3.5-9b-generic-cpu:2`
- `olmo-3-7b-instruct-generic-gpu:1`
- `olmo-3-7b-instruct-generic-cpu:1`
- `smollm3-3b-generic-gpu:1`
- `smollm3-3b-generic-cpu:1`
- `mistral-nemo-12b-instruct-generic-gpu:1`
- `mistral-nemo-12b-instruct-generic-cpu:1`
- `qwen3.5-2b-text-generic-gpu:3`
- `qwen3.5-2b-text-generic-cpu:1`
- `qwen3-vl-4b-instruct-generic-cpu:3`
- `ministral-3-3b-instruct-2512-generic-gpu:1`
- `ministral-3-3b-instruct-2512-generic-cpu:1`

Parse warnings:

- `[12:44:09 ERR] Failed to process model #0 on page 1.`
- `[12:44:10 ERR] Failed to process model #0 on page 1.`

## Model Catalog

All model IDs returned from `/v1/models`:

- `gpt-oss-20b-generic-cpu:1`
- `openai-whisper-tiny-generic-cpu:2`
- `Phi-3-mini-4k-instruct-generic-cpu:3`
- `qwen2.5-0.5b-instruct-generic-cpu:4`
- `qwen2.5-1.5b-instruct-generic-cpu:4`
- `qwen2.5-coder-0.5b-instruct-generic-cpu:4`
- `qwen2.5-coder-1.5b-instruct-generic-cpu:4`
- `qwen2.5-coder-7b-instruct-generic-cpu:4`

Chat/planning model candidates:

- `gpt-oss-20b-generic-cpu:1`
- `Phi-3-mini-4k-instruct-generic-cpu:3`
- `qwen2.5-0.5b-instruct-generic-cpu:4`
- `qwen2.5-1.5b-instruct-generic-cpu:4`
- `qwen2.5-coder-0.5b-instruct-generic-cpu:4`
- `qwen2.5-coder-1.5b-instruct-generic-cpu:4`
- `qwen2.5-coder-7b-instruct-generic-cpu:4`

Audio/STT model candidates:

- `openai-whisper-tiny-generic-cpu:2`

## Audio Transcription Route Probe

- Method: `OPTIONS`
- Path: `/v1/audio/transcriptions`
- HTTP status: `404`
- Classification: `OPTIONS_PROBE_HTTP_404_NON_CONCLUSIVE`
- Audio payload submitted: false
- Transcription attempted: false
- Transcription usability tested: false

The non-invasive OPTIONS probe returned HTTP 404. Because the documented transcription operation uses POST with audio data, this result does not establish whether transcription is supported or usable.

## Safety Boundary

- Dependency changes: false
- Model download attempted: false
- Model load attempted: false
- Inference attempted: false
- Transcription attempted: false
- Real STT attempted: false
- Speech-to-text used: false
- Fake transcripts generated: false
- Live microphone used: false
- Planner called: false
- Validators called: false
- Robot execution attempted: false

## Notes

M15B.1 completed the bounded capability audit but identified runtime capability gaps. CLI, package, REST, model-visibility, and runtime-usability findings are reported as separate capability surfaces. The audit did not attempt model inference or speech transcription.

## Readiness

- M15B.2: M15B.2 may proceed only as a separate bounded local audio-conversion-readiness audit. This does not mean conversion tools are present or conversion has succeeded.
- M15B.3 remains on hold: true
- M15B.3 hold reasons: Audio conversion and WAV/PCM readiness have not been assessed by M15B.2., CLI catalogue visibility is partial or degraded., M15B.1 did not test runtime inference usability., M15B.1 did not test runtime transcription usability., Nemotron model visibility is not confirmed., No current Foundry Local Python SDK distribution was detected in the active interpreter., foundry_local_sdk module is not importable.

## Claim Boundary

M15B.1 does not prove working voice control, real speech recognition, live microphone capture, robot execution, emergency-stop capability, or production safety. It does not modify the zero-trust validation pipeline. Nemotron remains a future local STT input route whose availability must be recorded explicitly because Foundry Local runtime, SDK, and model-catalog capabilities are evolving.

The previously evidenced localhost endpoint was probed as a bounded project-specific fallback. This does not establish that the same port is universal across Foundry Local installations.
