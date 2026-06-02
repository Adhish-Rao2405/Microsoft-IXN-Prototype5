# Phase 2 Milestone 14B Recorded-Audio Artefact Pack

## Purpose

Phase 2 Milestone 14B creates a reproducible artefact and metadata layer for recorded spoken-command samples corresponding to the M14A manual transcript cases. It prepares Prototype 5 for future STT or audio-runtime evaluation without adding speech recognition, audio processing, microphone capture, model downloads, dependencies, or execution authority.

Core research question: Can spoken-command audio artefacts be organised, documented, and linked to the existing manual transcript evaluation so future STT/live voice testing can be performed reproducibly without changing the zero-trust validation pathway?

## Relationship To M14A

M14A evaluated 15 manually transcribed spoken-command scenarios through the M12 voice policy and M13 typed transcript bridge. M14B adds the artefact structure that future recordings must follow:

```text
expected spoken audio file
-> manifest row
-> manually verified transcript metadata
-> linked M14A case ID
-> future STT comparison input
```

The M14B manifests preserve the M14A case IDs, intended commands, manual transcripts, expected intents, planner-call expectations, and primary risk flags. This keeps any future STT result comparable against the same zero-trust transcript policy evidence.

## Why Runtime Audio Is Deferred

Runtime audio is deliberately out of scope for M14B. Adding microphone capture, audio parsing, speech-to-text, Whisper, cloud speech services, speech model loading, or audio feature extraction would mix artefact governance with runtime behaviour. M14B isolates the dataset and evidence boundary first.

No audio file is required by tests. No binary audio is committed in this milestone.

## Artefact Structure

- `data/prototype5/mode_voice/audio_manifest.csv` records the expected audio artefact identity, linked case, intended spoken command, filename, storage status, recording metadata, and consent boundary.
- `data/prototype5/mode_voice/audio_transcript_manifest.csv` records the manual transcript ground truth and expected M14A policy outcome for each audio artefact.
- `data/prototype5/mode_voice/audio_samples/README.md` reserves a local folder for future recordings without committing binary samples.
- `results/prototype5/mode_voice/phase2_milestone14b_audio_artefact_summary.json` provides machine-readable milestone evidence.
- `results/prototype5/mode_voice/phase2_milestone14b_audio_artefact_summary.md` provides examiner-readable evidence.

## Recording Protocol

Future recordings should follow this protocol:

- use a quiet room
- use one speaker
- use normal speaking volume
- record one command per file
- avoid background music
- avoid overlapping speech
- record the intended command exactly where possible
- save as WAV where possible
- use stable lowercase snake_case filenames from the manifest
- preserve a manual transcript for each recording
- document any mismatch between intended command and spoken command
- keep large binary audio files local and untracked unless explicitly approved
- use self-recorded audio or obtain explicit consent

Recommended naming convention examples:

- `v14a_001_clear_planning_red_block.wav`
- `v14a_002_clear_planning_blue_object.wav`
- `v14a_003_stop_robot.wav`
- `v14a_013_stop_robot_and_proceed.wav`

## Privacy And Consent Boundary

Recorded speech can identify a speaker. M14B therefore stores metadata and expected filenames only. Audio artefacts should be self-recorded or collected with explicit consent, and large binary files should remain outside Git unless a later milestone approves a narrow committed sample.

## Reproducibility Boundary

The manifests make future recordings reproducible by fixing case IDs, intended utterances, expected filenames, manual transcripts, and expected M14A policy outcomes. They do not guarantee that future recordings will match those transcripts; any mismatch must be recorded in manifest metadata before STT evaluation.

## Future M15 Use

A future M15 STT evaluation can load recorded audio from the manifest, run a selected transcription adapter, compare automatic transcript output against the manual transcript manifest, and then route transcript candidates through the existing M12/M13 pathway. That future work must preserve the zero-trust rule that audio-derived text is untrusted input and cannot grant execution eligibility.

## Claim Boundary

M14B proves that Prototype 5 now has a reproducible artefact structure for spoken-command samples linked to known M14A cases and manual transcript ground truth.

M14B does not prove speech recognition, live microphone behaviour, voice control, emergency-stop capability, real robot execution, production safety, deployment readiness, or end-to-end voice understanding.
