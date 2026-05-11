from src.prototype5 import resource_profiler


def test_resource_snapshot_returns_required_keys():
    snapshot = resource_profiler.get_resource_snapshot()
    for key in resource_profiler.RESOURCE_SNAPSHOT_KEYS:
        assert key in snapshot


def test_resource_profiler_does_not_crash_when_psutil_missing(monkeypatch):
    monkeypatch.setattr(resource_profiler, "_psutil_module", lambda: None)
    snapshot = resource_profiler.get_resource_snapshot("test")
    assert snapshot["resource_profiler_status"] == "PSUTIL_NOT_AVAILABLE"
    assert snapshot["process_cpu_percent"] == "NOT_AVAILABLE"
    assert "pip install psutil" in snapshot["notes"]


def test_gpu_and_npu_unavailable_are_not_fake_numeric_values(monkeypatch):
    monkeypatch.setattr(resource_profiler, "_psutil_module", lambda: None)
    snapshot = resource_profiler.get_resource_snapshot("test")
    assert snapshot["gpu_available"] in {"NOT_AVAILABLE", "NOT_DETECTED"}
    assert snapshot["npu_available"] in {"NOT_AVAILABLE", "NOT_DETECTED"}
    assert snapshot["gpu_utilisation_percent"] == "NOT_AVAILABLE"
    assert snapshot["gpu_memory_used_mb"] == "NOT_AVAILABLE"
    assert snapshot["gpu_memory_total_mb"] == "NOT_AVAILABLE"
    assert snapshot["npu_utilisation_percent"] == "NOT_AVAILABLE"


def test_device_metadata_uses_not_available_when_psutil_missing(monkeypatch):
    monkeypatch.setattr(resource_profiler, "_psutil_module", lambda: None)
    monkeypatch.delenv("FOUNDRY_MODEL_ID", raising=False)
    metadata = resource_profiler.get_device_metadata()
    assert metadata["profiler_backend"] == "PSUTIL_NOT_AVAILABLE"
    assert metadata["cpu_logical_count"] == "NOT_AVAILABLE"
    assert metadata["total_memory_mb"] == "NOT_AVAILABLE"
