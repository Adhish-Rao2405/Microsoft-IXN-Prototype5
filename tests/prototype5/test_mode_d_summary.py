import json
import shutil
from pathlib import Path

import pytest

from src.prototype5.mode_d_summary import (
    build_mode_d_summary,
    collect_mode_d_evidence,
    write_mode_d_summary_outputs,
)


TMP_ROOT: Path


@pytest.fixture(autouse=True)
def isolated_tmp_root(tmp_path):
    global TMP_ROOT
    TMP_ROOT = tmp_path / "mode_d_summary"


def _samples(status="PSUTIL_AVAILABLE"):
    return [
        {
            "process_cpu_percent": 1.0,
            "system_cpu_percent": 10.0,
            "process_memory_rss_mb": 100.0,
            "gpu_available": "NOT_DETECTED",
            "npu_available": "NOT_DETECTED",
            "resource_profiler_status": status,
        },
        {
            "process_cpu_percent": 2.0,
            "system_cpu_percent": 20.0,
            "process_memory_rss_mb": 110.0,
            "gpu_available": "NOT_DETECTED",
            "npu_available": "NOT_DETECTED",
            "resource_profiler_status": status,
        },
    ]


def _throughput_rows():
    return [
        {
            "request_success": True,
            "json_valid": True,
            "latency_ms": 1000,
            "cumulative_elapsed_ms": 1000,
        },
        {
            "request_success": True,
            "json_valid": False,
            "latency_ms": 2000,
            "cumulative_elapsed_ms": 3000,
        },
    ]


def _metadata():
    return {
        "os_name": "Windows",
        "os_version": "test",
        "python_version": "3.12",
        "processor": "NOT_AVAILABLE",
        "machine": "AMD64",
        "cpu_logical_count": 8,
        "cpu_physical_count": 4,
        "total_memory_mb": 16000,
        "foundry_model_id": "Phi-3-mini-4k-instruct-generic-cpu:3",
        "profiling_timestamp_utc": "2026-05-11T00:00:00Z",
        "profiler_backend": "PSUTIL_AVAILABLE",
    }


def test_mode_d_summary_includes_limitations_and_claims():
    summary = build_mode_d_summary(
        _throughput_rows(),
        _samples(),
        _metadata(),
        "run-test",
        "evidence_replay",
        "NOT_REQUESTED",
        output_dir=TMP_ROOT / "mode_d",
        docs_dir=TMP_ROOT / "docs",
    )
    assert summary["mode"] == "Prototype 5 Mode D"
    assert summary["mode_d_status"] == "COMPLETE_REPLAY_PROFILE"
    assert summary["success_rate"] == 1.0
    assert summary["json_valid_rate"] == 0.5
    assert summary["gpu_profile"]["status"] in {"NOT_AVAILABLE", "NOT_DETECTED"}
    assert summary["npu_profile"]["status"] in {"NOT_AVAILABLE", "NOT_DETECTED"}
    assert summary["limitations"]
    assert summary["dissertation_claims_unlocked"]
    assert "No cloud calls are made in Mode D." in summary["limitations"]


def test_mode_d_summary_limited_when_psutil_missing():
    summary = build_mode_d_summary(
        _throughput_rows(),
        _samples(status="PSUTIL_NOT_AVAILABLE"),
        {**_metadata(), "profiler_backend": "PSUTIL_NOT_AVAILABLE"},
        "run-test",
        "evidence_replay",
        "NOT_REQUESTED",
        output_dir=TMP_ROOT / "mode_d",
        docs_dir=TMP_ROOT / "docs",
    )
    assert summary["mode_d_status"] == "COMPLETE_WITH_PROFILER_LIMITED"


def test_mode_d_summary_writes_csv_json_and_doc():
    shutil.rmtree(TMP_ROOT, ignore_errors=True)
    summary = build_mode_d_summary(
        _throughput_rows(),
        _samples(),
        _metadata(),
        "run-test",
        "evidence_replay",
        "NOT_REQUESTED",
        output_dir=TMP_ROOT / "mode_d",
        docs_dir=TMP_ROOT / "docs",
    )
    paths = write_mode_d_summary_outputs(summary, TMP_ROOT / "mode_d", TMP_ROOT / "docs")
    assert paths["resource_profile_summary"].exists()
    assert paths["mode_d_summary"].exists()
    assert paths["documentation"].exists()
    loaded = json.loads(paths["mode_d_summary"].read_text(encoding="utf-8"))
    assert loaded["dissertation_claims_unlocked"]
    assert "Replay profiling measures" in paths["documentation"].read_text(encoding="utf-8")
    shutil.rmtree(TMP_ROOT, ignore_errors=True)


def test_mode_d_summary_marks_missing_local_evidence():
    summary = build_mode_d_summary(
        [],
        _samples(),
        _metadata(),
        "run-test",
        "evidence_replay",
        "NOT_REQUESTED",
        output_dir=TMP_ROOT / "mode_d",
        docs_dir=TMP_ROOT / "docs",
    )
    assert summary["mode_d_status"] == "MISSING_LOCAL_EVIDENCE"


def test_collect_mode_d_evidence_prefers_final_live_summary():
    shutil.rmtree(TMP_ROOT, ignore_errors=True)
    mode_d_dir = TMP_ROOT / "mode_d"
    mode_d_dir.mkdir(parents=True, exist_ok=True)
    summary_path = mode_d_dir / "mode_d_final_evidence_summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "final_mode_d_status": "COMPLETE_LIVE_PROFILE",
                "live_foundry_profile": {
                    "status": "COMPLETE",
                    "total_commands": 30,
                    "successful_requests": 30,
                    "json_valid_rate": 0.8,
                    "mean_latency_ms": 7896.97,
                    "normalized_mean_foundry_cpu_percent_of_total_logical_capacity": 48.31,
                },
                "hardware_visibility": {
                    "gpu_status": "NOT_DETECTED",
                    "npu_status": "NOT_DETECTED",
                },
            }
        ),
        encoding="utf-8",
    )
    summary = collect_mode_d_evidence(mode_d_dir)
    assert summary["mode_d_status"] == "COMPLETE_LIVE_PROFILE"
    assert summary["live_foundry_profile_status"] == "PRESENT"
    assert summary["live_foundry_successful_requests"] == 30
    assert summary["live_foundry_total_commands"] == 30
    assert summary["live_foundry_json_valid_rate"] == 0.8
    assert summary["live_foundry_mean_latency_ms"] == 7896.97
    assert summary["live_foundry_normalized_mean_cpu_percent"] == 48.31
    shutil.rmtree(TMP_ROOT, ignore_errors=True)
