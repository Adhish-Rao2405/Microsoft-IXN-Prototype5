from src.prototype5.evidence_manifest import generate_evidence_manifest


def test_manifest_marks_quantisation_missing_without_explicit_evidence():
    status = {
        "prototype3_quantisation_coverage_table_csv": {
            "path": "coverage.csv",
            "status": "PRESENT",
        },
        "prototype3_rq5_comparison_csv": {"path": "rq5.csv", "status": "PRESENT"},
        "prototype4_execution_comparison_csv": {"path": "p4.csv", "status": "MISSING"},
    }
    manifest = generate_evidence_manifest(status, ["out.csv"])
    assert manifest["quantisation_status"] == "MISSING"
    assert "prototype3_rq5_comparison_csv" in manifest["input_files_present"]
    assert "prototype4_execution_comparison_csv" in manifest["input_files_missing"]


def test_manifest_includes_custom_precision_metadata_files():
    status = {}
    quantisation = {
        "fp16_evidence": "PRESENT",
        "int8_evidence": "PRESENT",
        "int4_evidence": "PRESENT",
        "quantisation_overall": "COMPLETE_CUSTOM_EVIDENCE",
        "built_in_foundry_precision_metadata": "MISSING",
        "custom_precision_artifacts": "PRESENT",
        "custom_precision_metadata_files": ["fp16.json", "int8.json", "int4.json"],
    }
    manifest = generate_evidence_manifest(status, ["out.csv"], {}, quantisation)
    assert manifest["quantisation_status"] == "COMPLETE_CUSTOM_EVIDENCE"
    assert manifest["fp16_evidence"] == "PRESENT"
    assert manifest["int8_evidence"] == "PRESENT"
    assert manifest["int4_evidence"] == "PRESENT"
    assert manifest["built_in_foundry_precision_metadata"] == "MISSING"
    assert manifest["custom_precision_artifacts"] == "PRESENT"
    assert manifest["custom_precision_metadata_files"] == ["fp16.json", "int8.json", "int4.json"]
