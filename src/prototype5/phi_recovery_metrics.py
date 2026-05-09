"""Metrics for Prototype 5 Phi recovery evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .evidence_paths import PHI_RECOVERY_DIR
from .loaders import load_json
from .simple_table import Table


PHI_RESULTS_COLUMNS = [
    "model",
    "commands_evaluated",
    "successful_requests",
    "failed_requests",
    "parse_success_rate",
    "json_valid_rate",
    "mean_latency_ms",
    "semantic_validity",
    "evidence_status",
]


def load_phi_results(path: str | Path) -> list[dict[str, Any]]:
    path = Path(path)
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def summarise_phi_results(
    results: list[dict[str, Any]],
    expected_commands: int = 30,
    failure_reason: str = "",
    model_id: str = "",
) -> dict[str, Any]:
    if not results:
        status = "FAILED" if failure_reason else "MISSING"
        return {
            "model": model_id,
            "commands_evaluated": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "parse_success_rate": 0.0,
            "json_valid_rate": 0.0,
            "mean_latency_ms": "",
            "semantic_validity": "NOT_EVALUATED",
            "evidence_status": status,
            "failure_reason": failure_reason,
        }

    successful = [row for row in results if row.get("request_success") is True]
    failed = [row for row in results if row.get("request_success") is not True]
    parse_success = [row for row in results if row.get("parse_success") is True]
    json_valid = [row for row in results if row.get("json_valid") is True]
    latencies = [
        float(row["latency_ms"])
        for row in successful
        if row.get("latency_ms") not in (None, "")
    ]
    if len(successful) >= expected_commands and expected_commands > 0:
        status = "PRESENT"
    elif successful:
        status = "PARTIAL"
    elif failure_reason or failed:
        status = "FAILED"
    else:
        status = "MISSING"

    return {
        "model": model_id or str(results[0].get("model_id", "")),
        "commands_evaluated": len(results),
        "successful_requests": len(successful),
        "failed_requests": len(failed),
        "parse_success_rate": round(len(parse_success) / len(results), 4),
        "json_valid_rate": round(len(json_valid) / len(results), 4),
        "mean_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else "",
        "semantic_validity": "NOT_EVALUATED",
        "evidence_status": status,
        "failure_reason": failure_reason,
    }


def phi_summary_table(summary: dict[str, Any]) -> Table:
    return Table([{column: summary.get(column, "") for column in PHI_RESULTS_COLUMNS}], PHI_RESULTS_COLUMNS)


def collect_phi_evidence(output_dir: str | Path = PHI_RECOVERY_DIR) -> dict[str, Any]:
    output_dir = Path(output_dir)
    manifest_path = output_dir / "phi_recovery_manifest.json"
    results_path = output_dir / "phi_recovery_results.jsonl"
    summary_path = output_dir / "phi_recovery_summary.csv"
    inventory_path = output_dir / "foundry_model_inventory.json"

    manifest = load_json(manifest_path)
    results = load_phi_results(results_path)
    if isinstance(manifest, dict) and manifest.get("summary"):
        summary = manifest["summary"]
    else:
        summary = summarise_phi_results(results)

    if results and summary.get("evidence_status") in {"MISSING", "FAILED"}:
        summary = summarise_phi_results(results)

    return {
        "phi_status": summary.get("evidence_status", "MISSING"),
        "summary": summary,
        "manifest_path": str(manifest_path) if manifest_path.exists() else "",
        "results_path": str(results_path) if results_path.exists() else "",
        "summary_path": str(summary_path) if summary_path.exists() else "",
        "inventory_path": str(inventory_path) if inventory_path.exists() else "",
        "output_files_present": [
            str(path)
            for path in [inventory_path, results_path, summary_path, manifest_path]
            if path.exists()
        ],
        "real_output_count": len([row for row in results if row.get("request_success") is True]),
    }
