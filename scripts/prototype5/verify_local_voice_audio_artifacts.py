from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_MANIFEST = REPO_ROOT / "data" / "prototype5" / "mode_voice" / "audio_manifest.csv"
DEFAULT_AUDIO_DIR = REPO_ROOT / "data" / "prototype5" / "mode_voice" / "audio_samples"
DEFAULT_SUMMARY_JSON = (
    REPO_ROOT
    / "results"
    / "prototype5"
    / "mode_voice"
    / "phase2_milestone14c_local_audio_artifact_verification_summary.json"
)
DEFAULT_SUMMARY_MD = (
    REPO_ROOT
    / "results"
    / "prototype5"
    / "mode_voice"
    / "phase2_milestone14c_local_audio_artifact_verification_summary.md"
)

MILESTONE = "Phase 2 Milestone 14C"
MODE = "local_audio_artifact_verification"

REQUIRED_COLUMNS = {
    "audio_id",
    "case_id",
    "expected_audio_filename",
}

STATUS_ALL_PRESENT = "COMPLETE_LOCAL_AUDIO_VERIFICATION_ALL_PRESENT"
STATUS_MISSING_LOCAL_FILES = "COMPLETE_LOCAL_AUDIO_VERIFICATION_MISSING_LOCAL_FILES"
STATUS_MANIFEST_ERROR = "FAILED_MANIFEST_ERROR"


def timestamp_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - columns
        if missing:
            raise ValueError(f"Audio manifest is missing required columns: {sorted(missing)}")
        rows = [dict(row) for row in reader]

    if not rows:
        raise ValueError("Audio manifest contains no rows")

    filenames = [row["expected_audio_filename"].strip() for row in rows]
    duplicate_filenames = sorted({name for name in filenames if filenames.count(name) > 1})
    if duplicate_filenames:
        raise ValueError(f"Audio manifest contains duplicate expected filenames: {duplicate_filenames}")

    return rows


def inspect_expected_files(rows: list[dict[str, str]], audio_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    present_files: list[dict[str, Any]] = []
    missing_files: list[dict[str, Any]] = []

    for row in rows:
        filename = row["expected_audio_filename"].strip()
        path = audio_dir / filename
        record = {
            "audio_id": row["audio_id"],
            "case_id": row["case_id"],
            "expected_audio_filename": filename,
            "relative_path": str(Path("data") / "prototype5" / "mode_voice" / "audio_samples" / filename),
            "extension": path.suffix.lower(),
        }

        if path.is_file():
            present_record = dict(record)
            present_record["size_bytes"] = path.stat().st_size
            present_files.append(present_record)
        else:
            missing_record = dict(record)
            missing_record["size_bytes"] = None
            missing_files.append(missing_record)

    return present_files, missing_files


def build_summary(
    manifest_path: Path,
    audio_dir: Path,
    rows: list[dict[str, str]],
    present_files: list[dict[str, Any]],
    missing_files: list[dict[str, Any]],
    *,
    strict: bool,
) -> dict[str, Any]:
    expected_audio_count = len(rows)
    present_audio_count = len(present_files)
    missing_audio_count = len(missing_files)

    return {
        "status": STATUS_ALL_PRESENT if missing_audio_count == 0 else STATUS_MISSING_LOCAL_FILES,
        "timestamp_utc": timestamp_utc(),
        "milestone": MILESTONE,
        "mode": MODE,
        "manifest_path": str(manifest_path),
        "audio_dir": str(audio_dir),
        "manifest_rows": len(rows),
        "expected_audio_count": expected_audio_count,
        "present_audio_count": present_audio_count,
        "missing_audio_count": missing_audio_count,
        "binary_audio_files_committed": False,
        "audio_runtime_used": False,
        "speech_to_text_used": False,
        "live_microphone_used": False,
        "dependency_changes": False,
        "strict_mode": strict,
        "missing_files": missing_files,
        "present_files": present_files,
        "notes": (
            "M14C verifies local file presence and manifest alignment only. It does not read binary audio "
            "content, capture microphone input, run speech-to-text, load speech models, or grant execution authority."
        ),
    }


def build_manifest_error_summary(manifest_path: Path, audio_dir: Path, error: Exception, *, strict: bool) -> dict[str, Any]:
    return {
        "status": STATUS_MANIFEST_ERROR,
        "timestamp_utc": timestamp_utc(),
        "milestone": MILESTONE,
        "mode": MODE,
        "manifest_path": str(manifest_path),
        "audio_dir": str(audio_dir),
        "manifest_rows": 0,
        "expected_audio_count": 0,
        "present_audio_count": 0,
        "missing_audio_count": 0,
        "binary_audio_files_committed": False,
        "audio_runtime_used": False,
        "speech_to_text_used": False,
        "live_microphone_used": False,
        "dependency_changes": False,
        "strict_mode": strict,
        "missing_files": [],
        "present_files": [],
        "notes": f"Manifest verification failed before local audio artefact inspection: {error}",
    }


def write_summary_json(path: Path, summary: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_summary_md(path: Path, summary: dict[str, Any]) -> None:
    present_lines = "\n".join(
        f"- `{item['expected_audio_filename']}` ({item['case_id']}, {item['size_bytes']} bytes)"
        for item in summary["present_files"]
    )
    missing_lines = "\n".join(
        f"- `{item['expected_audio_filename']}` ({item['case_id']})" for item in summary["missing_files"]
    )

    if not present_lines:
        present_lines = "- None"
    if not missing_lines:
        missing_lines = "- None"

    text = f"""# Phase 2 Milestone 14C Local Audio Artefact Verification

## Purpose

M14C verifies whether the 15 local spoken-command audio artefacts referenced by the M14B manifest are present under `data/prototype5/mode_voice/audio_samples/`.

The verifier supports the expected development state where recordings may not exist yet. Non-strict mode records the missing local files without failing CI. Strict mode is available for local checks once recordings have been placed in the audio samples folder.

## Current Result

- Status: `{summary["status"]}`
- Expected audio count: {summary["expected_audio_count"]}
- Present audio count: {summary["present_audio_count"]}
- Missing audio count: {summary["missing_audio_count"]}
- Strict mode: {str(summary["strict_mode"]).lower()}
- Binary audio files committed: {str(summary["binary_audio_files_committed"]).lower()}
- Audio runtime used: {str(summary["audio_runtime_used"]).lower()}
- Speech-to-text used: {str(summary["speech_to_text_used"]).lower()}
- Live microphone used: {str(summary["live_microphone_used"]).lower()}
- Dependency changes: {str(summary["dependency_changes"]).lower()}

## Present Files

{present_lines}

## Missing Files

{missing_lines}

## Method

The verifier reads `expected_audio_filename` values from `data/prototype5/mode_voice/audio_manifest.csv` and checks for matching files in `data/prototype5/mode_voice/audio_samples/`. For present files it records only the extension and byte size. It does not parse headers, decode audio, inspect waveform data, transcribe speech, or load runtime audio components.

## Claim Boundary

M14C proves that Prototype 5 has a local verification path for checking whether the M14B audio artefacts exist and align with the manifest.

M14C does not prove live voice control, speech recognition accuracy, audio capture reliability, emergency-stop capability, production safety, real robot readiness, deployment readiness, or end-to-end voice understanding.
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run_verification(
    manifest_path: Path,
    audio_dir: Path,
    summary_json: Path,
    summary_md: Path,
    *,
    strict: bool = False,
) -> dict[str, Any]:
    try:
        rows = load_manifest(manifest_path)
        present_files, missing_files = inspect_expected_files(rows, audio_dir)
        summary = build_summary(manifest_path, audio_dir, rows, present_files, missing_files, strict=strict)
    except Exception as exc:
        summary = build_manifest_error_summary(manifest_path, audio_dir, exc, strict=strict)

    write_summary_json(summary_json, summary)
    write_summary_md(summary_md, summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify local M14C voice audio artefact presence.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--audio-dir", type=Path, default=DEFAULT_AUDIO_DIR)
    parser.add_argument("--summary-json", type=Path, default=DEFAULT_SUMMARY_JSON)
    parser.add_argument("--summary-md", type=Path, default=DEFAULT_SUMMARY_MD)
    parser.add_argument("--strict", action="store_true", help="Fail when any expected local audio files are missing.")
    args = parser.parse_args()

    summary = run_verification(
        args.manifest,
        args.audio_dir,
        args.summary_json,
        args.summary_md,
        strict=args.strict,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))

    if summary["status"] == STATUS_MANIFEST_ERROR:
        return 2
    if args.strict and summary["missing_audio_count"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
