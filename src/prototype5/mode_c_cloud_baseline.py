"""Mode C cloud baseline and local-vs-cloud fallback support."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .benchmark_cases import load_benchmark_cases
from .evidence_paths import MODE_C_DIR, PHI_RECOVERY_DIR
from .phi_recovery_metrics import load_phi_results
from .report_exports import write_json
from .simple_table import Table


LOCAL_VS_CLOUD_COLUMNS = [
    "command_id",
    "command_text",
    "source",
    "model",
    "request_success",
    "parse_success",
    "json_valid",
    "latency_ms",
    "semantic_validity",
    "evidence_status",
    "error",
]


def cloud_api_key_present(env: dict[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return bool(source.get("OPENAI_API_KEY"))


def _cloud_payload(command_text: str, model: str) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": "Return only valid JSON. Do not explain."},
            {
                "role": "user",
                "content": (
                    "Convert this robot command into a minimal JSON action object:\n"
                    f"\"{command_text}\"\n"
                    "Return only JSON."
                ),
            },
        ],
        "temperature": 0,
        "max_tokens": int(os.environ.get("OPENAI_MAX_TOKENS", "128")),
    }


def _extract_chat_content(payload: dict[str, Any]) -> str:
    choices = payload.get("choices", [])
    if not choices or not isinstance(choices[0], dict):
        return ""
    message = choices[0].get("message", {})
    if isinstance(message, dict):
        return str(message.get("content", ""))
    return ""


def call_openai_chat(command_text: str, timeout_seconds: float = 180.0) -> dict[str, Any]:
    api_key = os.environ["OPENAI_API_KEY"]
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    endpoint = f"{base_url}/chat/completions"
    request = Request(
        endpoint,
        data=json.dumps(_cloud_payload(command_text, model)).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    start = time.perf_counter()
    with urlopen(request, timeout=timeout_seconds) as response:
        raw_payload = json.loads(response.read().decode("utf-8-sig"))
    return {
        "model": model,
        "raw_response": _extract_chat_content(raw_payload),
        "latency_ms": round((time.perf_counter() - start) * 1000, 2),
        "request_success": True,
        "error": "",
    }


def _local_rows(phi_results_path: Path) -> list[dict[str, Any]]:
    rows = []
    for row in load_phi_results(phi_results_path):
        rows.append(
            {
                "command_id": row.get("command_id", ""),
                "command_text": row.get("command_text", ""),
                "source": "local_phi",
                "model": row.get("model_id", ""),
                "request_success": row.get("request_success", False),
                "parse_success": row.get("parse_success", False),
                "json_valid": row.get("json_valid", False),
                "latency_ms": row.get("latency_ms", ""),
                "semantic_validity": row.get("semantic_validity", "NOT_EVALUATED"),
                "evidence_status": "PRESENT" if row.get("request_success") is True else "FAILED",
                "error": row.get("error", ""),
            }
        )
    return rows


def _cloud_not_run_rows(cases: list[dict[str, Any]], model: str) -> list[dict[str, Any]]:
    return [
        {
            "command_id": case["command_id"],
            "command_text": case["command_text"],
            "source": "cloud_openai",
            "model": model,
            "request_success": False,
            "parse_success": False,
            "json_valid": False,
            "latency_ms": "",
            "semantic_validity": "NOT_EVALUATED",
            "evidence_status": "NOT_RUN_API_KEY_MISSING",
            "error": "OPENAI_API_KEY missing",
        }
        for case in cases
    ]


def _cloud_run_rows(cases: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    rows = []
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    timeout_seconds = float(os.environ.get("OPENAI_TIMEOUT_SECONDS", "180"))
    for case in cases:
        row = {
            "command_id": case["command_id"],
            "command_text": case["command_text"],
            "source": "cloud_openai",
            "model": model,
            "request_success": False,
            "parse_success": False,
            "json_valid": False,
            "latency_ms": "",
            "semantic_validity": "NOT_EVALUATED",
            "evidence_status": "FAILED",
            "error": "",
        }
        try:
            result = call_openai_chat(case["command_text"], timeout_seconds=timeout_seconds)
            row.update(result)
            row["evidence_status"] = "PRESENT"
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            row["error"] = str(exc)
        rows.append(row)
    if all(row["request_success"] is True for row in rows) and rows:
        status = "PRESENT"
    elif any(row["request_success"] is True for row in rows):
        status = "PARTIAL"
    else:
        status = "FAILED"
    return rows, status


def _summarise(rows: list[dict[str, Any]], cloud_status: str) -> dict[str, Any]:
    local = [row for row in rows if row["source"] == "local_phi"]
    cloud = [row for row in rows if row["source"] == "cloud_openai"]
    return {
        "mode_c_status": "COMPLETE_WITH_CLOUD_NOT_RUN"
        if cloud_status == "NOT_RUN_API_KEY_MISSING"
        else "COMPLETE",
        "cloud_baseline_status": cloud_status,
        "local_rows": len(local),
        "cloud_rows": len(cloud),
        "local_successful_requests": sum(1 for row in local if row["request_success"] is True),
        "cloud_successful_requests": sum(1 for row in cloud if row["request_success"] is True),
        "semantic_validity": "NOT_EVALUATED",
        "outputs": {
            "local_vs_cloud_results": str(MODE_C_DIR / "local_vs_cloud_results.csv"),
            "local_vs_cloud_summary": str(MODE_C_DIR / "local_vs_cloud_summary.json"),
        },
    }


def run_mode_c(
    output_dir: Path = MODE_C_DIR,
    phi_results_path: Path = PHI_RECOVERY_DIR / "phi_recovery_results.jsonl",
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    benchmark = load_benchmark_cases()
    cases = benchmark.get("cases", [])
    rows = _local_rows(phi_results_path)
    cloud_model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    if not cloud_api_key_present():
        cloud_status = "NOT_RUN_API_KEY_MISSING"
        rows.extend(_cloud_not_run_rows(cases, cloud_model))
    elif benchmark.get("status") != "PRESENT":
        cloud_status = "NOT_RUN_BENCHMARK_MISSING"
    else:
        cloud_rows, cloud_status = _cloud_run_rows(cases)
        rows.extend(cloud_rows)

    table = Table(rows, LOCAL_VS_CLOUD_COLUMNS)
    results_path = output_dir / "local_vs_cloud_results.csv"
    summary_path = output_dir / "local_vs_cloud_summary.json"
    table.to_csv(results_path)
    summary = _summarise(rows, cloud_status)
    summary["benchmark_status"] = benchmark.get("status", "UNKNOWN")
    summary["api_key_present"] = cloud_api_key_present()
    write_json(summary, summary_path)
    return {"summary": summary, "rows": rows}


def collect_mode_c_evidence(output_dir: Path = MODE_C_DIR) -> dict[str, Any]:
    summary_path = output_dir / "local_vs_cloud_summary.json"
    results_path = output_dir / "local_vs_cloud_results.csv"
    if not summary_path.exists():
        return {
            "mode_c_status": "MISSING",
            "cloud_baseline_status": "MISSING",
            "output_files_present": [],
        }
    summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))
    return {
        **summary,
        "output_files_present": [
            str(path) for path in [results_path, summary_path] if path.exists()
        ],
    }
