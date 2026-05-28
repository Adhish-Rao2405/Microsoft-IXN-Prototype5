from pathlib import Path

import scripts.prototype5.audit_sdk_mini_replay_validators as validator_audit


def test_validator_audit_paths_are_mode_sdk_only():
    assert validator_audit.INPUT_JSON == Path("results/prototype5/mode_sdk/sdk_mini_replay_results.json")
    assert validator_audit.OUTPUT_JSON == Path("results/prototype5/mode_sdk/sdk_mini_replay_validator_audit.json")
    assert validator_audit.OUTPUT_MD == Path("results/prototype5/mode_sdk/sdk_mini_replay_validator_audit.md")


def test_safe_json_parse_accepts_valid_json():
    ok, payload, error = validator_audit.safe_json_parse('{"action":"noop"}')

    assert ok is True
    assert payload == {"action": "noop"}
    assert error is None


def test_safe_json_parse_rejects_invalid_json_fail_closed():
    ok, payload, error = validator_audit.safe_json_parse("not json")

    assert ok is False
    assert payload is None
    assert "json_decode_error" in error


def test_safe_json_parse_rejects_empty_text_fail_closed():
    ok, payload, error = validator_audit.safe_json_parse("")

    assert ok is False
    assert payload is None
    assert error == "empty_raw_text"


def test_audit_case_contains_required_fields_for_invalid_json():
    case = {
        "case_id": "x",
        "category": "test",
        "risk_type": "clear",
        "user_command": "Move home.",
        "success": True,
        "latency_ms": 1.0,
        "error_type": None,
        "raw_text": "not json",
    }

    row = validator_audit.audit_case(case)

    assert row["case_id"] == "x"
    assert row["sdk_success"] is True
    assert row["json_valid"] is False
    assert row["schema_valid"] is False
    assert row["semantic_valid"] is False
    assert row["safety_valid"] is False
    assert row["execution_eligible"] is False
    assert row["failure_mode"] == "json_invalid"


def test_run_existing_validation_never_marks_invalid_json_execution_eligible():
    result = validator_audit.run_existing_validation("not json", {"user_command": "Move home."})

    assert result["json_valid"] is False
    assert result["execution_eligible"] is False
    assert result["schema_valid"] is False
    assert result["semantic_valid"] is False
    assert result["safety_valid"] is False


def test_architectural_boundary_in_script_source_does_not_allow_scope_creep():
    source = Path("scripts/prototype5/audit_sdk_mini_replay_validators.py").read_text(encoding="utf-8")

    assert '"modifies_validators": False' in source
    assert '"repairs_model_output": False' in source
    assert '"runs_full_benchmark": False' in source
    assert '"calls_orchestrator": False' in source
    assert '"starts_voice_control": False' in source


def test_validator_audit_does_not_import_orchestrator():
    source = Path("scripts/prototype5/audit_sdk_mini_replay_validators.py").read_text(encoding="utf-8").lower()

    assert "run_orchestrator" not in source
    assert "final_evidence_orchestrator" not in source
