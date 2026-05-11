"""Cloud baseline benchmark runner for Prototype 5 Mode C."""

from __future__ import annotations

import csv
import json
import os
import time
from pathlib import Path
from typing import Any

from .benchmark_cases import load_benchmark_cases
from .cloud_client import run_cloud_completion
from .cloud_status import NOT_RUN_API_KEY_MISSING, get_cloud_status
from .evidence_paths import MODE_C_DIR
from .phi_recovery_runner import strip_json_fences

RATE_LIMITED = "RATE_LIMITED_OR_QUOTA_EXCEEDED"
CHECKPOINT_FILENAME = "cloud_baseline_checkpoint.csv"

CLOUD_RESULT_COLUMNS = [
    "backend",
    "model",
    "command_id",
    "command_text",
    "request_success",
    "latency_ms",
    "parse_success",
    "json_valid",
    "schema_valid",
    "safety_result",
    "semantic_validity",
    "estimated_cost_usd",
    "privacy_score",
    "offline_resilience_score",
    "cloud_baseline_status",
    "notes",
]


def _bool_env(name: str, default: bool = True) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y"}


def cloud_retry_policy() -> dict[str, Any]:
    return {
        "delay_seconds": float(os.environ.get("MODE_C_CLOUD_DELAY_SECONDS", "20")),
        "max_retries": int(os.environ.get("MODE_C_CLOUD_MAX_RETRIES", "5")),
        "backoff_seconds": float(os.environ.get("MODE_C_CLOUD_BACKOFF_SECONDS", "30")),
        "model": os.environ.get("MODE_C_CLOUD_MODEL", os.environ.get("OPENAI_MODEL", "gpt-4o-mini")),
        "resume_enabled": _bool_env("MODE_C_CLOUD_RESUME", True),
    }


def _parse_json(raw_response: str) -> bool:
    if not raw_response:
        return False
    try:
        json.loads(strip_json_fences(raw_response))
        return True
    except json.JSONDecodeError:
        return False


def _skipped_row(case: dict[str, Any], cloud_status: dict[str, Any]) -> dict[str, Any]:
    return {
        "backend": "cloud",
        "model": "gpt-4o-mini",
        "command_id": case["command_id"],
        "command_text": case["command_text"],
        "request_success": False,
        "latency_ms": "",
        "parse_success": False,
        "json_valid": False,
        "schema_valid": "NOT_EVALUATED",
        "safety_result": "NOT_EVALUATED",
        "semantic_validity": "NOT_EVALUATED",
        "estimated_cost_usd": "NOT_APPLICABLE",
        "privacy_score": "LOWER_EXTERNAL_API_DEPENDENCY",
        "offline_resilience_score": "LOW_REQUIRES_NETWORK",
        "cloud_baseline_status": cloud_status["cloud_baseline_status"],
        "notes": "cloud baseline not run because API key missing"
        if cloud_status["cloud_baseline_status"] == NOT_RUN_API_KEY_MISSING
        else cloud_status.get("reason", ""),
    }


def _load_checkpoint(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {
        row["command_id"]: row
        for row in rows
        if row.get("command_id") and str(row.get("request_success")).lower() == "true"
    }


def _write_checkpoint(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CLOUD_RESULT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in CLOUD_RESULT_COLUMNS})


def _wait_seconds(result: dict[str, Any], policy: dict[str, Any], retry_attempt: int) -> float:
    retry_after = result.get("retry_after_seconds")
    if retry_after not in (None, ""):
        try:
            return float(retry_after)
        except ValueError:
            pass
    return float(policy["backoff_seconds"]) * retry_attempt


def _cloud_row(case: dict[str, Any], result: dict[str, Any], status: str) -> dict[str, Any]:
    parse_success = _parse_json(result.get("raw_response", ""))
    return {
        "backend": "cloud",
        "model": result.get("model", ""),
        "command_id": case["command_id"],
        "command_text": case["command_text"],
        "request_success": result.get("request_success") is True,
        "latency_ms": result.get("latency_ms", ""),
        "parse_success": parse_success,
        "json_valid": parse_success,
        "schema_valid": "NOT_EVALUATED",
        "safety_result": "NOT_EVALUATED",
        "semantic_validity": "NOT_EVALUATED",
        "estimated_cost_usd": "NOT_MEASURED" if result.get("request_success") is True else "NOT_APPLICABLE",
        "privacy_score": "LOWER_EXTERNAL_API_DEPENDENCY",
        "offline_resilience_score": "LOW_REQUIRES_NETWORK",
        "cloud_baseline_status": status,
        "notes": result.get("error_type") or result.get("error", ""),
    }


def _run_one_with_retries(
    case: dict[str, Any],
    cloud_status: dict[str, Any],
    policy: dict[str, Any],
    sleep_fn,
) -> dict[str, Any]:
    last_result: dict[str, Any] = {}
    for attempt in range(0, int(policy["max_retries"]) + 1):
        last_result = run_cloud_completion(case["command_text"], cloud_status)
        if last_result.get("request_success") is True:
            return _cloud_row(case, last_result, "COMPLETE")
        if last_result.get("error_type") != RATE_LIMITED or attempt >= int(policy["max_retries"]):
            status = RATE_LIMITED if last_result.get("error_type") == RATE_LIMITED else "ERROR"
            return _cloud_row(case, last_result, status)
        sleep_fn(_wait_seconds(last_result, policy, attempt + 1))
    return _cloud_row(case, last_result, "ERROR")


def _status_from_rows(rows: list[dict[str, Any]], expected_count: int) -> str:
    successes = [row for row in rows if row.get("request_success") is True or str(row.get("request_success")).lower() == "true"]
    if len(successes) == expected_count and expected_count > 0:
        return "COMPLETE"
    if successes:
        return "PARTIAL"
    if any(row.get("cloud_baseline_status") == RATE_LIMITED for row in rows):
        return RATE_LIMITED
    return "ERROR"


def run_cloud_baseline(
    output_dir: Path = MODE_C_DIR,
    sleep_fn=time.sleep,
) -> dict[str, Any]:
    benchmark = load_benchmark_cases()
    cases = benchmark.get("cases", [])
    cloud_status = get_cloud_status()
    policy = cloud_retry_policy()
    rows: list[dict[str, Any]] = []
    checkpoint_path = output_dir / CHECKPOINT_FILENAME
    completed = _load_checkpoint(checkpoint_path) if policy["resume_enabled"] else {}
    if completed:
        rows = [completed[case["command_id"]] for case in cases if case["command_id"] in completed]
        if _status_from_rows(rows, len(cases)) == "COMPLETE":
            return {
                "rows": rows,
                "cloud_baseline_status": "COMPLETE",
                "benchmark_status": benchmark.get("status", "UNKNOWN"),
                "cloud_status": cloud_status,
                "cloud_error_type": "",
                "cloud_error_reason": "",
                "cloud_retry_policy": policy,
                "cloud_run_scope": "full_30_command_benchmark",
            }

    if not cloud_status["cloud_available"]:
        rows = [_skipped_row(case, cloud_status) for case in cases]
        return {
            "rows": rows,
            "cloud_baseline_status": cloud_status["cloud_baseline_status"],
            "benchmark_status": benchmark.get("status", "UNKNOWN"),
            "cloud_status": cloud_status,
            "cloud_error_type": cloud_status["cloud_baseline_status"],
            "cloud_error_reason": cloud_status.get("reason", ""),
            "cloud_retry_policy": policy,
            "cloud_run_scope": "fallback_no_api_key",
        }

    rows = [completed[case["command_id"]] for case in cases if case["command_id"] in completed]
    rows_by_id = {row["command_id"]: row for row in rows}
    for case in cases:
        if case["command_id"] in rows_by_id:
            continue
        row = _run_one_with_retries(case, cloud_status, policy, sleep_fn)
        rows_by_id[case["command_id"]] = row
        rows = [rows_by_id[known["command_id"]] for known in cases if known["command_id"] in rows_by_id]
        _write_checkpoint(rows, checkpoint_path)
        if float(policy["delay_seconds"]) > 0:
            sleep_fn(float(policy["delay_seconds"]))

    status = _status_from_rows(rows, len(cases))
    first_error = next((row for row in rows if row.get("request_success") is not True and str(row.get("request_success")).lower() != "true"), {})
    return {
        "rows": rows,
        "cloud_baseline_status": status,
        "benchmark_status": benchmark.get("status", "UNKNOWN"),
        "cloud_status": cloud_status,
        "cloud_error_type": first_error.get("cloud_baseline_status", ""),
        "cloud_error_reason": first_error.get("notes", ""),
        "cloud_retry_policy": policy,
        "cloud_run_scope": "full_30_command_benchmark",
    }
