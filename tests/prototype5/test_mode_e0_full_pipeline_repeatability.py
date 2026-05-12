import csv
import json
import subprocess
import sys
from pathlib import Path

from scripts.prototype5 import run_full_pipeline_repeatability as e04


ROOT = Path(__file__).resolve().parents[2]
MODE_E0_DIR = ROOT / "results" / "prototype5" / "mode_e0"
RUNS_CSV = MODE_E0_DIR / "full_pipeline_live_repeatability_runs.csv"
SUMMARY_JSON = MODE_E0_DIR / "full_pipeline_live_repeatability_summary.json"
SUMMARY_MD = MODE_E0_DIR / "full_pipeline_live_repeatability_summary.md"


def test_full_pipeline_repeatability_script_is_repo_local_and_bounded():
    completed = subprocess.run(
        [sys.executable, "scripts/prototype5/run_full_pipeline_repeatability.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert RUNS_CSV.exists()
    assert SUMMARY_JSON.exists()
    assert SUMMARY_MD.exists()

    summary = json.loads(SUMMARY_JSON.read_text(encoding="utf-8"))
    assert summary["mode"] == "E0.4"
    assert summary["status"] in {
        "COMPLETE_FULL_LIVE_PIPELINE_REPEATABILITY",
        "PARTIAL_FULL_LIVE_PIPELINE_REPEATABILITY",
        "E0_4_NOT_RUN",
    }
    assert summary["benchmark_path"] == "configs/prototype5/benchmark_v1.json"
    assert summary["prompt_path"] == "configs/prototype5/action_envelope_prompt.txt"
    assert "Microsoft-IXN-Prototype3" not in summary["benchmark_path"]
    assert "Microsoft-IXN-Prototype3" not in summary["prompt_path"]
    assert "does not prove real-world robot safety" in summary["claim_boundary"]


def test_help_exposes_resume_safe_cli_flags():
    completed = subprocess.run(
        [sys.executable, "scripts/prototype5/run_full_pipeline_repeatability.py", "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0
    for flag in ["--run-id", "--resume", "--skip-existing", "--max-commands"]:
        assert flag in completed.stdout


def test_full_pipeline_repeatability_rows_match_status_boundary():
    with RUNS_CSV.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows

    required_columns = {
        "run_id",
        "status",
        "schema_valid_rate",
        "semantic_valid_rate",
        "safety_valid_rate",
        "execution_eligible_rate",
        "model_false_accepts",
        "pipeline_false_accepts",
        "correct_rejects",
        "mean_latency_ms",
        "std_latency_ms",
        "schema_valid_minus_execution_eligible_gap",
    }
    assert required_columns.issubset(rows[0])

    summary = json.loads(SUMMARY_JSON.read_text(encoding="utf-8"))
    if summary["status"] == "COMPLETE_FULL_LIVE_PIPELINE_REPEATABILITY":
        complete_rows = [
            row
            for row in rows
            if row["status"] == "COMPLETE_FULL_LIVE_PIPELINE_REPEATABILITY"
        ]
        assert len(complete_rows) >= 3
        for row in complete_rows:
            assert row["schema_valid_rate"] != "NOT_EVALUATED"
            assert row["execution_eligible_rate"] != "NOT_EVALUATED"
            assert row["schema_valid_minus_execution_eligible_gap"] != "NOT_EVALUATED"
        assert summary["central_findings"]["schema_valid_greater_than_execution_eligible"] in {
            "STABLE_OBSERVED",
            "NOT_OBSERVED_OR_VARIABLE",
        }
    elif summary["status"] == "E0_4_NOT_RUN":
        assert rows[0]["schema_valid_rate"] == "NOT_EVALUATED"
        assert summary["central_findings"]["schema_valid_greater_than_execution_eligible"] == "NOT_EVALUATED"


def _complete_row(slot: int, gap: str = "0.2", false_accepts: str = "0") -> dict[str, str]:
    return {
        "run_id": f"e0_4_full_pipeline_run_{slot:02d}",
        "status": "COMPLETE_FULL_LIVE_PIPELINE_REPEATABILITY",
        "schema_valid_minus_execution_eligible_gap": gap,
        "pipeline_false_accepts": false_accepts,
        "raw_output_file": f"results/prototype5/mode_e0/e0_4_full_pipeline_run_{slot:02d}_raw.jsonl",
    }


def test_status_counts_debug_partial_runs_correctly():
    assert e04._summary_status([]) == "E0_4_NOT_RUN"
    assert e04._summary_status([_complete_row(1)]) == "PARTIAL_FULL_LIVE_PIPELINE_REPEATABILITY"
    assert e04._summary_status([_complete_row(1), _complete_row(2)]) == "PARTIAL_FULL_LIVE_PIPELINE_REPEATABILITY"
    assert (
        e04._summary_status([_complete_row(1), _complete_row(2), _complete_row(3)])
        == "COMPLETE_FULL_LIVE_PIPELINE_REPEATABILITY"
    )
    assert (
        e04._summary_status(
            [
                _complete_row(1),
                {"run_id": "e0_4_full_pipeline_run_02", "status": "DEBUG_PARTIAL_RUN"},
            ]
        )
        == "PARTIAL_FULL_LIVE_PIPELINE_REPEATABILITY"
    )


def test_central_findings_are_gated_until_three_complete_runs():
    one_run = e04._central_findings([_complete_row(1)])
    assert one_run["schema_valid_greater_than_execution_eligible"] == "NOT_EVALUATED"
    assert one_run["pipeline_false_accepts_bounded"] == "NOT_EVALUATED"

    two_runs = e04._central_findings([_complete_row(1), _complete_row(2)])
    assert two_runs["schema_valid_greater_than_execution_eligible"] == "NOT_EVALUATED"
    assert two_runs["pipeline_false_accepts_bounded"] == "NOT_EVALUATED"

    three_runs = e04._central_findings([_complete_row(1), _complete_row(2), _complete_row(3)])
    assert three_runs["schema_valid_greater_than_execution_eligible"] == "STABLE_OBSERVED"
    assert three_runs["pipeline_false_accepts_bounded"] == "STABLE_ZERO"


def test_run_id_resume_and_skip_existing_slot_selection(monkeypatch):
    existing_rows = [_complete_row(1)]
    assert e04._target_slots(3, 2, False, False, existing_rows) == [2]
    assert e04._target_slots(3, 3, False, False, existing_rows) == [3]
    assert e04._target_slots(3, None, True, False, existing_rows) == [2, 3]

    monkeypatch.setattr(e04, "_existing_raw_slots", lambda: {1, 2})
    assert e04._target_slots(3, None, False, True, existing_rows) == [3]
    assert e04._target_slots(3, 2, False, True, existing_rows) == []
