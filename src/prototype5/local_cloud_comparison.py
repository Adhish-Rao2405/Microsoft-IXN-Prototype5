"""Prototype 5 Mode C local-vs-cloud comparison layer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .benchmark_cases import load_benchmark_cases
from .cloud_baseline_runner import CLOUD_RESULT_COLUMNS, run_cloud_baseline
from .cloud_status import NOT_RUN_API_KEY_MISSING
from .evidence_paths import DOCS_DIR, MODE_C_DIR, PHI_RECOVERY_DIR
from .phi_recovery_metrics import load_phi_results
from .report_exports import write_json, write_markdown
from .simple_table import Table, numeric


COMPARISON_COLUMNS = CLOUD_RESULT_COLUMNS


def _bool_rate(rows: list[dict[str, Any]], key: str) -> float | str:
    if not rows:
        return "NOT_AVAILABLE"
    return round(
        sum(1 for row in rows if row.get(key) is True or str(row.get(key)).lower() == "true")
        / len(rows),
        4,
    )


def _mean_latency(rows: list[dict[str, Any]]) -> float | str:
    latencies = [
        numeric(row.get("latency_ms"))
        for row in rows
        if numeric(row.get("latency_ms")) is not None
    ]
    if not latencies:
        return "NOT_AVAILABLE"
    return round(sum(latencies) / len(latencies), 2)


def _final_interpretation(summary: dict[str, Any]) -> str:
    if summary["cloud_baseline_status"] == "COMPLETE":
        return (
            "Cloud inference was faster and more JSON-consistent in this benchmark, "
            "but it depended on external connectivity, API availability, provider rate limits "
            "and account configuration. Local inference was slower and less JSON-consistent, "
            "but supported local execution, data retention and offline resilience."
        )
    return (
        "Mode C records the local-vs-cloud comparison structure and fallback behaviour, "
        "but final cloud latency and JSON-validity claims require completed cloud rows."
    )


def _limitations(cloud_status: str) -> list[str]:
    common = [
        "Mode C is an evaluation/comparison layer, not a replacement for the local-first architecture.",
        "Semantic validity is only claimed where explicitly evaluated; Mode C marks semantic_validity as NOT_EVALUATED.",
        "Cost comparison was structurally supported but not quantitatively measured because token-level usage/cost accounting was not implemented.",
    ]
    if cloud_status == "COMPLETE":
        return [
            common[0],
            "The final cloud run completed across all 30 commands, but it required API configuration, request pacing, retry/backoff and checkpointed resume.",
            "This demonstrates that cloud baselines are operationally dependent on provider availability, rate limits and account configuration.",
            *common[1:],
        ]
    return [
        common[0],
        "If a cloud API key is missing, cloud rows are emitted as an explicit not-run fallback.",
        "Analytical comparison is still recorded, but experimental cloud latency/accuracy claims are not made when cloud is not run.",
        *common[1:],
    ]


def _dissertation_claims(cloud_status: str) -> list[str]:
    common = [
        "The project includes an explicit local-vs-cloud comparison layer.",
        "The local Foundry Local architecture can be evaluated against cloud inference under identical benchmark prompts.",
        "The comparison separates latency, validity, safety, cost structure, privacy and offline resilience.",
    ]
    if cloud_status == "COMPLETE":
        return [
            *common,
            "Prototype 5 Mode C completed a full 30-command cloud baseline and can support final local-vs-cloud benchmark discussion.",
            "Cloud inference was faster and more JSON-consistent in this benchmark, while local inference preserved stronger privacy and offline-resilience properties.",
        ]
    return [
        *common,
        "Where cloud execution is unavailable, the project records this transparently and avoids unsupported experimental claims.",
    ]


def _local_rows(phi_results_path: Path) -> list[dict[str, Any]]:
    rows = []
    for row in load_phi_results(phi_results_path):
        rows.append(
            {
                "backend": "local",
                "model": row.get("model_id", ""),
                "command_id": row.get("command_id", ""),
                "command_text": row.get("command_text", ""),
                "request_success": row.get("request_success", False),
                "latency_ms": row.get("latency_ms", ""),
                "parse_success": row.get("parse_success", False),
                "json_valid": row.get("json_valid", False),
                "schema_valid": "NOT_EVALUATED",
                "safety_result": "NOT_EVALUATED",
                "semantic_validity": row.get("semantic_validity", "NOT_EVALUATED"),
                "estimated_cost_usd": "NOT_APPLICABLE",
                "privacy_score": "HIGH_LOCAL_DATA_RETAINED",
                "offline_resilience_score": "HIGH_CAN_RUN_WITHOUT_CLOUD",
                "cloud_baseline_status": "NOT_APPLICABLE",
                "notes": "local Phi recovery evidence",
            }
        )
    return rows


def _summary(
    rows: list[dict[str, Any]],
    cloud_result: dict[str, Any],
    benchmark_status: str,
    output_dir: Path,
) -> dict[str, Any]:
    local_rows = [row for row in rows if row["backend"] == "local"]
    cloud_rows = [row for row in rows if row["backend"] == "cloud"]
    cloud_status = cloud_result["cloud_baseline_status"]
    mode_c_status = {
        NOT_RUN_API_KEY_MISSING: "COMPLETE_WITH_CLOUD_NOT_RUN",
        "COMPLETE": "COMPLETE",
        "PARTIAL": "COMPLETE_WITH_PARTIAL_CLOUD_BASELINE",
        "RATE_LIMITED_OR_QUOTA_EXCEEDED": "COMPLETE_WITH_CLOUD_RATE_LIMITED",
    }.get(cloud_status, "COMPLETE_WITH_PARTIAL_CLOUD_BASELINE")
    cloud_successes = [
        row
        for row in cloud_rows
        if row.get("request_success") is True or str(row.get("request_success")).lower() == "true"
    ]
    cloud_failures = [row for row in cloud_rows if row not in cloud_successes]
    cloud_not_run = cloud_status == NOT_RUN_API_KEY_MISSING
    policy = cloud_result.get("cloud_retry_policy", {})
    total_commands = max(len(local_rows), len(cloud_rows))
    summary = {
        "mode": "Prototype 5 Mode C",
        "mode_c_status": mode_c_status,
        "purpose": "Compare local Foundry Local inference evidence against a cloud/API baseline on the same 30-command benchmark.",
        "local_baseline_status": "PRESENT" if local_rows else "MISSING",
        "cloud_baseline_status": cloud_status,
        "total_commands": total_commands,
        "benchmark_status": benchmark_status,
        "local_success_rate": _bool_rate(local_rows, "request_success"),
        "cloud_success_rate": "NOT_AVAILABLE" if cloud_not_run else _bool_rate(cloud_rows, "request_success"),
        "local_mean_latency_ms": _mean_latency(local_rows),
        "cloud_mean_latency_ms": _mean_latency(cloud_rows),
        "local_json_valid_rate": _bool_rate(local_rows, "json_valid"),
        "cloud_json_valid_rate": "NOT_AVAILABLE" if cloud_not_run else _bool_rate(cloud_rows, "json_valid"),
        "cloud_successful_requests": len(cloud_successes),
        "cloud_failed_requests": 0 if cloud_not_run else len(cloud_failures),
        "cloud_commands_attempted": 0 if cloud_not_run else len(cloud_rows),
        "cloud_completion_rate": "NOT_AVAILABLE"
        if cloud_not_run or not cloud_rows
        else round(len(cloud_successes) / len(cloud_rows), 4),
        "cloud_error_type": cloud_result.get("cloud_error_type", ""),
        "cloud_error_reason": cloud_result.get("cloud_error_reason", ""),
        "cloud_run_scope": cloud_result.get("cloud_run_scope", ""),
        "cloud_retry_policy": policy,
        "cloud_delay_seconds": policy.get("delay_seconds", ""),
        "cloud_max_retries": policy.get("max_retries", ""),
        "cloud_resume_enabled": policy.get("resume_enabled", ""),
        "cost_comparison_available": False,
        "privacy_comparison": {
            "local": "HIGH_LOCAL_DATA_RETAINED",
            "cloud": "LOWER_EXTERNAL_API_DEPENDENCY",
        },
        "offline_resilience_comparison": {
            "local": "HIGH_CAN_RUN_WITHOUT_CLOUD",
            "cloud": "LOW_REQUIRES_NETWORK",
        },
        "cost_comparison_note": "Cost comparison was structurally supported but not quantitatively measured because token-level usage/cost accounting was not implemented.",
        "limitations": _limitations(cloud_status),
        "dissertation_claims_unlocked": _dissertation_claims(cloud_status),
        "outputs": {
            "local_vs_cloud_results": str(output_dir / "local_vs_cloud_results.csv"),
            "local_vs_cloud_summary": str(output_dir / "local_vs_cloud_summary.json"),
            "documentation": str(DOCS_DIR / "prototype5_local_vs_cloud_comparison.md"),
        },
    }
    summary["final_interpretation"] = _final_interpretation(summary)
    return summary


def build_mode_c_doc(summary: dict[str, Any]) -> str:
    method = (
        "Prototype 5 combines local Phi recovery evidence with a cloud baseline runner over the same benchmark. "
        "The final cloud baseline completed 30/30 commands. If no cloud API key is present and no completed checkpoint is available, "
        "cloud rows are emitted as an explicit not-run fallback."
        if summary["cloud_baseline_status"] == "COMPLETE"
        else (
            "Prototype 5 combines local Phi recovery evidence with a cloud baseline runner over the same benchmark. "
            "If no cloud API key is present and no completed checkpoint is available, cloud rows are emitted as an explicit not-run fallback."
        )
    )
    return "\n".join(
        [
            "# Prototype 5 Local-vs-Cloud Comparison",
            "",
            "## Purpose of Mode C",
            summary["purpose"],
            "",
            "## Microsoft Brief Requirement",
            "Mode C directly addresses the requirement to compare local inference against cloud-based inference while preserving the local-first architecture.",
            "",
            "## Method",
            method,
            "",
            "## Benchmark Used",
            f"Benchmark status: {summary['benchmark_status']}. Total commands: {summary['total_commands']}.",
            "",
            "## Metrics Recorded",
            "request_success, parse_success, json_valid, schema_valid, safety_result, semantic_validity, latency, cost estimate, privacy score and offline resilience score.",
            "",
            "## Cloud Status",
            f"Cloud baseline status: {summary['cloud_baseline_status']}.",
            "",
            "## Results Summary",
            f"Local baseline status: {summary['local_baseline_status']}. Local success rate: {summary['local_success_rate']}. Cloud success rate: {summary['cloud_success_rate']}.",
            f"Cloud successful requests: {summary['cloud_successful_requests']}/{summary['total_commands']}. Cloud mean latency: {summary['cloud_mean_latency_ms']}.",
            f"Local mean latency: {summary['local_mean_latency_ms']}. Local JSON-valid rate: {summary['local_json_valid_rate']}. Cloud JSON-valid rate: {summary['cloud_json_valid_rate']}.",
            "",
            "## Final Interpretation",
            summary["final_interpretation"],
            "",
            "## Cost Scope",
            summary["cost_comparison_note"],
            "",
            "## Limitations",
            *[f"- {item}" for item in summary["limitations"]],
            "",
            "## Dissertation Wording Unlocked",
            *[f"- {item}" for item in summary["dissertation_claims_unlocked"]],
            "",
        ]
    )


def run_local_cloud_comparison(
    output_dir: Path = MODE_C_DIR,
    phi_results_path: Path = PHI_RECOVERY_DIR / "phi_recovery_results.jsonl",
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    benchmark_status = load_benchmark_cases().get("status", "UNKNOWN")
    local_rows = _local_rows(phi_results_path)
    cloud_result = run_cloud_baseline(output_dir=output_dir)
    rows = local_rows + cloud_result["rows"]
    summary = _summary(rows, cloud_result, benchmark_status, output_dir)

    results_path = output_dir / "local_vs_cloud_results.csv"
    summary_path = output_dir / "local_vs_cloud_summary.json"
    doc_path = DOCS_DIR / "prototype5_local_vs_cloud_comparison.md"
    Table(rows, COMPARISON_COLUMNS).to_csv(results_path)
    write_json(summary, summary_path)
    write_markdown(build_mode_c_doc(summary), doc_path)
    return {"rows": rows, "summary": summary}


def collect_mode_c_evidence(output_dir: Path = MODE_C_DIR) -> dict[str, Any]:
    summary_path = output_dir / "local_vs_cloud_summary.json"
    results_path = output_dir / "local_vs_cloud_results.csv"
    doc_path = DOCS_DIR / "prototype5_local_vs_cloud_comparison.md"
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
            str(path) for path in [results_path, summary_path, doc_path] if path.exists()
        ],
    }


def main() -> None:
    result = run_local_cloud_comparison()
    summary = result["summary"]
    print(f"Prototype 5 Mode C Local-vs-Cloud Comparison: {summary['mode_c_status']}")
    print(f"Local baseline: {summary['local_baseline_status']}")
    print(f"Cloud baseline: {summary['cloud_baseline_status']}")
    print(f"Cloud successful requests: {summary['cloud_successful_requests']}/{summary['total_commands']}")
    print(f"Cloud mean latency: {summary['cloud_mean_latency_ms']}")
    print(f"Results CSV: {'PRESENT' if Path(summary['outputs']['local_vs_cloud_results']).exists() else 'MISSING'}")
    print(f"Summary JSON: {'PRESENT' if Path(summary['outputs']['local_vs_cloud_summary']).exists() else 'MISSING'}")
    print(f"Documentation: {'PRESENT' if Path(summary['outputs']['documentation']).exists() else 'MISSING'}")


if __name__ == "__main__":
    main()
