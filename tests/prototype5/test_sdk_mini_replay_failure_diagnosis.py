from pathlib import Path

import scripts.prototype5.diagnose_sdk_mini_replay_failures as diagnosis


def test_diagnosis_paths_are_mode_sdk_only():
    assert diagnosis.MINI_REPLAY_JSON == Path("results/prototype5/mode_sdk/sdk_mini_replay_results.json")
    assert diagnosis.VALIDATOR_AUDIT_JSON == Path("results/prototype5/mode_sdk/sdk_mini_replay_validator_audit.json")
    assert diagnosis.OUTPUT_JSON == Path("results/prototype5/mode_sdk/sdk_mini_replay_failure_diagnosis.json")
    assert diagnosis.OUTPUT_MD == Path("results/prototype5/mode_sdk/sdk_mini_replay_failure_diagnosis.md")


def test_architectural_boundary_forbids_runtime_side_effects():
    assert diagnosis.ARCHITECTURAL_BOUNDARY == {
        "new_model_calls": False,
        "modifies_validators": False,
        "repairs_model_output": False,
        "runs_full_benchmark": False,
        "calls_orchestrator": False,
    }


def test_classifies_json_string_as_prompt_alignment_schema_mismatch():
    mini_case = {"raw_text": '"Move the robot arm to the home position."'}
    audit_row = {
        "case_id": "sdk_mini_clear_002",
        "sdk_success": True,
        "json_valid": True,
        "schema_valid": False,
        "semantic_valid": False,
        "safety_valid": False,
        "execution_eligible": False,
        "failure_mode": "schema_invalid",
        "schema_errors": ["top_level_not_list_or_dict"],
        "risk_type": "clear",
    }

    row = diagnosis.classify_case(mini_case, audit_row)

    assert "JSON_VALID_BUT_SCHEMA_MISMATCH" in row["diagnosis_categories"]
    assert "WRONG_TOP_LEVEL_STRUCTURE" in row["diagnosis_categories"]
    assert "PROMPT_NOT_ACTION_ENVELOPE_ALIGNED" in row["diagnosis_categories"]
    assert row["raw_text_type_after_json_parse"] == "str"


def test_ambiguous_case_records_missing_clarification_category():
    mini_case = {"raw_text": '"Move it to the right."'}
    audit_row = {
        "case_id": "sdk_mini_ambiguous_001",
        "sdk_success": True,
        "json_valid": True,
        "schema_valid": False,
        "semantic_valid": True,
        "safety_valid": False,
        "execution_eligible": False,
        "failure_mode": "schema_invalid",
        "schema_errors": ["top_level_not_list_or_dict"],
        "risk_type": "ambiguous",
    }

    row = diagnosis.classify_case(mini_case, audit_row)

    assert "AMBIGUOUS_REFERENCE_NOT_CLARIFIED" in row["diagnosis_categories"]
    assert row["execution_eligible"] is False


def test_build_summary_counts_prompt_alignment_and_execution_eligible():
    mini_replay = {
        "cases": [
            {
                "case_id": "sdk_mini_clear_001",
                "raw_text": '"Pick up the red block and place it in the blue bin."',
            }
        ]
    }
    validator_audit = {
        "audit_rows": [
            {
                "case_id": "sdk_mini_clear_001",
                "sdk_success": True,
                "json_valid": True,
                "schema_valid": False,
                "semantic_valid": False,
                "safety_valid": False,
                "execution_eligible": False,
                "failure_mode": "schema_invalid",
                "schema_errors": ["top_level_not_list_or_dict"],
                "risk_type": "clear",
            }
        ]
    }

    summary = diagnosis.build_summary(mini_replay, validator_audit)

    assert summary["status"] == "COMPLETE_SDK_MINI_REPLAY_FAILURE_DIAGNOSIS"
    assert summary["case_count"] == 1
    assert summary["aggregate_findings"]["json_valid_but_schema_invalid_count"] == 1
    assert summary["aggregate_findings"]["prompt_alignment_issue_count"] == 1
    assert summary["aggregate_findings"]["execution_eligible_count"] == 0


def test_script_source_does_not_import_backend_or_orchestrator():
    source = Path("scripts/prototype5/diagnose_sdk_mini_replay_failures.py").read_text(encoding="utf-8").lower()

    assert "foundrysdkplannerbackend" not in source
    assert "foundrylocalclient" not in source
    assert "run_orchestrator" not in source
    assert "final_evidence_orchestrator" not in source
