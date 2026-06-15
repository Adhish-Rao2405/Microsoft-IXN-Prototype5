# Phase 2 Milestone 14C Local Audio Artefact Verification

## Purpose

Phase 2 Milestone 14C adds a lightweight local verification path for the 15 spoken-command audio artefacts referenced by the M14B manifest.

The milestone prepares Prototype 5 to check whether manually recorded local audio files exist and match the expected manifest filenames. It deliberately supports the current state where the recordings may not have been created yet.

Core research question: Can Prototype 5 verify the local presence and manifest alignment of expected spoken-command audio artefacts without adding audio runtime behaviour, speech-to-text, microphone capture, dependencies, or execution authority?

## Relationship To M14B And M15

M14B created the manifest and transcript metadata for 15 expected audio artefacts but committed no binary audio files. M14C adds a verifier that checks those expected filenames against the local `audio_samples` folder.

```text
M14B manifest row
-> expected local filename
-> M14C local presence check
-> future M15 bounded transcript comparison
```

M14C is the bridge before any later M15 transcript comparison. It makes missing recordings visible instead of pretending that controlled STT evidence exists.

## Verification Behaviour

The verifier reads `data/prototype5/mode_voice/audio_manifest.csv`, extracts `expected_audio_filename`, and checks for each expected file under `data/prototype5/mode_voice/audio_samples/`.

For each expected audio artefact it records:

- audio ID
- case ID
- expected filename
- file extension
- byte size when the file exists
- missing or present status

The verifier does not open, decode, parse, inspect, transcribe, or analyse audio content. File byte size is recorded from filesystem metadata only.

## Non-Strict And Strict Modes

Default non-strict mode is CI-safe. Missing local recordings are reported in the summary, but the command exits successfully so the repository test suite does not depend on private or uncommitted binary audio files.

Strict mode is intended for local manual checks after recordings have been placed in `audio_samples`. In strict mode, missing expected audio files cause a non-zero exit code.

Expected statuses:

- `COMPLETE_LOCAL_AUDIO_VERIFICATION_ALL_PRESENT`
- `COMPLETE_LOCAL_AUDIO_VERIFICATION_MISSING_LOCAL_FILES`
- `FAILED_MANIFEST_ERROR`

## Artefacts

- `scripts/prototype5/verify_local_voice_audio_artifacts.py`
- `docs/prototype5/phase2_milestone14c_local_audio_artifact_verification.md`
- `results/prototype5/mode_voice/phase2_milestone14c_local_audio_artifact_verification_summary.json`
- `results/prototype5/mode_voice/phase2_milestone14c_local_audio_artifact_verification_summary.md`
- `tests/prototype5/test_phase2_milestone14c_local_audio_artifact_verification.py`

## Current Expected State

At the time M14C is added, the 15 local recordings may be absent. That is an intentional and honest state:

- expected audio count: 15
- present audio count: reported by the local verifier
- missing audio count: reported by the local verifier
- binary audio files committed: false
- audio runtime used: false
- speech-to-text used: false
- live microphone used: false
- dependency changes: false

## Claim Boundary

M14C proves that Prototype 5 can verify the local presence and manifest alignment of the expected M14B audio artefacts, while preserving the zero-trust boundary around voice-derived input.

M14C does not prove live voice control, speech recognition accuracy, microphone capture reliability, emergency-stop capability, production safety, real robot readiness, deployment readiness, or end-to-end voice understanding.
