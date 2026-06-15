# Phase 2 Milestone 15A Bounded STT Feasibility Spike

## Purpose

M15A introduces a bounded speech-to-text feasibility probe for the 15 local M14B/M14C spoken-command artefacts.

The milestone tests only this path:

```text
audio file -> automatic transcript candidate -> evidence output
```

It deliberately does not route automatic transcripts into the planner or validators. That separation preserves the zero-trust architecture: any future transcript produced by STT remains untrusted text until later milestones compare it against ground truth and route it through the M12/M13 pathway.

## Relationship To Earlier Voice Evidence

M14A established manual transcript ground truth and showed that controlled transcript inputs can be risk-classified, failed closed, or routed to the planner bridge without receiving execution authority.

M14B created the audio and transcript manifests. M14C verified that the local M4A artefacts exist and align with the manifest.

M15A sits between those layers. It attempts to determine whether a real STT backend is available for the local recordings. It does not compare transcripts yet and does not make a governance decision.

## Backend Boundary

The probe supports:

- `--backend auto`
- `--backend foundry-whisper`
- `--backend local-whisper`
- `--backend unavailable-stub`

The default `auto` mode is conservative. It reports backend unavailability unless a real repo-local or explicitly configured no-download STT adapter exists. It does not install packages, download models, call a microphone, or fabricate transcripts.

In the current environment, no real STT backend is configured. The committed M15A evidence therefore records:

```text
COMPLETE_STT_FEASIBILITY_BLOCKED_BACKEND_UNAVAILABLE
```

This is an acceptable M15A outcome because it preserves evidence integrity and avoids pretending that manual transcripts came from audio.

## Ground Truth Boundary

The probe reads `audio_transcript_manifest.csv` only to record whether manual ground truth exists for a row. It does not copy manual transcripts into `automatic_transcript`, does not fabricate confidence values, and does not claim STT success without a real backend.

Manual transcripts remain ground truth for the later M15B comparison step.

## What M15A Proves

M15A proves that Prototype 5 has a test-backed STT feasibility adapter boundary over the local audio manifest. It also proves that the project can honestly report a blocked STT backend without weakening the zero-trust voice safety architecture.

## What M15A Does Not Prove

M15A does not prove live voice control, speech recognition accuracy, emergency-stop capability, real robot safety, production safety, a production voice interface, real robot execution, or deployment readiness.

## Next Milestones

M15B should compare real automatic transcripts against the manual transcript ground truth once a real STT backend is configured.

M15C should route automatic transcripts through the existing M12/M13 zero-trust pathway, preserving the rule that voice-derived text never grants execution authority by itself.
