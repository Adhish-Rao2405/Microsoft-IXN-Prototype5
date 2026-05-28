from pathlib import Path

import scripts.prototype5.run_sdk_mini_replay as mini_replay


class FakeBackendResponse:
    def __init__(self):
        self.success = True
        self.backend = "fake_foundry_sdk_backend"
        self.model_alias = "qwen2.5-coder-0.5b-instruct-generic-cpu:4"
        self.latency_ms = 1.23
        self.raw_text = '{"proposal":"noop"}'
        self.error_type = None
        self.error_message = None


class FakeBackend:
    def generate(self, command, context=None):
        return FakeBackendResponse()


def test_mini_replay_case_set_is_bounded():
    assert 1 <= len(mini_replay.MINI_REPLAY_CASES) <= 5


def test_mini_replay_case_ids_are_unique():
    case_ids = [case["case_id"] for case in mini_replay.MINI_REPLAY_CASES]
    assert len(case_ids) == len(set(case_ids))


def test_mini_replay_cases_have_required_fields():
    required = {"case_id", "category", "risk_type", "user_command"}

    for case in mini_replay.MINI_REPLAY_CASES:
        assert required.issubset(case)
        assert case["user_command"].strip()


def test_output_paths_are_in_mode_sdk_folder():
    assert mini_replay.JSON_OUTPUT == Path("results/prototype5/mode_sdk/sdk_mini_replay_results.json")
    assert mini_replay.MD_OUTPUT == Path("results/prototype5/mode_sdk/sdk_mini_replay_summary.md")


def test_run_case_preserves_raw_text_without_validation():
    result = mini_replay.run_case(FakeBackend(), mini_replay.MINI_REPLAY_CASES[0])

    assert result["success"] is True
    assert result["raw_text"] == '{"proposal":"noop"}'
    assert "schema_valid" not in result
    assert "semantic_valid" not in result
    assert "safety_valid" not in result
    assert "execution_eligible" not in result
    assert "validated" not in result
    assert "repaired" not in result


def test_architectural_boundary_flags_are_false():
    boundary = {
        "parses_json": False,
        "validates_schema": False,
        "repairs_model_output": False,
        "infers_semantic_validity": False,
        "infers_safety_validity": False,
        "infers_execution_eligibility": False,
        "calls_orchestrator": False,
        "runs_full_benchmark": False,
    }

    assert all(value is False for value in boundary.values())


def test_forbidden_model_constant_is_20b_model():
    assert mini_replay.FORBIDDEN_CPU_SMOKE_DEFAULT == "gpt-oss-20b-generic-cpu:1"


def test_summarise_latencies_handles_empty_latency_list():
    summary = mini_replay.summarise_latencies([{"latency_ms": None}])

    assert summary["mean_latency_ms"] is None
    assert summary["min_latency_ms"] is None
    assert summary["max_latency_ms"] is None


def test_summarise_latencies_calculates_values():
    summary = mini_replay.summarise_latencies(
        [
            {"latency_ms": 10.0},
            {"latency_ms": 20.0},
            {"latency_ms": None},
        ]
    )

    assert summary["mean_latency_ms"] == 15.0
    assert summary["min_latency_ms"] == 10.0
    assert summary["max_latency_ms"] == 20.0
