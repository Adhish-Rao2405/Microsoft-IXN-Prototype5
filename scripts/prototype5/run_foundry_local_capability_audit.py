from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import parse as urllib_parse
from urllib import error as urllib_error
from urllib import request as urllib_request


REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_SUMMARY_JSON = (
    REPO_ROOT
    / "results"
    / "prototype5"
    / "mode_voice"
    / "phase2_milestone15b1_foundry_local_capability_audit_summary.json"
)
DEFAULT_SUMMARY_MD = (
    REPO_ROOT
    / "results"
    / "prototype5"
    / "mode_voice"
    / "phase2_milestone15b1_foundry_local_capability_audit_summary.md"
)

MILESTONE = "Phase 2 Milestone 15B.1"
MODE = "foundry_local_version_and_capability_audit"
NEMOTRON_MODEL_ALIAS = "nemotron-speech-streaming-en-0.6b"
WHISPER_MODEL_ALIAS = "openai-whisper-tiny-generic-cpu:2"
PROJECT_FALLBACK_BASE_URL = "http://127.0.0.1:53402"
SDK_REQUIREMENT_BASIS = "NO_PROJECT_SPECIFIC_MINIMUM_ESTABLISHED"
MINIMUM_ARCHITECTURE_GENERATION = "CURRENT_PYTHON_SDK_1_X"
CURRENT_SDK_DISTRIBUTIONS = ("foundry-local-sdk-winml", "foundry-local-sdk")

STATUS_WITH_RUNTIME_GAPS = "COMPLETE_FOUNDRY_LOCAL_CAPABILITY_AUDIT_WITH_RUNTIME_GAPS"
STATUS_FAILED = "FAILED_FOUNDRY_LOCAL_CAPABILITY_AUDIT_ERROR"

CHAT_MODEL_TOKENS = ("phi", "qwen", "mistral", "llama", "gpt", "deepseek", "chat", "instruct")
CANONICAL_CLI_COMMANDS = {
    "version": ["foundry", "--version"],
    "help": ["foundry", "--help"],
    "model_list": ["foundry", "model", "list"],
    "service_status": ["foundry", "service", "status"],
}
CLI_OUTPUT_LIMIT = 2000
CATALOGUE_WARNING_PATTERNS = ("failed to process model",)
CLI_DEVICE_LABELS = {"CPU", "GPU", "NPU"}


def timestamp_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalise_base_url(base_url: str) -> str:
    return base_url.strip().rstrip("/")


def normalise_cli_text(value: str) -> str:
    replacements = {
        "\x00": "",
        "🚀": "[START]",
        "🟢": "[RUNNING]",
        "ðŸš€": "[START]",
        "ðŸŸ¢": "[RUNNING]",
        "\ufeff": "",
    }
    result = str(value)
    for source, target in replacements.items():
        result = result.replace(source, target)
    return result.strip()


def sanitise_path_text(value: str) -> str:
    text = str(value)
    user_profile = os.environ.get("USERPROFILE", "")
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    if local_appdata:
        text = text.replace(local_appdata, "%LOCALAPPDATA%")
    if user_profile:
        text = text.replace(user_profile, "<USER_PROFILE>")
    return text


def sanitise_command(command: list[str]) -> list[str]:
    return [sanitise_path_text(part) for part in command]


def sanitise_output(value: str, limit: int = CLI_OUTPUT_LIMIT) -> str:
    return sanitise_path_text(normalise_cli_text(value))[:limit]


def output_truncated(value: str, limit: int = CLI_OUTPUT_LIMIT) -> bool:
    return len(sanitise_path_text(normalise_cli_text(value))) > limit


def strict_stt_model_candidate(model_id: str, task: str | None = None) -> bool:
    model = model_id.lower()
    task_text = (task or "").lower()
    return (
        "whisper" in model
        or "nemotron-speech" in model
        or task_text in {"audio-transcription", "audio transcription", "speech-to-text", "stt"}
    )


def classify_sdk_version(version: str | None, *, package_detected: bool, module_importable: bool) -> str:
    if not package_detected:
        return "NOT_ASSESSABLE_SDK_NOT_DETECTED"
    if not module_importable:
        return "NOT_ASSESSABLE_MODULE_NOT_IMPORTABLE"
    parsed = parse_version(version)
    if parsed is None:
        return "NOT_ASSESSABLE_VERSION_METADATA_UNAVAILABLE"
    if parsed >= (1, 0, 0):
        return "CURRENT_PYTHON_SDK_1_X_DETECTED"
    return "LEGACY_OR_PRE_CURRENT_SDK_DETECTED"


def resolve_base_url(env_value: str | None) -> dict[str, Any]:
    environment_value = (env_value or "").strip()
    environment_override_present = bool(environment_value)
    if environment_value:
        parsed = urllib_parse.urlparse(environment_value)
        local_hostnames = {"127.0.0.1", "localhost", "::1"}
        if parsed.scheme in {"http", "https"} and parsed.hostname in local_hostnames:
            return {
                "base_url": normalise_base_url(environment_value),
                "base_url_source": "ENVIRONMENT",
                "environment_override_present": True,
                "environment_base_url_value": environment_value,
                "environment_base_url_valid": True,
                "environment_base_url_rejected_reason": "",
            }
        return {
            "base_url": PROJECT_FALLBACK_BASE_URL,
            "base_url_source": "PROJECT_PREVIOUSLY_EVIDENCED_FALLBACK",
            "environment_override_present": True,
            "environment_base_url_value": environment_value,
            "environment_base_url_valid": False,
            "environment_base_url_rejected_reason": (
                "Environment base URL was not a syntactically valid localhost HTTP(S) URL."
            ),
        }

    return {
        "base_url": PROJECT_FALLBACK_BASE_URL,
        "base_url_source": "PROJECT_PREVIOUSLY_EVIDENCED_FALLBACK",
        "environment_override_present": False,
        "environment_base_url_value": "",
        "environment_base_url_valid": False,
        "environment_base_url_rejected_reason": "FOUNDRY_LOCAL_BASE_URL is not configured.",
    }


def module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def distribution_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


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


def classify_command_failure(result: dict[str, Any]) -> str:
    text = f"{result.get('stdout', '')}\n{result.get('stderr', '')}\n{result.get('error', '')}".lower()
    if "winerror 1312" in text or "specified logon session does not exist" in text:
        return "CLI_INVOCATION_BLOCKED_WINDOWS_LOGON_SESSION"
    if result.get("error", "").startswith("TimeoutExpired"):
        return "CLI_INVOCATION_TIMEOUT"
    if result.get("returncode") == 0:
        return "CLI_COMMAND_SUCCEEDED"
    if result.get("attempted") is False:
        return "CLI_NOT_ATTEMPTED"
    return "CLI_COMMAND_FAILED"


def run_command(command: list[str], timeout_seconds: float) -> dict[str, Any]:
    timed_out = False
    try:
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
        )
        stdout_full = normalise_cli_text(completed.stdout)
        stderr_full = normalise_cli_text(completed.stderr)
        result = {
            "command": sanitise_command(command),
            "attempted": True,
            "returncode": completed.returncode,
            "timeout_seconds": timeout_seconds,
            "timed_out": False,
            "stdout": sanitise_output(stdout_full),
            "stderr": sanitise_output(stderr_full),
            "stdout_truncated": output_truncated(stdout_full),
            "stderr_truncated": output_truncated(stderr_full),
            "_stdout_full": stdout_full,
            "_stderr_full": stderr_full,
            "error": "",
        }
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        result = {
            "command": sanitise_command(command),
            "attempted": True,
            "returncode": None,
            "timeout_seconds": timeout_seconds,
            "timed_out": True,
            "stdout": "",
            "stderr": "",
            "stdout_truncated": False,
            "stderr_truncated": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
    except OSError as exc:
        result = {
            "command": sanitise_command(command),
            "attempted": True,
            "returncode": None,
            "timeout_seconds": timeout_seconds,
            "timed_out": timed_out,
            "stdout": "",
            "stderr": "",
            "stdout_truncated": False,
            "stderr_truncated": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
    result["failure_classification"] = classify_command_failure(result)
    result["cli_process_status"] = "CLI_PROCESS_EXITED_ZERO" if result.get("returncode") == 0 else result["failure_classification"]
    return result


def audit_foundry_cli(timeout_seconds: float) -> dict[str, Any]:
    executable = shutil.which("foundry")
    if not executable:
        command_results = {
            name: {
                "executable": "",
                "command": command,
                "attempted": False,
                "returncode": None,
                "timeout_seconds": timeout_seconds,
                "timed_out": False,
                "stdout": "",
                "stderr": "",
                "error": "foundry CLI was not found on PATH.",
                "failure_classification": "CLI_EXECUTABLE_NOT_FOUND",
                "parsed_result": "",
            }
            for name, command in CANONICAL_CLI_COMMANDS.items()
        }
        return {
            "foundry_cli_present": False,
            "foundry_cli_path": "",
            "foundry_cli_visibility": "CLI_NOT_FOUND",
            "foundry_cli_invocation_usable": False,
            "foundry_cli_command_results": command_results,
            "foundry_version": "",
            "foundry_version_probe": command_results["version"],
            "foundry_service_status": "",
            "foundry_service_status_probe": command_results["service_status"],
            "cli_catalogue_visible_models": [],
            "cli_catalogue_aliases": [],
            "cli_catalogue_model_ids": [],
            "cli_catalogue_task_labels": [],
            "cli_catalogue_parse_warnings": [],
            "cli_catalogue_output_complete": False,
            "cli_catalogue_output_truncated": False,
            "cli_catalogue_semantic_status": "CLI_CATALOGUE_NOT_ATTEMPTED",
        }

    command_results = {}
    for name, command in CANONICAL_CLI_COMMANDS.items():
        command_results[name] = run_command([executable, *command[1:]], timeout_seconds)
        command_results[name]["executable"] = sanitise_path_text(executable)
        command_results[name]["parsed_result"] = command_results[name]["stdout"] or command_results[name]["stderr"]

    version_probe = command_results["version"]
    help_probe = command_results["help"]
    model_list_probe = command_results["model_list"]
    service_probe = command_results["service_status"]
    version_text = version_probe["stdout"] or version_probe["stderr"]
    service_text = service_probe["stdout"] or service_probe["stderr"]
    catalogue_text = model_list_probe.get("_stdout_full", model_list_probe["stdout"])
    cli_catalogue = parse_cli_catalogue(catalogue_text, model_list_probe.get("stdout_truncated", False))
    if model_list_probe["failure_classification"] == "CLI_COMMAND_SUCCEEDED":
        model_list_probe["cli_catalogue_semantic_status"] = cli_catalogue["cli_catalogue_semantic_status"]
    for result in command_results.values():
        result.pop("_stdout_full", None)
        result.pop("_stderr_full", None)
    return {
        "foundry_cli_present": True,
        "foundry_cli_path": sanitise_path_text(executable),
        "foundry_cli_visibility": "CLI_SHIM_PRESENT",
        "foundry_cli_invocation_usable": any(
            result["failure_classification"] == "CLI_COMMAND_SUCCEEDED"
            for result in command_results.values()
        ),
        "foundry_cli_command_results": command_results,
        "foundry_version": version_text,
        "foundry_version_probe": version_probe,
        "foundry_help_probe": help_probe,
        "foundry_service_status": service_text,
        "foundry_service_status_probe": service_probe,
        **cli_catalogue,
    }


def _append_unique(values: list[str], value: str) -> None:
    if value and value not in values:
        values.append(value)


def parse_cli_catalogue(stdout: str, output_was_truncated: bool = False) -> dict[str, Any]:
    aliases: list[str] = []
    model_ids: list[str] = []
    task_labels: list[str] = []
    warnings: list[str] = []

    for line in normalise_cli_text(stdout).splitlines():
        stripped = line.strip()
        lower = stripped.lower()
        if not stripped:
            continue
        if any(pattern in lower for pattern in CATALOGUE_WARNING_PATTERNS):
            _append_unique(warnings, sanitise_output(stripped, 240))
            continue

        parts = [part.strip() for part in re.split(r"\s{2,}", stripped) if part.strip()]
        if not parts or parts[0].lower() in {"alias", "----"} or set(parts[0]) == {"-"}:
            continue

        for model_id in re.findall(r"[A-Za-z0-9_.-]+(?::[0-9]+)", stripped):
            _append_unique(model_ids, model_id.strip("`'\","))

        first = parts[0]
        device_index = next((idx for idx, part in enumerate(parts) if part in CLI_DEVICE_LABELS), None)
        if device_index is None:
            continue
        if device_index > 0:
            _append_unique(aliases, first.strip("`'\","))
        if len(parts) > device_index + 1:
            task_field = re.sub(r"\s+\d+(?:\.\d+)?\s*GB.*$", "", parts[device_index + 1], flags=re.IGNORECASE)
            for label in task_field.split(","):
                cleaned = label.strip().lower()
                if cleaned:
                    _append_unique(task_labels, cleaned)

    output_complete = not output_was_truncated and not warnings
    semantic_status = (
        "CLI_CATALOGUE_COMPLETED_WITH_PROCESSING_WARNINGS"
        if warnings
        else "CLI_CATALOGUE_OUTPUT_TRUNCATED"
        if output_was_truncated
        else "CLI_CATALOGUE_PARSED_WITHOUT_WARNINGS"
    )
    return {
        "cli_catalogue_aliases": aliases,
        "cli_catalogue_model_ids": model_ids,
        "cli_catalogue_task_labels": task_labels,
        "cli_catalogue_parse_warnings": warnings,
        "cli_catalogue_output_complete": output_complete,
        "cli_catalogue_output_truncated": bool(output_was_truncated),
        "cli_catalogue_semantic_status": semantic_status,
        "cli_catalogue_visible_models": model_ids,
    }


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


def classify_model_candidates(model_ids: list[str]) -> tuple[list[str], list[str]]:
    chat_candidates = [
        model_id
        for model_id in model_ids
        if any(token in model_id.lower() for token in CHAT_MODEL_TOKENS)
    ]
    stt_candidates = [model_id for model_id in model_ids if strict_stt_model_candidate(model_id)]
    return chat_candidates, stt_candidates


def classify_http_failure(response: dict[str, Any]) -> str:
    if response["reachable"]:
        return "REST_MODELS_ENDPOINT_REACHABLE"
    error = response.get("error", "")
    if "timed out" in error.lower() or "TimeoutError" in error:
        return "REST_MODELS_ENDPOINT_TIMEOUT"
    if "ConnectionRefusedError" in error or "actively refused" in error:
        return "REST_MODELS_ENDPOINT_CONNECTION_REFUSED"
    if response.get("http_status") == 404:
        return "REST_MODELS_ENDPOINT_HTTP_404"
    return "REST_MODELS_ENDPOINT_UNREACHABLE"


def get_json(url: str, timeout_seconds: float) -> dict[str, Any]:
    try:
        req = urllib_request.Request(url, method="GET", headers={"Accept": "application/json"})
        with urllib_request.urlopen(req, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8-sig")
            payload = json.loads(body)
        return {
            "reachable": True,
            "http_status": response.getcode(),
            "payload": payload if isinstance(payload, dict) else {},
            "attempted": True,
            "error": "",
        }
    except urllib_error.HTTPError as exc:
        return {
            "reachable": False,
            "http_status": exc.code,
            "payload": {},
            "attempted": True,
            "error": f"HTTPError: {exc.code} {exc.reason}",
        }
    except (OSError, TimeoutError, urllib_error.URLError, json.JSONDecodeError) as exc:
        return {
            "reachable": False,
            "http_status": None,
            "payload": {},
            "attempted": True,
            "error": f"{type(exc).__name__}: {exc}",
        }


def probe_audio_transcription_route(base_url: str, model_ids: list[str], timeout_seconds: float) -> dict[str, Any]:
    probe = {
        "method": "OPTIONS",
        "path": "/v1/audio/transcriptions",
        "http_status": None,
        "classification": "",
        "audio_payload_submitted": False,
        "transcription_attempted": False,
        "transcription_usability_tested": False,
    }
    if not base_url:
        probe["classification"] = "NOT_PROBED_BASE_URL_NOT_CONFIGURED"
        return probe
    if not model_ids:
        probe["classification"] = "NOT_PROBED_NO_MODELS"
        return probe

    endpoint = f"{normalise_base_url(base_url)}/v1/audio/transcriptions"
    try:
        req = urllib_request.Request(endpoint, method="OPTIONS", headers={"Accept": "application/json"})
        with urllib_request.urlopen(req, timeout=timeout_seconds):
            probe["http_status"] = 200
            probe["classification"] = "OPTIONS_PROBE_HTTP_200_NON_CONCLUSIVE"
            return probe
    except urllib_error.HTTPError as exc:
        probe["http_status"] = exc.code
        if exc.code == 404:
            probe["classification"] = "OPTIONS_PROBE_HTTP_404_NON_CONCLUSIVE"
            return probe
        if exc.code in {400, 401, 403, 405, 415, 422}:
            probe["classification"] = f"OPTIONS_PROBE_ENDPOINT_PRESENT_OR_PROTECTED_HTTP_{exc.code}"
            return probe
        probe["classification"] = f"OPTIONS_PROBE_HTTP_ERROR_{exc.code}"
        return probe
    except (OSError, TimeoutError, urllib_error.URLError) as exc:
        probe["classification"] = f"OPTIONS_PROBE_UNREACHABLE_{type(exc).__name__}"
        return probe


def extract_service_status_base_url(service_status: str) -> str | None:
    match = re.search(r"https?://(?:127\.0\.0\.1|localhost|\[?::1\]?):\d+", service_status)
    return match.group(0).rstrip("/") if match else None


def audit_http_endpoint(base_url_resolution: dict[str, Any], timeout_seconds: float) -> dict[str, Any]:
    normalised = normalise_base_url(base_url_resolution["base_url"])
    status_endpoint = f"{normalised}/openai/status"
    models_endpoint = f"{normalised}/v1/models"
    status_response = get_json(status_endpoint, timeout_seconds)
    response = get_json(models_endpoint, timeout_seconds)
    model_ids = extract_model_ids(response["payload"]) if response["reachable"] else []
    chat_candidates, stt_candidates = classify_model_candidates(model_ids)
    audio_route_probe = probe_audio_transcription_route(normalised, model_ids, timeout_seconds)
    return {
        "foundry_base_url_configured": bool(base_url_resolution["environment_override_present"]),
        "base_url": normalised,
        "base_url_source": base_url_resolution["base_url_source"],
        "environment_override_present": base_url_resolution["environment_override_present"],
        "environment_base_url_value": base_url_resolution["environment_base_url_value"],
        "environment_base_url_valid": base_url_resolution["environment_base_url_valid"],
        "environment_base_url_rejected_reason": base_url_resolution["environment_base_url_rejected_reason"],
        "foundry_base_url": normalised,
        "status_endpoint": status_endpoint,
        "status_endpoint_attempted": True,
        "status_endpoint_reachable": bool(status_response["reachable"]),
        "status_endpoint_http_status": status_response["http_status"],
        "status_endpoint_error": status_response["error"],
        "models_endpoint": models_endpoint,
        "models_endpoint_attempted": True,
        "models_endpoint_reachable": bool(response["reachable"]),
        "models_endpoint_http_status": response["http_status"],
        "models_endpoint_error": response["error"],
        "models_endpoint_failure_classification": classify_http_failure(response),
        "model_ids": model_ids,
        "chat_model_candidates": chat_candidates,
        "stt_audio_model_candidates": stt_candidates,
        "openai_whisper_tiny_generic_cpu_visible": WHISPER_MODEL_ALIAS in model_ids,
        "nemotron_speech_streaming_visible": NEMOTRON_MODEL_ALIAS in model_ids,
        "openai_compatible_models_route_available": bool(response["reachable"]),
        "openai_compatible_audio_transcription_route_probe": audio_route_probe,
        "openai_compatible_audio_transcription_route_probe_status": audio_route_probe["classification"],
    }


def safe_getattr(obj: Any, names: tuple[str, ...]) -> Any:
    for name in names:
        value = getattr(obj, name, None)
        if value is not None:
            return value
    return None


def model_alias(model: Any) -> str:
    value = safe_getattr(model, ("alias", "id", "model_id", "name"))
    return str(value) if value else ""


def audit_sdk_catalog(sdk_importable: bool, sdk_version_compatibility: str) -> dict[str, Any]:
    if not sdk_importable:
        return {
            "sdk_catalog_probe_attempted": False,
            "sdk_catalog_probe_error": "foundry_local_sdk is not importable.",
            "sdk_catalog_model_aliases": [],
            "sdk_nemotron_speech_streaming_visible": False,
            "sdk_audio_client_route_discoverable": False,
        }
    if sdk_version_compatibility != "CURRENT_PYTHON_SDK_1_X_DETECTED":
        return {
            "sdk_catalog_probe_attempted": False,
            "sdk_catalog_probe_error": f"SDK catalog probe not attempted because compatibility is {sdk_version_compatibility}.",
            "sdk_catalog_model_aliases": [],
            "sdk_nemotron_speech_streaming_visible": False,
            "sdk_audio_client_route_discoverable": False,
        }

    try:
        from foundry_local_sdk import Configuration, FoundryLocalManager  # type: ignore[import]

        FoundryLocalManager.initialize(Configuration(app_name="prototype5-capability-audit"))
        manager = FoundryLocalManager.instance
        catalog = manager.catalog
        models = catalog.list_models() if hasattr(catalog, "list_models") else []
        aliases = sorted({model_alias(model) for model in models if model_alias(model)})
        model = catalog.get_model(NEMOTRON_MODEL_ALIAS) if hasattr(catalog, "get_model") else None
        audio_route = bool(model is not None and hasattr(model, "get_audio_client"))
        return {
            "sdk_catalog_probe_attempted": True,
            "sdk_catalog_probe_error": "",
            "sdk_catalog_model_aliases": aliases,
            "sdk_nemotron_speech_streaming_visible": model is not None,
            "sdk_audio_client_route_discoverable": audio_route,
        }
    except Exception as exc:  # noqa: BLE001 - audit must fail closed and report.
        return {
            "sdk_catalog_probe_attempted": True,
            "sdk_catalog_probe_error": f"{type(exc).__name__}: {exc}",
            "sdk_catalog_model_aliases": [],
            "sdk_nemotron_speech_streaming_visible": False,
            "sdk_audio_client_route_discoverable": False,
        }


def classify_summary(summary: dict[str, Any]) -> str:
    if summary.get("audit_error"):
        return STATUS_FAILED
    return STATUS_WITH_RUNTIME_GAPS


def build_notes(summary: dict[str, Any]) -> str:
    status = summary["status"]
    if status == STATUS_WITH_RUNTIME_GAPS:
        return (
            "M15B.1 completed the bounded capability audit but identified runtime capability gaps. "
            "CLI, package, REST, model-visibility, and runtime-usability findings are reported as separate "
            "capability surfaces. The audit did not attempt model inference or speech transcription."
        )
    return "The capability audit hit an unexpected error and failed closed without changing runtime state."


def build_gap_codes(summary: dict[str, Any]) -> list[str]:
    gaps: list[str] = []
    if not summary["current_foundry_local_sdk_distribution_detected"]:
        gaps.append("CURRENT_PYTHON_SDK_DISTRIBUTION_NOT_DETECTED_IN_ACTIVE_INTERPRETER")
    if not summary["foundry_local_sdk_importable"]:
        gaps.append("PYTHON_SDK_MODULE_NOT_IMPORTABLE")
    cli_classifications = {
        result["failure_classification"]
        for result in summary["foundry_cli_command_results"].values()
        if result.get("attempted")
    }
    if "CLI_INVOCATION_BLOCKED_WINDOWS_LOGON_SESSION" in cli_classifications:
        gaps.append("CLI_INVOCATION_BLOCKED_WINDOWS_LOGON_SESSION")
    if summary["foundry_cli_present"] and summary["foundry_version_probe"]["failure_classification"] != "CLI_COMMAND_SUCCEEDED":
        gaps.append("CLI_VERSION_NOT_CONFIRMED")
    if summary["foundry_cli_present"] and summary["foundry_cli_command_results"]["model_list"]["failure_classification"] != "CLI_COMMAND_SUCCEEDED":
        gaps.append("CLI_CATALOGUE_NOT_CONFIRMED")
    if summary.get("cli_catalogue_semantic_status") in {
        "CLI_CATALOGUE_COMPLETED_WITH_PROCESSING_WARNINGS",
        "CLI_CATALOGUE_OUTPUT_TRUNCATED",
    }:
        gaps.append("CLI_CATALOGUE_PARTIAL_OR_DEGRADED")
    if not summary["models_endpoint_reachable"]:
        gaps.append(summary["models_endpoint_failure_classification"])
    if not summary["openai_whisper_tiny_generic_cpu_visible"]:
        gaps.append("WHISPER_VISIBILITY_NOT_CONFIRMED")
    if not (summary["nemotron_speech_streaming_visible"] or summary["sdk_nemotron_speech_streaming_visible"]):
        gaps.append("NEMOTRON_VISIBILITY_NOT_CONFIRMED")
    return sorted(dict.fromkeys(gaps))


def build_m15b2_readiness(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "may_proceed_as_separate_audit": True,
        "statement": (
            "M15B.2 may proceed only as a separate bounded local audio-conversion-readiness audit. "
            "This does not mean conversion tools are present or conversion has succeeded."
        ),
    }


def build_m15b3_hold(summary: dict[str, Any]) -> dict[str, Any]:
    reasons = [
        "M15B.1 did not test runtime inference usability.",
        "M15B.1 did not test runtime transcription usability.",
        "Audio conversion and WAV/PCM readiness have not been assessed by M15B.2.",
    ]
    if "CURRENT_PYTHON_SDK_DISTRIBUTION_NOT_DETECTED_IN_ACTIVE_INTERPRETER" in summary["runtime_gap_codes"]:
        reasons.append("No current Foundry Local Python SDK distribution was detected in the active interpreter.")
    if "PYTHON_SDK_MODULE_NOT_IMPORTABLE" in summary["runtime_gap_codes"]:
        reasons.append("foundry_local_sdk module is not importable.")
    if "NEMOTRON_VISIBILITY_NOT_CONFIRMED" in summary["runtime_gap_codes"]:
        reasons.append("Nemotron model visibility is not confirmed.")
    if "REST_MODELS_ENDPOINT_UNREACHABLE" in summary["runtime_gap_codes"] or any(
        code.startswith("REST_MODELS_ENDPOINT_") for code in summary["runtime_gap_codes"]
    ):
        reasons.append("REST model catalog reachability is not confirmed.")
    if "CLI_CATALOGUE_NOT_CONFIRMED" in summary["runtime_gap_codes"] or "CLI_CATALOGUE_PARTIAL_OR_DEGRADED" in summary["runtime_gap_codes"]:
        reasons.append("CLI catalogue visibility is partial or degraded.")
    return {
        "must_remain_on_hold": True,
        "hold_reasons": sorted(dict.fromkeys(reasons)),
    }


def build_summary(timeout_seconds: float) -> dict[str, Any]:
    cli = audit_foundry_cli(timeout_seconds)
    base_url_resolution = resolve_base_url(os.environ.get("FOUNDRY_LOCAL_BASE_URL"))
    http = audit_http_endpoint(base_url_resolution, timeout_seconds)
    sdk_importable = module_available("foundry_local_sdk")
    foundry_local_importable = module_available("foundry_local")
    sdk_distribution_versions = {
        package: distribution_version(package)
        for package in (*CURRENT_SDK_DISTRIBUTIONS, "foundry-local-core")
    }
    sdk_version = sdk_distribution_versions["foundry-local-sdk-winml"] or sdk_distribution_versions["foundry-local-sdk"]
    sdk_distribution_detected = any(sdk_distribution_versions[package] for package in CURRENT_SDK_DISTRIBUTIONS)
    core_version = distribution_version("foundry-local-core")
    sdk_version_compatibility = classify_sdk_version(
        sdk_version,
        package_detected=sdk_distribution_detected,
        module_importable=sdk_importable,
    )
    sdk_catalog = audit_sdk_catalog(sdk_importable, sdk_version_compatibility)
    service_status_base_url = extract_service_status_base_url(cli.get("foundry_service_status", ""))
    base_url_confirmed_by_cli = bool(service_status_base_url and service_status_base_url == http["base_url"])

    summary: dict[str, Any] = {
        "timestamp_utc": timestamp_utc(),
        "milestone": MILESTONE,
        "mode": MODE,
        "operating_system": platform.platform(),
        "python_version": sys.version.replace("\n", " "),
        "active_python_executable": sanitise_path_text(sys.executable),
        "minimum_required_sdk_version": None,
        "minimum_architecture_generation": MINIMUM_ARCHITECTURE_GENERATION,
        "sdk_requirement_basis": SDK_REQUIREMENT_BASIS,
        "target_nemotron_model_alias": NEMOTRON_MODEL_ALIAS,
        "target_whisper_model_alias": WHISPER_MODEL_ALIAS,
        "foundry_local_sdk_importable": sdk_importable,
        "foundry_local_importable": foundry_local_importable,
        "foundry_local_sdk_version": sdk_version,
        "foundry_local_core_version": core_version,
        "sdk_version": sdk_version,
        "sdk_version_compatible": None,
        "sdk_version_compatibility": sdk_version_compatibility,
        "current_foundry_local_sdk_distribution_detected": sdk_distribution_detected,
        "sdk_catalog_route_could_be_attempted": bool(
            sdk_importable and sdk_version_compatibility == "CURRENT_PYTHON_SDK_1_X_DETECTED"
        ),
        "python_distribution_surface": sdk_distribution_versions,
        "python_module_import_surface": {
            "foundry_local_sdk": sdk_importable,
            "foundry_local": foundry_local_importable,
        },
        "runtime_inference_usability": "NOT_TESTED_BY_M15B1",
        "runtime_transcription_usability": "NOT_TESTED_BY_M15B1",
        "inference_attempted": False,
        "transcription_attempted": False,
        "model_download_attempted": False,
        "model_load_attempted": False,
        "real_stt_attempted": False,
        "speech_to_text_used": False,
        "fake_transcripts_generated": False,
        "dependency_changes": False,
        "live_microphone_used": False,
        "planner_called": False,
        "validators_called": False,
        "robot_execution_attempted": False,
        "emergency_stop_implemented": False,
        "binary_audio_files_committed": False,
        "capabilities_not_tested_by_m15b1": [
            "RUNTIME_INFERENCE_USABILITY",
            "RUNTIME_TRANSCRIPTION_USABILITY",
        ],
        "service_status_reported_base_url": service_status_base_url,
        "base_url_confirmed_by_cli_service_status": base_url_confirmed_by_cli,
        "endpoint_selected_through_project_fallback": http["base_url_source"] == "PROJECT_PREVIOUSLY_EVIDENCED_FALLBACK",
        "audit_error": "",
    }
    summary.update(cli)
    summary.update(http)
    summary.update(sdk_catalog)
    summary["available_chat_models"] = summary["chat_model_candidates"]
    summary["strict_stt_audio_model_candidates"] = summary["stt_audio_model_candidates"]
    summary["available_audio_stt_models"] = summary["stt_audio_model_candidates"]
    summary["service_visible_models"] = summary["model_ids"]
    summary["whisper_visibility"] = (
        "VISIBLE" if summary["openai_whisper_tiny_generic_cpu_visible"] else "NOT_CONFIRMED"
    )
    summary["nemotron_visibility"] = (
        "VISIBLE"
        if summary["nemotron_speech_streaming_visible"] or summary["sdk_nemotron_speech_streaming_visible"]
        else "NOT_CONFIRMED"
    )
    summary["status"] = classify_summary(summary)
    summary["runtime_gap_codes"] = build_gap_codes(summary)
    summary["observed_runtime_gap_codes"] = summary["runtime_gap_codes"]
    summary["m15b2_audio_conversion_readiness"] = build_m15b2_readiness(summary)
    summary["m15b3_single_file_stt_readiness"] = build_m15b3_hold(summary)
    summary["notes"] = build_notes(summary)
    return summary


def write_summary_json(path: Path, summary: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_summary_md(path: Path, summary: dict[str, Any]) -> None:
    chat_models = "\n".join(f"- `{model}`" for model in summary["available_chat_models"]) or "- None"
    stt_models = "\n".join(f"- `{model}`" for model in summary["available_audio_stt_models"]) or "- None"
    all_models = "\n".join(f"- `{model}`" for model in summary["model_ids"]) or "- None"
    cli_aliases = "\n".join(f"- `{alias}`" for alias in summary["cli_catalogue_aliases"]) or "- None"
    cli_model_ids = "\n".join(f"- `{model}`" for model in summary["cli_catalogue_model_ids"]) or "- None"
    cli_task_labels = "\n".join(f"- `{task}`" for task in summary["cli_catalogue_task_labels"]) or "- None"
    cli_warnings = "\n".join(f"- `{warning}`" for warning in summary["cli_catalogue_parse_warnings"]) or "- None"
    observed_gaps = "\n".join(f"- `{code}`" for code in summary["observed_runtime_gap_codes"]) or "- None"
    untested = "\n".join(f"- `{code}`" for code in summary["capabilities_not_tested_by_m15b1"]) or "- None"
    packages = "\n".join(
        f"- `{name}`: `{version}`"
        for name, version in summary["python_distribution_surface"].items()
    )

    text = f"""# Phase 2 Milestone 15B.1 Foundry Local Capability Audit

## Purpose

M15B.1 records the local Foundry Local runtime, CLI, SDK, endpoint, and model-catalog capability state for the Nemotron future-extension route. It is version and capability discovery only.

## Current Result

- Status: `{summary["status"]}`
- Foundry CLI present: {str(summary["foundry_cli_present"]).lower()}
- Foundry CLI visibility: `{summary["foundry_cli_visibility"]}`
- Foundry CLI invocation usable: {str(summary["foundry_cli_invocation_usable"]).lower()}
- Foundry CLI version output: `{summary["foundry_version"] or 'not available'}`
- Base URL: `{summary["base_url"]}`
- Base URL source: `{summary["base_url_source"]}`
- Endpoint selected through project fallback: {str(summary["endpoint_selected_through_project_fallback"]).lower()}
- Service-status reported base URL: `{summary["service_status_reported_base_url"]}`
- Base URL confirmed by CLI service status: {str(summary["base_url_confirmed_by_cli_service_status"]).lower()}
- Environment override present: {str(summary["environment_override_present"]).lower()}
- `FOUNDRY_LOCAL_BASE_URL` configured: {str(summary["foundry_base_url_configured"]).lower()}
- `/openai/status` reachable: {str(summary["status_endpoint_reachable"]).lower()}
- `/openai/status` HTTP status: `{summary["status_endpoint_http_status"]}`
- Models endpoint: `{summary["models_endpoint"]}`
- `/v1/models` reachable: {str(summary["models_endpoint_reachable"]).lower()}
- `/v1/models` HTTP status: `{summary["models_endpoint_http_status"]}`
- `/v1/models` failure classification: `{summary["models_endpoint_failure_classification"]}`
- `foundry_local_sdk` importable: {str(summary["foundry_local_sdk_importable"]).lower()}
- Active Python executable: `{summary["active_python_executable"]}`
- Current SDK distribution detected in active interpreter: {str(summary["current_foundry_local_sdk_distribution_detected"]).lower()}
- SDK version: `{summary["sdk_version"]}`
- SDK version compatibility: `{summary["sdk_version_compatibility"]}`
- Minimum required SDK version: `{summary["minimum_required_sdk_version"]}`
- SDK requirement basis: `{summary["sdk_requirement_basis"]}`
- Whisper candidate `{summary["target_whisper_model_alias"]}` visible: {str(summary["openai_whisper_tiny_generic_cpu_visible"]).lower()}
- Nemotron candidate `{summary["target_nemotron_model_alias"]}` visible: {str(summary["nemotron_speech_streaming_visible"] or summary["sdk_nemotron_speech_streaming_visible"]).lower()}
- OpenAI-compatible audio transcription route probe: `{summary["openai_compatible_audio_transcription_route_probe_status"]}`
- SDK catalog route could be attempted: {str(summary["sdk_catalog_route_could_be_attempted"]).lower()}
- SDK audio client route discoverable: {str(summary["sdk_audio_client_route_discoverable"]).lower()}
- Runtime inference usability: `{summary["runtime_inference_usability"]}`
- Runtime transcription usability: `{summary["runtime_transcription_usability"]}`

## Python Package Surface

{packages}

The SDK distribution result is scoped to the Python interpreter used to run Prototype 5. It is not a system-wide package audit.

## Observed Runtime Gap Codes

{observed_gaps}

## Capabilities Not Tested By M15B.1

{untested}

## Canonical CLI Probes

{chr(10).join(f"- `{name}`: attempted `{str(result['attempted']).lower()}`, return code `{result['returncode']}`, process status `{result.get('cli_process_status', result['failure_classification'])}`, classification `{result['failure_classification']}`" for name, result in summary["foundry_cli_command_results"].items())}

## CLI Catalogue Parse

- Semantic status: `{summary["cli_catalogue_semantic_status"]}`
- Output complete: {str(summary["cli_catalogue_output_complete"]).lower()}
- Output truncated: {str(summary["cli_catalogue_output_truncated"]).lower()}

Aliases:

{cli_aliases}

Task labels:

{cli_task_labels}

Model IDs:

{cli_model_ids}

Parse warnings:

{cli_warnings}

## Model Catalog

All model IDs returned from `/v1/models`:

{all_models}

Chat/planning model candidates:

{chat_models}

Audio/STT model candidates:

{stt_models}

## Audio Transcription Route Probe

- Method: `{summary["openai_compatible_audio_transcription_route_probe"]["method"]}`
- Path: `{summary["openai_compatible_audio_transcription_route_probe"]["path"]}`
- HTTP status: `{summary["openai_compatible_audio_transcription_route_probe"]["http_status"]}`
- Classification: `{summary["openai_compatible_audio_transcription_route_probe"]["classification"]}`
- Audio payload submitted: {str(summary["openai_compatible_audio_transcription_route_probe"]["audio_payload_submitted"]).lower()}
- Transcription attempted: {str(summary["openai_compatible_audio_transcription_route_probe"]["transcription_attempted"]).lower()}
- Transcription usability tested: {str(summary["openai_compatible_audio_transcription_route_probe"]["transcription_usability_tested"]).lower()}

The non-invasive OPTIONS probe returned HTTP 404. Because the documented transcription operation uses POST with audio data, this result does not establish whether transcription is supported or usable.

## Safety Boundary

- Dependency changes: {str(summary["dependency_changes"]).lower()}
- Model download attempted: {str(summary["model_download_attempted"]).lower()}
- Model load attempted: {str(summary["model_load_attempted"]).lower()}
- Inference attempted: {str(summary["inference_attempted"]).lower()}
- Transcription attempted: {str(summary["transcription_attempted"]).lower()}
- Real STT attempted: {str(summary["real_stt_attempted"]).lower()}
- Speech-to-text used: {str(summary["speech_to_text_used"]).lower()}
- Fake transcripts generated: {str(summary["fake_transcripts_generated"]).lower()}
- Live microphone used: {str(summary["live_microphone_used"]).lower()}
- Planner called: {str(summary["planner_called"]).lower()}
- Validators called: {str(summary["validators_called"]).lower()}
- Robot execution attempted: {str(summary["robot_execution_attempted"]).lower()}

## Notes

{summary["notes"]}

## Readiness

- M15B.2: {summary["m15b2_audio_conversion_readiness"]["statement"]}
- M15B.3 remains on hold: {str(summary["m15b3_single_file_stt_readiness"]["must_remain_on_hold"]).lower()}
- M15B.3 hold reasons: {", ".join(summary["m15b3_single_file_stt_readiness"]["hold_reasons"])}

## Claim Boundary

M15B.1 does not prove working voice control, real speech recognition, live microphone capture, robot execution, emergency-stop capability, or production safety. It does not modify the zero-trust validation pipeline. Nemotron remains a future local STT input route whose availability must be recorded explicitly because Foundry Local runtime, SDK, and model-catalog capabilities are evolving.

The previously evidenced localhost endpoint was probed as a bounded project-specific fallback. This does not establish that the same port is universal across Foundry Local installations.
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run_audit(summary_json: Path, summary_md: Path, *, timeout_seconds: float) -> dict[str, Any]:
    try:
        summary = build_summary(timeout_seconds)
    except Exception as exc:  # noqa: BLE001 - top-level audit must fail closed.
        summary = {
            "status": STATUS_FAILED,
            "timestamp_utc": timestamp_utc(),
            "milestone": MILESTONE,
            "mode": MODE,
            "audit_error": f"{type(exc).__name__}: {exc}",
            "dependency_changes": False,
            "model_download_attempted": False,
            "model_load_attempted": False,
            "real_stt_attempted": False,
            "speech_to_text_used": False,
            "fake_transcripts_generated": False,
            "live_microphone_used": False,
            "planner_called": False,
            "validators_called": False,
            "robot_execution_attempted": False,
            "binary_audio_files_committed": False,
            "notes": "The capability audit failed closed without changing runtime state.",
        }
    write_summary_json(summary_json, summary)
    write_summary_md(summary_md, summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Foundry Local runtime and model capability state.")
    parser.add_argument("--summary-json", type=Path, default=DEFAULT_SUMMARY_JSON)
    parser.add_argument("--summary-md", type=Path, default=DEFAULT_SUMMARY_MD)
    parser.add_argument("--timeout-seconds", type=float, default=2.0)
    args = parser.parse_args()

    summary = run_audit(args.summary_json, args.summary_md, timeout_seconds=args.timeout_seconds)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
