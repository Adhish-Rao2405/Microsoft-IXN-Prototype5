# Foundry Local + NVIDIA Nemotron: Voice-Activated AI Assistant

Reference snapshot from Lee Stott's `fl-nemotron` repository:

https://github.com/leestott/fl-nemotron

This snapshot is included in Prototype 5 only as an external reference. It is
not imported by Prototype 5 and is not part of the tested runtime.

The upstream project describes a fully on-device voice assistant built with
Microsoft Foundry Local and NVIDIA Nemotron Speech Streaming. In that design,
speech is transcribed locally by the Nemotron 0.6B streaming STT model, passed
to a Foundry Local chat LLM, and spoken back through offline TTS. The upstream
README states that this route uses no cloud endpoint, no API key, and no data
leaving the device.

## Required SDK Route

The upstream project requires:

```text
foundry-local-sdk >= 1.1.0,<2
foundry-local-core >= 1.1.0
```

It also states that NVIDIA Nemotron Speech Streaming is available through the
1.1.x Foundry Local catalog as:

```text
nemotron-speech-streaming-en-0.6b
```

The implementation uses the SDK module name:

```text
foundry_local_sdk
```

and model clients obtained through SDK methods such as `get_chat_client()` and
`get_audio_client()`. This differs from the HTTP `/v1/audio/transcriptions`
route probed by Prototype 5 in M15A.2.

## Prototype 5 Interpretation

Prototype 5 does not become a general voice assistant. This reference supports
only the future extension path:

```text
voice -> Nemotron local STT -> transcript -> existing zero-trust planning pipeline
```

Prototype 5's contribution remains deterministic governance over robot-task
plans: schema validation, semantic validation, policy checks, ambiguity
handling, execution-eligibility checks, and fail-closed routing.

## Included Upstream Files

This minimal reference snapshot includes:

- `LICENSE`
- `requirements.txt`
- `src/foundry_client.py`
- `src/_nemotron_live.py`

The full upstream repository contains additional assistant, UI, setup,
scenario, and TTS code that is intentionally not copied here.
