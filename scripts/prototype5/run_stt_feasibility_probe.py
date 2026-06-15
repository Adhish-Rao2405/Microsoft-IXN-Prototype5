from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_AUDIO_MANIFEST = REPO_ROOT / "data" / "prototype5" / "mode_voice" / "audio_manifest.csv"
DEFAULT_TRANSCRIPT_MANIFEST = (
    REPO_ROOT / "data" / "prototype5" / "mode_voice" / "audio_transcript_manifest.csv"
)
DEFAULT_AUDIO_DIR = REPO_ROOT / "data" / "prototype5" / "mode_voice" / "audio_samples"
DEFAULT_RESULTS_CSV = (
    REPO_ROOT / "results" / "prototype5" / "mode_voice" / "phase2_milestone15a_stt_feasibility_results.csv"
)
DEFAULT_SUMMARY_JSON = (
    REPO_ROOT / "results" / "prototype5" / "mode_voice" / "phase2_milestone15a_stt_feasibility_summary.json"
)
DEFAULT_SUMMARY_MD = (
    REPO_ROOT / "results" / "prototype5" / "mode_voice" / "phase2_milestone15a_stt_feasibility_summary.md"
)

MILESTONE = "Phase 2 Milestone 15A"
MODE = "bounded_stt_feasibility_spike"

STATUS_REAL_TRANSCRIPTS = "COMPLETE_STT_FEASIBILITY_REAL_TRANSCRIPTS"
STATUS_BLOCKED_BACKEND_UNAVAILABLE = "COMPLETE_STT_FEASIBILITY_BLOCKED_BACKEND_UNAVAILABLE"
STATUS_BLOCKED_AUDIO_MISSING = "COMPLETE_STT_FEASIBILITY_BLOCKED_AUDIO_MISSING"
STATUS_MANIFEST_ERROR = "FAILED_STT_FEASIBILITY_MANIFEST_ERROR"

RESULT_FIELDS = (
    "audio_id",
    "case_id",
    "scenario_family",
    "audio_filename",
    "audio_present",
    "backend",
    "stt_attempted",
    "stt_success",
    "automatic_transcript",
    "confidence",
    "latency_ms",
    "failure_reason",
    "manual_transcript_available",
    "notes",
)

REQUIRED_AUDIO_COLUMNS = {
    "audio_id",
    "case_id",
    "scenario_family",
    "expected_audio_filename",
}


@dataclass(frozen=True)
class BackendAvailability:
    selected_backend: str
    available: bool
    failure_reason: str
    speech_to_text_used: bool = False
    audio_runtime_used: bool = False


def timestamp_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def load_audio_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
        missing = REQUIRED_AUDIO_COLUMNS - columns
        if missing:
            raise ValueError(f"Audio manifest is missing required columns: {sorted(missing)}")
        rows = [dict(row) for row in reader]

    if not rows:
        raise ValueError("Audio manifest contains no rows")

    return rows


def load_manual_transcript_ids(path: Path) -> set[str]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return {row["audio_id"] for row in reader if row.get("audio_id")}


def resolve_backend(backend: str) -> BackendAvailability:
    if backend == "unavailable-stub":
        return BackendAvailability(
            selected_backend="unavailable-stub",
            available=False,
            failure_reason="STT_BACKEND_UNAVAILABLE: unavailable-stub selected for blocked-boundary evidence",
        )

    whisper_module_available = importlib.util.find_spec("whisper") is not None
    whisper_cli_path = shutil.which("whisper")

    if backend == "local-whisper":
        if whisper_module_available or whisper_cli_path:
            return BackendAvailability(
                selected_backend="local-whisper",
                available=False,
                failure_reason=(
                    "STT_BACKEND_UNAVAILABLE: local Whisper was detected but M15A does not load models "
                    "or risk implicit downloads without a configured no-download adapter"
                ),
            )
        return BackendAvailability(
            selected_backend="local-whisper",
            available=False,
            failure_reason="STT_BACKEND_UNAVAILABLE: no installed whisper module or whisper CLI found",
        )

    if backend == "foundry-whisper":
        return BackendAvailability(
            selected_backend="foundry-whisper",
            available=False,
            failure_reason=(
                "STT_BACKEND_UNAVAILABLE: no repo-local Foundry Whisper transcription adapter is configured"
            ),
        )

    if backend == "auto":
        if whisper_module_available or whisper_cli_path:
            return BackendAvailability(
                selected_backend="auto",
                available=False,
                failure_reason=(
                    "STT_BACKEND_UNAVAILABLE: Whisper appears present but no explicit no-download "
                    "transcription adapter is configured for M15A"
                ),
            )
        return BackendAvailability(
            selected_backend="auto",
            available=False,
            failure_reason="STT_BACKEND_UNAVAILABLE: no configured Foundry Whisper or local Whisper backend found",
        )

    raise ValueError(f"Unsupported STT backend: {backend}")


def build_blocked_row(
    row: dict[str, str],
    audio_dir: Path,
    backend: str,
    failure_reason: str,
    manual_transcript_ids: set[str],
) -> dict[str, str]:
    filename = row["expected_audio_filename"].strip()
    audio_present = (audio_dir / filename).is_file()
    audio_missing_reason = "AUDIO_MISSING: expected local audio file is absent"

    return {
        "audio_id": row["audio_id"],
        "case_id": row["case_id"],
        "scenario_family": row["scenario_family"],
        "audio_filename": filename,
        "audio_present": bool_text(audio_present),
        "backend": backend,
        "stt_attempted": "false",
        "stt_success": "false",
        "automatic_transcript": "",
        "confidence": "",
        "latency_ms": "",
        "failure_reason": failure_reason if audio_present else audio_missing_reason,
        "manual_transcript_available": bool_text(row["audio_id"] in manual_transcript_ids),
        "notes": (
            "No automatic transcript was generated. Manual transcript metadata is used only to mark "
            "ground-truth availability for later M15B comparison."
        ),
    }


def build_results(
    audio_rows: list[dict[str, str]],
    manual_transcript_ids: set[str],
    audio_dir: Path,
    backend: BackendAvailability,
) -> list[dict[str, str]]:
    return [
        build_blocked_row(row, audio_dir, backend.selected_backend, backend.failure_reason, manual_transcript_ids)
        for row in audio_rows
    ]


def build_summary(results: list[dict[str, str]], backend: BackendAvailability) -> dict[str, Any]:
    audio_count = len(results)
    audio_present_count = sum(row["audio_present"] == "true" for row in results)
    stt_attempted_count = sum(row["stt_attempted"] == "true" for row in results)
    stt_success_count = sum(row["stt_success"] == "true" for row in results)
    transcript_count = sum(bool(row["automatic_transcript"].strip()) for row in results)
    latencies = [float(row["latency_ms"]) for row in results if row["latency_ms"].strip()]

    if audio_present_count < audio_count:
        status = STATUS_BLOCKED_AUDIO_MISSING
    elif stt_success_count > 0:
        status = STATUS_REAL_TRANSCRIPTS
    else:
        status = STATUS_BLOCKED_BACKEND_UNAVAILABLE

    return {
        "status": status,
        "timestamp_utc": timestamp_utc(),
        "milestone": MILESTONE,
        "mode": MODE,
        "backend": backend.selected_backend,
        "audio_count": audio_count,
        "audio_present_count": audio_present_count,
        "stt_attempted_count": stt_attempted_count,
        "stt_success_count": stt_success_count,
        "stt_failure_count": audio_count - stt_success_count,
        "automatic_transcript_count": transcript_count,
        "mean_latency_ms": round(mean(latencies), 2) if latencies else None,
        "speech_to_text_used": backend.speech_to_text_used,
        "live_microphone_used": False,
        "audio_runtime_used": backend.audio_runtime_used,
        "dependency_changes": False,
        "planner_called": False,
        "validators_called": False,
        "execution_eligible_count": 0,
        "binary_audio_files_committed": False,
        "manual_transcripts_used_as_ground_truth_only": True,
        "fake_transcripts_generated": False,
        "notes": backend.failure_reason
        if status != STATUS_REAL_TRANSCRIPTS
        else "Real STT transcripts were generated by the selected backend.",
    }


def build_manifest_error_summary(error: Exception, backend_name: str) -> dict[str, Any]:
    return {
        "status": STATUS_MANIFEST_ERROR,
        "timestamp_utc": timestamp_utc(),
        "milestone": MILESTONE,
        "mode": MODE,
        "backend": backend_name,
        "audio_count": 0,
        "audio_present_count": 0,
        "stt_attempted_count": 0,
        "stt_success_count": 0,
        "stt_failure_count": 0,
        "automatic_transcript_count": 0,
        "mean_latency_ms": None,
        "speech_to_text_used": False,
        "live_microphone_used": False,
        "audio_runtime_used": False,
        "dependency_changes": False,
        "planner_called": False,
        "validators_called": False,
        "execution_eligible_count": 0,
        "binary_audio_files_committed": False,
        "manual_transcripts_used_as_ground_truth_only": True,
        "fake_transcripts_generated": False,
        "notes": f"M15A manifest loading failed before STT feasibility probing: {error}",
    }


def write_results_csv(path: Path, results: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(results)


def write_summary_json(path: Path, summary: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_summary_md(path: Path, summary: dict[str, Any]) -> None:
    text = f"""# Phase 2 Milestone 15A STT Feasibility Summary

## Purpose

M15A tests whether the 15 local M14B/M14C voice artefacts can enter a bounded speech-to-text feasibility path without changing the zero-trust planning architecture.

This milestone is audio file to automatic transcript candidate only. It does not call the planner, run validators, grant execution eligibility, capture microphone input, or execute a robot.

## Current Result

- Status: `{summary["status"]}`
- Backend: `{summary["backend"]}`
- Audio count: {summary["audio_count"]}
- Audio present count: {summary["audio_present_count"]}
- STT attempted count: {summary["stt_attempted_count"]}
- STT success count: {summary["stt_success_count"]}
- Automatic transcript count: {summary["automatic_transcript_count"]}
- Mean latency ms: {summary["mean_latency_ms"]}
- Speech-to-text used: {str(summary["speech_to_text_used"]).lower()}
- Audio runtime used: {str(summary["audio_runtime_used"]).lower()}
- Live microphone used: {str(summary["live_microphone_used"]).lower()}
- Planner called: {str(summary["planner_called"]).lower()}
- Validators called: {str(summary["validators_called"]).lower()}
- Execution-eligible count: {summary["execution_eligible_count"]}
- Fake transcripts generated: {str(summary["fake_transcripts_generated"]).lower()}

## Backend Finding

{summary["notes"]}

## Claim Boundary

M15A proves either real bounded STT feasibility or an honest blocked STT adapter boundary. In the current summary, no automatic transcript is recorded unless a real backend actually produces it from audio.

M15A does not prove live voice control, speech recognition accuracy, emergency-stop capability, real robot safety, production readiness, a production voice interface, or deployment readiness.

## Next Milestones

M15B should compare real automatic transcripts against the M14A/M14B manual transcript ground truth. M15C should route automatic transcripts through the existing M12/M13 zero-trust pathway.
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run_probe(
    audio_manifest: Path,
    transcript_manifest: Path,
    audio_dir: Path,
    results_csv: Path,
    summary_json: Path,
    summary_md: Path,
    *,
    backend_name: str,
) -> dict[str, Any]:
    try:
        backend = resolve_backend(backend_name)
        audio_rows = load_audio_manifest(audio_manifest)
        manual_transcript_ids = load_manual_transcript_ids(transcript_manifest)
        results = build_results(audio_rows, manual_transcript_ids, audio_dir, backend)
        summary = build_summary(results, backend)
        write_results_csv(results_csv, results)
    except Exception as exc:
        summary = build_manifest_error_summary(exc, backend_name)
        write_results_csv(results_csv, [])

    write_summary_json(summary_json, summary)
    write_summary_md(summary_md, summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the M15A bounded STT feasibility probe.")
    parser.add_argument("--backend", choices=("auto", "foundry-whisper", "local-whisper", "unavailable-stub"), default="auto")
    parser.add_argument("--audio-manifest", type=Path, default=DEFAULT_AUDIO_MANIFEST)
    parser.add_argument("--transcript-manifest", type=Path, default=DEFAULT_TRANSCRIPT_MANIFEST)
    parser.add_argument("--audio-dir", type=Path, default=DEFAULT_AUDIO_DIR)
    parser.add_argument("--results-csv", type=Path, default=DEFAULT_RESULTS_CSV)
    parser.add_argument("--summary-json", type=Path, default=DEFAULT_SUMMARY_JSON)
    parser.add_argument("--summary-md", type=Path, default=DEFAULT_SUMMARY_MD)
    args = parser.parse_args()

    summary = run_probe(
        args.audio_manifest,
        args.transcript_manifest,
        args.audio_dir,
        args.results_csv,
        args.summary_json,
        args.summary_md,
        backend_name=args.backend,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))

    return 2 if summary["status"] == STATUS_MANIFEST_ERROR else 0


if __name__ == "__main__":
    raise SystemExit(main())
