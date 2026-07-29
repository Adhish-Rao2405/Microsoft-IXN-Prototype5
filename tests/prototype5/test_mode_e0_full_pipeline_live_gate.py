import csv
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
def test_e0_3_full_live_pipeline_gate_writes_not_run_report(tmp_path):
    output_dir = tmp_path / "mode_e0"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/prototype5/run_full_pipeline_repeatability_live.py",
            "--output-dir",
            str(output_dir),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr

    summary = json.loads(
        (output_dir / "full_pipeline_repeatability_summary.json").read_text()
    )
    assert summary["mode"] == "E0.3"
    assert summary["status"] == "E0_3_NOT_RUN"
    assert "repo-local callable live runner" in summary["reason"]
    assert "Schema-valid versus execution-eligible repeatability is not proven" in summary["claim_boundary"]

    with (output_dir / "full_pipeline_repeatability_live_runs.csv").open(
        newline="",
        encoding="utf-8",
    ) as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    row = rows[0]
    assert row["status"] == "E0_3_NOT_RUN"
    assert row["schema_valid_rate"] == "NOT_EVALUATED"
    assert row["execution_eligible_rate"] == "NOT_EVALUATED"
    assert row["model_false_accepts"] == "NOT_EVALUATED"
    assert row["pipeline_false_accepts"] == "NOT_EVALUATED"
