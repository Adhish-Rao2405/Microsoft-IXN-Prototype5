from dataclasses import dataclass

from src.prototype5.voice_to_planner_bridge import bridge_transcript_to_planner


@dataclass
class FakeBackendResponse:
    raw_text: str = '{"actions": []}'
    success: bool = True
    backend: str = "fake_voice_bridge_backend"
    model_alias: str = "mock"
    latency_ms: float = 1.25
    error_type: str | None = None
    error_message: str | None = None


class FakeBackend:
    def __init__(self, raw_text: str = '{"actions": []}', success: bool = True) -> None:
        self.raw_text = raw_text
        self.success = success
        self.calls: list[tuple[str, dict | None]] = []

    def generate(self, command: str, context: dict | None = None) -> FakeBackendResponse:
        self.calls.append((command, context))
        return FakeBackendResponse(raw_text=self.raw_text, success=self.success)


class RaisingBackend:
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, command: str, context: dict | None = None):
        self.calls += 1
        raise RuntimeError("backend unavailable")


def test_ineligible_stop_command_never_calls_backend():
    backend = FakeBackend()
    result = bridge_transcript_to_planner("Stop the robot", planner_backend=backend)

    assert backend.calls == []
    assert result.planner_called is False
    assert result.rejection_stage == "voice_policy"
    assert result.execution_eligible is False


def test_ineligible_ambiguous_command_never_calls_backend():
    backend = FakeBackend()
    result = bridge_transcript_to_planner("Move it over there", planner_backend=backend)

    assert backend.calls == []
    assert result.planner_called is False
    assert result.rejection_stage == "voice_policy"
    assert "ambiguous_reference" in result.voice_risk_flags


def test_ineligible_proceed_command_never_calls_backend():
    backend = FakeBackend()
    result = bridge_transcript_to_planner("Proceed", planner_backend=backend)

    assert backend.calls == []
    assert result.planner_called is False
    assert result.rejection_stage == "voice_policy"
    assert result.execution_eligible is False


def test_eligible_planning_command_calls_backend():
    backend = FakeBackend()
    result = bridge_transcript_to_planner("Move the red block to the inspection zone", planner_backend=backend)

    assert len(backend.calls) == 1
    assert backend.calls[0][0] == "Move the red block to the inspection zone"
    assert result.planner_called is True
    assert result.voice_eligible_for_planning is True


def test_backend_exception_fails_closed():
    backend = RaisingBackend()
    result = bridge_transcript_to_planner("Move the red block to the inspection zone", planner_backend=backend)

    assert backend.calls == 1
    assert result.execution_eligible is False
    assert result.rejection_stage == "planner_backend"
    assert result.error == "RuntimeError: backend unavailable"


def test_backend_failure_response_fails_closed():
    backend = FakeBackend(success=False)
    result = bridge_transcript_to_planner("Move the red block to the inspection zone", planner_backend=backend)

    assert result.planner_called is True
    assert result.planner_success is False
    assert result.execution_eligible is False
    assert result.rejection_stage == "planner_backend"


def test_schema_invalid_planner_response_fails_closed():
    backend = FakeBackend(raw_text="not json")
    result = bridge_transcript_to_planner("Move the red block to the inspection zone", planner_backend=backend)

    assert result.json_valid is False
    assert result.schema_valid is False
    assert result.execution_eligible is False
    assert result.rejection_stage == "deterministic_validators"


def test_schema_valid_but_safety_invalid_response_remains_not_execution_eligible():
    backend = FakeBackend(raw_text='{"actions": []}')
    result = bridge_transcript_to_planner("Move the red block to the inspection zone", planner_backend=backend)

    assert result.json_valid is True
    assert result.schema_valid is True
    assert result.safety_valid is False
    assert result.execution_eligible is False


def test_voice_eligibility_never_equals_execution_eligibility():
    backend = FakeBackend(raw_text='{"actions": []}')
    result = bridge_transcript_to_planner("Move the red block to the inspection zone", planner_backend=backend)

    assert result.voice_eligible_for_planning is True
    assert result.execution_eligible is False


def test_bridge_preserves_transcripts_raw_planner_response_and_rejection_reason():
    backend = FakeBackend(raw_text='{"actions": []}')
    result = bridge_transcript_to_planner("  Move   the red block to the inspection zone  ", planner_backend=backend)

    assert result.raw_transcript == "  Move   the red block to the inspection zone  "
    assert result.normalised_transcript == "Move the red block to the inspection zone"
    assert result.raw_planner_response == '{"actions": []}'
    assert result.rejection_reason == "semantic_invalid"


def test_tests_use_fake_backend_without_audio_or_live_sdk_dependencies():
    backend = FakeBackend()
    result = bridge_transcript_to_planner("Move the red block to the inspection zone", planner_backend=backend)

    assert result.planner_backend == "fake_voice_bridge_backend"
    assert result.planner_called is True
