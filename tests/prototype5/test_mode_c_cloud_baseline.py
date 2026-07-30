import json
import shutil
from pathlib import Path

import pytest

from src.prototype5.mode_c_cloud_baseline import cloud_api_key_present, run_mode_c


TMP_ROOT: Path


@pytest.fixture(autouse=True)
def isolated_tmp_root(tmp_path):
    global TMP_ROOT
    TMP_ROOT = tmp_path / "mode_c"


def test_cloud_api_key_present_respects_empty_env():
    assert cloud_api_key_present({}) is False
    assert cloud_api_key_present({"OPENAI_API_KEY": "test-key"}) is True


def test_mode_c_no_key_fallback_generates_outputs(monkeypatch):
    from src.prototype5 import mode_c_cloud_baseline

    shutil.rmtree(TMP_ROOT, ignore_errors=True)
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    phi_path = TMP_ROOT / "phi_recovery_results.jsonl"
    phi_path.write_text(
        json.dumps(
            {
                "command_id": "C01",
                "command_text": "Pick up the medicine cup",
                "model_id": "Phi-3-mini-4k-instruct-generic-cpu:3",
                "request_success": True,
                "parse_success": True,
                "json_valid": True,
                "latency_ms": 10,
                "semantic_validity": "NOT_EVALUATED",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(
        mode_c_cloud_baseline,
        "load_benchmark_cases",
        lambda: {
            "status": "PRESENT",
            "path": "benchmark.json",
            "cases": [
                {"command_id": "C01", "command_text": "Pick up the medicine cup"},
                {"command_id": "C02", "command_text": "Place the pill box on the tray"},
            ],
        },
    )

    result = run_mode_c(output_dir=TMP_ROOT / "mode_c", phi_results_path=phi_path)
    summary = result["summary"]
    results_path = TMP_ROOT / "mode_c" / "local_vs_cloud_results.csv"
    summary_path = TMP_ROOT / "mode_c" / "local_vs_cloud_summary.json"
    csv_text = results_path.read_text(encoding="utf-8")

    assert summary["mode_c_status"] == "COMPLETE_WITH_CLOUD_NOT_RUN"
    assert summary["cloud_baseline_status"] == "NOT_RUN_API_KEY_MISSING"
    assert results_path.exists()
    assert summary_path.exists()
    assert "cloud_openai" in csv_text
    assert "NOT_EVALUATED" in csv_text
    shutil.rmtree(TMP_ROOT, ignore_errors=True)
