from src.prototype5.claims_matrix import create_claims_matrix
from src.prototype5.simple_table import Table


def test_claims_matrix_includes_required_missing_evidence_claims():
    claims = create_claims_matrix()
    claim_text = {row["claim"] for row in claims.rows}
    assert "FP16/INT8/INT4 quantisation comparison is missing." in claim_text
    assert "Phi-family evaluation is missing." in claim_text
    assert "cloud-vs-local comparison is missing." in claim_text
    assert "GPU/NPU profiling is missing." in claim_text
    assert "memory footprint measurement is missing." in claim_text
    assert "physical robot execution is not proven." in claim_text
    assert set(claims.columns) == {
        "claim",
        "status",
        "evidence_source",
        "safe_dissertation_wording",
        "unsafe_wording_to_avoid",
    }


def test_false_accept_reduction_claim_can_be_proven():
    status = {"prototype4_execution_comparison_csv": {"status": "PRESENT", "path": "x"}}
    zero_trust = Table(
        [
            {"pipeline_mode": "baseline_trust_model", "unsafe_false_accepts": 3},
            {"pipeline_mode": "zero_trust_pipeline", "unsafe_false_accepts": 0},
        ]
    )
    claims = create_claims_matrix(status, {"zero_trust_comparison": zero_trust})
    row = next(
        row
        for row in claims.rows
        if row["claim"]
        == "Prototype 4 shows unsafe false accepts reduced from baseline to zero-trust pipeline."
    )
    assert row["status"] == "PROVEN"


def test_claims_matrix_marks_complete_custom_quantisation_evidence_proven():
    quantisation = {
        "quantisation_overall": "COMPLETE_CUSTOM_EVIDENCE",
        "custom_precision_metadata_files": ["fp16.json", "int8.json", "int4.json"],
    }
    claims = create_claims_matrix({}, {}, quantisation)
    row = next(
        row
        for row in claims.rows
        if row["claim"] == "FP16/INT8/INT4 custom precision artifact evidence is present."
    )
    assert row["status"] == "PROVEN"
    assert "CPU/GPU model labels" in row["unsafe_wording_to_avoid"]
