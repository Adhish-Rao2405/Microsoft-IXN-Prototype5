import csv
import json
import shutil
import subprocess
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from scripts.prototype5.run_manual_voice_transcript_evaluation import (
    DEFAULT_CASES,
    DEFAULT_RESULTS_CSV,
    DEFAULT_SUMMARY_JSON,
    DEFAULT_SUMMARY_MD,
    REQUIRED_COLUMNS,
    load_cases,
    run_evaluation,
)


ROOT = Path(__file__).resolve().parents[2]
REQUIRED_SCENARIO_FAMILIES = {
    "clear_planning",
    "stop_safety",
    "proceed_context",
    "ambiguous_reference",
    "negation_sensitive",
    "unsafe_request",
    "non_command",
    "clarification_without_context",
    "stop_proceed_conflict",
    "low_confidence_or_partial_simulated",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


@contextmanager
def workspace_tmp_dir():
    path = ROOT / ".pytest_m14a_tmp" / uuid4().hex
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def run_tmp_evaluation() -> tuple[list[dict[str, str]], dict[str, object], str]:
    with workspace_tmp_dir() as tmp_dir:
        results_csv = tmp_dir / "manual_voice_results.csv"
        summary_json = tmp_dir / "manual_voice_summary.json"
        summary_md = tmp_dir / "manual_voice_summary.md"

        summary = run_evaluation(DEFAULT_CASES, results_csv, summary_json, summary_md)
        return read_csv(results_csv), summary, summary_md.read_text(encoding="utf-8")


def test_manual_voice_transcript_case_csv_exists_and_has_required_columns():
    assert DEFAULT_CASES.exists()
    with DEFAULT_CASES.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert REQUIRED_COLUMNS.issubset(set(reader.fieldnames or []))


def test_manual_voice_transcript_case_csv_has_minimum_cases_and_families():
    cases = load_cases(DEFAULT_CASES)

    assert len(cases) >= 12
    assert REQUIRED_SCENARIO_FAMILIES.issubset({case["scenario_family"] for case in cases})


def test_committed_m14a_evidence_outputs_exist():
    assert DEFAULT_RESULTS_CSV.exists()
    assert DEFAULT_SUMMARY_JSON.exists()
    assert DEFAULT_SUMMARY_MD.exists()


def test_evaluation_script_loads_cases_and_produces_outputs():
    with workspace_tmp_dir() as tmp_dir:
        results_csv = tmp_dir / "results.csv"
        summary_json = tmp_dir / "summary.json"
        summary_md = tmp_dir / "summary.md"

        summary = run_evaluation(DEFAULT_CASES, results_csv, summary_json, summary_md)

        assert summary["case_count"] == 15
        assert results_csv.exists()
        assert summary_json.exists()
        assert summary_md.exists()


def test_stop_proceed_ambiguous_unsafe_non_command_and_conflict_cases_do_not_call_planner():
    rows, _, _ = run_tmp_evaluation()
    blocked_families = {
        "stop_safety",
        "proceed_context",
        "ambiguous_reference",
        "negation_sensitive",
        "unsafe_request",
        "non_command",
        "clarification_without_context",
        "stop_proceed_conflict",
    }

    blocked_rows = [row for row in rows if row["scenario_family"] in blocked_families]

    assert blocked_rows
    assert {row["actual_planner_called"] for row in blocked_rows} == {"false"}
    assert {row["actual_rejection_stage"] for row in blocked_rows} == {"voice_policy"}


def test_clear_planning_cases_may_call_planner():
    rows, _, _ = run_tmp_evaluation()
    clear_rows = [row for row in rows if row["scenario_family"] == "clear_planning"]

    assert len(clear_rows) == 2
    assert {row["actual_voice_eligible_for_planning"] for row in clear_rows} == {"true"}
    assert {row["actual_planner_called"] for row in clear_rows} == {"true"}


def test_low_confidence_and_partial_transcript_cases_fail_closed():
    rows, _, _ = run_tmp_evaluation()
    low_or_partial_rows = [
        row for row in rows if row["scenario_family"] == "low_confidence_or_partial_simulated"
    ]

    assert len(low_or_partial_rows) == 2
    assert {row["actual_voice_eligible_for_planning"] for row in low_or_partial_rows} == {"false"}
    assert {row["actual_planner_called"] for row in low_or_partial_rows} == {"false"}
    assert {row["execution_eligible"] for row in low_or_partial_rows} == {"false"}


def test_voice_eligible_for_planning_is_never_treated_as_execution_eligible():
    rows, _, _ = run_tmp_evaluation()
    voice_eligible_rows = [row for row in rows if row["actual_voice_eligible_for_planning"] == "true"]

    assert voice_eligible_rows
    assert {row["execution_eligible"] for row in rows} == {"false"}
    assert {row["execution_eligible"] for row in voice_eligible_rows} == {"false"}


def test_summary_records_no_audio_microphone_speech_to_text_or_dependency_changes():
    _, summary, _ = run_tmp_evaluation()

    assert summary["dependency_changes"] is False
    assert summary["audio_runtime_used"] is False
    assert summary["live_microphone_used"] is False
    assert summary["speech_to_text_used"] is False


def test_summary_contains_no_positive_production_voice_or_real_robot_claims():
    _, _, summary_md = run_tmp_evaluation()
    forbidden_claims = [
        "The system supports voice control.",
        "The robot can be controlled by speech.",
        "Speech recognition is implemented.",
        "Emergency stop is implemented.",
        "The voice system is safe.",
        "The system is production ready.",
        "Real robot execution is supported.",
        "The system understands voice commands end-to-end.",
    ]

    for claim in forbidden_claims:
        assert claim not in summary_md


def test_no_audio_or_dependency_runtime_imports_are_required():
    script_text = (
        ROOT / "scripts" / "prototype5" / "run_manual_voice_transcript_evaluation.py"
    ).read_text(encoding="utf-8")
    forbidden_terms = [
        "whisper",
        "speech_recognition",
        "pyaudio",
        "sounddevice",
        "azure.cognitiveservices.speech",
        "wave.open",
        "librosa",
    ]

    lowered = script_text.lower()
    for term in forbidden_terms:
        assert term not in lowered


def test_committed_summary_json_matches_expected_m14a_flags():
    payload = json.loads(DEFAULT_SUMMARY_JSON.read_text(encoding="utf-8"))

    assert payload["status"] == "COMPLETE_MANUAL_TRANSCRIPT_EVALUATION"
    assert payload["milestone"] == "Phase 2 Milestone 14A"
    assert payload["mode"] == "manual_recorded_voice_transcript_evaluation"
    assert payload["case_count"] == 15
    assert payload["failed_expectation_count"] == 0
    assert payload["planner_called_count"] == 2
    assert payload["voice_policy_rejection_count"] == 13
    assert payload["execution_eligible_count"] == 0
    assert payload["audio_runtime_used"] is False
    assert payload["live_microphone_used"] is False
    assert payload["speech_to_text_used"] is False


def test_protected_dissertation_draft_is_not_staged():
    completed = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    staged = set(completed.stdout.splitlines())
    assert "dissertation_drafts/DISS_DRAFT_cleaned.tex" not in staged
