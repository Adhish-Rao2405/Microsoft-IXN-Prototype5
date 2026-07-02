# Phase 2 External Reference: fl-nemotron

Lee Stott's `fl-nemotron` repository is included as a documentation-only
external reference for Prototype 5:

https://github.com/leestott/fl-nemotron

It demonstrates a Foundry Local + NVIDIA Nemotron Speech Streaming route for
local speech-to-text. The important engineering lesson for Prototype 5 is that
the Microsoft-aligned future voice path is SDK-based: Foundry Local SDK 1.1.x,
the `nemotron-speech-streaming-en-0.6b` model alias, and an SDK audio
client/live-session transcription pattern. This is different from the HTTP
`/v1/audio/transcriptions` route tested in M15A.2.

Prototype 5 does not copy the `fl-nemotron` architecture wholesale and does not
become a general voice assistant. The reference is used only to justify a
future voice-derived command extension:

```text
voice -> Nemotron local STT -> transcript -> existing zero-trust planning pipeline
```

The current proven Prototype 5 contribution remains the local-first zero-trust
validation pipeline for industrial robot task plans. The model proposes;
deterministic validation decides.

## Relationship To Existing Evidence

M15A.2 remains valid negative HTTP endpoint evidence. Foundry Local exposed a
Whisper candidate model, but the tested HTTP transcription routes returned 404,
so no usable Whisper HTTP transcription endpoint was confirmed.

M15B.0 remains valid Nemotron SDK assessment evidence. On this machine,
`foundry-local-sdk` was not installed, no `.wav` files existed, local audio was
present as `.m4a`, and dependency plus WAV/PCM handling decisions would be
required before a controlled Nemotron STT spike.

## Reference Mapping

| fl-nemotron concept | Prototype 5 future-work interpretation |
| --- | --- |
| Microphone / voice assistant | Future input modality only |
| Nemotron Speech Streaming | Future local STT candidate |
| Foundry Local SDK 1.1.x | Future dependency requirement |
| Transcript text | Input to existing command pipeline |
| Chat LLM | Existing local SLM planner equivalent |
| TTS / spoken response | Out of scope |
| Web UI / assistant scenarios | Out of scope |
| Robot validation | Prototype 5 contribution |

## Out Of Scope

The external reference snapshot does not add live microphone capture, speech
recognition, TTS, web UI, FastAPI, assistant scenarios, robot execution,
emergency-stop behavior, or planner/validator changes to Prototype 5.

Any future implementation would need explicit approval because it may require
dependency changes, Foundry Local SDK installation, model download decisions,
and WAV/PCM audio handling.
