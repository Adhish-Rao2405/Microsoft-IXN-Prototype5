import csv
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODE_E0_DIR = ROOT / "results" / "prototype5" / "mode_e0"


def test_pipeline_repeatability_script_generates_outputs(tmp_path):
    output_dir = tmp_path / "mode_e0"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/prototype5/run_pipeline_repeatability_analysis.py",
            "--input-dir",
            str(MODE_E0_DIR),
            "--output-dir",
            str(output_dir),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert (output_dir / "pipeline_repeatability_records.jsonl").exists()
    assert (output_dir / "pipeline_repeatability_summary.csv").exists()
    assert (output_dir / "pipeline_repeatability_variance_summary.json").exists()
    assert (output_dir / "pipeline_repeatability_variance_summary.md").exists()


def test_pipeline_repeatability_summary_schema_and_boundaries():
    with (MODE_E0_DIR / "pipeline_repeatability_summary.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) >= 3
    for row in rows:
        assert row["status"] == "COMPLETE_PIPELINE_REPLAY_ON_MINIMAL_PROMPT_OUTPUTS"
        assert row["schema_valid_rate"] != "NOT_EVALUATED"
        assert row["execution_eligible_rate"] != "NOT_EVALUATED"
        assert row["pipeline_false_accepts"] != "NOT_EVALUATED"

    summary = json.loads((MODE_E0_DIR / "pipeline_repeatability_variance_summary.json").read_text())
    assert summary["mode"] == "E0.2"
    assert summary["status"] == "COMPLETE_PIPELINE_REPLAY_ON_MINIMAL_PROMPT_OUTPUTS"
    assert summary["runs_evaluated"] >= 3
    assert "metric_variance" in summary
    assert "central_findings" in summary
    assert "does not replace the locked Prototype 3/4 benchmark evidence" in summary["claim_boundary"]
    assert "minimal JSON action object" in summary["important_caveat"]
