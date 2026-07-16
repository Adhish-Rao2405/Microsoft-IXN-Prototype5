from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_AUDIO_DIR = REPO_ROOT / "data" / "prototype5" / "mode_voice" / "audio_samples"
DEFAULT_SUMMARY_JSON = (
    REPO_ROOT
    / "results"
    / "prototype5"
    / "mode_voice"
    / "phase2_milestone15b0_nemotron_sdk_stt_feasibility_summary.json"
)
DEFAULT_SUMMARY_MD = (
    REPO_ROOT
    / "results"
    / "prototype5"
    / "mode_voice"
    / "phase2_milestone15b0_nemotron_sdk_stt_feasibility_summary.md"
)

MILESTONE = "Phase 2 Milestone 15B.0"
MODE = "nemotron_sdk_stt_future_extension_feasibility"
MINIMUM_SDK_VERSION = "1.1.0"
REFERENCE_MODEL_ALIAS = "nemotron-speech-streaming-en-0.6b"

STATUS_SDK_NOT_INSTALLED = "COMPLETE_NEMOTRON_SDK_ASSESSMENT_SDK_NOT_INSTALLED"
STATUS_SDK_TOO_OLD = "COMPLETE_NEMOTRON_SDK_ASSESSMENT_SDK_TOO_OLD"
STATUS_READY = "COMPLETE_NEMOTRON_SDK_ASSESSMENT_READY_FOR_CONTROLLED_SPIKE"
STATUS_BLOCKED_AUDIO_FORMAT = "COMPLETE_NEMOTRON_SDK_ASSESSMENT_BLOCKED_AUDIO_FORMAT"


def timestamp_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def distribution_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def parse_version(value: str | None) -> tuple[int, ...] | None:
    if not value:
        return None
    parts: list[int] = []
    for token in value.replace("-", ".").split("."):
        if token.isdigit():
            parts.append(int(token))
        else:
            break
    return tuple(parts) if parts else None


def version_at_least(version: str | None, minimum: str) -> bool:
    parsed_version = parse_version(version)
    parsed_minimum = parse_version(minimum)
    if parsed_version is None or parsed_minimum is None:
        return False

    width = max(len(parsed_version), len(parsed_minimum))
    padded_version = parsed_version + (0,) * (width - len(parsed_version))
    padded_minimum = parsed_minimum + (0,) * (width - len(parsed_minimum))
    return padded_version >= padded_minimum


def audio_inventory(audio_dir: Path) -> dict[str, Any]:
    m4a_files = sorted(path.name for path in audio_dir.glob("*.m4a") if path.is_file())
    wav_files = sorted(path.name for path in audio_dir.glob("*.wav") if path.is_file())
    return {
        "audio_dir": str(audio_dir),
        "m4a_audio_count": len(m4a_files),
        "wav_audio_count": len(wav_files),
        "m4a_audio_files": m4a_files,
        "wav_audio_files": wav_files,
        "m4a_audio_exists": bool(m4a_files),
        "wav_audio_exists": bool(wav_files),
        "audio_conversion_would_be_required": bool(m4a_files) and not bool(wav_files),
    }


def classify(
    *,
    sdk_installed: bool,
    sdk_version_compatible: bool,
    wav_audio_exists: bool,
) -> str:
    if not sdk_installed:
        return STATUS_SDK_NOT_INSTALLED
    if not sdk_version_compatible:
        return STATUS_SDK_TOO_OLD
    if not wav_audio_exists:
        return STATUS_BLOCKED_AUDIO_FORMAT
    return STATUS_READY


def build_notes(status: str) -> str:
    if status == STATUS_SDK_NOT_INSTALLED:
        return (
            "Nemotron SDK STT remains future work because foundry-local-sdk is not installed in this environment. "
            "Implementing the fl-nemotron-style route would require an explicit dependency/configuration decision."
        )
    if status == STATUS_SDK_TOO_OLD:
        return (
            "A Foundry Local SDK distribution is present, but its version is below the >= 1.1.0 reference threshold "
            "for the Nemotron Speech Streaming route."
        )
    if status == STATUS_BLOCKED_AUDIO_FORMAT:
        return (
            "The SDK threshold appears satisfied, but only M4A local audio artefacts are present. A controlled "
            "implementation would need explicit WAV/PCM handling or approved conversion before any one-file spike."
        )
    return (
        "The environment appears ready for a controlled one-file Nemotron SDK STT spike, subject to explicit approval. "
        "M15B.0 itself did not attempt transcription."
    )


def build_summary(audio_dir: Path) -> dict[str, Any]:
    sdk_importable = module_available("foundry_local_sdk")
    foundry_local_importable = module_available("foundry_local")
    sdk_version = distribution_version("foundry-local-sdk")
    core_version = distribution_version("foundry-local-core")
    sdk_installed = sdk_version is not None or sdk_importable
    sdk_version_compatible = version_at_least(sdk_version, MINIMUM_SDK_VERSION)
    inventory = audio_inventory(audio_dir)
    dependency_changes_required = not sdk_installed or not sdk_version_compatible or inventory[
        "audio_conversion_would_be_required"
    ]
    status = classify(
        sdk_installed=sdk_installed,
        sdk_version_compatible=sdk_version_compatible,
        wav_audio_exists=inventory["wav_audio_exists"],
    )

    return {
        "status": status,
        "timestamp_utc": timestamp_utc(),
        "milestone": MILESTONE,
        "mode": MODE,
        "reference_route": "Foundry Local SDK 1.1.x Nemotron Speech Streaming future-extension route",
        "reference_model_alias": REFERENCE_MODEL_ALIAS,
        "foundry_local_sdk_importable": sdk_importable,
        "foundry_local_importable": foundry_local_importable,
        "foundry_local_sdk_version": sdk_version,
        "foundry_local_core_version": core_version,
        "minimum_required_sdk_version": MINIMUM_SDK_VERSION,
        "sdk_version_compatible": sdk_version_compatible,
        "environment_compatible_with_reference_route": status == STATUS_READY,
        "m4a_audio_exists": inventory["m4a_audio_exists"],
        "m4a_audio_count": inventory["m4a_audio_count"],
        "wav_audio_exists": inventory["wav_audio_exists"],
        "wav_audio_count": inventory["wav_audio_count"],
        "audio_conversion_would_be_required": inventory["audio_conversion_would_be_required"],
        "dependency_changes_would_be_required_for_implementation": dependency_changes_required,
        "model_download_attempted": False,
        "real_stt_attempted": False,
        "speech_to_text_used": False,
        "fake_transcripts_generated": False,
        "live_microphone_used": False,
        "planner_called": False,
        "validators_called": False,
        "robot_execution_attempted": False,
        "emergency_stop_implemented": False,
        "binary_audio_files_committed": False,
        "notes": build_notes(status),
    }


def write_summary_json(path: Path, summary: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_summary_md(path: Path, summary: dict[str, Any]) -> None:
    text = f"""# Phase 2 Milestone 15B.0 Nemotron SDK STT Feasibility Summary

## Purpose

M15B.0 assesses whether Prototype 5 could adopt a future Foundry Local SDK plus Nemotron Speech Streaming STT route. It is an assessment only; it does not attempt transcription or implement voice control.

## Current Result

- Status: `{summary["status"]}`
- `foundry-local-sdk` importable: {str(summary["foundry_local_sdk_importable"]).lower()}
- `foundry-local-sdk` version: `{summary["foundry_local_sdk_version"]}`
- `foundry-local-core` version: `{summary["foundry_local_core_version"]}`
- SDK version compatible with `>= {summary["minimum_required_sdk_version"]}`: {str(summary["sdk_version_compatible"]).lower()}
- M4A audio files present: {summary["m4a_audio_count"]}
- WAV audio files present: {summary["wav_audio_count"]}
- Audio conversion would be required: {str(summary["audio_conversion_would_be_required"]).lower()}
- Dependency changes would be required for implementation: {str(summary["dependency_changes_would_be_required_for_implementation"]).lower()}

## Safety Boundary

- Model download attempted: {str(summary["model_download_attempted"]).lower()}
- Real STT attempted: {str(summary["real_stt_attempted"]).lower()}
- Speech-to-text used: {str(summary["speech_to_text_used"]).lower()}
- Fake transcripts generated: {str(summary["fake_transcripts_generated"]).lower()}
- Live microphone used: {str(summary["live_microphone_used"]).lower()}
- Planner called: {str(summary["planner_called"]).lower()}
- Validators called: {str(summary["validators_called"]).lower()}
- Robot execution attempted: {str(summary["robot_execution_attempted"]).lower()}

## Notes

{summary["notes"]}

## Claim Boundary

M15A.2 remains valid as negative HTTP endpoint evidence: the visible Foundry Whisper model did not expose a usable tested HTTP transcription route. M15B.0 records Nemotron SDK STT as a future-extension route only.

Prototype 5 remains a local-first zero-trust validation system for industrial robot task planning. This milestone does not expand it into a general voice assistant and does not prove live voice control, speech recognition accuracy, real robot readiness, or production safety.
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run_assessment(summary_json: Path, summary_md: Path, *, audio_dir: Path) -> dict[str, Any]:
    summary = build_summary(audio_dir)
    write_summary_json(summary_json, summary)
    write_summary_md(summary_md, summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Assess Nemotron SDK STT future-extension feasibility.")
    parser.add_argument("--audio-dir", type=Path, default=DEFAULT_AUDIO_DIR)
    parser.add_argument("--summary-json", type=Path, default=DEFAULT_SUMMARY_JSON)
    parser.add_argument("--summary-md", type=Path, default=DEFAULT_SUMMARY_MD)
    args = parser.parse_args()

    summary = run_assessment(args.summary_json, args.summary_md, audio_dir=args.audio_dir)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
