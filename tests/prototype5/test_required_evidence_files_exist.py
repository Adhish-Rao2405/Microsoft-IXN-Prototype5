import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODE_E0_DIR = ROOT / "results" / "prototype5" / "mode_e0"


def test_required_mode_e0_files_exist():
    required = [
        ROOT / "docs" / "prototype5" / "reproducibility_guide.md",
        ROOT / "docs" / "prototype5" / "evaluation_design_justification.md",
        ROOT / "docs" / "prototype5" / "benchmark_representativeness.md",
        ROOT / "docs" / "prototype5" / "repeatability_and_variance_plan.md",
        ROOT / "docs" / "prototype5" / "claim_to_evidence_traceability.md",
        MODE_E0_DIR / "reproducibility_check_summary.json",
        MODE_E0_DIR / "claim_to_evidence_traceability.csv",
        MODE_E0_DIR / "repeatability_summary.csv",
        MODE_E0_DIR / "repeatability_live_runs.csv",
        MODE_E0_DIR / "repeatability_variance_summary.json",
        MODE_E0_DIR / "repeatability_variance_summary.md",
        MODE_E0_DIR / "pipeline_repeatability_records.jsonl",
        MODE_E0_DIR / "pipeline_repeatability_summary.csv",
        MODE_E0_DIR / "pipeline_repeatability_variance_summary.json",
        MODE_E0_DIR / "pipeline_repeatability_variance_summary.md",
        MODE_E0_DIR / "full_pipeline_repeatability_live_runs.csv",
        MODE_E0_DIR / "full_pipeline_repeatability_summary.json",
        MODE_E0_DIR / "full_pipeline_repeatability_summary.md",
    ]
    assert [path for path in required if not path.exists()] == []


def test_traceability_missing_files_are_not_marked_proven():
    with (MODE_E0_DIR / "claim_to_evidence_traceability.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    for row in rows:
        paths = [ROOT / item.strip() for item in row["evidence_file"].split(";") if item.strip()]
        all_exist = all(path.exists() for path in paths)
        assert row["file_exists"] == str(all_exist).lower()
        if row["evidence_status"] == "PROVEN":
            assert all_exist


def test_mode_e0_docs_include_required_bounded_language():
    benchmark_doc = (ROOT / "docs" / "prototype5" / "benchmark_representativeness.md").read_text(
        encoding="utf-8"
    )
    evaluation_doc = (
        ROOT / "docs" / "prototype5" / "evaluation_design_justification.md"
    ).read_text(encoding="utf-8")
    assert "not claimed to be exhaustive" in benchmark_doc
    assert "controlled exploratory benchmark" in benchmark_doc
    assert "not designed to prove that a local SLM is a safe robot controller" in evaluation_doc
