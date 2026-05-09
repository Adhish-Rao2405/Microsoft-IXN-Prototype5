from src.prototype5.claims_matrix import create_claims_matrix


def test_phi_claim_is_partial_when_real_phi_outputs_exist():
    claims = create_claims_matrix(
        phi_summary={
            "phi_status": "PARTIAL",
            "output_files_present": ["phi_recovery_results.jsonl"],
        }
    )
    row = next(
        row
        for row in claims.rows
        if row["claim"] == "Phi-family evaluation evidence is present."
    )
    assert row["status"] == "PARTIAL"
    assert "NOT_EVALUATED" in row["safe_dissertation_wording"]


def test_phi_claim_remains_missing_without_real_outputs():
    claims = create_claims_matrix(phi_summary={"phi_status": "MISSING"})
    row = next(row for row in claims.rows if row["claim"] == "Phi-family evaluation is missing.")
    assert row["status"] == "MISSING"
