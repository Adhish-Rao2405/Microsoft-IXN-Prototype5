import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
def test_mode_e_audit_script_generates_outputs(tmp_path):
    output_dir = tmp_path / "mode_e"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/prototype5/run_mode_e_benchmark_audit.py",
            "--output-dir",
            str(output_dir),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    audit_json = output_dir / "mode_e_benchmark_audit.json"
    audit_md = output_dir / "mode_e_benchmark_audit.md"
    assert audit_json.exists()
    assert audit_md.exists()

    audit = json.loads(audit_json.read_text(encoding="utf-8"))
    assert audit["status"] == "COMPLETE_BALANCED_EXTENSION"
    assert audit["metrics"]["total_cases"] == 30
    assert audit["metrics"]["cases_by_difficulty"] == {
        "ambiguous": 10,
        "clear": 10,
        "unsafe_or_invalid": 10,
    }
    assert all(count == 5 for count in audit["metrics"]["cases_by_scenario_family"].values())
    assert {path.name for path in output_dir.iterdir()} == {
        "mode_e_benchmark_audit.json",
        "mode_e_benchmark_audit.md",
    }


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
