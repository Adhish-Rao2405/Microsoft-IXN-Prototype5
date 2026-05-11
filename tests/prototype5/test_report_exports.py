import json
import shutil
from pathlib import Path

from src.prototype5.report_exports import export_all
from src.prototype5.run_orchestrator import run
from src.prototype5.simple_table import Table

TMP_ROOT = Path("tests/prototype5/_tmp_exports")


def test_report_exports_create_csv_json_and_markdown_outputs():
    shutil.rmtree(TMP_ROOT, ignore_errors=True)
    results_dir = TMP_ROOT / "results"
    docs_dir = TMP_ROOT / "docs"
    tables = {
        "model_comparison": Table([{"model": "m1", "evidence_status": "PRESENT"}]),
        "zero_trust_comparison": Table(
            [{"pipeline_mode": "zero_trust_pipeline", "evidence_status": "PRESENT"}]
        ),
        "safety_latency_summary": Table(
            [{"configuration": "full_zero_trust", "evidence_status": "PRESENT"}]
        ),
        "extension_summary": Table(
            [{"phase": "4.7", "extension_name": "gate", "evidence_status": "PRESENT"}]
        ),
        "claims_matrix": Table(
            [{"claim": "c", "status": "PROVEN", "safe_dissertation_wording": "s"}]
        ),
        "limitations_matrix": Table(
            [{"limitation": "l", "status": "MISSING", "safe_interpretation": "s"}]
        ),
    }
    manifest = {
        "quantisation_status": "MISSING",
        "fp16_evidence": "MISSING",
        "int8_evidence": "MISSING",
        "int4_evidence": "MISSING",
        "quantisation_overall": "MISSING",
        "built_in_foundry_precision_metadata": "MISSING",
        "custom_precision_artifacts": "MISSING",
        "custom_precision_metadata_files": [],
    }

    generated = export_all(tables, manifest, results_dir, docs_dir)

    generated_names = {path.name for path in generated}
    assert "final_model_comparison.csv" in generated_names
    assert "final_evidence_manifest.json" in generated_names
    assert "prototype5_final_evaluation_protocol.md" in generated_names
    assert "prototype5_quantisation_metadata_check.md" in generated_names
    assert (results_dir / "final_model_comparison.csv").exists()
    manifest_data = json.loads((results_dir / "final_evidence_manifest.json").read_text())
    assert manifest_data["quantisation_status"] == "MISSING"
    shutil.rmtree(TMP_ROOT, ignore_errors=True)


def test_orchestrator_can_run_with_available_local_evidence():
    result, generated = run()
    assert result["manifest"]["quantisation_status"] == "COMPLETE_CUSTOM_EVIDENCE"
    assert result["manifest"]["mode_d_status"] == "COMPLETE_LIVE_PROFILE"
    assert result["manifest"]["live_foundry_profile_status"] == "PRESENT"
    assert result["manifest"]["live_foundry_successful_requests"] == 30
    assert result["manifest"]["live_foundry_total_commands"] == 30
    assert result["manifest"]["live_foundry_json_valid_rate"] == 0.8
    assert result["manifest"]["live_foundry_mean_latency_ms"] == 7896.97
    assert result["manifest"]["live_foundry_normalized_mean_cpu_percent"] == 48.31
    assert len(generated) >= 12
    assert all(path.exists() for path in generated)
