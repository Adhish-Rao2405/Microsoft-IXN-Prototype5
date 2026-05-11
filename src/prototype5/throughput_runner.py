"""Prototype 5 Mode D throughput and resource profiling runner."""

from __future__ import annotations

import csv
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .evidence_paths import DOCS_DIR, MODE_C_DIR, MODE_D_DIR, PHI_RECOVERY_DIR
from .mode_d_summary import build_mode_d_summary, write_mode_d_summary_outputs
from .phi_recovery_metrics import load_phi_results
from .report_exports import write_json
from .resource_profiler import (
    NOT_AVAILABLE,
    get_device_metadata,
    sample_resource_usage,
)
from .simple_table import Table, numeric, read_csv_table, truthy


RESOURCE_SAMPLE_COLUMNS = [
    "timestamp_utc",
    "phase",
    "workload_mode",
    "command_id",
    "process_cpu_percent",
    "system_cpu_percent",
    "process_memory_rss_mb",
    "process_memory_vms_mb",
    "system_memory_total_mb",
    "system_memory_available_mb",
    "system_memory_used_percent",
    "gpu_available",
    "gpu_name",
    "gpu_utilisation_percent",
    "gpu_memory_used_mb",
    "gpu_memory_total_mb",
    "npu_available",
    "npu_name",
    "npu_utilisation_percent",
    "resource_profiler_status",
    "notes",
]

THROUGHPUT_COLUMNS = [
    "run_id",
    "workload_mode",
    "command_id",
    "command_text",
    "model",
    "backend",
    "iteration",
    "request_success",
    "json_valid",
    "latency_ms",
    "cumulative_elapsed_ms",
    "instantaneous_throughput_commands_per_min",
    "rolling_mean_latency_ms",
    "rolling_p95_latency_ms",
    "process_cpu_percent",
    "system_cpu_percent",
    "process_memory_rss_mb",
    "system_memory_used_percent",
    "resource_profiler_status",
    "notes",
]


def _run_id() -> str:
    return datetime.now(UTC).strftime("mode_d_%Y%m%dT%H%M%SZ")


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


def _sample(phase: str, workload_mode: str, command_id: str = "") -> dict[str, Any]:
    snapshot = sample_resource_usage(phase)
    return {
        "timestamp_utc": snapshot.get("timestamp_utc", ""),
        "phase": phase,
        "workload_mode": workload_mode,
        "command_id": command_id,
        "process_cpu_percent": snapshot.get("process_cpu_percent", NOT_AVAILABLE),
        "system_cpu_percent": snapshot.get("system_cpu_percent", NOT_AVAILABLE),
        "process_memory_rss_mb": snapshot.get("process_memory_rss_mb", NOT_AVAILABLE),
        "process_memory_vms_mb": snapshot.get("process_memory_vms_mb", NOT_AVAILABLE),
        "system_memory_total_mb": snapshot.get("system_memory_total_mb", NOT_AVAILABLE),
        "system_memory_available_mb": snapshot.get("system_memory_available_mb", NOT_AVAILABLE),
        "system_memory_used_percent": snapshot.get("system_memory_used_percent", NOT_AVAILABLE),
        "gpu_available": snapshot.get("gpu_available", NOT_AVAILABLE),
        "gpu_name": snapshot.get("gpu_name", NOT_AVAILABLE),
        "gpu_utilisation_percent": snapshot.get("gpu_utilisation_percent", NOT_AVAILABLE),
        "gpu_memory_used_mb": snapshot.get("gpu_memory_used_mb", NOT_AVAILABLE),
        "gpu_memory_total_mb": snapshot.get("gpu_memory_total_mb", NOT_AVAILABLE),
        "npu_available": snapshot.get("npu_available", NOT_AVAILABLE),
        "npu_name": snapshot.get("npu_name", NOT_AVAILABLE),
        "npu_utilisation_percent": snapshot.get("npu_utilisation_percent", NOT_AVAILABLE),
        "resource_profiler_status": snapshot.get("resource_profiler_status", NOT_AVAILABLE),
        "notes": snapshot.get("notes", ""),
    }


def _load_mode_c_local_rows(path: Path = MODE_C_DIR / "local_vs_cloud_results.csv") -> list[dict[str, Any]]:
    table = read_csv_table(path)
    rows = []
    for row in table.rows:
        if row.get("backend") == "local":
            rows.append(
                {
                    "command_id": row.get("command_id", ""),
                    "command_text": row.get("command_text", ""),
                    "model_id": row.get("model", ""),
                    "request_success": truthy(row.get("request_success")),
                    "json_valid": truthy(row.get("json_valid")),
                    "latency_ms": row.get("latency_ms", ""),
                }
            )
    return rows


def load_evidence_replay_workload(
    phi_results_path: Path = PHI_RECOVERY_DIR / "phi_recovery_results.jsonl",
) -> list[dict[str, Any]]:
    rows = load_phi_results(phi_results_path)
    if rows:
        return rows
    return _load_mode_c_local_rows()


def _throughput_row(
    run_id: str,
    workload_mode: str,
    workload: dict[str, Any],
    iteration: int,
    cumulative_elapsed_ms: float,
    rolling_latencies: list[float],
    sample: dict[str, Any],
) -> dict[str, Any]:
    throughput = (
        round(iteration / (cumulative_elapsed_ms / 60000), 2)
        if cumulative_elapsed_ms > 0
        else NOT_AVAILABLE
    )
    return {
        "run_id": run_id,
        "workload_mode": workload_mode,
        "command_id": workload.get("command_id", ""),
        "command_text": workload.get("command_text", ""),
        "model": workload.get("model_id") or workload.get("model", ""),
        "backend": "local",
        "iteration": iteration,
        "request_success": workload.get("request_success", False),
        "json_valid": workload.get("json_valid", False),
        "latency_ms": workload.get("latency_ms", ""),
        "cumulative_elapsed_ms": round(cumulative_elapsed_ms, 2),
        "instantaneous_throughput_commands_per_min": throughput,
        "rolling_mean_latency_ms": _mean(rolling_latencies),
        "rolling_p95_latency_ms": _percentile(rolling_latencies, 0.95),
        "process_cpu_percent": sample.get("process_cpu_percent", NOT_AVAILABLE),
        "system_cpu_percent": sample.get("system_cpu_percent", NOT_AVAILABLE),
        "process_memory_rss_mb": sample.get("process_memory_rss_mb", NOT_AVAILABLE),
        "system_memory_used_percent": sample.get("system_memory_used_percent", NOT_AVAILABLE),
        "resource_profiler_status": sample.get("resource_profiler_status", NOT_AVAILABLE),
        "notes": "evidence replay workload; no new model call performed",
    }


def run_throughput_profile(
    output_dir: Path = MODE_D_DIR,
    docs_dir: Path = DOCS_DIR,
    phi_results_path: Path = PHI_RECOVERY_DIR / "phi_recovery_results.jsonl",
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    docs_dir.mkdir(parents=True, exist_ok=True)
    live_requested = os.environ.get("MODE_D_LIVE_LOCAL_RUN", "").strip().lower() == "true"
    live_local_status = "NOT_IMPLEMENTED" if live_requested else "NOT_REQUESTED"
    workload_mode = "evidence_replay"
    run_id = _run_id()
    workload = load_evidence_replay_workload(phi_results_path)
    resource_samples: list[dict[str, Any]] = [_sample("before_run", workload_mode)]
    throughput_rows: list[dict[str, Any]] = []
    rolling_latencies: list[float] = []
    cumulative_elapsed_ms = 0.0
    wall_start = time.perf_counter()

    for index, unit in enumerate(workload, start=1):
        latency = numeric(unit.get("latency_ms"))
        if latency is not None:
            cumulative_elapsed_ms += latency
            rolling_latencies.append(latency)
        else:
            cumulative_elapsed_ms = max((time.perf_counter() - wall_start) * 1000, cumulative_elapsed_ms)
        sample = _sample("per_command", workload_mode, str(unit.get("command_id", "")))
        resource_samples.append(sample)
        throughput_rows.append(
            _throughput_row(
                run_id,
                workload_mode,
                unit,
                index,
                cumulative_elapsed_ms,
                rolling_latencies,
                sample,
            )
        )

    resource_samples.append(_sample("after_run", workload_mode))
    resource_samples.append(_sample("summary", workload_mode))
    device_metadata = get_device_metadata()
    summary = build_mode_d_summary(
        throughput_rows,
        resource_samples,
        device_metadata,
        run_id,
        workload_mode,
        live_local_status,
        output_dir=output_dir,
        docs_dir=docs_dir,
    )

    samples_path = output_dir / "resource_profile_samples.csv"
    throughput_path = output_dir / "throughput_stability.csv"
    metadata_path = output_dir / "resource_profile_metadata.json"
    Table(resource_samples, RESOURCE_SAMPLE_COLUMNS).to_csv(samples_path)
    Table(throughput_rows, THROUGHPUT_COLUMNS).to_csv(throughput_path)
    write_json({"run_id": run_id, "device_metadata": device_metadata}, metadata_path)
    write_mode_d_summary_outputs(summary, output_dir=output_dir, docs_dir=docs_dir)
    return {
        "summary": summary,
        "throughput_rows": throughput_rows,
        "resource_samples": resource_samples,
    }


def main() -> None:
    result = run_throughput_profile()
    summary = result["summary"]
    outputs = summary["outputs"]
    print(f"Prototype 5 Mode D Resource Profiling: {summary['mode_d_status']}")
    print(f"Workload mode: {summary['workload_mode']}")
    print(f"Total commands: {summary['total_commands']}")
    print(f"Successful commands: {summary['successful_commands']}")
    print(f"Mean latency: {summary['mean_latency_ms']}")
    print(f"Throughput: {summary['throughput_commands_per_min']} commands/min")
    print(f"CPU profile: {summary['cpu_profile']['status']}")
    print(f"Memory profile: {summary['memory_profile']['status']}")
    print(f"GPU profile: {summary['gpu_profile']['status']}")
    print(f"NPU profile: {summary['npu_profile']['status']}")
    print(f"Resource samples CSV: {'PRESENT' if Path(outputs['resource_profile_samples']).exists() else 'MISSING'}")
    print(f"Throughput CSV: {'PRESENT' if Path(outputs['throughput_stability']).exists() else 'MISSING'}")
    print(f"Summary CSV: {'PRESENT' if Path(outputs['resource_profile_summary']).exists() else 'MISSING'}")
    print(f"Summary JSON: {'PRESENT' if Path(outputs['mode_d_summary']).exists() else 'MISSING'}")
    print(f"Documentation: {'PRESENT' if Path(outputs['documentation']).exists() else 'MISSING'}")


if __name__ == "__main__":
    main()
