"""Resource profiling helpers for Prototype 5 Mode D."""

from __future__ import annotations

import importlib
import os
import platform
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .evidence_paths import PHI_RECOVERY_DIR
from .loaders import load_json


NOT_AVAILABLE = "NOT_AVAILABLE"
NOT_DETECTED = "NOT_DETECTED"
PSUTIL_AVAILABLE = "PSUTIL_AVAILABLE"
PSUTIL_NOT_AVAILABLE = "PSUTIL_NOT_AVAILABLE"

RESOURCE_SNAPSHOT_KEYS = [
    "timestamp_utc",
    "label",
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


def _timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _psutil_module() -> Any | None:
    try:
        return importlib.import_module("psutil")
    except ImportError:
        return None


def _mb(value: int | float | None) -> float | str:
    if value is None:
        return NOT_AVAILABLE
    return round(float(value) / (1024 * 1024), 2)


def _gpu_profile_unavailable() -> dict[str, str]:
    return {
        "gpu_available": NOT_DETECTED,
        "gpu_name": NOT_AVAILABLE,
        "gpu_utilisation_percent": NOT_AVAILABLE,
        "gpu_memory_used_mb": NOT_AVAILABLE,
        "gpu_memory_total_mb": NOT_AVAILABLE,
    }


def _npu_profile_unavailable() -> dict[str, str]:
    return {
        "npu_available": NOT_DETECTED,
        "npu_name": NOT_AVAILABLE,
        "npu_utilisation_percent": NOT_AVAILABLE,
    }


def _not_available_snapshot(label: str, status: str, notes: str) -> dict[str, Any]:
    return {
        "timestamp_utc": _timestamp(),
        "label": label,
        "process_cpu_percent": NOT_AVAILABLE,
        "system_cpu_percent": NOT_AVAILABLE,
        "process_memory_rss_mb": NOT_AVAILABLE,
        "process_memory_vms_mb": NOT_AVAILABLE,
        "system_memory_total_mb": NOT_AVAILABLE,
        "system_memory_available_mb": NOT_AVAILABLE,
        "system_memory_used_percent": NOT_AVAILABLE,
        **_gpu_profile_unavailable(),
        **_npu_profile_unavailable(),
        "resource_profiler_status": status,
        "notes": notes,
    }


def get_resource_snapshot(label: str = "") -> dict[str, Any]:
    """Return one process/system resource snapshot without requiring GPU/NPU counters."""

    psutil = _psutil_module()
    if psutil is None:
        return _not_available_snapshot(
            label,
            PSUTIL_NOT_AVAILABLE,
            "psutil is not installed; install with pip install psutil for CPU and memory metrics",
        )

    try:
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        system_memory = psutil.virtual_memory()
        return {
            "timestamp_utc": _timestamp(),
            "label": label,
            "process_cpu_percent": round(float(process.cpu_percent(interval=None)), 2),
            "system_cpu_percent": round(float(psutil.cpu_percent(interval=None)), 2),
            "process_memory_rss_mb": _mb(memory_info.rss),
            "process_memory_vms_mb": _mb(memory_info.vms),
            "system_memory_total_mb": _mb(system_memory.total),
            "system_memory_available_mb": _mb(system_memory.available),
            "system_memory_used_percent": round(float(system_memory.percent), 2),
            **_gpu_profile_unavailable(),
            **_npu_profile_unavailable(),
            "resource_profiler_status": PSUTIL_AVAILABLE,
            "notes": "GPU/NPU counters are not queried unless measurable through a supported local backend",
        }
    except Exception as exc:  # pragma: no cover - defensive against platform psutil errors
        return _not_available_snapshot(label, "PSUTIL_ERROR", f"psutil snapshot failed: {exc}")


def sample_resource_usage(label: str) -> dict[str, Any]:
    return get_resource_snapshot(label=label)


def _mean(values: list[float]) -> float | str:
    return round(sum(values) / len(values), 2) if values else NOT_AVAILABLE


def _max(values: list[float]) -> float | str:
    return round(max(values), 2) if values else NOT_AVAILABLE


def _numeric_values(samples: list[dict[str, Any]], key: str) -> list[float]:
    values = []
    for sample in samples:
        value = sample.get(key)
        try:
            values.append(float(value))
        except (TypeError, ValueError):
            continue
    return values


def summarise_resource_samples(samples: list[dict[str, Any]]) -> dict[str, Any]:
    process_cpu = _numeric_values(samples, "process_cpu_percent")
    system_cpu = _numeric_values(samples, "system_cpu_percent")
    memory_rss = _numeric_values(samples, "process_memory_rss_mb")
    statuses = sorted({str(sample.get("resource_profiler_status", NOT_AVAILABLE)) for sample in samples})
    first = samples[0] if samples else {}
    last = samples[-1] if samples else {}
    memory_before = first.get("process_memory_rss_mb", NOT_AVAILABLE)
    memory_after = last.get("process_memory_rss_mb", NOT_AVAILABLE)
    try:
        memory_delta = round(float(memory_after) - float(memory_before), 2)
    except (TypeError, ValueError):
        memory_delta = NOT_AVAILABLE
    return {
        "sample_count": len(samples),
        "mean_process_cpu_percent": _mean(process_cpu),
        "peak_process_cpu_percent": _max(process_cpu),
        "mean_system_cpu_percent": _mean(system_cpu),
        "peak_system_cpu_percent": _max(system_cpu),
        "memory_before_rss_mb": memory_before,
        "memory_after_rss_mb": memory_after,
        "peak_memory_rss_mb": _max(memory_rss),
        "memory_delta_rss_mb": memory_delta,
        "gpu_status": first.get("gpu_available", NOT_AVAILABLE),
        "npu_status": first.get("npu_available", NOT_AVAILABLE),
        "resource_profiler_status": " | ".join(statuses) if statuses else NOT_AVAILABLE,
    }


def _foundry_model_from_evidence(phi_dir: Path = PHI_RECOVERY_DIR) -> str:
    manifest = load_json(phi_dir / "phi_recovery_manifest.json")
    if isinstance(manifest, dict):
        summary = manifest.get("summary", {})
        if isinstance(summary, dict) and summary.get("model"):
            return str(summary["model"])
        if manifest.get("model"):
            return str(manifest["model"])
    return NOT_AVAILABLE


def get_device_metadata() -> dict[str, Any]:
    psutil = _psutil_module()
    total_memory = NOT_AVAILABLE
    cpu_logical = NOT_AVAILABLE
    cpu_physical = NOT_AVAILABLE
    profiler_backend = PSUTIL_NOT_AVAILABLE
    if psutil is not None:
        profiler_backend = PSUTIL_AVAILABLE
        try:
            total_memory = _mb(psutil.virtual_memory().total)
            cpu_logical = psutil.cpu_count(logical=True) or NOT_AVAILABLE
            cpu_physical = psutil.cpu_count(logical=False) or NOT_AVAILABLE
        except Exception:  # pragma: no cover - defensive platform guard
            total_memory = NOT_AVAILABLE
    return {
        "os_name": platform.system() or NOT_AVAILABLE,
        "os_version": platform.version() or NOT_AVAILABLE,
        "python_version": platform.python_version() or NOT_AVAILABLE,
        "processor": platform.processor() or NOT_AVAILABLE,
        "machine": platform.machine() or NOT_AVAILABLE,
        "cpu_logical_count": cpu_logical,
        "cpu_physical_count": cpu_physical,
        "total_memory_mb": total_memory,
        "foundry_model_id": os.environ.get("FOUNDRY_MODEL_ID") or _foundry_model_from_evidence(),
        "profiling_timestamp_utc": _timestamp(),
        "profiler_backend": profiler_backend,
    }
