import csv
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODE_E0_DIR = ROOT / "results" / "prototype5" / "mode_e0"

REQUIRED_REPEATABILITY_COLUMNS = {
    "run_id",
    "model_alias",
    "benchmark_id",
    "config_id",
    "status",
    "request_success_rate",
    "parse_success_rate",
    "json_valid_rate",
    "schema_valid_rate",
    "semantic_valid_rate",
    "safety_valid_rate",
    "execution_eligible_rate",
    "model_false_accepts",
    "pipeline_false_accepts",
    "mean_latency_ms",
    "std_latency_ms",
    "notes",
}

REPEATABILITY_STATUSES = {
    "COMPLETE",
    "AVAILABLE",
    "COMPLETE_LIVE_OUTPUT_REPEATABILITY",
    "PARTIAL",
    "FAILED",
    "NOT_RUN",
}


def test_repeatability_analysis_script_generates_e0_1_outputs(tmp_path):
    output_dir = tmp_path / "mode_e0"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/prototype5/run_repeatability_analysis.py",
            "--output-dir",
            str(output_dir),
            "--skip-foundry-probe",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr

    assert (output_dir / "repeatability_live_runs.csv").exists()
    assert (output_dir / "repeatability_variance_summary.json").exists()
    assert (output_dir / "repeatability_variance_summary.md").exists()


def test_repeatability_live_runs_csv_schema_and_honest_not_run_metrics():
    with (MODE_E0_DIR / "repeatability_live_runs.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert rows
    assert REQUIRED_REPEATABILITY_COLUMNS.issubset(rows[0].keys())
    for row in rows:
        assert row["status"] in REPEATABILITY_STATUSES
        if row["status"] == "NOT_RUN":
            metric_values = [
                row["request_success_rate"],
                row["parse_success_rate"],
                row["json_valid_rate"],
                row["schema_valid_rate"],
                row["semantic_valid_rate"],
                row["safety_valid_rate"],
                row["execution_eligible_rate"],
                row["model_false_accepts"],
                row["pipeline_false_accepts"],
                row["mean_latency_ms"],
                row["std_latency_ms"],
            ]
            assert all(value == "" for value in metric_values)
        if row["status"] in {"COMPLETE", "COMPLETE_LIVE_OUTPUT_REPEATABILITY"}:
            assert row["request_success_rate"]
            assert row["parse_success_rate"]
            assert row["json_valid_rate"]
            assert row["schema_valid_rate"] == "NOT_EVALUATED"
            assert row["execution_eligible_rate"] == "NOT_EVALUATED"


def test_repeatability_variance_summary_is_bounded():
    summary = json.loads((MODE_E0_DIR / "repeatability_variance_summary.json").read_text())
    assert summary["mode"] == "E0.1"
    assert summary["name"] == "Live Repeatability and Variance Evidence"
    assert summary["status"] in {"COMPLETE_LIVE_OUTPUT_REPEATABILITY", "COMPLETE", "PARTIAL", "NOT_RUN"}
    assert summary["target_run_count"] >= 3
    assert summary["ideal_run_count"] >= summary["target_run_count"]
    assert "metric_variance" in summary
    assert "central_findings" in summary

    if summary["status"] in {"COMPLETE", "COMPLETE_LIVE_OUTPUT_REPEATABILITY"}:
        assert summary["completed_run_count"] >= 3
        assert summary["metric_variance"]["request_success_rate"]["stable"] in {"STABLE", "VARIABLE"}
        assert summary["metric_variance"]["json_valid_rate"]["stable"] in {"STABLE", "VARIABLE"}
        assert "full deterministic validation pipeline repeatability" in summary["not_evaluated_scope"]
    else:
        assert summary["central_findings"]["schema_valid_greater_than_execution_eligible"]["status"] in {
            "NOT_EVALUATED",
            "STABLE",
            "VARIABLE",
        }

    markdown = (MODE_E0_DIR / "repeatability_variance_summary.md").read_text(encoding="utf-8")
    assert "No repeatability metrics are inferred from single-run evidence" in markdown
    assert "general model-reliability claim" in markdown
