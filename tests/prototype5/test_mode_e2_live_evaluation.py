import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.prototype5 import run_mode_e_live_evaluation as e2


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts" / "prototype5" / "run_mode_e_live_evaluation.py"
SUMMARY_DOC = ROOT / "docs" / "prototype5" / "mode_e2_live_evaluation_summary.md"
WORDING_DOC = ROOT / "docs" / "prototype5" / "mode_e2_dissertation_wording.md"
REPO_TEST_OUTPUT_DIR = ROOT / ".pytest_cache" / "mode_e2_not_run"

REQUIRED_METRICS = {
    "run_status",
    "model_alias",
    "base_url",
    "benchmark_id",
    "policy_id",
    "vocabulary_id",
    "total_cases",
    "request_success_rate",
    "parse_success_rate",
    "json_valid_rate",
    "schema_valid_rate",
    "semantic_valid_rate",
    "safety_valid_rate",
    "execution_eligible_rate",
    "model_false_accepts",
    "pipeline_false_accepts",
    "schema_valid_minus_execution_eligible_gap",
    "mean_latency_ms",
    "median_latency_ms",
    "max_latency_ms",
    "cases_by_difficulty",
    "cases_by_scenario_family",
    "cases_by_policy_decision",
}


def test_mode_e2_runner_exists():
    assert RUNNER.exists()


def test_mode_e2_refuses_missing_or_incomplete_e1_audit(monkeypatch):
    missing = ROOT / "results" / "prototype5" / "mode_e" / "__missing_policy_audit_for_test__.json"
    with pytest.raises(RuntimeError, match="policy audit is missing"):
        e2._read_e1_audit(missing)

    monkeypatch.setattr(e2, "load_json", lambda path: {"audit_status": "INCOMPLETE_POLICY_CONTEXT"})
    with pytest.raises(RuntimeError, match="not COMPLETE_POLICY_CONTEXT"):
        e2._read_e1_audit(e2.E1_AUDIT_JSON)


def test_mode_e2_help_exposes_required_cli_flags():
    completed = subprocess.run(
        [sys.executable, "scripts/prototype5/run_mode_e_live_evaluation.py", "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0
    for flag in [
        "--base-url",
        "--model",
        "--output-dir",
        "--max-cases",
        "--timeout-seconds",
        "--allow-overwrite",
    ]:
        assert flag in completed.stdout


def test_mode_e2_writes_not_run_summary_when_foundry_unavailable():
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/prototype5/run_mode_e_live_evaluation.py",
            "--base-url",
            "http://127.0.0.1:1",
            "--model",
            "Phi-3-mini-4k-instruct-generic-cpu:3",
            "--output-dir",
            str(REPO_TEST_OUTPUT_DIR),
            "--max-cases",
            "1",
            "--timeout-seconds",
            "0.2",
            "--allow-overwrite",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    summary_path = REPO_TEST_OUTPUT_DIR / "mode_e2_live_industrial_not_run_summary.json"
    md_path = REPO_TEST_OUTPUT_DIR / "mode_e2_live_industrial_not_run_summary.md"
    assert summary_path.exists()
    assert md_path.exists()

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["run_status"] == "NOT_RUN_FOUNDRY_UNAVAILABLE"
    assert REQUIRED_METRICS.issubset(summary)
    assert summary["request_success_rate"] == "NOT_EVALUATED"
    assert summary["e0_4_descriptive_comparison"]["pipeline_false_accepts"] == 0
    assert "descriptive rather than statistically conclusive" in summary["e0_4_descriptive_comparison"]["comparison_boundary"]


def test_mode_e2_not_run_summary_schema_helper():
    benchmark = {"benchmark_id": "prototype5_mode_e_industrial_v1"}
    vocabulary = {"vocabulary_id": "prototype5_mode_e_industrial_vocabulary_v1"}
    policy = {"policy_id": "prototype5_mode_e_industrial_policy_v1"}
    summary = e2._build_summary(
        run_status="NOT_RUN_FOUNDRY_UNAVAILABLE",
        model_alias="not_run",
        base_url="http://127.0.0.1:1",
        benchmark=benchmark,
        vocabulary=vocabulary,
        policy=policy,
        rows=[],
        reason="unavailable",
    )
    assert REQUIRED_METRICS.issubset(summary)
    assert summary["temperature"] == 0.0


def test_mode_e2_docs_contain_bounded_language():
    assert SUMMARY_DOC.exists()
    assert WORDING_DOC.exists()
    combined = (SUMMARY_DOC.read_text(encoding="utf-8") + "\n" + WORDING_DOC.read_text(encoding="utf-8")).lower()
    assert "not proof of general industrial deployment readiness" in combined
    assert "no certified safety layer" in combined
    assert "descriptive rather than statistically conclusive" in combined
    assert "production safety" in combined
    assert "proves production safety" not in combined
