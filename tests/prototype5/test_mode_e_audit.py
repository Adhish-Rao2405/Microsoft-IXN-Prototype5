import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AUDIT_JSON = ROOT / "results" / "prototype5" / "mode_e" / "mode_e_benchmark_audit.json"
AUDIT_MD = ROOT / "results" / "prototype5" / "mode_e" / "mode_e_benchmark_audit.md"


def test_mode_e_audit_script_generates_outputs():
    completed = subprocess.run(
        [sys.executable, "scripts/prototype5/run_mode_e_benchmark_audit.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert AUDIT_JSON.exists()
    assert AUDIT_MD.exists()

    audit = json.loads(AUDIT_JSON.read_text(encoding="utf-8"))
    assert audit["status"] == "COMPLETE_BALANCED_EXTENSION"
    assert audit["metrics"]["total_cases"] == 30
    assert audit["metrics"]["cases_by_difficulty"] == {
        "ambiguous": 10,
        "clear": 10,
        "unsafe_or_invalid": 10,
    }
    assert all(count == 5 for count in audit["metrics"]["cases_by_scenario_family"].values())


def test_mode_e_docs_use_bounded_language():
    docs = [
        ROOT / "docs" / "prototype5" / "mode_e_benchmark_representativeness.md",
        ROOT / "docs" / "prototype5" / "mode_e_evidence_summary.md",
        ROOT / "docs" / "prototype5" / "mode_e_dissertation_wording.md",
    ]
    assert [path for path in docs if not path.exists()] == []
    combined = "\n".join(path.read_text(encoding="utf-8") for path in docs).lower()

    for phrase in [
        "this extension improves scenario coverage but does not make the benchmark comprehensive",
        "bounded benchmark-extension result",
        "does not prove real robot safety",
        "does not establish full industrial generalisation",
    ]:
        assert phrase in combined
    assert "proves production robot safety" not in combined
    assert "proves industrial deployment readiness" not in combined
