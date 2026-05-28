from pathlib import Path

import scripts.prototype5.run_sdk_action_envelope_mini_replay as action_replay
from scripts.prototype5.run_sdk_mini_replay import MINI_REPLAY_CASES


class FakeBackendResponse:
    def __init__(self, raw_text='{"actions": []}'):
        self.success = True
        self.backend = "fake_foundry_sdk_backend"
        self.model_alias = "qwen2.5-coder-0.5b-instruct-generic-cpu:4"
        self.latency_ms = 2.5
        self.raw_text = raw_text
        self.error_type = None
        self.error_message = None


class FakeBackend:
    def generate(self, command, context=None):
        self.command = command
        self.context = context
        return FakeBackendResponse()


def test_action_envelope_uses_same_five_case_ids_as_mini_replay():
    assert [case["case_id"] for case in action_replay.MINI_REPLAY_CASES] == [
        case["case_id"] for case in MINI_REPLAY_CASES
    ]


def test_prompt_contains_validator_derived_action_envelope_contract():
    prompt = action_replay.build_prompt("Move home.")

    assert '"actions"' in prompt
    assert "pick, place, moveee, opengripper, closegripper, reset, describescene" in prompt
    assert "Allowed safe objects" in prompt
    assert "Allowed safe targets" in prompt
    assert "Do not include markdown" in prompt
    assert "Do not include explanation" in prompt


def test_output_paths_are_mode_sdk_only():
    assert action_replay.JSON_OUTPUT == Path("results/prototype5/mode_sdk/sdk_action_envelope_mini_replay_results.json")
    assert action_replay.MD_OUTPUT == Path("results/prototype5/mode_sdk/sdk_action_envelope_mini_replay_summary.md")


def test_forbidden_model_guard_remains_present():
    assert action_replay.FORBIDDEN_CPU_SMOKE_DEFAULT == "gpt-oss-20b-generic-cpu:1"


def test_run_case_records_validation_without_repairing_raw_text():
    backend = FakeBackend()
    result = action_replay.run_case(backend, action_replay.MINI_REPLAY_CASES[2])

    assert result["sdk_success"] is True
    assert result["raw_text"] == '{"actions": []}'
    assert result["json_valid"] is True
    assert result["schema_valid"] is True
    assert result["execution_eligible"] is False
    assert "execution_eligible" in result
    assert "validated" not in result
    assert "repaired" not in result


def test_build_summary_compares_against_m7_counts():
    rows = [
        {
            "sdk_success": True,
            "json_valid": True,
            "schema_valid": True,
            "semantic_valid": False,
            "safety_valid": False,
            "execution_eligible": False,
            "latency_ms": 1.0,
        }
    ]

    summary = action_replay.build_summary(
        status="COMPLETE_SDK_ACTION_ENVELOPE_MINI_REPLAY",
        base_url="http://127.0.0.1:53402",
        model_alias="qwen2.5-coder-0.5b-instruct-generic-cpu:4",
        case_results=rows,
    )

    assert summary["comparison_to_m7"]["m7"]["schema_valid_count"] == 0
    assert summary["comparison_to_m7"]["m9"]["schema_valid_count"] == 1
    assert summary["comparison_to_m7"]["schema_valid_delta"] == 1


def test_architectural_boundary_prevents_scope_creep():
    assert action_replay.ARCHITECTURAL_BOUNDARY["uses_existing_validators"] is True
    assert action_replay.ARCHITECTURAL_BOUNDARY["modifies_validators"] is False
    assert action_replay.ARCHITECTURAL_BOUNDARY["repairs_model_output"] is False
    assert action_replay.ARCHITECTURAL_BOUNDARY["runs_full_benchmark"] is False
    assert action_replay.ARCHITECTURAL_BOUNDARY["calls_orchestrator"] is False


def test_script_does_not_import_orchestrator_and_derives_execution_from_validation():
    source = Path("scripts/prototype5/run_sdk_action_envelope_mini_replay.py").read_text(encoding="utf-8")

    assert "run_orchestrator" not in source
    assert "final_evidence_orchestrator" not in source
    assert "validation[\"schema_valid\"] and validation[\"semantic_valid\"] and validation[\"safety_valid\"]" in source
