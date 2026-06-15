from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request


REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_SUMMARY_JSON = (
    REPO_ROOT
    / "results"
    / "prototype5"
    / "mode_voice"
    / "phase2_milestone15a1_stt_backend_discovery_summary.json"
)
DEFAULT_SUMMARY_MD = (
    REPO_ROOT
    / "results"
    / "prototype5"
    / "mode_voice"
    / "phase2_milestone15a1_stt_backend_discovery_summary.md"
)

MILESTONE = "Phase 2 Milestone 15A.1"
MODE = "stt_backend_discovery_spike"

STT_ENV_VARS = (
    "FOUNDRY_LOCAL_BASE_URL",
    "FOUNDRY_LOCAL_MODEL",
    "FOUNDRY_LOCAL_STT_MODEL",
    "PROTOTYPE5_STT_BACKEND",
    "PROTOTYPE5_STT_MODEL",
    "WHISPER_MODEL",
)
STT_MODEL_TOKENS = ("whisper", "speech", "stt", "audio")
CLI_CANDIDATES = ("whisper", "whisper-cli", "faster-whisper", "ffmpeg")
PYTHON_PACKAGE_CANDIDATES = ("whisper", "faster_whisper", "openai")

STATUS_CANDIDATE_FOUND = "COMPLETE_STT_BACKEND_DISCOVERY_CANDIDATE_FOUND"
STATUS_CANDIDATE_ENDPOINT_UNAVAILABLE = "COMPLETE_STT_BACKEND_DISCOVERY_CANDIDATE_FOUND_ENDPOINT_UNAVAILABLE"
STATUS_NO_BACKEND_FOUND = "COMPLETE_STT_BACKEND_DISCOVERY_NO_BACKEND_FOUND"
STATUS_FOUNDRY_UNREACHABLE = "COMPLETE_STT_BACKEND_DISCOVERY_FOUNDRY_UNREACHABLE"


def timestamp_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalise_base_url(base_url: str) -> str:
    return base_url.strip().rstrip("/")


def configured_environment() -> dict[str, str]:
    return {name: os.environ[name] for name in STT_ENV_VARS if os.environ.get(name)}


def extract_model_ids(payload: dict[str, Any]) -> list[str]:
    data = payload.get("data", [])
    model_ids: list[str] = []
    if not isinstance(data, list):
        return model_ids

    for item in data:
        if isinstance(item, dict) and item.get("id"):
            model_ids.append(str(item["id"]))
        elif isinstance(item, str):
            model_ids.append(item)
    return model_ids


def discover_foundry_models(base_url: str | None, timeout_seconds: float) -> dict[str, Any]:
    if not base_url:
        return {
            "base_url": "",
            "models_endpoint": "",
            "reachable": False,
            "model_aliases": [],
            "candidate_stt_models": [],
            "error": "FOUNDRY_LOCAL_BASE_URL is not configured.",
        }

    normalised = normalise_base_url(base_url)
    endpoint = f"{normalised}/v1/models"
    try:
        req = urllib_request.Request(endpoint, method="GET", headers={"Accept": "application/json"})
        with urllib_request.urlopen(req, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8-sig"))
        aliases = extract_model_ids(payload)
        return {
            "base_url": normalised,
            "models_endpoint": endpoint,
            "reachable": True,
            "model_aliases": aliases,
            "candidate_stt_models": [
                alias for alias in aliases if any(token in alias.lower() for token in STT_MODEL_TOKENS)
            ],
            "error": "",
        }
    except (OSError, TimeoutError, urllib_error.URLError, json.JSONDecodeError) as exc:
        return {
            "base_url": normalised,
            "models_endpoint": endpoint,
            "reachable": False,
            "model_aliases": [],
            "candidate_stt_models": [],
            "error": f"{type(exc).__name__}: {exc}",
        }


def probe_audio_transcription_endpoint(
    base_url: str | None,
    candidate_models: list[str],
    timeout_seconds: float,
) -> str:
    if not base_url:
        return "NOT_PROBED_BASE_URL_NOT_CONFIGURED"
    if not candidate_models:
        return "NOT_PROBED_NO_CANDIDATE_STT_MODEL"

    endpoint = f"{normalise_base_url(base_url)}/v1/audio/transcriptions"
    try:
        req = urllib_request.Request(endpoint, method="OPTIONS", headers={"Accept": "application/json"})
        with urllib_request.urlopen(req, timeout=timeout_seconds):
            return "REACHABLE_OPTIONS_OK"
    except urllib_error.HTTPError as exc:
        if exc.code in {400, 401, 403, 405, 415}:
            return f"ENDPOINT_PRESENT_OR_PROTECTED_HTTP_{exc.code}"
        if exc.code == 404:
            return "NOT_FOUND_HTTP_404"
        return f"HTTP_ERROR_{exc.code}"
    except (OSError, TimeoutError, urllib_error.URLError) as exc:
        return f"UNREACHABLE_{type(exc).__name__}"


def discover_cli_candidates() -> dict[str, str | None]:
    return {name: shutil.which(name) for name in CLI_CANDIDATES}


def discover_python_package_candidates() -> dict[str, bool]:
    return {name: importlib.util.find_spec(name) is not None for name in PYTHON_PACKAGE_CANDIDATES}


def recommend_backend(
    candidate_foundry_stt_models: list[str],
    endpoint_probe_status: str,
    cli_candidates: dict[str, str | None],
    python_package_candidates: dict[str, bool],
) -> str:
    if candidate_foundry_stt_models and transcription_endpoint_candidate_is_usable(endpoint_probe_status):
        return "foundry-whisper-candidate"
    if cli_candidates.get("whisper") or cli_candidates.get("whisper-cli"):
        return "local-whisper-cli-candidate"
    if cli_candidates.get("faster-whisper"):
        return "faster-whisper-cli-candidate"
    if python_package_candidates.get("whisper"):
        return "local-whisper-python-candidate"
    if python_package_candidates.get("faster_whisper"):
        return "faster-whisper-python-candidate"
    return "none"


def transcription_endpoint_candidate_is_usable(endpoint_probe_status: str) -> bool:
    return endpoint_probe_status == "REACHABLE_OPTIONS_OK" or endpoint_probe_status.startswith(
        "ENDPOINT_PRESENT_OR_PROTECTED_HTTP_"
    )


def classify_discovery(
    *,
    base_url: str,
    foundry_reachable: bool,
    candidate_models: list[str],
    endpoint_probe_status: str,
    recommended_backend: str,
    foundry_error: str,
) -> tuple[str, str]:
    if recommended_backend != "none":
        return (
            STATUS_CANDIDATE_FOUND,
            "Discovery found a usable STT backend candidate. M15A.2 should run a controlled one-file smoke test.",
        )

    if base_url and not foundry_reachable:
        return (
            STATUS_FOUNDRY_UNREACHABLE,
            f"Foundry Local base URL was configured but /v1/models was not reachable: {foundry_error}",
        )

    if foundry_reachable and candidate_models:
        return (
            STATUS_CANDIDATE_ENDPOINT_UNAVAILABLE,
            (
                "Foundry Local is reachable and exposes an STT/Whisper model candidate, but no usable "
                f"audio transcription endpoint was confirmed. Endpoint probe status: {endpoint_probe_status}."
            ),
        )

    return (
        STATUS_NO_BACKEND_FOUND,
        "No STT backend candidate was discovered without installing dependencies or downloading models.",
    )


def build_summary(timeout_seconds: float) -> dict[str, Any]:
    env = configured_environment()
    base_url = env.get("FOUNDRY_LOCAL_BASE_URL", "")
    foundry = discover_foundry_models(base_url, timeout_seconds)
    candidate_models = foundry["candidate_stt_models"]
    endpoint_probe_status = probe_audio_transcription_endpoint(base_url, candidate_models, timeout_seconds)
    cli_candidates = discover_cli_candidates()
    python_package_candidates = discover_python_package_candidates()
    recommended_backend = recommend_backend(
        candidate_models,
        endpoint_probe_status,
        cli_candidates,
        python_package_candidates,
    )

    status, notes = classify_discovery(
        base_url=base_url,
        foundry_reachable=bool(foundry["reachable"]),
        candidate_models=candidate_models,
        endpoint_probe_status=endpoint_probe_status,
        recommended_backend=recommended_backend,
        foundry_error=foundry["error"],
    )

    return {
        "status": status,
        "timestamp_utc": timestamp_utc(),
        "milestone": MILESTONE,
        "mode": MODE,
        "configured_environment_variables": sorted(env.keys()),
        "foundry_base_url_configured": bool(base_url),
        "foundry_base_url": base_url,
        "foundry_models_endpoint_reachable": bool(foundry["reachable"]),
        "foundry_model_aliases": foundry["model_aliases"],
        "candidate_foundry_stt_models": candidate_models,
        "audio_transcription_endpoint_probe_status": endpoint_probe_status,
        "local_cli_candidates": cli_candidates,
        "python_package_candidates": python_package_candidates,
        "recommended_backend": recommended_backend,
        "real_stt_attempted": False,
        "speech_to_text_used": False,
        "fake_transcripts_generated": False,
        "dependency_changes": False,
        "live_microphone_used": False,
        "planner_called": False,
        "validators_called": False,
        "execution_eligible_count": 0,
        "binary_audio_files_committed": False,
        "notes": notes,
    }


def write_summary_json(path: Path, summary: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_summary_md(path: Path, summary: dict[str, Any]) -> None:
    cli_lines = "\n".join(
        f"- `{name}`: `{path or 'not found'}`" for name, path in summary["local_cli_candidates"].items()
    )
    package_lines = "\n".join(
        f"- `{name}`: {str(available).lower()}"
        for name, available in summary["python_package_candidates"].items()
    )
    model_lines = "\n".join(f"- `{model}`" for model in summary["candidate_foundry_stt_models"]) or "- None"

    text = f"""# Phase 2 Milestone 15A.1 STT Backend Discovery Summary

## Purpose

M15A.1 discovers whether this machine already exposes a usable speech-to-text backend for the local M4A voice artefacts. It does not transcribe audio, install packages, download models, capture microphone input, call the planner, or run validators.

## Current Result

- Status: `{summary["status"]}`
- Foundry Local base URL configured: {str(summary["foundry_base_url_configured"]).lower()}
- `/v1/models` reachable: {str(summary["foundry_models_endpoint_reachable"]).lower()}
- Audio transcription endpoint probe: `{summary["audio_transcription_endpoint_probe_status"]}`
- Recommended backend: `{summary["recommended_backend"]}`
- Real STT attempted: {str(summary["real_stt_attempted"]).lower()}
- Speech-to-text used: {str(summary["speech_to_text_used"]).lower()}
- Fake transcripts generated: {str(summary["fake_transcripts_generated"]).lower()}
- Dependency changes: {str(summary["dependency_changes"]).lower()}
- Live microphone used: {str(summary["live_microphone_used"]).lower()}
- Planner called: {str(summary["planner_called"]).lower()}
- Validators called: {str(summary["validators_called"]).lower()}

## Candidate Foundry STT Models

{model_lines}

## Local CLI Candidates

{cli_lines}

## Python Package Candidates

{package_lines}

## Notes

{summary["notes"]}

## Claim Boundary

M15A.1 proves only backend discovery status. It does not prove speech recognition works, live voice control, emergency-stop capability, production safety, real robot readiness, a production voice interface, or deployment readiness.
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run_discovery(summary_json: Path, summary_md: Path, *, timeout_seconds: float) -> dict[str, Any]:
    summary = build_summary(timeout_seconds)
    write_summary_json(summary_json, summary)
    write_summary_md(summary_md, summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover already-available STT backends for M15A.1.")
    parser.add_argument("--summary-json", type=Path, default=DEFAULT_SUMMARY_JSON)
    parser.add_argument("--summary-md", type=Path, default=DEFAULT_SUMMARY_MD)
    parser.add_argument("--timeout-seconds", type=float, default=2.0)
    args = parser.parse_args()

    summary = run_discovery(args.summary_json, args.summary_md, timeout_seconds=args.timeout_seconds)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
