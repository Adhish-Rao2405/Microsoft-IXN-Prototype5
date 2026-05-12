import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODE_E0_DIR = ROOT / "results" / "prototype5" / "mode_e0"


def test_mode_e0_docs_and_results_exist():
    required_docs = [
        "docs/prototype5/reproducibility_guide.md",
        "docs/prototype5/evaluation_design_justification.md",
        "docs/prototype5/benchmark_representativeness.md",
        "docs/prototype5/repeatability_and_variance_plan.md",
        "docs/prototype5/claim_to_evidence_traceability.md",
    ]
    required_results = [
        "results/prototype5/mode_e0/reproducibility_check_summary.json",
        "results/prototype5/mode_e0/claim_to_evidence_traceability.csv",
        "results/prototype5/mode_e0/repeatability_summary.csv",
    ]
    missing = [path for path in [*required_docs, *required_results] if not (ROOT / path).exists()]
    assert missing == []


def test_mode_e0_reproducibility_script_generates_summary():
    completed = subprocess.run(
        [sys.executable, "scripts/prototype5/run_reproducibility_check.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr

    summary = json.loads((MODE_E0_DIR / "reproducibility_check_summary.json").read_text())
    assert summary["mode"] == "E0"
    assert summary["name"] == "Reproducibility and Evaluation Rigour Audit"
    assert summary["status"] in {"COMPLETE", "COMPLETE_WITH_WARNINGS"}
    assert set(summary) >= {
        "required_documents",
        "required_result_files",
        "evidence_files_checked",
        "claim_traceability",
        "notes",
    }
    assert summary["required_documents"]["present"] == 5
    assert summary["claim_traceability"]["total_claims"] >= 10


def test_repeatability_summary_is_honest_placeholder_not_fake_metrics():
    text = (MODE_E0_DIR / "repeatability_summary.csv").read_text(encoding="utf-8")
    assert "repeatability_protocol" in text
    assert "PLANNED" in text
    assert "live repeated runs not yet executed" in text
