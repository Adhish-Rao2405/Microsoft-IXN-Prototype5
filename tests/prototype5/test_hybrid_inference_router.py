from __future__ import annotations

import json
from datetime import datetime, timezone
from itertools import count
from pathlib import Path

import pytest

from src.prototype5.canonical_governance_runner import (
    CanonicalGovernanceRequestV2,
    CanonicalGovernanceRunner,
    CanonicalRunnerConfigurationV2,
)
from src.prototype5.foundry_sdk_backend import ModelBackendResponse
from src.prototype5.governance_contract_v2 import (
    FallbackReason,
    FinalDecision,
    GateStatus,
    InferenceMode,
    ProviderId,
)
from src.prototype5.hybrid_inference_router import (
    CircuitState,
    HybridInferenceRouter,
    HybridRoutingPolicyV1,
    InferenceProviderBinding,
    LoadedHybridRoutingPolicyV1,
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
ROUTING_PATH = (
    ROOT / "configs" / "prototype5" / "hybrid_routing_policy_v1.json"
)
FIXED_TIME = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)


class SequenceBackend:
    def __init__(self, responses: list[ModelBackendResponse | Exception]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, dict[str, object] | None]] = []

    def generate(
        self, command: str, context: dict[str, object] | None = None
    ) -> ModelBackendResponse:
        self.calls.append((command, context))
        if not self.responses:
            raise AssertionError("unexpected provider call")
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class MutableAvailability:
    def __init__(self, *, available: bool = True, model_ready: bool = True):
        self.available = available
        self.model_ready = model_ready
        self.calls = 0

    def __call__(self) -> ProviderAvailabilityV2:
        self.calls += 1
        return ProviderAvailabilityV2(
            available=self.available,
            model_ready=self.model_ready,
            detail_code="READY" if self.available and self.model_ready else "NOT_READY",
        )


class FakeTimer:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def response(
    raw_text: str | None,
    *,
    provider: ProviderId,
    success: bool = True,
    latency_ms: float = 10.0,
    error_type: str | None = None,
) -> ModelBackendResponse:
    return ModelBackendResponse(
        backend=provider.value,
        model_alias=(
            "local-test-model"
            if provider is ProviderId.FOUNDRY_LOCAL
            else "cloud-test-model"
        ),
        prompt_id="manufacturing-demo-prompt",
        raw_text=raw_text,
        success=success,
        latency_ms=latency_ms,
        error_type=error_type,
        error_message=error_type,
        timestamp_utc=FIXED_TIME.isoformat(),
    )


def valid_move(
    *,
    object_id: str = "blue_component",
    destination_id: str = "assembly_fixture_b",
) -> str:
    return json.dumps(
        {
            "actions": [
                {
                    "action": "MOVE",
                    "object_id": object_id,
                    "source_id": "input_tray_a",
                    "destination_id": destination_id,
                }
            ]
        }
    )


def request(mode: InferenceMode | str, **overrides: object):
    payload: dict[str, object] = {
        "input_mode": "TYPED",
        "typed_text": (
            "Move the blue component from input tray A "
            "to assembly fixture B."
        ),
        "scene": ManufacturingSceneStateV2(
            scene_id="manufacturing_demo_scene",
            state_version="1.0.0",
            objects=(
                SceneObjectStateV2(
                    object_id="blue_component", location_id="input_tray_a"
                ),
            ),
        ),
        "requester": RequesterContextV2(
            requester_id="synthetic_operator_01", role="operator"
        ),
        "requested_inference_mode": mode,
    }
    payload.update(overrides)
    return CanonicalGovernanceRequestV2.model_validate(payload)


def routing_policy(**overrides: object) -> LoadedHybridRoutingPolicyV1:
    payload = {
        "routing_policy_id": "test_hybrid_policy",
        "routing_policy_version": "1.0.0-test",
        "local_timeout_ms": 1000,
        "local_max_consecutive_failures": 2,
        "local_circuit_open_seconds": 30,
        "rolling_window_size": 4,
        "minimum_structured_success_rate": 0.7,
        "maximum_local_p95_latency_ms": 900,
        "maximum_provider_attempts": 1,
    }
    payload.update(overrides)
    return LoadedHybridRoutingPolicyV1(
        config=HybridRoutingPolicyV1.model_validate(payload),
        sha256="d" * 64,
    )


def build_router(
    local_responses: list[ModelBackendResponse | Exception],
    cloud_responses: list[ModelBackendResponse | Exception],
    *,
    availability: MutableAvailability | None = None,
    policy: LoadedHybridRoutingPolicyV1 | None = None,
    timer: FakeTimer | None = None,
):
    sequence = count(1)
    runner = CanonicalGovernanceRunner(
        policy=load_manufacturing_policy(POLICY_PATH),
        configuration=CanonicalRunnerConfigurationV2(
            source_repository="Adhish-Rao2405/Microsoft-IXN-Prototype5",
            software_commit="a" * 40,
            prompt_id="manufacturing-demo-prompt",
            prompt_version="2.0.0",
        ),
        clock=lambda: FIXED_TIME,
        id_factory=lambda: f"id-{next(sequence)}",
    )
    local_backend = SequenceBackend(local_responses)
    cloud_backend = SequenceBackend(cloud_responses)
    local_availability = availability or MutableAvailability()
    fake_timer = timer or FakeTimer()
    router = HybridInferenceRouter(
        local=InferenceProviderBinding(
            provider_id=ProviderId.FOUNDRY_LOCAL,
            model_id="local-test-model",
            backend=local_backend,
            availability_probe=local_availability,
        ),
        cloud=InferenceProviderBinding(
            provider_id=ProviderId.CLOUD,
            model_id="cloud-test-model",
            backend=cloud_backend,
        ),
        governance_runner=runner,
        routing_policy=policy or routing_policy(),
        timer=fake_timer,
        utc_clock=lambda: FIXED_TIME,
    )
    return router, local_backend, cloud_backend, local_availability, fake_timer


def test_local_mode_uses_only_local_and_applies_governance():
    router, local, cloud, _, _ = build_router(
        [response(valid_move(), provider=ProviderId.FOUNDRY_LOCAL)],
        [],
    )

    result = router.route(request("LOCAL"))
    record = result.canonical_result.governance_record

    assert len(local.calls) == 1
    assert cloud.calls == []
    assert record.routing.selected_provider is ProviderId.FOUNDRY_LOCAL
    assert record.final_decision is FinalDecision.ACCEPT
    assert record.routing.fallback_triggered is False


def test_cloud_mode_uses_only_cloud_without_local_probe():
    router, local, cloud, availability, _ = build_router(
        [],
        [response(valid_move(), provider=ProviderId.CLOUD)],
    )

    result = router.route(request("CLOUD"))
    record = result.canonical_result.governance_record

    assert local.calls == []
    assert availability.calls == 0
    assert len(cloud.calls) == 1
    assert record.routing.selected_provider is ProviderId.CLOUD
    assert record.final_decision is FinalDecision.ACCEPT


def test_auto_prefers_structurally_valid_local_response():
    router, local, cloud, _, _ = build_router(
        [response(valid_move(), provider=ProviderId.FOUNDRY_LOCAL)],
        [],
    )

    record = router.route(request("AUTO")).canonical_result.governance_record

    assert len(local.calls) == 1
    assert cloud.calls == []
    assert record.routing.selected_provider is ProviderId.FOUNDRY_LOCAL
    assert record.routing.fallback_triggered is False


@pytest.mark.parametrize(
    ("raw_text", "expected_reason"),
    [
        ("not-json", FallbackReason.LOCAL_PARSE_FAILURE),
        ("[]", FallbackReason.LOCAL_JSON_FAILURE),
        (json.dumps({"actions": []}), FallbackReason.LOCAL_SCHEMA_FAILURE),
        ("", FallbackReason.LOCAL_EMPTY_RESPONSE),
    ],
)
def test_auto_falls_back_only_for_structural_generation_failure(
    raw_text, expected_reason
):
    router, local, cloud, _, _ = build_router(
        [response(raw_text, provider=ProviderId.FOUNDRY_LOCAL)],
        [response(valid_move(), provider=ProviderId.CLOUD)],
    )

    record = router.route(request("AUTO")).canonical_result.governance_record

    assert len(local.calls) == 1
    assert len(cloud.calls) == 1
    assert record.routing.fallback_triggered is True
    assert record.routing.fallback_reason is expected_reason
    assert record.routing.selected_provider is ProviderId.CLOUD
    assert record.final_decision is FinalDecision.ACCEPT


@pytest.mark.parametrize(
    ("error_type", "expected_reason"),
    [
        ("timeout", FallbackReason.LOCAL_TIMEOUT),
        ("endpoint_unavailable", FallbackReason.LOCAL_UNAVAILABLE),
        ("bad_model_alias", FallbackReason.LOCAL_MODEL_NOT_READY),
        ("unknown_error", FallbackReason.LOCAL_TRANSPORT_ERROR),
        ("empty_model_response", FallbackReason.LOCAL_EMPTY_RESPONSE),
    ],
)
def test_auto_classifies_local_operational_failures(error_type, expected_reason):
    router, _, cloud, _, _ = build_router(
        [
            response(
                None,
                provider=ProviderId.FOUNDRY_LOCAL,
                success=False,
                error_type=error_type,
            )
        ],
        [response(valid_move(), provider=ProviderId.CLOUD)],
    )

    record = router.route(request("AUTO")).canonical_result.governance_record

    assert len(cloud.calls) == 1
    assert record.routing.fallback_reason is expected_reason


def test_auto_falls_back_when_local_provider_raises():
    router, _, cloud, _, _ = build_router(
        [RuntimeError("connection failed")],
        [response(valid_move(), provider=ProviderId.CLOUD)],
    )

    record = router.route(request("AUTO")).canonical_result.governance_record

    assert len(cloud.calls) == 1
    assert (
        record.routing.fallback_reason
        is FallbackReason.LOCAL_TRANSPORT_ERROR
    )


def test_auto_falls_back_when_measured_local_latency_exceeds_timeout():
    router, _, cloud, _, _ = build_router(
        [
            response(
                valid_move(),
                provider=ProviderId.FOUNDRY_LOCAL,
                latency_ms=1100,
            )
        ],
        [response(valid_move(), provider=ProviderId.CLOUD)],
    )

    record = router.route(request("AUTO")).canonical_result.governance_record

    assert len(cloud.calls) == 1
    assert record.routing.fallback_reason is FallbackReason.LOCAL_TIMEOUT
    assert record.routing.local_latency_ms == 1100


@pytest.mark.parametrize(
    ("command", "local_raw", "requester_role", "expected_decision", "failed_gate"),
    [
        (
            "Continue movement despite the human obstruction.",
            valid_move(),
            "operator",
            FinalDecision.REJECT,
            "safety",
        ),
        (
            "Move the part over there.",
            valid_move(),
            "operator",
            FinalDecision.CLARIFY,
            "ambiguity",
        ),
        (
            (
                "Move the blue component from input tray A "
                "to assembly fixture B."
            ),
            valid_move(),
            "observer",
            FinalDecision.REJECT,
            "authority",
        ),
        (
            (
                "Move the blue component from input tray A "
                "to assembly fixture B."
            ),
            valid_move(object_id="red_component"),
            "operator",
            FinalDecision.REJECT,
            "semantics",
        ),
    ],
)
def test_governance_rejection_never_causes_cloud_provider_shopping(
    command,
    local_raw,
    requester_role,
    expected_decision,
    failed_gate,
):
    router, local, cloud, _, _ = build_router(
        [response(local_raw, provider=ProviderId.FOUNDRY_LOCAL)],
        [],
    )
    current = request(
        "AUTO",
        typed_text=command,
        requester=RequesterContextV2(
            requester_id=f"synthetic_{requester_role}_01",
            role=requester_role,
        ),
    )

    record = router.route(current).canonical_result.governance_record

    assert len(local.calls) == 1
    assert cloud.calls == []
    assert record.routing.fallback_triggered is False
    assert record.final_decision is expected_decision
    if failed_gate == "safety":
        assert record.safety_status is GateStatus.FAILED
    elif failed_gate == "ambiguity":
        assert record.ambiguity_status is GateStatus.FAILED
    elif failed_gate == "authority":
        assert record.authority_status is GateStatus.FAILED
    else:
        assert record.plan_semantic_status.value == "INVALID"


def test_cloud_fallback_still_uses_same_safety_gateway():
    router, _, cloud, _, _ = build_router(
        [response("not-json", provider=ProviderId.FOUNDRY_LOCAL)],
        [response(valid_move(), provider=ProviderId.CLOUD)],
    )
    current = request(
        "AUTO",
        typed_text="Continue movement despite the human obstruction.",
    )

    record = router.route(current).canonical_result.governance_record

    assert len(cloud.calls) == 1
    assert record.routing.selected_provider is ProviderId.CLOUD
    assert record.safety_status is GateStatus.FAILED
    assert record.final_decision is FinalDecision.REJECT
    assert record.execution_eligible is False


def test_local_unavailable_skips_local_in_auto_but_never_in_cloud_mode():
    availability = MutableAvailability(available=False, model_ready=False)
    router, local, cloud, _, _ = build_router(
        [],
        [response(valid_move(), provider=ProviderId.CLOUD)],
        availability=availability,
    )

    record = router.route(request("AUTO")).canonical_result.governance_record

    assert local.calls == []
    assert len(cloud.calls) == 1
    assert record.routing.local_attempted is False
    assert record.routing.fallback_reason is FallbackReason.LOCAL_UNAVAILABLE


def test_local_mode_reports_unavailable_without_silent_cloud_fallback():
    availability = MutableAvailability(available=False, model_ready=False)
    router, local, cloud, _, _ = build_router(
        [],
        [],
        availability=availability,
    )

    record = router.route(request("LOCAL")).canonical_result.governance_record

    assert local.calls == []
    assert cloud.calls == []
    assert record.routing.selected_provider is ProviderId.NONE
    assert record.routing.fallback_triggered is False
    assert record.final_decision is FinalDecision.ERROR
    assert record.decision_reason_codes == ("LOCAL_BACKEND_UNAVAILABLE",)


def test_local_mode_retains_structural_failure_without_cloud_fallback():
    router, local, cloud, _, _ = build_router(
        [
            response(
                json.dumps({"actions": []}),
                provider=ProviderId.FOUNDRY_LOCAL,
            )
        ],
        [],
    )

    record = router.route(request("LOCAL")).canonical_result.governance_record

    assert len(local.calls) == 1
    assert cloud.calls == []
    assert record.parse_status is GateStatus.PASSED
    assert record.json_status is GateStatus.PASSED
    assert record.schema_status is GateStatus.FAILED
    assert record.routing.fallback_triggered is False
    assert record.final_decision is FinalDecision.ERROR


def test_local_model_not_ready_is_distinct_from_service_unavailable():
    availability = MutableAvailability(available=True, model_ready=False)
    router, local, cloud, _, _ = build_router(
        [],
        [response(valid_move(), provider=ProviderId.CLOUD)],
        availability=availability,
    )

    record = router.route(request("AUTO")).canonical_result.governance_record

    assert local.calls == []
    assert len(cloud.calls) == 1
    assert (
        record.routing.fallback_reason
        is FallbackReason.LOCAL_MODEL_NOT_READY
    )


def test_cloud_failure_is_explicit_and_never_fabricates_success():
    router, _, cloud, _, _ = build_router(
        [],
        [
            response(
                None,
                provider=ProviderId.CLOUD,
                success=False,
                error_type="authentication_failed",
            )
        ],
    )

    record = router.route(request("CLOUD")).canonical_result.governance_record

    assert len(cloud.calls) == 1
    assert record.final_decision is FinalDecision.ERROR
    assert record.execution_eligible is False
    assert record.decision_reason_codes == ("CLOUD_AUTHENTICATION_FAILED",)


def test_consecutive_failures_open_circuit_and_next_auto_request_skips_local():
    router, local, cloud, _, _ = build_router(
        [
            response("not-json", provider=ProviderId.FOUNDRY_LOCAL),
            response("not-json", provider=ProviderId.FOUNDRY_LOCAL),
        ],
        [
            response(valid_move(), provider=ProviderId.CLOUD),
            response(valid_move(), provider=ProviderId.CLOUD),
            response(valid_move(), provider=ProviderId.CLOUD),
        ],
    )

    router.route(request("AUTO"))
    second = router.route(request("AUTO"))
    third = router.route(request("AUTO"))

    assert len(local.calls) == 2
    assert len(cloud.calls) == 3
    assert second.local_health.circuit_state is CircuitState.OPEN
    assert third.canonical_result.governance_record.routing.fallback_reason is (
        FallbackReason.LOCAL_CIRCUIT_OPEN
    )
    assert third.canonical_result.governance_record.routing.local_attempted is False


def test_circuit_half_open_probe_can_restore_local_service():
    timer = FakeTimer()
    router, local, cloud, _, timer = build_router(
        [
            response("not-json", provider=ProviderId.FOUNDRY_LOCAL),
            response("not-json", provider=ProviderId.FOUNDRY_LOCAL),
            response(valid_move(), provider=ProviderId.FOUNDRY_LOCAL),
        ],
        [
            response(valid_move(), provider=ProviderId.CLOUD),
            response(valid_move(), provider=ProviderId.CLOUD),
        ],
        timer=timer,
    )
    router.route(request("AUTO"))
    router.route(request("AUTO"))
    timer.advance(31)

    restored = router.route(request("AUTO"))

    assert len(local.calls) == 3
    assert len(cloud.calls) == 2
    assert restored.local_health.circuit_state is CircuitState.CLOSED
    assert restored.local_health.last_circuit_transition == "HALF_OPEN_TO_CLOSED"
    assert (
        restored.canonical_result.governance_record.routing.selected_provider
        is ProviderId.FOUNDRY_LOCAL
    )


def test_rolling_reliability_threshold_is_evaluated_before_new_local_attempt():
    policy = routing_policy(
        rolling_window_size=2,
        local_max_consecutive_failures=10,
        minimum_structured_success_rate=0.75,
    )
    router, local, cloud, _, _ = build_router(
        [
            response("not-json", provider=ProviderId.FOUNDRY_LOCAL),
            response(valid_move(), provider=ProviderId.FOUNDRY_LOCAL),
        ],
        [
            response(valid_move(), provider=ProviderId.CLOUD),
            response(valid_move(), provider=ProviderId.CLOUD),
        ],
        policy=policy,
    )
    router.route(request("AUTO"))
    router.route(request("AUTO"))

    third = router.route(request("AUTO"))

    assert len(local.calls) == 2
    assert len(cloud.calls) == 2
    assert third.canonical_result.governance_record.routing.fallback_reason is (
        FallbackReason.LOCAL_ROLLING_RELIABILITY_BELOW_THRESHOLD
    )
    assert third.local_health.circuit_state is CircuitState.OPEN


def test_rolling_p95_threshold_opens_circuit_before_new_local_attempt():
    policy = routing_policy(
        rolling_window_size=2,
        local_max_consecutive_failures=10,
        minimum_structured_success_rate=0.0,
        local_timeout_ms=1000,
        maximum_local_p95_latency_ms=100,
    )
    router, local, cloud, _, _ = build_router(
        [
            response(
                valid_move(),
                provider=ProviderId.FOUNDRY_LOCAL,
                latency_ms=150,
            ),
            response(
                valid_move(),
                provider=ProviderId.FOUNDRY_LOCAL,
                latency_ms=150,
            ),
        ],
        [
            response(valid_move(), provider=ProviderId.CLOUD),
            response(valid_move(), provider=ProviderId.CLOUD),
            response(valid_move(), provider=ProviderId.CLOUD),
        ],
        policy=policy,
    )
    router.route(request("AUTO"))
    router.route(request("AUTO"))

    third = router.route(request("AUTO"))

    assert len(local.calls) == 2
    assert len(cloud.calls) == 3
    assert third.canonical_result.governance_record.routing.fallback_reason is (
        FallbackReason.LOCAL_LATENCY_THRESHOLD_EXCEEDED
    )
    assert third.canonical_result.governance_record.routing.local_attempted is False
    assert third.local_health.last_circuit_transition == "CLOSED_TO_OPEN_P95_LATENCY"
    assert third.local_health.rolling_structured_success_rate == 1.0


def test_router_records_policy_hash_health_statistics_and_timeout_context():
    loaded = load_hybrid_routing_policy(ROUTING_PATH)
    router, local, _, _, _ = build_router(
        [response(valid_move(), provider=ProviderId.FOUNDRY_LOCAL, latency_ms=42)],
        [],
        policy=loaded,
    )

    result = router.route(request("AUTO"))

    assert result.routing_policy_sha256 == loaded.sha256
    assert result.local_health.rolling_sample_count == 1
    assert result.local_health.rolling_structured_success_rate == 1.0
    assert result.local_health.rolling_p50_latency_ms == 42
    assert result.local_health.rolling_p95_latency_ms == 42
    assert local.calls[0][1]["request_timeout_ms"] == 15000
    assert (
        local.calls[0][1]["routing_policy_id"]
        == "prototype5_hybrid_routing_policy_v1"
    )


def test_router_never_sends_local_timeout_setting_to_cloud_provider():
    router, _, cloud, _, _ = build_router(
        [],
        [response(valid_move(), provider=ProviderId.CLOUD)],
    )

    router.route(request("CLOUD"))

    assert "request_timeout_ms" not in cloud.calls[0][1]


def test_configuration_has_no_model_self_confidence_threshold():
    payload = json.loads(ROUTING_PATH.read_text(encoding="utf-8"))

    assert "confidence" not in json.dumps(payload).casefold()
    assert payload["maximum_provider_attempts"] == 1
