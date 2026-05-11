import json
import shutil
from pathlib import Path

from src.prototype5.local_cloud_comparison import run_local_cloud_comparison


TMP_ROOT = Path("tests/prototype5/_tmp_local_cloud")


def test_local_cloud_comparison_generates_fallback_outputs_without_overwriting_mode_b(monkeypatch):
    from src.prototype5 import cloud_baseline_runner, local_cloud_comparison

    shutil.rmtree(TMP_ROOT, ignore_errors=True)
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    phi_path = TMP_ROOT / "phi_recovery_results.jsonl"
    phi_contents = json.dumps(
        {
            "command_id": "C01",
            "command_text": "Pick up the medicine cup",
            "model_id": "Phi-3-mini-4k-instruct-generic-cpu:3",
            "request_success": True,
            "parse_success": True,
            "json_valid": True,
            "latency_ms": 12,
            "semantic_validity": "NOT_EVALUATED",
        }
    ) + "\n"
    phi_path.write_text(phi_contents, encoding="utf-8")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(
        cloud_baseline_runner,
        "load_benchmark_cases",
        lambda: {
            "status": "PRESENT",
            "cases": [{"command_id": "C01", "command_text": "Pick up the medicine cup"}],
        },
    )
    monkeypatch.setattr(
        local_cloud_comparison,
        "load_benchmark_cases",
        lambda: {"status": "PRESENT", "cases": []},
    )
    monkeypatch.setattr(local_cloud_comparison, "DOCS_DIR", TMP_ROOT / "docs")
    monkeypatch.setattr(local_cloud_comparison, "MODE_C_DIR", TMP_ROOT / "mode_c")

    result = run_local_cloud_comparison(output_dir=TMP_ROOT / "mode_c", phi_results_path=phi_path)
    summary = result["summary"]
    results_path = TMP_ROOT / "mode_c" / "local_vs_cloud_results.csv"
    summary_path = TMP_ROOT / "mode_c" / "local_vs_cloud_summary.json"
    docs_path = TMP_ROOT / "docs" / "prototype5_local_vs_cloud_comparison.md"

    assert results_path.exists()
    assert summary_path.exists()
    assert docs_path.exists()
    assert summary["cloud_baseline_status"] == "NOT_RUN_API_KEY_MISSING"
    assert "dissertation_claims_unlocked" in summary
    assert "NOT_EVALUATED" in results_path.read_text(encoding="utf-8")
    assert phi_path.read_text(encoding="utf-8") == phi_contents
    shutil.rmtree(TMP_ROOT, ignore_errors=True)
