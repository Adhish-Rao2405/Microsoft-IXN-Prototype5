from __future__ import annotations

import argparse
import json
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request


REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_AUDIO_DIR = REPO_ROOT / "data" / "prototype5" / "mode_voice" / "audio_samples"
DEFAULT_MODEL = "openai-whisper-tiny-generic-cpu:2"
DEFAULT_SUMMARY_JSON = (
    REPO_ROOT
    / "results"
    / "prototype5"
    / "mode_voice"
    / "phase2_milestone15a2_foundry_whisper_endpoint_probe_summary.json"
)
DEFAULT_SUMMARY_MD = (
    REPO_ROOT
    / "results"
    / "prototype5"
    / "mode_voice"
    / "phase2_milestone15a2_foundry_whisper_endpoint_probe_summary.md"
)

MILESTONE = "Phase 2 Milestone 15A.2"
MODE = "foundry_whisper_transcription_endpoint_feasibility_probe"

STATUS_USABLE = "COMPLETE_FOUNDRY_WHISPER_ENDPOINT_PROBE_USABLE_STT_CONFIRMED"
STATUS_NO_USABLE_ENDPOINT = "COMPLETE_FOUNDRY_WHISPER_ENDPOINT_PROBE_NO_USABLE_ENDPOINT"
STATUS_BASE_URL_MISSING = "COMPLETE_FOUNDRY_WHISPER_ENDPOINT_PROBE_BASE_URL_MISSING"
STATUS_AUDIO_MISSING = "COMPLETE_FOUNDRY_WHISPER_ENDPOINT_PROBE_AUDIO_MISSING"

ENDPOINT_PATHS = (
    "/v1/audio/transcriptions",
    "/v1/transcriptions",
    "/v1/models/{model}/transcriptions",
)


@dataclass(frozen=True)
class HttpProbeResponse:
    status_code: int | None
    body: str
    latency_ms: float
    error: str


def timestamp_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalise_base_url(base_url: str) -> str:
    return base_url.strip().rstrip("/")


def locate_audio_file(audio_dir: Path, requested_audio: Path | None = None) -> Path | None:
    if requested_audio is not None:
        candidate = requested_audio if requested_audio.is_absolute() else REPO_ROOT / requested_audio
        return candidate if candidate.is_file() else None

    candidates = sorted(
        (path for path in audio_dir.glob("*.m4a") if path.is_file()),
        key=lambda path: (path.stat().st_size, path.name),
    )
    return candidates[0] if candidates else None


def extract_model_ids(payload: dict[str, Any]) -> list[str]:
    data = payload.get("data", [])
    if not isinstance(data, list):
        return []
    return [
        str(item["id"])
        for item in data
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    ]


def get_json(url: str, timeout_seconds: float) -> HttpProbeResponse:
    started = time.perf_counter()
    try:
        req = urllib_request.Request(url, method="GET", headers={"Accept": "application/json"})
        with urllib_request.urlopen(req, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8", errors="replace")
            return HttpProbeResponse(
                status_code=response.getcode(),
                body=body,
                latency_ms=round((time.perf_counter() - started) * 1000.0, 3),
                error="",
            )
    except urllib_error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return HttpProbeResponse(
            status_code=exc.code,
            body=body,
            latency_ms=round((time.perf_counter() - started) * 1000.0, 3),
            error=f"HTTP {exc.code}: {exc.reason}",
        )
    except (OSError, TimeoutError, urllib_error.URLError) as exc:
        return HttpProbeResponse(
            status_code=None,
            body="",
            latency_ms=round((time.perf_counter() - started) * 1000.0, 3),
            error=f"{type(exc).__name__}: {exc}",
        )


def build_multipart_body(audio_path: Path, model: str | None) -> tuple[bytes, str]:
    boundary = f"----prototype5-{uuid.uuid4().hex}"
    chunks: list[bytes] = []

    def add_field(name: str, value: str) -> None:
        chunks.extend(
            [
                f"--{boundary}\r\n".encode("ascii"),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("ascii"),
                value.encode("utf-8"),
                b"\r\n",
            ]
        )

    if model:
        add_field("model", model)

    chunks.extend(
        [
            f"--{boundary}\r\n".encode("ascii"),
            (
                f'Content-Disposition: form-data; name="file"; filename="{audio_path.name}"\r\n'
            ).encode("utf-8"),
            b"Content-Type: audio/mp4\r\n\r\n",
            audio_path.read_bytes(),
            b"\r\n",
            f"--{boundary}--\r\n".encode("ascii"),
        ]
    )
    return b"".join(chunks), boundary


def post_audio(
    url: str,
    audio_path: Path,
    model: str | None,
    timeout_seconds: float,
) -> HttpProbeResponse:
    started = time.perf_counter()
    body, boundary = build_multipart_body(audio_path, model)
    req = urllib_request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    try:
        with urllib_request.urlopen(req, timeout=timeout_seconds) as response:
            response_body = response.read().decode("utf-8", errors="replace")
            return HttpProbeResponse(
                status_code=response.getcode(),
                body=response_body,
                latency_ms=round((time.perf_counter() - started) * 1000.0, 3),
                error="",
            )
    except urllib_error.HTTPError as exc:
        response_body = exc.read().decode("utf-8", errors="replace")
        return HttpProbeResponse(
            status_code=exc.code,
            body=response_body,
            latency_ms=round((time.perf_counter() - started) * 1000.0, 3),
            error=f"HTTP {exc.code}: {exc.reason}",
        )
    except (OSError, TimeoutError, urllib_error.URLError) as exc:
        return HttpProbeResponse(
            status_code=None,
            body="",
            latency_ms=round((time.perf_counter() - started) * 1000.0, 3),
            error=f"{type(exc).__name__}: {exc}",
        )


def extract_transcript_like_text(body: str) -> str:
    if not body.strip():
        return ""
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return ""
    if not isinstance(payload, dict):
        return ""

    for key in ("text", "transcript"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    segments = payload.get("segments")
    if isinstance(segments, list):
        texts = [
            str(segment["text"]).strip()
            for segment in segments
            if isinstance(segment, dict) and str(segment.get("text", "")).strip()
        ]
        return " ".join(texts)
    return ""


def response_snippet(body: str, limit: int = 500) -> str:
    return body.strip().replace("\x00", "")[:limit]


def probe_endpoints(
    base_url: str,
    model: str,
    audio_path: Path,
    timeout_seconds: float,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for path_template in ENDPOINT_PATHS:
        path = path_template.format(model=model)
        include_model = not path_template.startswith("/v1/models/")
        response = post_audio(
            f"{normalise_base_url(base_url)}{path}",
            audio_path,
            model if include_model else None,
            timeout_seconds,
        )
        transcript = extract_transcript_like_text(response.body) if response.status_code else ""
        usable = bool(response.status_code and 200 <= response.status_code < 300 and transcript)
        results.append(
            {
                "route": path,
                "http_status": response.status_code,
                "latency_ms": response.latency_ms,
                "response_snippet": response_snippet(response.body),
                "error": response.error,
                "transcript_like_response": bool(transcript),
                "automatic_transcript": transcript if usable else "",
                "usable_stt_confirmed": usable,
            }
        )
    return results


def build_summary(
    *,
    base_url: str,
    model: str,
    audio_path: Path | None,
    timeout_seconds: float,
) -> dict[str, Any]:
    common = {
        "timestamp_utc": timestamp_utc(),
        "milestone": MILESTONE,
        "mode": MODE,
        "foundry_base_url_configured": bool(base_url),
        "foundry_base_url": base_url,
        "candidate_model": model,
        "candidate_model_visible": False,
        "audio_file": audio_path.name if audio_path else "",
        "audio_file_present": bool(audio_path),
        "routes_attempted": [],
        "usable_endpoint_confirmed": False,
        "automatic_transcript": "",
        "real_stt_attempted": False,
        "speech_to_text_used": False,
        "fake_transcripts_generated": False,
        "dependency_changes": False,
        "live_microphone_used": False,
        "planner_called": False,
        "validators_called": False,
        "robot_execution_used": False,
        "emergency_stop_implemented": False,
        "execution_eligible_count": 0,
        "binary_audio_files_committed": False,
    }

    if not base_url:
        return {
            **common,
            "status": STATUS_BASE_URL_MISSING,
            "notes": "FOUNDRY_LOCAL_BASE_URL is not configured; no endpoint probe was attempted.",
        }
    if audio_path is None:
        return {
            **common,
            "status": STATUS_AUDIO_MISSING,
            "notes": "No local M4A audio file was available; no endpoint probe was attempted.",
        }

    models_response = get_json(f"{normalise_base_url(base_url)}/v1/models", timeout_seconds)
    model_ids: list[str] = []
    if models_response.status_code and 200 <= models_response.status_code < 300:
        try:
            payload = json.loads(models_response.body)
            if isinstance(payload, dict):
                model_ids = extract_model_ids(payload)
        except json.JSONDecodeError:
            model_ids = []
    candidate_visible = model in model_ids

    routes = probe_endpoints(base_url, model, audio_path, timeout_seconds)
    usable_route = next((route for route in routes if route["usable_stt_confirmed"]), None)

    return {
        **common,
        "status": STATUS_USABLE if usable_route else STATUS_NO_USABLE_ENDPOINT,
        "candidate_model_visible": candidate_visible,
        "foundry_models_endpoint_status": models_response.status_code,
        "routes_attempted": routes,
        "usable_endpoint_confirmed": usable_route is not None,
        "automatic_transcript": usable_route["automatic_transcript"] if usable_route else "",
        "real_stt_attempted": True,
        "speech_to_text_used": usable_route is not None,
        "notes": (
            "A 2xx transcript-like response confirmed a usable Foundry Whisper transcription endpoint."
            if usable_route
            else (
                "The candidate model was visible, but none of the fixed transcription routes returned "
                "a usable 2xx transcript-like response."
            )
        ),
    }


def write_summary_json(path: Path, summary: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_summary_md(path: Path, summary: dict[str, Any]) -> None:
    route_lines = []
    for route in summary["routes_attempted"]:
        route_lines.append(
            f"- `{route['route']}`: HTTP `{route['http_status']}`, "
            f"transcript-like response `{str(route['transcript_like_response']).lower()}`, "
            f"usable `{str(route['usable_stt_confirmed']).lower()}`"
        )
    routes = "\n".join(route_lines) or "- None"

    text = f"""# Phase 2 Milestone 15A.2 Foundry Whisper Endpoint Probe

## Purpose

M15A.2 probes a fixed set of likely Foundry Local transcription routes using one existing local M4A artefact. It is endpoint feasibility only.

## Current Result

- Status: `{summary["status"]}`
- Foundry base URL configured: {str(summary["foundry_base_url_configured"]).lower()}
- Candidate model: `{summary["candidate_model"]}`
- Candidate model visible: {str(summary["candidate_model_visible"]).lower()}
- Audio file: `{summary["audio_file"]}`
- Audio file present: {str(summary["audio_file_present"]).lower()}
- Usable endpoint confirmed: {str(summary["usable_endpoint_confirmed"]).lower()}
- Real STT attempted: {str(summary["real_stt_attempted"]).lower()}
- Speech-to-text used successfully: {str(summary["speech_to_text_used"]).lower()}
- Fake transcripts generated: {str(summary["fake_transcripts_generated"]).lower()}

## Routes Attempted

{routes}

## Notes

{summary["notes"]}

## Claim Boundary

M15A.2 tests endpoint feasibility for one local audio file. It does not implement live voice control, microphone capture, planner or validator routing, robot execution, emergency stop, production safety, or deployment readiness.
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run_probe(
    summary_json: Path,
    summary_md: Path,
    *,
    base_url: str,
    model: str,
    audio_dir: Path,
    audio_file: Path | None,
    timeout_seconds: float,
) -> dict[str, Any]:
    audio_path = locate_audio_file(audio_dir, audio_file)
    summary = build_summary(
        base_url=base_url,
        model=model,
        audio_path=audio_path,
        timeout_seconds=timeout_seconds,
    )
    write_summary_json(summary_json, summary)
    write_summary_md(summary_md, summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe Foundry Whisper transcription endpoint feasibility.")
    parser.add_argument("--base-url", default=os.environ.get("FOUNDRY_LOCAL_BASE_URL", ""))
    parser.add_argument(
        "--model",
        default=os.environ.get("FOUNDRY_LOCAL_STT_MODEL", DEFAULT_MODEL),
    )
    parser.add_argument("--audio-dir", type=Path, default=DEFAULT_AUDIO_DIR)
    parser.add_argument("--audio-file", type=Path)
    parser.add_argument("--summary-json", type=Path, default=DEFAULT_SUMMARY_JSON)
    parser.add_argument("--summary-md", type=Path, default=DEFAULT_SUMMARY_MD)
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    args = parser.parse_args()

    summary = run_probe(
        args.summary_json,
        args.summary_md,
        base_url=args.base_url,
        model=args.model,
        audio_dir=args.audio_dir,
        audio_file=args.audio_file,
        timeout_seconds=args.timeout_seconds,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
