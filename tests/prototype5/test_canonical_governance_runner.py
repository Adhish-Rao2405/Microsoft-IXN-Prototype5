from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.prototype5.canonical_governance_runner import (
    CanonicalGovernanceRequestV2,
    CanonicalGovernanceRunner,
    CanonicalRunnerConfigurationV2,
)
from src.prototype5.foundry_sdk_backend import ModelBackendResponse
from src.prototype5.governance_contract_v2 import (
    CorrectnessStatus,
    FinalDecision,
    GateStatus,
    PlanSemanticStatus,
    ProviderId,
    SimulationStatus,
)
from src.prototype5.manufacturing_policy_v2 import (
    ManufacturingSceneStateV2,
    RequesterContextV2,
    SceneObjectStateV2,
    load_manufacturing_policy,
)
from src.prototype5.task_proposal_v2 import (
    ActionStepV2,
    StructuredTaskProposalV2,
)


ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "configs" / "prototype5" / "manufacturing_policy_v2.json"
SOFTWARE_COMMIT = "a" * 40
CONTENT_HASH = "b" * 64
FIXED_TIME = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)


class FakeBackend:
    def __init__(
        self,
        raw_text: str | None,
        *,
        success: bool = True,
        raises: Exception | None = None,
        model_alias: str = "local-test-model",
    ) -> None:
        self.raw_text = raw_text
        self.success = success
        self.raises = raises
        self.model_alias = model_alias
        self.calls: list[tuple[str, dict[str, object] | None]] = []

    def generate(
        self, command: str, context: dict[str, object] | None = None
    ) -> ModelBackendResponse:
        self.calls.append((command, context))
        if self.raises is not None:
            raise self.raises
        return ModelBackendResponse(
            backend="FOUNDRY_LOCAL",
            model_alias=self.model_alias,
            prompt_id="manufacturing-demo-prompt",
            raw_text=self.raw_text,
            success=self.success,
            latency_ms=12.5,
            error_type=None if self.success else "TransportError",
            error_message=None if self.success else "backend failed",
            timestamp_utc=FIXED_TIME.isoformat(),
        )


def scene(*, obstructed: bool = False) -> ManufacturingSceneStateV2:
    return ManufacturingSceneStateV2(
        scene_id="manufacturing_demo_scene",
        state_version="1.0.0",
        objects=(
            SceneObjectStateV2(
                object_id="blue_component", location_id="input_tray_a"
            ),
            SceneObjectStateV2(
                object_id="red_component", location_id="conveyor_a"
            ),
        ),
        human_obstruction=obstructed,
        safety_interlock_enabled=True,
    )


def request(**overrides: object) -> CanonicalGovernanceRequestV2:
    payload: dict[str, object] = {
        "input_mode": "TYPED",
        "typed_text": (
            "Move the blue component from input tray A "
            "to assembly fixture B."
        ),
        "domain_id": "MANUFACTURING",
        "scene": scene(),
        "requester": RequesterContextV2(
            requester_id="synthetic_operator_01", role="operator"
        ),
        "requested_inference_mode": "LOCAL",
        "evaluation_mode": "LIVE",
    }
    payload.update(overrides)
    return CanonicalGovernanceRequestV2.model_validate(payload)


def valid_move(
    *,
    object_id: str = "blue_component",
    source_id: str = "input_tray_a",
    destination_id: str = "assembly_fixture_b",
) -> str:
    return json.dumps(
        {
            "actions": [
                {
                    "action": "MOVE",
                    "object_id": object_id,
                    "source_id": source_id,
                    "destination_id": destination_id,
                }
            ]
        }
    )


@pytest.fixture
def runner() -> CanonicalGovernanceRunner:
    return CanonicalGovernanceRunner(
        policy=load_manufacturing_policy(POLICY_PATH),
        configuration=CanonicalRunnerConfigurationV2(
            source_repository="Adhish-Rao2405/Microsoft-IXN-Prototype5",
            software_commit=SOFTWARE_COMMIT,
            prompt_id="manufacturing-demo-prompt",
            prompt_version="2.0.0",
        ),
        clock=lambda: FIXED_TIME,
        id_factory=iter(("record-1", "trace-1")).__next__,
    )


def run_local(
    runner: CanonicalGovernanceRunner,
    backend: FakeBackend,
    current_request: CanonicalGovernanceRequestV2 | None = None,
):
    return runner.run(
        current_request or request(),
        backend=backend,
        provider=ProviderId.FOUNDRY_LOCAL,
        model_id="local-test-model",
    )


def test_clear_typed_command_is_accepted_by_all_independent_gates(runner):
    backend = FakeBackend(valid_move())

    result = run_local(runner, backend)
    record = result.governance_record

    assert record.parse_status is GateStatus.PASSED
    assert record.json_status is GateStatus.PASSED
    assert record.schema_status is GateStatus.PASSED
    assert record.plan_semantic_status is PlanSemanticStatus.VALID
    assert record.ambiguity_status is GateStatus.PASSED
    assert record.safety_status is GateStatus.PASSED
    assert record.authority_status is GateStatus.PASSED
    assert record.final_decision is FinalDecision.ACCEPT
    assert record.execution_eligible is True
    assert record.decision_correctness_status is CorrectnessStatus.NOT_EVALUATED
    assert record.simulation_status is SimulationStatus.NOT_REQUESTED
    assert record.execution_permit_id is None
    assert result.proposal is not None
    assert result.raw_response_text == valid_move()


def test_backend_receives_scene_requester_and_versioned_policy_context(runner):
    backend = FakeBackend(valid_move())

    run_local(runner, backend)

    command, context = backend.calls[0]
    assert command.startswith("Move the blue component")
    assert context is not None
    assert context["policy_id"] == "prototype5_manufacturing_policy_v2"
    assert context["policy_version"] == "2.0.0"
    assert context["scene"]["scene_id"] == "manufacturing_demo_scene"
    assert context["requester"]["role"] == "operator"


def test_pick_then_place_is_semantically_equivalent_to_move(runner):
    backend = FakeBackend(
        json.dumps(
            {
                "actions": [
                    {
                        "action": "PICK",
                        "object_id": "blue_component",
                        "source_id": "input_tray_a",
                    },
                    {
                        "action": "PLACE",
                        "object_id": "blue_component",
                        "destination_id": "assembly_fixture_b",
                    },
                ]
            }
        )
    )

    record = run_local(runner, backend).governance_record

    assert record.plan_semantic_status is PlanSemanticStatus.VALID
    assert record.execution_eligible is True


@pytest.mark.parametrize(
    ("command", "proposal"),
    [
        (
            "Pick the blue component from input tray A.",
            {
                "actions": [
                    {
                        "action": "PICK",
                        "object_id": "blue_component",
                        "source_id": "input_tray_a",
                    }
                ]
            },
        ),
        (
            "Place the blue component on assembly fixture B.",
            {
                "actions": [
                    {
                        "action": "PLACE",
                        "object_id": "blue_component",
                        "destination_id": "assembly_fixture_b",
                    }
                ]
            },
        ),
        (
            "Wait for 5 seconds.",
            {"actions": [{"action": "WAIT", "duration_ms": 5000}]},
        ),
        ("Stop.", {"actions": [{"action": "STOP"}]}),
        (
            "Inspect the blue component.",
            {
                "actions": [
                    {"action": "INSPECT", "object_id": "blue_component"}
                ]
            },
        ),
    ],
)
def test_each_bounded_action_has_deterministic_semantics(
    runner, command, proposal
):
    current = request(typed_text=command)

    record = run_local(
        runner, FakeBackend(json.dumps(proposal)), current
    ).governance_record

    assert record.plan_semantic_status is PlanSemanticStatus.VALID
    assert record.final_decision is FinalDecision.ACCEPT


def test_wait_without_duration_requires_clarification(runner):
    current = request(typed_text="Wait.")

    record = run_local(
        runner,
        FakeBackend(json.dumps({"actions": [{"action": "WAIT", "duration_ms": 1000}]})),
        current,
    ).governance_record

    assert record.ambiguity_status is GateStatus.FAILED
    assert record.final_decision is FinalDecision.CLARIFY
    assert "DURATION_UNRESOLVED" in record.decision_reason_codes


def test_voice_and_typed_inputs_converge_on_same_governance_gates():
    shared_policy = load_manufacturing_policy(POLICY_PATH)
    configuration = CanonicalRunnerConfigurationV2(
        source_repository="Adhish-Rao2405/Microsoft-IXN-Prototype5",
        software_commit=SOFTWARE_COMMIT,
        prompt_id="manufacturing-demo-prompt",
        prompt_version="2.0.0",
    )
    typed_runner = CanonicalGovernanceRunner(
        policy=shared_policy,
        configuration=configuration,
        clock=lambda: FIXED_TIME,
        id_factory=iter(("typed-record", "typed-trace")).__next__,
    )
    voice_runner = CanonicalGovernanceRunner(
        policy=shared_policy,
        configuration=configuration,
        clock=lambda: FIXED_TIME,
        id_factory=iter(("voice-record", "voice-trace")).__next__,
    )
    voice_request = request(
        input_mode="VOICE",
        typed_text=None,
        transcript_text=(
            "Move the blue component from input tray A "
            "to assembly fixture B."
        ),
        transcript_status="READY",
        transcript_backend="nemotron-speech-streaming-en-0.6b",
        transcript_confidence=0.92,
        audio_sha256=CONTENT_HASH,
    )

    typed = run_local(typed_runner, FakeBackend(valid_move())).governance_record
    voice = run_local(
        voice_runner, FakeBackend(valid_move()), voice_request
    ).governance_record

    assert voice.normalised_command == typed.normalised_command
    assert (
        voice.parse_status,
        voice.json_status,
        voice.schema_status,
        voice.plan_semantic_status,
        voice.ambiguity_status,
        voice.safety_status,
        voice.authority_status,
        voice.final_decision,
    ) == (
        typed.parse_status,
        typed.json_status,
        typed.schema_status,
        typed.plan_semantic_status,
        typed.ambiguity_status,
        typed.safety_status,
        typed.authority_status,
        typed.final_decision,
    )


def test_partial_voice_transcript_cannot_enter_planning():
    with pytest.raises(ValidationError, match="reviewed READY transcript"):
        request(
            input_mode="VOICE",
            typed_text=None,
            transcript_text="Move the part",
            transcript_status="PARTIAL",
            transcript_backend="nemotron-speech-streaming-en-0.6b",
            transcript_confidence=0.4,
            audio_sha256=CONTENT_HASH,
        )


def test_ambiguous_command_clarifies_and_never_becomes_eligible(runner):
    current = request(typed_text="Move the part over there.")
    backend = FakeBackend(valid_move())

    record = run_local(runner, backend, current).governance_record

    assert (
        record.plan_semantic_status
        is PlanSemanticStatus.NOT_ASSESSABLE_MISSING_REQUIRED_CONTEXT
    )
    assert record.ambiguity_status is GateStatus.FAILED
    assert record.final_decision is FinalDecision.CLARIFY
    assert record.execution_eligible is False
    assert "OBJECT_UNRESOLVED" in record.decision_reason_codes


def test_explicit_human_obstruction_override_is_safety_rejected(runner):
    current = request(
        typed_text="Continue movement despite the human obstruction."
    )
    backend = FakeBackend(valid_move())

    record = run_local(runner, backend, current).governance_record

    assert record.safety_status is GateStatus.FAILED
    assert record.final_decision is FinalDecision.REJECT
    assert record.execution_eligible is False
    assert "HUMAN_OBSTRUCTION_OVERRIDE" in record.decision_reason_codes


def test_scene_human_obstruction_is_safety_rejected(runner):
    current = request(scene=scene(obstructed=True))

    record = run_local(runner, FakeBackend(valid_move()), current).governance_record

    assert record.plan_semantic_status is PlanSemanticStatus.VALID
    assert record.safety_status is GateStatus.FAILED
    assert record.final_decision is FinalDecision.REJECT
    assert "HUMAN_OBSTRUCTION_PRESENT" in record.decision_reason_codes


def test_restricted_destination_is_rejected_by_domain_policy(runner):
    current = request(
        typed_text=(
            "Move the blue component from input tray A to restricted zone."
        )
    )

    record = run_local(
        runner,
        FakeBackend(valid_move(destination_id="restricted_zone")),
        current,
    ).governance_record

    assert record.plan_semantic_status is PlanSemanticStatus.VALID
    assert record.safety_status is GateStatus.FAILED
    assert "RESTRICTED_DESTINATION" in record.decision_reason_codes
    assert "RESTRICTED_DESTINATION_REQUESTED" in record.decision_reason_codes


def test_requester_authority_is_independent_from_semantics(runner):
    current = request(
        requester=RequesterContextV2(
            requester_id="synthetic_observer_01", role="observer"
        )
    )

    record = run_local(runner, FakeBackend(valid_move()), current).governance_record

    assert record.plan_semantic_status is PlanSemanticStatus.VALID
    assert record.authority_status is GateStatus.FAILED
    assert record.final_decision is FinalDecision.REJECT
    assert "ACTION_NOT_AUTHORISED_MOVE" in record.decision_reason_codes


@pytest.mark.parametrize(
    ("raw_text", "reason"),
    [
        (valid_move(object_id="red_component"), "OBJECT_MISMATCH"),
        (
            valid_move(destination_id="destination_bin_b"),
            "DESTINATION_MISMATCH",
        ),
    ],
)
def test_wrong_object_or_destination_is_semantically_invalid(
    runner, raw_text, reason
):
    record = run_local(runner, FakeBackend(raw_text)).governance_record

    assert record.schema_status is GateStatus.PASSED
    assert record.plan_semantic_status is PlanSemanticStatus.INVALID
    assert record.final_decision is FinalDecision.REJECT
    assert reason in record.decision_reason_codes


def test_invalid_json_fails_structurally_without_positive_semantics(runner):
    record = run_local(runner, FakeBackend("not-json")).governance_record

    assert record.parse_status is GateStatus.FAILED
    assert record.json_status is GateStatus.FAILED
    assert record.schema_status is GateStatus.NOT_ASSESSABLE
    assert (
        record.plan_semantic_status
        is PlanSemanticStatus.NOT_ASSESSABLE_PARSE_FAILED
    )
    assert record.final_decision is FinalDecision.ERROR
    assert record.execution_eligible is False


def test_schema_invalid_correct_rejection_is_not_semantic_validity(runner):
    record = run_local(
        runner, FakeBackend(json.dumps({"actions": []}))
    ).governance_record

    assert record.parse_status is GateStatus.PASSED
    assert record.json_status is GateStatus.PASSED
    assert record.schema_status is GateStatus.FAILED
    assert (
        record.plan_semantic_status
        is PlanSemanticStatus.NOT_ASSESSABLE_SCHEMA_INVALID
    )
    assert record.final_decision is FinalDecision.ERROR
    assert "semantic_valid" not in record.model_dump()
    assert "semantic_score" not in record.model_dump()


def test_json_array_is_not_a_structured_proposal_object(runner):
    record = run_local(runner, FakeBackend("[]")).governance_record

    assert record.parse_status is GateStatus.PASSED
    assert record.json_status is GateStatus.FAILED
    assert record.schema_status is GateStatus.NOT_ASSESSABLE
    assert record.final_decision is FinalDecision.ERROR


def test_backend_failure_fails_closed_without_fabricated_proposal(runner):
    result = run_local(
        runner, FakeBackend(None, success=False)
    )
    record = result.governance_record

    assert result.proposal is None
    assert record.raw_response_present is False
    assert record.parse_status is GateStatus.ERROR
    assert record.final_decision is FinalDecision.ERROR
    assert record.execution_eligible is False
    assert record.decision_reason_codes == ("PROVIDER_REQUEST_FAILED",)


def test_backend_exception_is_converted_to_a_fail_closed_record(runner):
    record = run_local(
        runner,
        FakeBackend(None, raises=RuntimeError("local service unavailable")),
    ).governance_record

    assert record.parse_status is GateStatus.ERROR
    assert record.final_decision is FinalDecision.ERROR
    assert record.provider_latency_ms is not None
    assert record.execution_eligible is False


def test_evaluation_mode_scores_decision_correctness_not_plan_semantics(runner):
    evaluation_request = request(
        evaluation_mode="EVALUATION",
        benchmark_id="manufacturing_oracle_fixture",
        benchmark_sha256=CONTENT_HASH,
        oracle_version="2.0.0-test",
        oracle_sha256="c" * 64,
        expected_decision="ACCEPT",
    )

    record = run_local(
        runner, FakeBackend(valid_move()), evaluation_request
    ).governance_record

    assert record.plan_semantic_status is PlanSemanticStatus.VALID
    assert record.decision_correctness_status is CorrectnessStatus.CORRECT
    assert record.provenance.benchmark_sha256 == CONTENT_HASH
    assert record.provenance.oracle_sha256 == "c" * 64


def test_evaluation_mode_can_mark_correct_rejection_without_semantic_validity(
    runner,
):
    evaluation_request = request(
        typed_text="Move the part over there.",
        evaluation_mode="EVALUATION",
        benchmark_id="manufacturing_oracle_fixture",
        benchmark_sha256=CONTENT_HASH,
        oracle_version="2.0.0-test",
        oracle_sha256="c" * 64,
        expected_decision="CLARIFY",
    )

    record = run_local(
        runner, FakeBackend(valid_move()), evaluation_request
    ).governance_record

    assert record.decision_correctness_status is CorrectnessStatus.CORRECT
    assert (
        record.plan_semantic_status
        is PlanSemanticStatus.NOT_ASSESSABLE_MISSING_REQUIRED_CONTEXT
    )


def test_direct_runner_refuses_auto_or_cross_provider_routing(runner):
    auto_request = request(requested_inference_mode="AUTO")
    with pytest.raises(ValueError, match="HybridInferenceRouter"):
        run_local(runner, FakeBackend(valid_move()), auto_request)

    with pytest.raises(ValueError, match="provider must match"):
        runner.run(
            request(),
            backend=FakeBackend(valid_move()),
            provider=ProviderId.CLOUD,
            model_id="cloud-test-model",
        )


def test_policy_configuration_contains_no_benchmark_expected_labels():
    payload = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    serialised = json.dumps(payload)

    assert "expected_decision" not in serialised
    assert "gold_label" not in serialised
    assert "semantic_score" not in serialised
    assert "correct_reject" not in serialised


def test_proposal_contract_is_strict_and_action_specific():
    with pytest.raises(ValidationError, match="MOVE requires"):
        ActionStepV2(action="MOVE", object_id="blue_component")

    with pytest.raises(ValidationError, match="Extra inputs"):
        StructuredTaskProposalV2.model_validate(
            {
                "actions": [
                    {
                        "action": "STOP",
                        "unsafe_extra_field": "ignored by weak parsers",
                    }
                ]
            }
        )

    with pytest.raises(ValidationError, match="STOP must be the final action"):
        StructuredTaskProposalV2.model_validate(
            {
                "actions": [
                    {"action": "STOP"},
                    {"action": "WAIT", "duration_ms": 100},
                ]
            }
        )


def test_runner_does_not_write_repository_evidence(runner, tmp_path):
    before = {
        path.relative_to(ROOT): path.read_bytes()
        for root_name in ("results", "docs")
        for path in (ROOT / root_name).rglob("*")
        if path.is_file()
    }

    run_local(runner, FakeBackend(valid_move()))

    after = {
        path.relative_to(ROOT): path.read_bytes()
        for root_name in ("results", "docs")
        for path in (ROOT / root_name).rglob("*")
        if path.is_file()
    }
    assert after == before
    assert list(tmp_path.iterdir()) == []
