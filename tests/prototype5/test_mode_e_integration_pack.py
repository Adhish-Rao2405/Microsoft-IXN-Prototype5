from pathlib import Path

from src.prototype5.claims_matrix import create_claims_matrix
from src.prototype5.report_exports import build_final_dissertation_metrics_md
from src.prototype5.simple_table import Table


ROOT = Path(__file__).resolve().parents[2]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_mode_e_integration_docs_exist_and_are_bounded():
    docs = [
        ROOT / "docs" / "prototype5" / "mode_e_final_evidence_summary.md",
        ROOT / "docs" / "prototype5" / "mode_e_lee_feedback_closure.md",
        ROOT / "docs" / "prototype5" / "mode_e_final_dissertation_wording.md",
    ]
    assert [path for path in docs if not path.exists()] == []
    combined = "\n".join(_read(path) for path in docs).lower()
    for phrase in [
        "curated industrial benchmark",
        "does not prove production robot safety",
        "single local model",
        "deterministic policy context",
        "not proof of general industrial deployment readiness",
    ]:
        assert phrase in combined


def test_mode_e_claims_are_in_claim_matrix():
    claims = create_claims_matrix()
    rows_by_claim = {row["claim"]: row for row in claims.rows}
    expected_claims = [
        "C15: A balanced industrial benchmark extension was created to improve scenario coverage beyond the original 30-command benchmark.",
        "C16: A deterministic industrial vocabulary and policy context was created to support bounded validation of the Mode E benchmark.",
        "C17: Under the Mode E industrial benchmark and E.1 deterministic policy context, live local Foundry evaluation preserved the core schema-valid vs execution-eligible gap and produced zero pipeline false accepts.",
    ]
    for claim in expected_claims:
        assert claim in rows_by_claim
        assert rows_by_claim[claim]["status"] == "PROVEN"
        assert "production robot safety" in rows_by_claim[claim]["unsafe_wording_to_avoid"].lower()


def test_mode_e_final_metrics_export_section_is_generated():
    content = build_final_dissertation_metrics_md(
        Table(),
        Table(),
        Table(),
        Table(),
        create_claims_matrix(),
        Table(),
    )
    assert "Mode E.2 Live Industrial Benchmark" in content
    assert "schema_valid_rate = 0.6333" in content
    assert "execution_eligible_rate = 0.1" in content
    assert "schema_valid_minus_execution_eligible_gap = 0.5333" in content
    assert "pipeline_false_accepts = 0" in content
    assert "mean_latency_ms = 28359.26" in content
    assert "not proof of general industrial deployment readiness" in content
