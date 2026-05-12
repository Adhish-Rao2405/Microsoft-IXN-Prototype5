import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TRACEABILITY = ROOT / "results" / "prototype5" / "mode_e0" / "claim_to_evidence_traceability.csv"
ALLOWED_STATUSES = {"PROVEN", "SUPPORTED", "PARTIAL", "FUTURE_WORK", "LIMITED"}
REQUIRED_COLUMNS = {
    "claim_id",
    "claim",
    "prototype_or_mode",
    "evidence_file",
    "metrics",
    "evidence_status",
    "claim_boundary",
    "dissertation_relevance",
    "file_exists",
}


def read_rows():
    with TRACEABILITY.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_claim_traceability_csv_schema_and_statuses():
    rows = read_rows()
    assert len(rows) >= 10
    assert REQUIRED_COLUMNS.issubset(rows[0].keys())
    for row in rows:
        assert row["claim_id"]
        assert row["claim"]
        assert row["evidence_status"] in ALLOWED_STATUSES
        assert row["file_exists"] in {"true", "false"}


def test_claim_traceability_has_minimum_expected_claim_ids():
    claim_ids = {row["claim_id"] for row in read_rows()}
    assert {f"C{index}" for index in range(1, 11)}.issubset(claim_ids)


def test_proven_claims_have_existing_evidence_files():
    for row in read_rows():
        evidence_paths = [item.strip() for item in row["evidence_file"].split(";") if item.strip()]
        assert evidence_paths
        if row["evidence_status"] == "PROVEN":
            missing = [path for path in evidence_paths if not (ROOT / path).exists()]
            assert missing == []
            assert row["file_exists"] == "true"
