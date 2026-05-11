import csv
import shutil
from pathlib import Path

from src.prototype5.cloud_baseline_runner import CLOUD_RESULT_COLUMNS, run_cloud_baseline

TMP_ROOT = Path("tests/prototype5/_tmp_cloud_runner")


def test_cloud_runner_does_not_crash_when_api_key_missing(monkeypatch):
    from src.prototype5 import cloud_baseline_runner

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(
        cloud_baseline_runner,
        "load_benchmark_cases",
        lambda: {
            "status": "PRESENT",
            "cases": [
                {"command_id": "C01", "command_text": "Pick up the medicine cup"},
                {"command_id": "C02", "command_text": "Place the pill box on the tray"},
            ],
        },
    )
    shutil.rmtree(TMP_ROOT, ignore_errors=True)
    result = run_cloud_baseline(output_dir=TMP_ROOT)
    assert result["cloud_baseline_status"] == "NOT_RUN_API_KEY_MISSING"
    assert len(result["rows"]) == 2
    assert all(row["semantic_validity"] == "NOT_EVALUATED" for row in result["rows"])
    assert all(row["estimated_cost_usd"] == "NOT_APPLICABLE" for row in result["rows"])
    shutil.rmtree(TMP_ROOT, ignore_errors=True)


def _cases(count):
    return {
        "status": "PRESENT",
        "cases": [
            {"command_id": f"C{index:02d}", "command_text": f"Command {index}"}
            for index in range(1, count + 1)
        ],
    }


def _success(command_text, status):
    return {
        "request_success": True,
        "raw_response": '{"action":"move"}',
        "latency_ms": 100,
        "error": "",
        "error_type": "",
        "retry_after_seconds": "",
        "provider": "openai",
        "model": "gpt-4o-mini",
    }


def _rate_limited(command_text, status):
    return {
        "request_success": False,
        "raw_response": "",
        "latency_ms": "",
        "error": "HTTP Error 429: Too Many Requests",
        "error_type": "RATE_LIMITED_OR_QUOTA_EXCEEDED",
        "retry_after_seconds": "",
        "provider": "openai",
        "model": "gpt-4o-mini",
    }


def test_429_retry_classification_then_success(monkeypatch):
    from src.prototype5 import cloud_baseline_runner

    shutil.rmtree(TMP_ROOT, ignore_errors=True)
    calls = []
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("MODE_C_CLOUD_DELAY_SECONDS", "0")
    monkeypatch.setenv("MODE_C_CLOUD_BACKOFF_SECONDS", "0")
    monkeypatch.setenv("MODE_C_CLOUD_MAX_RETRIES", "1")
    monkeypatch.setattr(cloud_baseline_runner, "load_benchmark_cases", lambda: _cases(1))

    def fake_completion(command_text, status):
        calls.append(command_text)
        return _rate_limited(command_text, status) if len(calls) == 1 else _success(command_text, status)

    monkeypatch.setattr(cloud_baseline_runner, "run_cloud_completion", fake_completion)
    result = run_cloud_baseline(output_dir=TMP_ROOT, sleep_fn=lambda seconds: None)
    assert len(calls) == 2
    assert result["cloud_baseline_status"] == "COMPLETE"
    assert result["rows"][0]["request_success"] is True
    shutil.rmtree(TMP_ROOT, ignore_errors=True)


def test_all_429_gives_rate_limited_status(monkeypatch):
    from src.prototype5 import cloud_baseline_runner

    shutil.rmtree(TMP_ROOT, ignore_errors=True)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("MODE_C_CLOUD_DELAY_SECONDS", "0")
    monkeypatch.setenv("MODE_C_CLOUD_BACKOFF_SECONDS", "0")
    monkeypatch.setenv("MODE_C_CLOUD_MAX_RETRIES", "0")
    monkeypatch.setattr(cloud_baseline_runner, "load_benchmark_cases", lambda: _cases(2))
    monkeypatch.setattr(cloud_baseline_runner, "run_cloud_completion", _rate_limited)
    result = run_cloud_baseline(output_dir=TMP_ROOT, sleep_fn=lambda seconds: None)
    assert result["cloud_baseline_status"] == "RATE_LIMITED_OR_QUOTA_EXCEEDED"
    assert all(row["cloud_baseline_status"] == "RATE_LIMITED_OR_QUOTA_EXCEEDED" for row in result["rows"])
    shutil.rmtree(TMP_ROOT, ignore_errors=True)


def test_successful_checkpoint_rows_are_preserved_and_resume_skips(monkeypatch):
    from src.prototype5 import cloud_baseline_runner

    shutil.rmtree(TMP_ROOT, ignore_errors=True)
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    checkpoint = TMP_ROOT / "cloud_baseline_checkpoint.csv"
    with checkpoint.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CLOUD_RESULT_COLUMNS)
        writer.writeheader()
        writer.writerow(
            {
                "backend": "cloud",
                "model": "gpt-4o-mini",
                "command_id": "C01",
                "command_text": "Command 1",
                "request_success": True,
                "latency_ms": 50,
                "parse_success": True,
                "json_valid": True,
                "schema_valid": "NOT_EVALUATED",
                "safety_result": "NOT_EVALUATED",
                "semantic_validity": "NOT_EVALUATED",
                "estimated_cost_usd": "NOT_MEASURED",
                "privacy_score": "LOWER_EXTERNAL_API_DEPENDENCY",
                "offline_resilience_score": "LOW_REQUIRES_NETWORK",
                "cloud_baseline_status": "COMPLETE",
                "notes": "",
            }
        )
    calls = []
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("MODE_C_CLOUD_DELAY_SECONDS", "0")
    monkeypatch.setenv("MODE_C_CLOUD_RESUME", "true")
    monkeypatch.setattr(cloud_baseline_runner, "load_benchmark_cases", lambda: _cases(2))

    def fake_completion(command_text, status):
        calls.append(command_text)
        return _success(command_text, status)

    monkeypatch.setattr(cloud_baseline_runner, "run_cloud_completion", fake_completion)
    result = run_cloud_baseline(output_dir=TMP_ROOT, sleep_fn=lambda seconds: None)
    assert calls == ["Command 2"]
    assert result["rows"][0]["command_id"] == "C01"
    assert str(result["rows"][0]["request_success"]).lower() == "true"
    assert result["cloud_baseline_status"] == "COMPLETE"
    shutil.rmtree(TMP_ROOT, ignore_errors=True)


def test_complete_checkpoint_is_used_without_api_key(monkeypatch):
    from src.prototype5 import cloud_baseline_runner

    shutil.rmtree(TMP_ROOT, ignore_errors=True)
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    checkpoint = TMP_ROOT / "cloud_baseline_checkpoint.csv"
    with checkpoint.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CLOUD_RESULT_COLUMNS)
        writer.writeheader()
        for index in range(1, 3):
            writer.writerow(
                {
                    "backend": "cloud",
                    "model": "gpt-4o-mini",
                    "command_id": f"C{index:02d}",
                    "command_text": f"Command {index}",
                    "request_success": True,
                    "latency_ms": 50,
                    "parse_success": True,
                    "json_valid": True,
                    "schema_valid": "NOT_EVALUATED",
                    "safety_result": "NOT_EVALUATED",
                    "semantic_validity": "NOT_EVALUATED",
                    "estimated_cost_usd": "NOT_MEASURED",
                    "privacy_score": "LOWER_EXTERNAL_API_DEPENDENCY",
                    "offline_resilience_score": "LOW_REQUIRES_NETWORK",
                    "cloud_baseline_status": "COMPLETE",
                    "notes": "",
                }
            )
    calls = []
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(cloud_baseline_runner, "load_benchmark_cases", lambda: _cases(2))

    def fake_completion(command_text, status):
        calls.append(command_text)
        return _success(command_text, status)

    monkeypatch.setattr(cloud_baseline_runner, "run_cloud_completion", fake_completion)
    result = run_cloud_baseline(output_dir=TMP_ROOT, sleep_fn=lambda seconds: None)
    assert calls == []
    assert result["cloud_baseline_status"] == "COMPLETE"
    assert len(result["rows"]) == 2
    shutil.rmtree(TMP_ROOT, ignore_errors=True)


def test_full_30_success_gives_complete(monkeypatch):
    from src.prototype5 import cloud_baseline_runner

    shutil.rmtree(TMP_ROOT, ignore_errors=True)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("MODE_C_CLOUD_DELAY_SECONDS", "0")
    monkeypatch.setattr(cloud_baseline_runner, "load_benchmark_cases", lambda: _cases(30))
    monkeypatch.setattr(cloud_baseline_runner, "run_cloud_completion", _success)
    result = run_cloud_baseline(output_dir=TMP_ROOT, sleep_fn=lambda seconds: None)
    assert result["cloud_baseline_status"] == "COMPLETE"
    assert len(result["rows"]) == 30
    shutil.rmtree(TMP_ROOT, ignore_errors=True)


def test_partial_success_gives_partial(monkeypatch):
    from src.prototype5 import cloud_baseline_runner

    shutil.rmtree(TMP_ROOT, ignore_errors=True)
    calls = []
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("MODE_C_CLOUD_DELAY_SECONDS", "0")
    monkeypatch.setenv("MODE_C_CLOUD_MAX_RETRIES", "0")
    monkeypatch.setattr(cloud_baseline_runner, "load_benchmark_cases", lambda: _cases(2))

    def fake_completion(command_text, status):
        calls.append(command_text)
        return _success(command_text, status) if len(calls) == 1 else _rate_limited(command_text, status)

    monkeypatch.setattr(cloud_baseline_runner, "run_cloud_completion", fake_completion)
    result = run_cloud_baseline(output_dir=TMP_ROOT, sleep_fn=lambda seconds: None)
    assert result["cloud_baseline_status"] == "PARTIAL"
    shutil.rmtree(TMP_ROOT, ignore_errors=True)
