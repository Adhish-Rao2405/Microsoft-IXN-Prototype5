"""Summary builders for Prototype 5 Mode D resource profiling."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .evidence_paths import DOCS_DIR, MODE_D_DIR
from .report_exports import write_json, write_markdown
from .resource_profiler import NOT_AVAILABLE, PSUTIL_NOT_AVAILABLE, summarise_resource_samples
from .simple_table import Table, numeric, truthy


SUMMARY_COLUMNS = [
    "mode",
    "run_id",
    "workload_mode",
    "total_commands",
    "successful_commands",
    "success_rate",
    "json_valid_rate",
    "mean_latency_ms",
    "p50_latency_ms",
    "p95_latency_ms",
    "min_latency_ms",
    "max_latency_ms",
    "throughput_commands_per_min",
    "mean_process_cpu_percent",
    "peak_process_cpu_percent",
    "mean_system_cpu_percent",
    "peak_system_cpu_percent",
    "memory_before_rss_mb",
    "memory_after_rss_mb",
    "peak_memory_rss_mb",
    "memory_delta_rss_mb",
    "gpu_status",
    "npu_status",
    "resource_profiler_status",
    "live_local_status",
    "notes",
]


def _rate(rows: list[dict[str, Any]], key: str) -> float | str:
    if not rows:
        return NOT_AVAILABLE
    return round(sum(1 for row in rows if truthy(row.get(key))) / len(rows), 4)


def _percentile(values: list[float], percentile: float) -> float | str:
    if not values:
        return NOT_AVAILABLE
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 2)
    index = (len(ordered) - 1) * percentile
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    weight = index - lower
    return round(ordered[lower] * (1 - weight) + ordered[upper] * weight, 2)


def _mean(values: list[float]) -> float | str:
    return round(sum(values) / len(values), 2) if values else NOT_AVAILABLE


def _latencies(rows: list[dict[str, Any]]) -> list[float]:
    return [value for value in (numeric(row.get("latency_ms")) for row in rows) if value is not None]


def _throughput(rows: list[dict[str, Any]]) -> float | str:
    if not rows:
        return NOT_AVAILABLE
    elapsed_values = [
        value
        for value in (numeric(row.get("cumulative_elapsed_ms")) for row in rows)
        if value is not None and value > 0
    ]
    if not elapsed_values:
        return NOT_AVAILABLE
    return round(len(rows) / (max(elapsed_values) / 60000), 2)


def mode_d_status(
    workload_mode: str,
    total_commands: int,
    resource_profiler_status: str,
) -> str:
    if total_commands == 0:
        return "MISSING_LOCAL_EVIDENCE"
    if PSUTIL_NOT_AVAILABLE in resource_profiler_status:
        return "COMPLETE_WITH_PROFILER_LIMITED"
    if workload_mode == "live_local":
        return "COMPLETE_LIVE_PROFILE"
    return "COMPLETE_REPLAY_PROFILE"


def build_mode_d_summary(
    throughput_rows: list[dict[str, Any]],
    resource_samples: list[dict[str, Any]],
    device_metadata: dict[str, Any],
    run_id: str,
    workload_mode: str,
    live_local_status: str,
    output_dir: Path = MODE_D_DIR,
    docs_dir: Path = DOCS_DIR,
) -> dict[str, Any]:
    latencies = _latencies(throughput_rows)
    resource_summary = summarise_resource_samples(resource_samples)
    total_commands = len(throughput_rows)
    successful_commands = sum(1 for row in throughput_rows if truthy(row.get("request_success")))
    profiler_status = str(resource_summary.get("resource_profiler_status", NOT_AVAILABLE))
    status = mode_d_status(workload_mode, total_commands, profiler_status)
    cpu_profile = {
        "status": "PRESENT" if resource_summary["mean_process_cpu_percent"] != NOT_AVAILABLE else NOT_AVAILABLE,
        "mean_process_cpu_percent": resource_summary["mean_process_cpu_percent"],
        "peak_process_cpu_percent": resource_summary["peak_process_cpu_percent"],
        "mean_system_cpu_percent": resource_summary["mean_system_cpu_percent"],
        "peak_system_cpu_percent": resource_summary["peak_system_cpu_percent"],
    }
    memory_profile = {
        "status": "PRESENT" if resource_summary["peak_memory_rss_mb"] != NOT_AVAILABLE else NOT_AVAILABLE,
        "memory_before_rss_mb": resource_summary["memory_before_rss_mb"],
        "memory_after_rss_mb": resource_summary["memory_after_rss_mb"],
        "peak_memory_rss_mb": resource_summary["peak_memory_rss_mb"],
        "memory_delta_rss_mb": resource_summary["memory_delta_rss_mb"],
    }
    gpu_profile = {
        "status": resource_summary["gpu_status"],
        "notes": "GPU counters are reported only when measurable; no GPU metrics were inferred.",
    }
    npu_profile = {
        "status": resource_summary["npu_status"],
        "notes": "NPU counters are reported only when measurable; no NPU metrics were inferred.",
    }
    limitations = [
        "Mode D is a resource/throughput profiling layer, not a new model benchmark.",
        "Default Mode D uses evidence replay unless live local execution is explicitly enabled.",
        "Replay profiling measures the profiling harness and evidence-processing workload, not a fresh Foundry model inference run.",
        "Live local inference profiling can be added if Foundry Local live-call integration is enabled.",
        "GPU/NPU fields are reported only if measurable; otherwise they are recorded as unavailable.",
        "If psutil is not installed, install it with pip install psutil to enable CPU and memory counters.",
        "No cloud calls are made in Mode D.",
    ]
    claims = [
        "The project includes a resource profiling layer aligned with the Microsoft IXN requirement for resource-utilisation evaluation.",
        "The profiling layer records CPU, memory, throughput and hardware visibility metrics for the local evidence-processing workload.",
        "GPU/NPU metrics are reported cautiously and only where measurable.",
        "The results separate local inference/evidence latency from resource pressure and throughput stability.",
        "The project avoids unsupported claims where live Foundry or hardware counters are unavailable.",
    ]
    return {
        "mode": "Prototype 5 Mode D",
        "mode_d_status": status,
        "purpose": "Quantify the resource footprint and throughput stability of the local Prototype 5 evidence-processing workload.",
        "run_id": run_id,
        "workload_mode": workload_mode,
        "live_local_status": live_local_status,
        "total_commands": total_commands,
        "successful_commands": successful_commands,
        "success_rate": _rate(throughput_rows, "request_success"),
        "json_valid_rate": _rate(throughput_rows, "json_valid"),
        "mean_latency_ms": _mean(latencies),
        "p50_latency_ms": _percentile(latencies, 0.50),
        "p95_latency_ms": _percentile(latencies, 0.95),
        "min_latency_ms": round(min(latencies), 2) if latencies else NOT_AVAILABLE,
        "max_latency_ms": round(max(latencies), 2) if latencies else NOT_AVAILABLE,
        "throughput_commands_per_min": _throughput(throughput_rows),
        "cpu_profile": cpu_profile,
        "memory_profile": memory_profile,
        "gpu_profile": gpu_profile,
        "npu_profile": npu_profile,
        "device_metadata": device_metadata,
        "outputs": {
            "resource_profile_samples": str(output_dir / "resource_profile_samples.csv"),
            "resource_profile_summary": str(output_dir / "resource_profile_summary.csv"),
            "throughput_stability": str(output_dir / "throughput_stability.csv"),
            "mode_d_summary": str(output_dir / "mode_d_summary.json"),
            "documentation": str(docs_dir / "prototype5_resource_profile.md"),
        },
        "limitations": limitations,
        "dissertation_claims_unlocked": claims,
        "notes": "Evidence replay workload; no new model call performed.",
    }


def summary_csv_row(summary: dict[str, Any]) -> dict[str, Any]:
    cpu = summary["cpu_profile"]
    memory = summary["memory_profile"]
    return {
        "mode": summary["mode"],
        "run_id": summary["run_id"],
        "workload_mode": summary["workload_mode"],
        "total_commands": summary["total_commands"],
        "successful_commands": summary["successful_commands"],
        "success_rate": summary["success_rate"],
        "json_valid_rate": summary["json_valid_rate"],
        "mean_latency_ms": summary["mean_latency_ms"],
        "p50_latency_ms": summary["p50_latency_ms"],
        "p95_latency_ms": summary["p95_latency_ms"],
        "min_latency_ms": summary["min_latency_ms"],
        "max_latency_ms": summary["max_latency_ms"],
        "throughput_commands_per_min": summary["throughput_commands_per_min"],
        "mean_process_cpu_percent": cpu["mean_process_cpu_percent"],
        "peak_process_cpu_percent": cpu["peak_process_cpu_percent"],
        "mean_system_cpu_percent": cpu["mean_system_cpu_percent"],
        "peak_system_cpu_percent": cpu["peak_system_cpu_percent"],
        "memory_before_rss_mb": memory["memory_before_rss_mb"],
        "memory_after_rss_mb": memory["memory_after_rss_mb"],
        "peak_memory_rss_mb": memory["peak_memory_rss_mb"],
        "memory_delta_rss_mb": memory["memory_delta_rss_mb"],
        "gpu_status": summary["gpu_profile"]["status"],
        "npu_status": summary["npu_profile"]["status"],
        "resource_profiler_status": summary["device_metadata"].get("profiler_backend", NOT_AVAILABLE),
        "live_local_status": summary["live_local_status"],
        "notes": summary["notes"],
    }


def build_mode_d_doc(summary: dict[str, Any]) -> str:
    device = summary["device_metadata"]
    cpu = summary["cpu_profile"]
    memory = summary["memory_profile"]
    return "\n".join(
        [
            "# Prototype 5 Resource Profile",
            "",
            "## Purpose of Mode D",
            summary["purpose"],
            "",
            "## Microsoft Brief Requirement",
            "Mode D addresses the requirement to benchmark resource utilisation, CPU/GPU/NPU pressure and throughput stability for the local-first evaluation pipeline.",
            "",
            "## Profiling Method",
            "Mode D is a resource/throughput profiling layer, not a new model benchmark. Default Mode D uses evidence replay unless live local execution is explicitly enabled. Replay profiling measures the profiling harness and evidence-processing workload, not a fresh Foundry model inference run. No cloud calls are made in Mode D.",
            "",
            "## Workload Mode Used",
            f"Workload mode: {summary['workload_mode']}. Live local status: {summary['live_local_status']}.",
            "",
            "## Metrics Recorded",
            "CPU percentage, memory RSS/VMS, system memory pressure, throughput commands per minute, rolling latency, GPU/NPU visibility fields and device metadata.",
            "",
            "## Device Metadata",
            f"OS: {device.get('os_name')}. Python: {device.get('python_version')}. Machine: {device.get('machine')}. CPU logical count: {device.get('cpu_logical_count')}. Total memory MB: {device.get('total_memory_mb')}. Foundry model ID: {device.get('foundry_model_id')}. Profiler backend: {device.get('profiler_backend')}.",
            "",
            "## CPU and Memory Summary",
            f"CPU profile: {cpu['status']}. Mean process CPU: {cpu['mean_process_cpu_percent']}. Peak process CPU: {cpu['peak_process_cpu_percent']}. Mean system CPU: {cpu['mean_system_cpu_percent']}. Peak system CPU: {cpu['peak_system_cpu_percent']}.",
            f"Memory profile: {memory['status']}. Before RSS MB: {memory['memory_before_rss_mb']}. After RSS MB: {memory['memory_after_rss_mb']}. Peak RSS MB: {memory['peak_memory_rss_mb']}. Delta RSS MB: {memory['memory_delta_rss_mb']}.",
            "",
            "## GPU/NPU Visibility and Limitations",
            f"GPU profile: {summary['gpu_profile']['status']}. NPU profile: {summary['npu_profile']['status']}. GPU/NPU fields are reported only if measurable; otherwise they are recorded as unavailable.",
            "",
            "## Throughput Stability Results",
            f"Total commands: {summary['total_commands']}. Successful commands: {summary['successful_commands']}. Mean latency ms: {summary['mean_latency_ms']}. P95 latency ms: {summary['p95_latency_ms']}. Throughput commands/min: {summary['throughput_commands_per_min']}.",
            "",
            "## Limitations",
            *[f"- {item}" for item in summary["limitations"]],
            "",
            "## Dissertation Wording Unlocked",
            *[f"- {item}" for item in summary["dissertation_claims_unlocked"]],
            "",
        ]
    )


def write_mode_d_summary_outputs(
    summary: dict[str, Any],
    output_dir: Path = MODE_D_DIR,
    docs_dir: Path = DOCS_DIR,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    docs_dir.mkdir(parents=True, exist_ok=True)
    summary_csv = output_dir / "resource_profile_summary.csv"
    summary_json = output_dir / "mode_d_summary.json"
    doc_path = docs_dir / "prototype5_resource_profile.md"
    Table([summary_csv_row(summary)], SUMMARY_COLUMNS).to_csv(summary_csv)
    write_json(summary, summary_json)
    write_markdown(build_mode_d_doc(summary), doc_path)
    return {
        "resource_profile_summary": summary_csv,
        "mode_d_summary": summary_json,
        "documentation": doc_path,
    }


def collect_mode_d_evidence(output_dir: Path = MODE_D_DIR) -> dict[str, Any]:
    final_summary_path = output_dir / "mode_d_final_evidence_summary.json"
    replay_summary_path = output_dir / "mode_d_summary.json"
    summary_path = final_summary_path if final_summary_path.exists() else replay_summary_path
    if not summary_path.exists():
        return {"mode_d_status": "MISSING", "output_files_present": []}
    summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))
    if summary_path == final_summary_path:
        live_profile = summary.get("live_foundry_profile", {})
        total_commands = live_profile.get("total_commands", 0)
        successful_requests = live_profile.get("successful_requests", 0)
        output_paths = [
            output_dir / "mode_d_final_evidence_summary.json",
            output_dir / "manual_live_30_command_foundry_process_summary_normalized.json",
            output_dir / "manual_live_30_command_foundry_process_profile.csv",
            output_dir / "mode_d_summary.json",
            DOCS_DIR / "prototype5_mode_d_final_live_profile.md",
        ]
        return {
            **summary,
            "mode_d_status": summary.get("final_mode_d_status", "MISSING"),
            "live_foundry_profile_status": "PRESENT"
            if live_profile.get("status") == "COMPLETE"
            else "MISSING",
            "live_foundry_successful_requests": successful_requests,
            "live_foundry_total_commands": total_commands,
            "live_foundry_json_valid_rate": live_profile.get("json_valid_rate", "NOT_AVAILABLE"),
            "live_foundry_mean_latency_ms": live_profile.get("mean_latency_ms", "NOT_AVAILABLE"),
            "live_foundry_normalized_mean_cpu_percent": live_profile.get(
                "normalized_mean_foundry_cpu_percent_of_total_logical_capacity",
                "NOT_AVAILABLE",
            ),
            "output_files_present": [str(path) for path in output_paths if path.exists()],
            "evidence_source": str(final_summary_path),
        }
    files = [
        output_dir / "resource_profile_samples.csv",
        output_dir / "resource_profile_summary.csv",
        output_dir / "throughput_stability.csv",
        summary_path,
        DOCS_DIR / "prototype5_resource_profile.md",
    ]
    return {
        **summary,
        "mode_d_status": summary.get("mode_d_status", "MISSING"),
        "live_foundry_profile_status": "MISSING",
        "live_foundry_successful_requests": "NOT_AVAILABLE",
        "live_foundry_total_commands": "NOT_AVAILABLE",
        "live_foundry_json_valid_rate": "NOT_AVAILABLE",
        "live_foundry_mean_latency_ms": "NOT_AVAILABLE",
        "live_foundry_normalized_mean_cpu_percent": "NOT_AVAILABLE",
        "output_files_present": [str(path) for path in files if path.exists()],
        "evidence_source": str(summary_path),
    }
