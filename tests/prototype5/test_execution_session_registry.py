from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from itertools import count
from pathlib import Path

import pytest

from src.prototype5.canonical_governance_runner import (
    CanonicalGovernanceRequestV2,
    CanonicalGovernanceRunner,
    CanonicalRunnerConfigurationV2,
    InternalGovernanceExecutionContextV1,
)
from src.prototype5.demo_service import (
    DemoApplicationService,
    TypedCommandApiRequest,
)
from src.prototype5.execution_permit import (
    PermitVerificationResult,
    verify_execution_permit,
)
from src.prototype5.execution_session import (
    DuplicateExecutionTraceError,
    ExecutionClaimReason,
    ExecutionRegistryAtCapacityError,
    ExecutionSessionRegistry,
    PermitState,
)
from src.prototype5.foundry_sdk_backend import ModelBackendResponse
from src.prototype5.governance_contract_v2 import (
    FinalDecision,
    InferenceMode,
    ProviderId,
    SimulationStatus,
)
from src.prototype5.hybrid_inference_router import (
    HybridInferenceRouter,
    InferenceProviderBinding,
    ProviderAvailabilityV2,
    load_hybrid_routing_policy,
)
from src.prototype5.manufacturing_policy_v2 import (
    ManufacturingSceneStateV2,
    RequesterContextV2,
    SceneObjectStateV2,
    load_manufacturing_policy,
)


ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "configs" / "prototype5" / "manufacturing_policy_v2.json"
ROUTING_POLICY_PATH = (
    ROOT / "configs" / "prototype5" / "hybrid_routing_policy_v1.json"
)
SOFTWARE_COMMIT = "a" * 40
FIXED_TIME = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
MOVE_COMMAND = (
    "Move the blue component from input tray A to assembly fixture B."
)


class FakeBackend:
    def __init__(
        self,
        raw_text: str | None,
        *,
        success: bool = True,
        model_alias: str = "local-test-model",
    ) -> None:
        self.raw_text = raw_text
        self.success = success
        self.model_alias = model_alias
        self.calls = 0

    def generate(
        self, command: str, context: dict[str, object] | None = None
    ) -> ModelBackendResponse:
        self.calls += 1
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


def scene() -> ManufacturingSceneStateV2:
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
    )


def move_json(
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


_IDS = count(1)


def build_runner() -> CanonicalGovernanceRunner:
    return CanonicalGovernanceRunner(
        policy=load_manufacturing_policy(POLICY_PATH),
        configuration=CanonicalRunnerConfigurationV2(
            source_repository="Adhish-Rao2405/Microsoft-IXN-Prototype5",
            software_commit=SOFTWARE_COMMIT,
            prompt_id="manufacturing-demo-prompt",
            prompt_version="2.0.0",
        ),
        clock=lambda: FIXED_TIME,
        id_factory=lambda: f"id-{next(_IDS)}",
    )


def build_request(
    *,
    command: str = MOVE_COMMAND,
    mode: str = "LOCAL",
) -> CanonicalGovernanceRequestV2:
    return CanonicalGovernanceRequestV2(
        input_mode="TYPED",
        typed_text=command,
        domain_id="MANUFACTURING",
        scene=scene(),
        requester=RequesterContextV2(
            requester_id="synthetic_operator_ui", role="operator"
        ),
        requested_inference_mode=mode,
        evaluation_mode="LIVE",
    )


def context_for(
    raw_text: str | None,
    *,
    command: str = MOVE_COMMAND,
    success: bool = True,
) -> InternalGovernanceExecutionContextV1:
    runner = build_runner()
    backend = FakeBackend(raw_text, success=success)
    request = build_request(command=command)
    return runner.evaluate_response_with_execution_context(
        request,
        response=backend.generate(command),
        routing=_local_route(success=success),
    )


def _local_route(*, success: bool = True):
    from src.prototype5.governance_contract_v2 import RoutingRecordV2

    return RoutingRecordV2(
        requested_mode=InferenceMode.LOCAL,
        selected_provider=ProviderId.FOUNDRY_LOCAL,
        selected_model="local-test-model",
        local_attempted=True,
        cloud_attempted=False,
        local_latency_ms=12.5,
    )


def build_registry(
    *,
    clock: object | None = None,
    ttl_seconds: int = 600,
    capacity: int = 20,
    permit_ttl_seconds: int = 60,
) -> ExecutionSessionRegistry:
    counter = count(1)
    return ExecutionSessionRegistry(
        secret=b"\x00" * 32,
        ttl_seconds=ttl_seconds,
        capacity=capacity,
        permit_ttl_seconds=permit_ttl_seconds,
        utc_clock=clock or (lambda: FIXED_TIME),
        id_factory=lambda: f"gen-{next(counter)}",
    )


# --------------------------------------------------------------------------
# governance provenance capture
# --------------------------------------------------------------------------


def test_eligible_context_carries_governance_time_interpretation():
    context = context_for(move_json())
    assert context.result.governance_record.execution_eligible is True
    assert context.policy_evaluation is not None
    interpretation = context.policy_evaluation.interpretation
    assert interpretation.object_id == "blue_component"
    assert interpretation.source_id == "input_tray_a"
    assert interpretation.destination_id == "assembly_fixture_b"
    assert context.policy_id == "prototype5_manufacturing_policy_v2"
    assert context.policy_version == "2.0.0"
    assert len(context.policy_sha256) == 64


def test_structural_failure_context_has_no_policy_evaluation():
    context = context_for("this is not json")
    assert context.policy_evaluation is None
    assert context.result.governance_record.execution_eligible is False


def test_registry_retains_non_executable_traces():
    registry = build_registry()
    context = context_for("this is not json")
    state = registry.register(context)
    assert state.execution_eligible is False
    trace_id = context.result.governance_record.trace_id
    assert registry.get_state(trace_id) is not None
    claim = registry.issue_and_claim(trace_id)
    assert claim.claimed is False
    assert claim.reason_code is (
        ExecutionClaimReason.GOVERNANCE_RECORD_NOT_EXECUTION_ELIGIBLE
    )


def test_unknown_trace_is_distinguished_from_ineligible_trace():
    registry = build_registry()
    claim = registry.issue_and_claim("never-registered")
    assert claim.reason_code is ExecutionClaimReason.TRACE_NOT_FOUND_OR_EXPIRED


@pytest.mark.parametrize(
    "command,raw_text",
    [
        ("Do something with the thing over there.", move_json()),
        (MOVE_COMMAND, move_json(destination_id="restricted_zone")),
        (MOVE_COMMAND, move_json(object_id="red_component")),
    ],
)
def test_non_accepted_decisions_cannot_issue_a_permit(command, raw_text):
    registry = build_registry()
    context = context_for(raw_text, command=command)
    assert context.result.governance_record.final_decision is not (
        FinalDecision.ACCEPT
    )
    registry.register(context)
    claim = registry.issue_and_claim(
        context.result.governance_record.trace_id
    )
    assert claim.claimed is False
    assert claim.permit is None


def test_provider_error_trace_is_registered_but_cannot_issue():
    registry = build_registry()
    context = context_for(None, success=False)
    registry.register(context)
    trace_id = context.result.governance_record.trace_id
    assert registry.get_state(trace_id) is not None
    assert registry.issue_and_claim(trace_id).claimed is False


# --------------------------------------------------------------------------
# router context identity across LOCAL / CLOUD / AUTO
# --------------------------------------------------------------------------


def build_service(
    *,
    local_text: str | None = None,
    cloud_text: str | None = None,
    local_available: bool = True,
    local_success: bool = True,
) -> tuple[DemoApplicationService, FakeBackend, FakeBackend]:
    local = FakeBackend(local_text, success=local_success)
    cloud = FakeBackend(cloud_text, model_alias="cloud-test-model")
    router = HybridInferenceRouter(
        local=InferenceProviderBinding(
            provider_id=ProviderId.FOUNDRY_LOCAL,
            model_id="local-test-model",
            backend=local,
            availability_probe=lambda: ProviderAvailabilityV2(
                available=local_available,
                model_ready=local_available,
                detail_code="READY" if local_available else "UNAVAILABLE",
            ),
        ),
        cloud=InferenceProviderBinding(
            provider_id=ProviderId.CLOUD,
            model_id="cloud-test-model",
            backend=cloud,
        ),
        governance_runner=build_runner(),
        routing_policy=load_hybrid_routing_policy(ROUTING_POLICY_PATH),
        utc_clock=lambda: FIXED_TIME,
    )
    service = DemoApplicationService(
        router=router,
        software_commit=SOFTWARE_COMMIT,
        cloud_configured=True,
        utc_clock=lambda: FIXED_TIME,
        execution_registry=build_registry(),
    )
    return service, local, cloud


@pytest.mark.parametrize("mode", ["LOCAL", "CLOUD", "AUTO"])
def test_public_result_and_registered_context_describe_the_same_trace(mode):
    service, _, _ = build_service(
        local_text=move_json(), cloud_text=move_json()
    )
    result = service.submit_typed(
        TypedCommandApiRequest(command=MOVE_COMMAND, inference_mode=mode)
    )
    trace_id = result.canonical_result.governance_record.trace_id
    state = service.execution_state(trace_id)
    assert state is not None
    assert state.trace_id == trace_id
    assert state.governance_record_id == (
        result.canonical_result.governance_record.record_id
    )


def test_auto_fallback_registers_the_cloud_result_not_the_local_attempt():
    service, local, cloud = build_service(
        local_text="not json at all",
        cloud_text=move_json(),
    )
    result = service.submit_typed(
        TypedCommandApiRequest(command=MOVE_COMMAND, inference_mode="AUTO")
    )
    record = result.canonical_result.governance_record
    assert local.calls == 1 and cloud.calls == 1
    assert record.routing.fallback_triggered is True
    assert record.routing.selected_provider is ProviderId.CLOUD
    assert record.execution_eligible is True

    state = service.execution_state(record.trace_id)
    assert state is not None
    assert state.execution_eligible is True

    claim = service.execution_registry.issue_and_claim(record.trace_id)
    assert claim.claimed is True
    assert claim.permit is not None
    assert claim.permit.governance_record_id == record.record_id


def test_voice_submission_registers_its_execution_context():
    from src.prototype5.demo_service import VoiceCommandApiRequest
    from src.prototype5.recorded_speech import (
        NEMOTRON_SPEECH_MODEL_ID,
        RecordedAudioMetadataV1,
        RecordedTranscriptionResultV1,
    )

    class Transcriber:
        is_worker_configured = True

        def transcribe_wav(self, audio_bytes, *, original_filename):
            return RecordedTranscriptionResultV1(
                transcription_id="transcript-1",
                timestamp_utc=FIXED_TIME.isoformat(),
                transcript_text=MOVE_COMMAND,
                transcript_status="READY",
                transcript_confidence=0.95,
                transcription_latency_ms=10.0,
                audio=RecordedAudioMetadataV1(
                    original_filename=original_filename,
                    audio_sha256="d" * 64,
                    audio_bytes=len(audio_bytes),
                    sample_rate_hz=16000,
                    channels=1,
                    bits_per_sample=16,
                    frame_count=16000,
                    duration_ms=1000.0,
                ),
                resolved_model_id=NEMOTRON_SPEECH_MODEL_ID,
                sdk_version="1.2.3",
                core_version="1.2.3",
                model_cached_before=True,
                model_loaded_before=True,
            )

    service, _, _ = build_service(local_text=move_json())
    service.speech_transcriber = Transcriber()
    service.transcribe_recorded(b"\x00" * 32, original_filename="clip.wav")
    result = service.submit_voice(
        VoiceCommandApiRequest(
            transcription_id="transcript-1",
            reviewed_transcript_text=MOVE_COMMAND,
            inference_mode="LOCAL",
        )
    )
    record = result.canonical_result.governance_record
    state = service.execution_state(record.trace_id)
    assert state is not None
    assert state.execution_eligible is True


def test_public_response_does_not_expose_internal_execution_context():
    service, _, _ = build_service(local_text=move_json())
    result = service.submit_typed(
        TypedCommandApiRequest(command=MOVE_COMMAND, inference_mode="LOCAL")
    )
    payload = json.loads(result.model_dump_json())
    assert set(payload) == {
        "routing_policy_id",
        "routing_policy_version",
        "routing_policy_sha256",
        "local_health",
        "canonical_result",
    }
    assert set(payload["canonical_result"]) == {
        "request",
        "raw_response_text",
        "proposal",
        "governance_record",
    }
    rendered = result.model_dump_json()
    for leaked in (
        "policy_evaluation",
        "interpretation",
        "semantic_reason_codes",
        "authority_reason_codes",
        "signature",
        "plan_hash",
        "permit_state",
        "execution_id",
    ):
        assert leaked not in rendered


def test_governance_record_keeps_historical_simulation_fields():
    service, _, _ = build_service(local_text=move_json())
    result = service.submit_typed(
        TypedCommandApiRequest(command=MOVE_COMMAND, inference_mode="LOCAL")
    )
    record = result.canonical_result.governance_record
    assert record.execution_permit_id is None
    assert record.simulation_status is SimulationStatus.NOT_REQUESTED

    claim = service.execution_registry.issue_and_claim(record.trace_id)
    assert claim.claimed is True
    unchanged = result.canonical_result.governance_record
    assert unchanged.execution_permit_id is None
    assert unchanged.simulation_status is SimulationStatus.NOT_REQUESTED


# --------------------------------------------------------------------------
# registry lifecycle
# --------------------------------------------------------------------------


def test_eligible_trace_issues_and_claims_one_verifiable_permit():
    registry = build_registry()
    context = context_for(move_json())
    registry.register(context)
    record = context.result.governance_record

    claim = registry.issue_and_claim(record.trace_id)
    assert claim.claimed is True
    assert claim.execution_id is not None
    assert claim.proposal is context.result.proposal
    permit = claim.permit
    assert permit is not None
    assert permit.trace_id == record.trace_id
    assert permit.object_id == "blue_component"
    assert permit.source_id == "input_tray_a"
    assert permit.destination_id == "assembly_fixture_b"
    assert (
        verify_execution_permit(
            permit,
            secret=registry.verification_secret(),
            now=FIXED_TIME,
            proposal=claim.proposal,
            expected_scene_id="manufacturing_demo_scene",
            expected_scene_state_version="1.0.0",
            expected_policy_id=context.policy_id,
            expected_policy_version=context.policy_version,
            expected_policy_sha256=context.policy_sha256,
        )
        is PermitVerificationResult.VALID
    )

    state = registry.get_state(record.trace_id)
    assert state is not None
    assert state.permit_state is PermitState.CONSUMED
    assert state.simulation_status is SimulationStatus.QUEUED
    assert state.permit_id == permit.permit_id
    assert state.execution_id == claim.execution_id


def test_a_trace_yields_at_most_one_permit():
    registry = build_registry()
    context = context_for(move_json())
    registry.register(context)
    trace_id = context.result.governance_record.trace_id

    first = registry.issue_and_claim(trace_id)
    assert first.claimed is True
    for _ in range(3):
        repeat = registry.issue_and_claim(trace_id)
        assert repeat.claimed is False
        assert repeat.permit is None
        assert repeat.reason_code is (
            ExecutionClaimReason.EXECUTION_AUTHORITY_ALREADY_CLAIMED
        )

    state = registry.get_state(trace_id)
    assert state is not None
    assert state.permit_id == first.permit.permit_id
    assert state.execution_id == first.execution_id


def test_state_view_never_exposes_the_permit_signature():
    registry = build_registry()
    context = context_for(move_json())
    registry.register(context)
    trace_id = context.result.governance_record.trace_id
    claim = registry.issue_and_claim(trace_id)
    state = registry.get_state(trace_id)
    assert state is not None
    rendered = state.model_dump_json()
    assert claim.permit is not None
    assert claim.permit.signature not in rendered
    assert registry.verification_secret().hex() not in rendered


def test_concurrent_claims_produce_exactly_one_permit():
    registry = build_registry()
    context = context_for(move_json())
    registry.register(context)
    trace_id = context.result.governance_record.trace_id

    barrier = threading.Barrier(4)

    def attempt():
        barrier.wait()
        return registry.issue_and_claim(trace_id)

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = [future.result() for future in [
            executor.submit(attempt) for _ in range(4)
        ]]

    claimed = [result for result in results if result.claimed]
    refused = [result for result in results if not result.claimed]
    assert len(claimed) == 1
    assert len(refused) == 3
    assert {result.reason_code for result in refused} == {
        ExecutionClaimReason.EXECUTION_AUTHORITY_ALREADY_CLAIMED
    }
    assert len({result.execution_id for result in claimed}) == 1
    assert len({result.permit.permit_id for result in claimed}) == 1


def test_consumed_authority_survives_the_permit_becoming_expired():
    """Lifecycle and temporal validity are separate axes.

    The permit may later verify as EXPIRED while the session still records
    that this trace irreversibly spent its one execution authority.
    """

    registry = build_registry(permit_ttl_seconds=60)
    context = context_for(move_json())
    registry.register(context)
    trace_id = context.result.governance_record.trace_id

    claim = registry.issue_and_claim(trace_id)
    assert claim.claimed is True
    permit = claim.permit
    assert permit is not None
    secret = registry.verification_secret()

    def check(now):
        return verify_execution_permit(
            permit,
            secret=secret,
            now=now,
            proposal=claim.proposal,
            expected_scene_id=context.result.request.scene.scene_id,
            expected_scene_state_version=(
                context.result.request.scene.state_version
            ),
            expected_policy_id=context.policy_id,
            expected_policy_version=context.policy_version,
            expected_policy_sha256=context.policy_sha256,
        )

    assert check(FIXED_TIME) is PermitVerificationResult.VALID
    assert check(FIXED_TIME + timedelta(seconds=60)) is (
        PermitVerificationResult.EXPIRED
    )

    state = registry.get_state(trace_id)
    assert state is not None
    assert state.permit_state is PermitState.CONSUMED
    assert registry.issue_and_claim(trace_id).claimed is False


def test_permit_state_has_no_expired_member():
    assert {member.value for member in PermitState} == {
        "NOT_ISSUED",
        "CONSUMED",
    }


# --------------------------------------------------------------------------
# registry invariants: duplicate traces and capacity safety
# --------------------------------------------------------------------------


def test_duplicate_trace_registration_is_refused():
    registry = build_registry()
    context = context_for(move_json())
    registry.register(context)
    trace_id = context.result.governance_record.trace_id

    with pytest.raises(DuplicateExecutionTraceError):
        registry.register(context)

    state = registry.get_state(trace_id)
    assert state is not None
    assert state.permit_state is PermitState.NOT_ISSUED


def test_duplicate_registration_cannot_reset_a_claimed_session():
    registry = build_registry()
    context = context_for(move_json())
    registry.register(context)
    trace_id = context.result.governance_record.trace_id
    claim = registry.issue_and_claim(trace_id)
    assert claim.claimed is True

    with pytest.raises(DuplicateExecutionTraceError):
        registry.register(context)

    state = registry.get_state(trace_id)
    assert state is not None
    assert state.permit_state is PermitState.CONSUMED
    assert state.permit_id == claim.permit.permit_id
    assert state.execution_id == claim.execution_id
    assert registry.issue_and_claim(trace_id).claimed is False


def test_capacity_pressure_never_evicts_a_claimed_session():
    registry = build_registry(capacity=2)
    active = context_for(move_json())
    registry.register(active)
    active_trace = active.result.governance_record.trace_id
    assert registry.issue_and_claim(active_trace).claimed is True

    later = []
    for _ in range(3):
        context = context_for("this is not json")
        registry.register(context)
        later.append(context.result.governance_record.trace_id)

    state = registry.get_state(active_trace)
    assert state is not None
    assert state.simulation_status is SimulationStatus.QUEUED
    assert registry.get_state(later[-1]) is not None
    assert registry.get_state(later[0]) is None


def test_registration_is_refused_when_only_active_sessions_remain():
    registry = build_registry(capacity=1)
    active = context_for(move_json())
    registry.register(active)
    active_trace = active.result.governance_record.trace_id
    assert registry.issue_and_claim(active_trace).claimed is True

    with pytest.raises(ExecutionRegistryAtCapacityError):
        registry.register(context_for(move_json()))

    state = registry.get_state(active_trace)
    assert state is not None
    assert state.permit_state is PermitState.CONSUMED


def test_capacity_eviction_is_registration_order_not_read_order():
    registry = build_registry(capacity=2)
    contexts = [context_for("this is not json") for _ in range(2)]
    for context in contexts:
        registry.register(context)
    first, second = (
        context.result.governance_record.trace_id for context in contexts
    )

    # Reading the oldest entry must not protect it from FIFO eviction.
    assert registry.get_state(first) is not None

    third = context_for("this is not json")
    registry.register(third)
    assert registry.get_state(first) is None
    assert registry.get_state(second) is not None


def test_active_session_survives_its_registration_ttl():
    """An execution can outlive the TTL of the trace that authorised it.

    Deleting it would orphan the execution and break the governance-to-audit
    chain, so TTL reclamation must skip QUEUED and RUNNING sessions.
    """

    now = [FIXED_TIME]
    registry = build_registry(clock=lambda: now[0], ttl_seconds=60, capacity=5)
    context = context_for(move_json())
    registry.register(context)
    trace_id = context.result.governance_record.trace_id

    claim = registry.issue_and_claim(trace_id)
    assert claim.claimed is True

    now[0] = FIXED_TIME + timedelta(seconds=601)

    # get_state() runs TTL reclamation
    state = registry.get_state(trace_id)
    assert state is not None
    assert state.simulation_status is SimulationStatus.QUEUED
    assert state.permit_id == claim.permit.permit_id
    assert state.execution_id == claim.execution_id

    # register() runs TTL reclamation
    registry.register(context_for("this is not json"))
    assert registry.get_state(trace_id) is not None

    # issue_and_claim() runs TTL reclamation
    repeat = registry.issue_and_claim(trace_id)
    assert repeat.reason_code is (
        ExecutionClaimReason.EXECUTION_AUTHORITY_ALREADY_CLAIMED
    )
    survivor = registry.get_state(trace_id)
    assert survivor is not None
    assert survivor.execution_id == claim.execution_id


def test_ttl_still_reclaims_inactive_sessions_around_an_active_one():
    now = [FIXED_TIME]
    registry = build_registry(clock=lambda: now[0], ttl_seconds=60, capacity=5)

    active = context_for(move_json())
    registry.register(active)
    active_trace = active.result.governance_record.trace_id
    assert registry.issue_and_claim(active_trace).claimed is True

    inactive = context_for("this is not json")
    registry.register(inactive)
    inactive_trace = inactive.result.governance_record.trace_id

    now[0] = FIXED_TIME + timedelta(seconds=61)
    assert registry.get_state(inactive_trace) is None
    assert registry.get_state(active_trace) is not None


def test_terminal_retention_is_a_slice_two_contract():
    """Placeholder guard: terminal retention must not reuse registration age.

    Slice 2 must recompute the retention deadline from the terminal time when
    a session leaves an active state. Until the controller exists, only the
    active-state exemption is implemented here.
    """

    from src.prototype5.execution_session import ACTIVE_SIMULATION_STATUSES

    assert ACTIVE_SIMULATION_STATUSES == frozenset(
        {SimulationStatus.QUEUED, SimulationStatus.RUNNING}
    )
    assert SimulationStatus.COMPLETED not in ACTIVE_SIMULATION_STATUSES
    assert SimulationStatus.FAILED not in ACTIVE_SIMULATION_STATUSES
    assert SimulationStatus.STOPPED_BY_OPERATOR not in ACTIVE_SIMULATION_STATUSES


def test_sessions_expire_after_their_ttl():
    now = [FIXED_TIME]
    registry = build_registry(clock=lambda: now[0], ttl_seconds=60)
    context = context_for(move_json())
    registry.register(context)
    trace_id = context.result.governance_record.trace_id
    assert registry.get_state(trace_id) is not None

    now[0] = FIXED_TIME + timedelta(seconds=61)
    assert registry.get_state(trace_id) is None
    assert registry.issue_and_claim(trace_id).reason_code is (
        ExecutionClaimReason.TRACE_NOT_FOUND_OR_EXPIRED
    )


def test_registry_evicts_in_registration_order_over_capacity():
    registry = build_registry(capacity=2)
    trace_ids = []
    for _ in range(3):
        context = context_for(move_json())
        registry.register(context)
        trace_ids.append(context.result.governance_record.trace_id)

    assert registry.get_state(trace_ids[0]) is None
    assert registry.get_state(trace_ids[1]) is not None
    assert registry.get_state(trace_ids[2]) is not None


@pytest.mark.parametrize(
    "ttl_seconds,capacity,permit_ttl_seconds",
    [(0, 20, 60), (601 * 6, 20, 60), (600, 0, 60), (600, 20, 0)],
)
def test_registry_rejects_out_of_range_configuration(
    ttl_seconds, capacity, permit_ttl_seconds
):
    with pytest.raises(ValueError):
        ExecutionSessionRegistry(
            ttl_seconds=ttl_seconds,
            capacity=capacity,
            permit_ttl_seconds=permit_ttl_seconds,
        )


def test_registry_generates_its_own_secret_when_none_is_supplied():
    first = ExecutionSessionRegistry()
    second = ExecutionSessionRegistry()
    assert len(first.verification_secret()) >= 32
    assert first.verification_secret() != second.verification_secret()


# --------------------------------------------------------------------------
# signing-key configuration fails fast
# --------------------------------------------------------------------------


def test_short_signing_key_fails_at_construction():
    with pytest.raises(ValueError):
        ExecutionSessionRegistry(secret=bytes(31))


@pytest.mark.parametrize("secret", ["not-bytes", 12345, memoryview(bytes(32))])
def test_invalid_signing_key_type_fails_at_construction(secret):
    with pytest.raises(TypeError):
        ExecutionSessionRegistry(secret=secret)


def test_exact_minimum_signing_key_is_accepted():
    registry = ExecutionSessionRegistry(secret=bytes(32))
    assert registry.verification_secret() == bytes(32)


def test_mutable_signing_key_is_defensively_copied():
    supplied = bytearray(bytes(32))
    registry = ExecutionSessionRegistry(secret=supplied)
    assert isinstance(registry.verification_secret(), bytes)
    assert not isinstance(registry.verification_secret(), bytearray)

    supplied[0] = 0xFF
    assert registry.verification_secret()[0] == 0x00
    assert registry.verification_secret() == bytes(32)


def test_signing_key_failure_is_not_deferred_to_claim_time():
    """A bad key must not let the app start and fail only at motion time."""

    with pytest.raises((ValueError, TypeError)):
        ExecutionSessionRegistry(secret=b"too-short")
