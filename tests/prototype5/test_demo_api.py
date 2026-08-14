from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from itertools import count
from pathlib import Path

from fastapi.testclient import TestClient
import pytest
from pydantic import ValidationError

from src.prototype5.canonical_governance_runner import (
    CanonicalGovernanceRunner,
    CanonicalRunnerConfigurationV2,
)
from src.prototype5 import demo_api as demo_api_module
from src.prototype5.demo_api import create_demo_app
from src.prototype5.demo_service import (
    DemoApplicationService,
    TranscriptNotReadyError,
    TypedCommandApiRequest,
    VoiceCommandApiRequest,
)
from src.prototype5.foundry_sdk_backend import ModelBackendResponse
from src.prototype5.governance_contract_v2 import ProviderId
from src.prototype5.hybrid_inference_router import (
    HybridInferenceRouter,
    InferenceProviderBinding,
    ProviderAvailabilityV2,
    load_hybrid_routing_policy,
)
from src.prototype5.manufacturing_policy_v2 import load_manufacturing_policy
from src.prototype5.recorded_speech import (
    DEFAULT_MAX_AUDIO_BYTES,
    NEMOTRON_SPEECH_MODEL_ID,
    RecordedAudioMetadataV1,
    RecordedTranscriptionResultV1,
)
from src.prototype5.frozen_evidence_replay import (
    REPLAY_SCENARIO_ID,
    load_registered_frozen_evidence_replay,
)
from src.prototype5.replay_coordinator import (
    ReplayCoordinator,
    ReplayErrorCode,
    ReplayTimings,
)


ROOT = Path(__file__).resolve().parents[2]
FIXED_TIME = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)
LIVE_SCENARIO = "MANUFACTURING_TYPED_ACCEPT"


class SequenceBackend:
    def __init__(self, responses: list[ModelBackendResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, dict[str, object] | None]] = []

    def generate(self, command: str, context=None) -> ModelBackendResponse:
        self.calls.append((command, context))
        if not self.responses:
            raise AssertionError("unexpected provider call")
        return self.responses.pop(0)


def model_response(
    raw_text: str,
    *,
    provider: ProviderId,
) -> ModelBackendResponse:
    return ModelBackendResponse(
        backend=provider.value,
        model_alias=(
            "local-test-model"
            if provider is ProviderId.FOUNDRY_LOCAL
            else "cloud-test-model"
        ),
        prompt_id="prototype5_integrated_demo_v2",
        raw_text=raw_text,
        success=True,
        latency_ms=10,
        error_type=None,
        error_message=None,
        timestamp_utc=FIXED_TIME.isoformat(),
    )


def valid_move() -> str:
    return json.dumps(
        {
            "actions": [
                {
                    "action": "MOVE",
                    "object_id": "blue_component",
                    "source_id": "input_tray_a",
                    "destination_id": "assembly_fixture_b",
                }
            ]
        }
    )


def build_client(
    *,
    local_responses: list[ModelBackendResponse],
    cloud_responses: list[ModelBackendResponse],
    local_available: bool = True,
    frontend_dist: Path | None = None,
    speech_transcriber=None,
    transcript_ttl_seconds: int = 600,
    transcript_registry_capacity: int = 20,
    utc_clock=None,
    replay_coordinator: ReplayCoordinator | None = None,
):
    sequence = count(1)
    local = SequenceBackend(local_responses)
    cloud = SequenceBackend(cloud_responses)
    runner = CanonicalGovernanceRunner(
        policy=load_manufacturing_policy(
            ROOT / "configs" / "prototype5" / "manufacturing_policy_v2.json"
        ),
        configuration=CanonicalRunnerConfigurationV2(
            source_repository="Adhish-Rao2405/Microsoft-IXN-Prototype5",
            software_commit="a" * 40,
            prompt_id="prototype5_integrated_demo_v2",
            prompt_version="2.0.0",
        ),
        clock=lambda: FIXED_TIME,
        id_factory=lambda: f"id-{next(sequence)}",
    )
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
        governance_runner=runner,
        routing_policy=load_hybrid_routing_policy(
            ROOT
            / "configs"
            / "prototype5"
            / "hybrid_routing_policy_v1.json"
        ),
        utc_clock=lambda: FIXED_TIME,
    )
    service = DemoApplicationService(
        router=router,
        software_commit="a" * 40,
        cloud_configured=True,
        speech_transcriber=speech_transcriber,
        transcript_ttl_seconds=transcript_ttl_seconds,
        transcript_registry_capacity=transcript_registry_capacity,
        utc_clock=utc_clock or (lambda: FIXED_TIME),
    )
    app = create_demo_app(
        service,
        frontend_dist=frontend_dist,
        replay_coordinator=replay_coordinator,
    )
    app.state.demo_service = service
    return (
        TestClient(app),
        local,
        cloud,
    )


class _ApiReplaySession:
    def __init__(self) -> None:
        self.plan = load_registered_frozen_evidence_replay()
        self.owner_thread = threading.get_ident()
        self.frame_index: int | None = None
        self.closed = False

    def _owned(self) -> None:
        assert threading.get_ident() == self.owner_thread

    def open(self):
        self._owned()
        return self

    def apply_frame(self, frame_index: int):
        self._owned()
        self.frame_index = frame_index
        return type("Readback", (), {"frame": self.plan.frame_at(frame_index)})()

    @property
    def current_frame(self):
        self._owned()
        assert self.frame_index is not None
        return self.plan.frame_at(self.frame_index)

    def probe_connection(self) -> bool:
        self._owned()
        return True

    def reset_view(self) -> None:
        self._owned()

    def close(self) -> None:
        self._owned()
        self.closed = True


def _api_replay_coordinator() -> ReplayCoordinator:
    return ReplayCoordinator(
        _ApiReplaySession,
        known_scenario_ids=frozenset({REPLAY_SCENARIO_ID, LIVE_SCENARIO}),
        timings=ReplayTimings(
            startup_seconds=1.0,
            control_seconds=1.0,
            idle_seconds=100.0,
            shutdown_seconds=1.0,
            liveness_seconds=100.0,
            cadence_seconds=100.0,
            tombstone_seconds=10.0,
        ),
    )


def test_status_is_side_effect_free_and_claim_bounded():
    client, local, cloud = build_client(
        local_responses=[],
        cloud_responses=[],
    )

    response = client.get("/api/v1/status")
    body = response.json()

    assert response.status_code == 200
    assert body["service_status"] == "READY"
    assert body["local_status"] == "NOT_ASSESSED"
    assert body["speech_status"] == "UNAVAILABLE"
    assert body["simulator_status"] == "NOT_ASSESSED"
    assert body["supported_domains"] == ["MANUFACTURING"]
    assert local.calls == []
    assert cloud.calls == []


def test_manifest_is_d0_derived_side_effect_free_and_presentation_safe():
    client, local, cloud = build_client(
        local_responses=[],
        cloud_responses=[],
    )

    response = client.get("/api/v1/demo/manifest")
    body = response.json()

    def all_keys(value: object) -> set[str]:
        if isinstance(value, dict):
            return set(value) | {
                nested
                for item in value.values()
                for nested in all_keys(item)
            }
        if isinstance(value, list):
            return {
                nested
                for item in value
                for nested in all_keys(item)
            }
        return set()

    assert response.status_code == 200
    assert body["contract_id"] == "PROTOTYPE5_FINAL_DEMONSTRATOR_D0"
    assert body["contract_version"] == "1.0.0"
    assert body["physical_execution_authority_state"] == "NOT_IMPLEMENTED"
    assert body["d2_replay_enabled"] is False
    assert len(body["scenarios"]) == 10
    assert len({item["scenario_id"] for item in body["scenarios"]}) == 10
    assert sum(
        item["replay_capability_classification"]
        == "FROZEN_B2_REPLAY_COMPATIBLE"
        for item in body["scenarios"]
    ) == 1
    for forbidden in (
        "artifact_path",
        "artifact_sha",
        "joint_vector",
        "urdf",
        "pybullet_client_id",
        "permit_id",
    ):
        assert forbidden not in all_keys(body)
    assert local.calls == []
    assert cloud.calls == []


@pytest.mark.parametrize(
    "scenario_id, expected_status",
    [
        (None, 422),
        ("", 422),
        ("   ", 422),
        ("UNKNOWN_SCENARIO", 404),
    ],
)
def test_typed_scenario_identifier_fails_closed(
    scenario_id: object,
    expected_status: int,
):
    client, local, cloud = build_client(
        local_responses=[],
        cloud_responses=[],
    )

    response = client.post(
        "/api/v1/governance/typed",
        json={
            "scenario_id": scenario_id,
            "command": "Move the blue component.",
            "inference_mode": "LOCAL",
        },
    )

    assert response.status_code == expected_status
    assert local.calls == []
    assert cloud.calls == []


@pytest.mark.parametrize(
    "scenario_id",
    [
        "MODE_E_CONVEYOR_GOVERNANCE",
        "MODE_E_WAREHOUSE_GOVERNANCE",
        "MODE_E_HUMAN_PROXIMITY_GOVERNANCE",
        "MODE_E_RESTRICTED_ZONE_GOVERNANCE",
        "FROZEN_B2_PICK_PLACE_EVIDENCE_REPLAY",
    ],
)
def test_evidence_scenarios_cannot_invoke_live_inference(scenario_id: str):
    client, local, cloud = build_client(
        local_responses=[],
        cloud_responses=[],
    )

    response = client.post(
        "/api/v1/governance/typed",
        json={
            "scenario_id": scenario_id,
            "command": "Move the blue component.",
            "inference_mode": "LOCAL",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == (
        "SCENARIO_LIVE_INFERENCE_FORBIDDEN"
    )
    assert local.calls == []
    assert cloud.calls == []


@pytest.mark.parametrize(
    "legacy_field, value",
    [
        ("domain_id", "MANUFACTURING"),
        ("requester_role", "operator"),
        ("human_obstruction", False),
        ("safety_interlock_enabled", True),
    ],
)
def test_typed_legacy_authority_fields_are_rejected(
    legacy_field: str,
    value: object,
):
    client, local, cloud = build_client(
        local_responses=[],
        cloud_responses=[],
    )
    payload: dict[str, object] = {
        "scenario_id": LIVE_SCENARIO,
        "command": "Move the blue component.",
        "inference_mode": "LOCAL",
        legacy_field: value,
    }

    response = client.post("/api/v1/governance/typed", json=payload)

    assert response.status_code == 422
    assert local.calls == []
    assert cloud.calls == []


def test_typed_http_request_requires_scenario_identifier():
    client, local, cloud = build_client(
        local_responses=[],
        cloud_responses=[],
    )

    response = client.post(
        "/api/v1/governance/typed",
        json={"command": "Move the blue component.", "inference_mode": "LOCAL"},
    )

    assert response.status_code == 422
    assert local.calls == []
    assert cloud.calls == []


def test_internal_requests_require_explicit_scenario_identifier():
    with pytest.raises(ValidationError):
        TypedCommandApiRequest(
            command="Move the blue component.",
            inference_mode="LOCAL",
        )
    with pytest.raises(ValidationError):
        VoiceCommandApiRequest(
            transcription_id="transcription-1",
            reviewed_transcript_text="Move the blue component.",
            inference_mode="LOCAL",
        )


def test_voice_http_request_requires_scenario_identifier():
    client, local, cloud = build_client(
        local_responses=[],
        cloud_responses=[],
    )

    response = client.post(
        "/api/v1/governance/voice",
        json={
            "transcription_id": "transcription-1",
            "reviewed_transcript_text": "Move the blue component.",
            "inference_mode": "LOCAL",
        },
    )

    assert response.status_code == 422
    assert local.calls == []
    assert cloud.calls == []


@pytest.mark.parametrize(
    "legacy_field, value",
    [
        ("domain_id", "MANUFACTURING"),
        ("requester_role", "operator"),
        ("human_obstruction", False),
        ("safety_interlock_enabled", True),
    ],
)
def test_voice_legacy_authority_fields_are_rejected(
    legacy_field: str,
    value: object,
):
    client, local, cloud = build_client(
        local_responses=[],
        cloud_responses=[],
    )
    payload: dict[str, object] = {
        "scenario_id": LIVE_SCENARIO,
        "transcription_id": "transcription-does-not-need-to-exist",
        "reviewed_transcript_text": "Move the blue component.",
        "inference_mode": "LOCAL",
        legacy_field: value,
    }

    response = client.post("/api/v1/governance/voice", json=payload)

    assert response.status_code == 422
    assert local.calls == []
    assert cloud.calls == []


def test_typed_local_request_returns_proposal_gates_and_trace():
    client, local, cloud = build_client(
        local_responses=[
            model_response(valid_move(), provider=ProviderId.FOUNDRY_LOCAL)
        ],
        cloud_responses=[],
    )

    response = client.post(
        "/api/v1/governance/typed",
        json={
            "scenario_id": LIVE_SCENARIO,
            "command": (
                "Move the blue component from input tray A "
                "to assembly fixture B."
            ),
            "inference_mode": "LOCAL",
        },
    )
    body = response.json()
    record = body["canonical_result"]["governance_record"]

    assert response.status_code == 200
    assert len(local.calls) == 1
    assert cloud.calls == []
    planner_context = local.calls[0][1]
    assert planner_context is not None
    assert planner_context["domain_id"] == "MANUFACTURING"
    assert planner_context["requester"] == {
        "requester_id": "synthetic_operator_ui",
        "role": "operator",
    }
    assert planner_context["scene"]["human_obstruction"] is False
    assert planner_context["scene"]["safety_interlock_enabled"] is True
    assert body["canonical_result"]["proposal"]["actions"][0]["action"] == "MOVE"
    assert record["parse_status"] == "PASSED"
    assert record["schema_status"] == "PASSED"
    assert record["plan_semantic_status"] == "VALID"
    assert record["final_decision"] == "ACCEPT"
    assert record["execution_eligible"] is True
    assert record["simulation_status"] == "NOT_REQUESTED"
    assert record["execution_permit_id"] is None
    assert record["trace_id"]


def test_auto_fallback_is_visible_and_cloud_output_uses_same_gateway():
    client, local, cloud = build_client(
        local_responses=[
            model_response("not-json", provider=ProviderId.FOUNDRY_LOCAL)
        ],
        cloud_responses=[
            model_response(valid_move(), provider=ProviderId.CLOUD)
        ],
    )

    response = client.post(
        "/api/v1/governance/typed",
        json={
            "scenario_id": LIVE_SCENARIO,
            "command": (
                "Move the blue component from input tray A "
                "to assembly fixture B."
            ),
            "inference_mode": "AUTO",
        },
    )
    body = response.json()
    route = body["canonical_result"]["governance_record"]["routing"]

    assert response.status_code == 200
    assert len(local.calls) == 1
    assert len(cloud.calls) == 1
    assert route["fallback_triggered"] is True
    assert route["fallback_reason"] == "LOCAL_PARSE_FAILURE"
    assert route["selected_provider"] == "CLOUD"
    assert (
        body["canonical_result"]["governance_record"]["final_decision"]
        == "ACCEPT"
    )


def test_unsafe_local_proposal_rejects_without_cloud_fallback():
    client, local, cloud = build_client(
        local_responses=[
            model_response(valid_move(), provider=ProviderId.FOUNDRY_LOCAL)
        ],
        cloud_responses=[],
    )

    response = client.post(
        "/api/v1/governance/typed",
        json={
            "scenario_id": "MANUFACTURING_UNSAFE_REJECT",
            "command": "Continue movement despite the human obstruction.",
            "inference_mode": "AUTO",
        },
    )
    record = response.json()["canonical_result"]["governance_record"]

    assert response.status_code == 200
    assert len(local.calls) == 1
    assert cloud.calls == []
    assert record["routing"]["fallback_triggered"] is False
    assert record["safety_status"] == "FAILED"
    assert record["final_decision"] == "REJECT"
    assert record["execution_eligible"] is False


def test_legacy_domain_field_is_rejected_before_provider_call():
    client, local, cloud = build_client(
        local_responses=[],
        cloud_responses=[],
    )

    response = client.post(
        "/api/v1/governance/typed",
        json={
            "scenario_id": LIVE_SCENARIO,
            "command": "Move the sterile clamp.",
            "inference_mode": "LOCAL",
            "domain_id": "HEALTHCARE_SYNTHETIC",
        },
    )

    assert response.status_code == 422
    assert local.calls == []
    assert cloud.calls == []


def test_blank_command_and_unknown_role_are_rejected_before_provider_call():
    client, local, cloud = build_client(
        local_responses=[],
        cloud_responses=[],
    )

    blank = client.post(
        "/api/v1/governance/typed",
        json={
            "scenario_id": LIVE_SCENARIO,
            "command": "   ",
            "inference_mode": "LOCAL",
        },
    )
    role = client.post(
        "/api/v1/governance/typed",
        json={
            "scenario_id": LIVE_SCENARIO,
            "command": "Stop.",
            "inference_mode": "LOCAL",
            "requester_role": "administrator",
        },
    )

    assert blank.status_code == 422
    assert role.status_code == 422
    assert local.calls == []
    assert cloud.calls == []


def test_api_response_and_schema_never_expose_cloud_credentials():
    client, _, _ = build_client(local_responses=[], cloud_responses=[])

    status_text = client.get("/api/v1/status").text
    schema_text = client.get("/api/openapi.json").text

    assert "api_key" not in status_text
    assert "api_key" not in schema_text
    assert "OPENAI_API_KEY" not in schema_text


def test_built_frontend_can_be_served_without_shadowing_api(tmp_path):
    (tmp_path / "index.html").write_text(
        "<html><body>Prototype 5 UI</body></html>",
        encoding="utf-8",
    )
    client, _, _ = build_client(
        local_responses=[],
        cloud_responses=[],
        frontend_dist=tmp_path,
    )

    frontend = client.get("/")
    status = client.get("/api/v1/status")

    assert frontend.status_code == 200
    assert "Prototype 5 UI" in frontend.text
    assert status.status_code == 200


def test_local_cors_origin_is_allowed_without_credentials():
    client, _, _ = build_client(local_responses=[], cloud_responses=[])

    response = client.options(
        "/api/v1/governance/typed",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == (
        "http://localhost:5173"
    )
    assert "access-control-allow-credentials" not in response.headers


class FakeSpeechTranscriber:
    is_worker_configured = True

    def __init__(
        self,
        *,
        status: str = "READY",
        text: str | None = "Move the blue component.",
    ) -> None:
        self.status = status
        self.text = text
        self.calls: list[tuple[bytes, str]] = []
        self.fixed_transcription_id: str | None = None

    def transcribe_wav(
        self,
        audio_bytes: bytes,
        *,
        original_filename: str,
    ) -> RecordedTranscriptionResultV1:
        self.calls.append((audio_bytes, original_filename))
        return RecordedTranscriptionResultV1(
            transcription_id=(
                self.fixed_transcription_id
                or f"transcription-{len(self.calls)}"
            ),
            timestamp_utc=FIXED_TIME.isoformat(),
            transcript_status=self.status,
            transcript_text=self.text,
            audio=RecordedAudioMetadataV1(
                original_filename=original_filename,
                audio_sha256="b" * 64,
                audio_bytes=len(audio_bytes),
                sample_rate_hz=16000,
                channels=1,
                bits_per_sample=16,
                frame_count=1600,
                duration_ms=100,
            ),
            resolved_model_id=NEMOTRON_SPEECH_MODEL_ID,
            sdk_version="1.2.3",
            core_version="1.2.3",
            model_cached_before=True,
            model_loaded_before=False,
            model_loaded_for_request=True,
            model_unloaded_after_request=True,
            segment_count=1 if self.text else 0,
            transcription_latency_ms=100,
            error_code=(
                "VOICE_BACKEND_UNAVAILABLE"
                if self.status == "BACKEND_UNAVAILABLE"
                else None
            ),
            error_detail=(
                "Speech backend is unavailable."
                if self.status == "BACKEND_UNAVAILABLE"
                else None
            ),
        )


def test_recorded_transcript_requires_explicit_review_then_uses_same_gateway():
    speech = FakeSpeechTranscriber()
    client, local, cloud = build_client(
        local_responses=[
            model_response(valid_move(), provider=ProviderId.FOUNDRY_LOCAL)
        ],
        cloud_responses=[],
        speech_transcriber=speech,
    )

    transcription = client.post(
        "/api/v1/speech/recorded",
        content=b"test-wav-payload",
        headers={
            "Content-Type": "audio/wav",
            "X-Audio-Filename": "operator.wav",
        },
    )

    assert transcription.status_code == 200
    assert transcription.json()["transcript_status"] == "READY"
    assert local.calls == []
    assert cloud.calls == []

    governance = client.post(
        "/api/v1/governance/voice",
        json={
            "scenario_id": LIVE_SCENARIO,
            "transcription_id": "transcription-1",
            "reviewed_transcript_text": (
                "Move the blue component from input tray A "
                "to assembly fixture B."
            ),
            "inference_mode": "LOCAL",
        },
    )
    record = governance.json()["canonical_result"]["governance_record"]

    assert governance.status_code == 200
    assert len(local.calls) == 1
    assert local.calls[0][0].startswith("Move the blue component")
    assert record["input_mode"] == "VOICE"
    assert record["transcription_id"] == "transcription-1"
    assert record["original_transcript_text"] == "Move the blue component."
    assert record["transcript_text"].startswith("Move the blue component from")
    assert record["transcript_backend"] == "foundry_nemotron"
    assert record["audio_sha256"] == "b" * 64
    assert record["final_decision"] == "ACCEPT"
    assert record["execution_eligible"] is True

    replay = client.post(
        "/api/v1/governance/voice",
        json={
            "scenario_id": LIVE_SCENARIO,
            "transcription_id": "transcription-1",
            "reviewed_transcript_text": "Move the blue component.",
            "inference_mode": "LOCAL",
        },
    )
    assert replay.status_code == 409
    assert replay.json()["detail"]["code"] == (
        "TRANSCRIPT_NOT_READY_OR_EXPIRED"
    )


def test_typed_and_reviewed_voice_share_server_scenario_resolution():
    speech = FakeSpeechTranscriber()
    client, local, cloud = build_client(
        local_responses=[
            model_response(valid_move(), provider=ProviderId.FOUNDRY_LOCAL),
            model_response(valid_move(), provider=ProviderId.FOUNDRY_LOCAL),
        ],
        cloud_responses=[],
        speech_transcriber=speech,
    )
    scenario_id = "MANUFACTURING_OBSERVER_ROLE_REJECT"

    typed = client.post(
        "/api/v1/governance/typed",
        json={
            "scenario_id": scenario_id,
            "command": "Move the blue component.",
            "inference_mode": "LOCAL",
        },
    )
    client.post(
        "/api/v1/speech/recorded",
        content=b"test-wav-payload",
        headers={"Content-Type": "audio/wav"},
    )
    voice = client.post(
        "/api/v1/governance/voice",
        json={
            "scenario_id": scenario_id,
            "transcription_id": "transcription-1",
            "reviewed_transcript_text": "Move the blue component.",
            "inference_mode": "LOCAL",
        },
    )

    assert typed.status_code == 200
    assert voice.status_code == 200
    assert cloud.calls == []
    assert len(local.calls) == 2
    typed_context = local.calls[0][1]
    voice_context = local.calls[1][1]
    assert typed_context is not None
    assert voice_context is not None
    assert typed_context["domain_id"] == voice_context["domain_id"]
    assert typed_context["scene"] == voice_context["scene"]
    assert typed_context["requester"] == voice_context["requester"]
    assert typed_context["requester"] == {
        "requester_id": "synthetic_observer_ui",
        "role": "observer",
    }


def test_speech_status_is_claim_bounded_before_and_after_real_worker_result():
    speech = FakeSpeechTranscriber()
    client, _, _ = build_client(
        local_responses=[],
        cloud_responses=[],
        speech_transcriber=speech,
    )

    before = client.get("/api/v1/status").json()
    client.post(
        "/api/v1/speech/recorded",
        content=b"test-wav-payload",
        headers={"Content-Type": "audio/wav"},
    )
    after = client.get("/api/v1/status").json()

    assert before["speech_status"] == "NOT_ASSESSED"
    assert after["speech_status"] == "AVAILABLE"


def test_unconfigured_speech_endpoint_fails_with_explicit_status():
    client, _, _ = build_client(local_responses=[], cloud_responses=[])

    response = client.post(
        "/api/v1/speech/recorded",
        content=b"test-wav-payload",
        headers={"Content-Type": "audio/wav"},
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "VOICE_BACKEND_UNAVAILABLE"


def test_audio_content_type_is_rejected_before_transcriber_call():
    speech = FakeSpeechTranscriber()
    client, _, _ = build_client(
        local_responses=[],
        cloud_responses=[],
        speech_transcriber=speech,
    )

    response = client.post(
        "/api/v1/speech/recorded",
        content=b"not-audio",
        headers={"Content-Type": "text/plain"},
    )

    assert response.status_code == 415
    assert speech.calls == []


def test_audio_length_and_filename_are_rejected_before_transcriber_call():
    speech = FakeSpeechTranscriber()
    client, _, _ = build_client(
        local_responses=[],
        cloud_responses=[],
        speech_transcriber=speech,
    )

    too_large = client.post(
        "/api/v1/speech/recorded",
        content=b"x",
        headers={
            "Content-Type": "audio/wav",
            "Content-Length": str(DEFAULT_MAX_AUDIO_BYTES + 1),
        },
    )
    unsafe_name = client.post(
        "/api/v1/speech/recorded",
        content=b"x",
        headers={
            "Content-Type": "audio/wav",
            "X-Audio-Filename": "../operator.wav",
        },
    )

    assert too_large.status_code == 413
    assert too_large.json()["detail"]["code"] == "AUDIO_TOO_LARGE"
    assert unsafe_name.status_code == 400
    assert unsafe_name.json()["detail"]["code"] == "AUDIO_FILENAME_INVALID"
    assert speech.calls == []


def test_unavailable_transcript_cannot_be_submitted_to_planner():
    speech = FakeSpeechTranscriber(
        status="BACKEND_UNAVAILABLE",
        text=None,
    )
    client, local, cloud = build_client(
        local_responses=[],
        cloud_responses=[],
        speech_transcriber=speech,
    )

    transcription = client.post(
        "/api/v1/speech/recorded",
        content=b"test-wav-payload",
        headers={"Content-Type": "audio/wav"},
    )
    governance = client.post(
        "/api/v1/governance/voice",
        json={
            "scenario_id": LIVE_SCENARIO,
            "transcription_id": "transcription-1",
            "reviewed_transcript_text": "Move the blue component.",
            "inference_mode": "LOCAL",
        },
    )

    assert transcription.json()["transcript_status"] == "BACKEND_UNAVAILABLE"
    assert governance.status_code == 409
    assert local.calls == []
    assert cloud.calls == []


def test_expired_transcript_is_evicted_before_governance():
    now = [FIXED_TIME]
    speech = FakeSpeechTranscriber()
    client, local, cloud = build_client(
        local_responses=[],
        cloud_responses=[],
        speech_transcriber=speech,
        transcript_ttl_seconds=600,
        utc_clock=lambda: now[0],
    )
    client.post(
        "/api/v1/speech/recorded",
        content=b"test-wav-payload",
        headers={"Content-Type": "audio/wav"},
    )
    now[0] += timedelta(seconds=601)

    response = client.post(
        "/api/v1/governance/voice",
        json={
            "scenario_id": LIVE_SCENARIO,
            "transcription_id": "transcription-1",
            "reviewed_transcript_text": "Move the blue component.",
            "inference_mode": "LOCAL",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "TRANSCRIPT_NOT_READY_OR_EXPIRED"
    assert local.calls == []
    assert cloud.calls == []


def test_registry_capacity_evicts_oldest_ready_transcript():
    speech = FakeSpeechTranscriber()
    client, _, _ = build_client(
        local_responses=[],
        cloud_responses=[],
        speech_transcriber=speech,
        transcript_registry_capacity=1,
    )
    for _ in range(2):
        response = client.post(
            "/api/v1/speech/recorded",
            content=b"test-wav-payload",
            headers={"Content-Type": "audio/wav"},
        )
        assert response.status_code == 200

    evicted = client.post(
        "/api/v1/governance/voice",
        json={
            "scenario_id": LIVE_SCENARIO,
            "transcription_id": "transcription-1",
            "reviewed_transcript_text": "Move the blue component.",
            "inference_mode": "LOCAL",
        },
    )

    assert evicted.status_code == 409


def test_concurrent_submission_can_claim_transcript_only_once():
    speech = FakeSpeechTranscriber()
    client, local, _ = build_client(
        local_responses=[
            model_response(valid_move(), provider=ProviderId.FOUNDRY_LOCAL)
        ],
        cloud_responses=[],
        speech_transcriber=speech,
    )
    client.post(
        "/api/v1/speech/recorded",
        content=b"test-wav-payload",
        headers={"Content-Type": "audio/wav"},
    )
    service = client.app.state.demo_service
    request = VoiceCommandApiRequest(
        scenario_id=LIVE_SCENARIO,
        transcription_id="transcription-1",
        reviewed_transcript_text=(
            "Move the blue component from input tray A to assembly fixture B."
        ),
        inference_mode="LOCAL",
    )
    barrier = threading.Barrier(2)

    def submit() -> str:
        barrier.wait()
        try:
            service.submit_voice(request)
            return "ACCEPTED"
        except TranscriptNotReadyError:
            return "NOT_READY"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(lambda _: submit(), range(2)))

    assert sorted(outcomes) == ["ACCEPTED", "NOT_READY"]
    assert len(local.calls) == 1


def test_registry_configuration_is_bounded():
    with pytest.raises(ValueError, match="transcript_ttl_seconds"):
        build_client(
            local_responses=[],
            cloud_responses=[],
            transcript_ttl_seconds=0,
        )
    with pytest.raises(ValueError, match="transcript_registry_capacity"):
        build_client(
            local_responses=[],
            cloud_responses=[],
            transcript_registry_capacity=0,
        )


def test_replay_lifespan_and_canonical_idle_dto_are_exact() -> None:
    coordinator = _api_replay_coordinator()
    client, _, _ = build_client(
        local_responses=[],
        cloud_responses=[],
        replay_coordinator=coordinator,
    )
    with client:
        response = client.get("/api/v1/replay/state")
        assert response.status_code == 200
        body = response.json()
        assert body["contract_id"] == "PROTOTYPE5_D3_REPLAY_STATE_V1"
        assert body["session_id"] is None
        assert body["control_version"] == body["projection_version"] == 0
        assert body["lifecycle_state"] == "IDLE"
        assert body["current_frame"] is None
        assert body["available_controls"] == ["START"]
        assert body["frame_count"] == 469
        assert body["physical_execution_authority"] == "NOT_IMPLEMENTED"
        assert "joint_positions" not in json.dumps(body)
        assert coordinator._thread is not None and coordinator._thread.is_alive()
    assert coordinator._thread is not None and not coordinator._thread.is_alive()


def test_replay_start_control_get_and_stop_use_exact_envelopes() -> None:
    coordinator = _api_replay_coordinator()
    client, _, _ = build_client(
        local_responses=[], cloud_responses=[], replay_coordinator=coordinator
    )
    with client:
        started = client.post(
            "/api/v1/replay/start",
            json={"scenario_id": REPLAY_SCENARIO_ID},
        )
        assert started.status_code == 200
        state = started.json()
        assert state["lifecycle_state"] == "PAUSED"
        assert state["current_frame"]["frame_index"] == 0
        assert state["command_in_flight"] is False
        updated = state["updated_at_utc"]

        read = client.get("/api/v1/replay/state")
        assert read.status_code == 200
        assert read.json()["updated_at_utc"] == updated
        assert read.json()["projection_version"] == state["projection_version"]

        advanced = client.post(
            "/api/v1/replay/control",
            json={
                "scenario_id": REPLAY_SCENARIO_ID,
                "session_id": state["session_id"],
                "expected_control_version": state["control_version"],
                "control": "NEXT_SNAPSHOT",
            },
        )
        assert advanced.status_code == 200
        state = advanced.json()
        assert state["current_frame"]["frame_index"] == 1

        stopped = client.post(
            "/api/v1/replay/control",
            json={
                "scenario_id": REPLAY_SCENARIO_ID,
                "session_id": state["session_id"],
                "expected_control_version": state["control_version"],
                "control": "STOP",
            },
        )
        assert stopped.status_code == 200
        assert stopped.json()["lifecycle_state"] == "IDLE"


@pytest.mark.parametrize(
    ("content", "headers"),
    [
        (b"", {"content-type": "application/json"}),
        (b"[]", {"content-type": "application/json"}),
        (b'{"scenario_id":"x","scenario_id":"y"}', {"content-type": "application/json"}),
        (b'{"scenario_id":NaN}', {"content-type": "application/json"}),
        (b"\xef\xbb\xbf{}", {"content-type": "application/json"}),
        (b"{}", {"content-type": "text/plain"}),
        (b"{}", {"content-type": "application/json; charset=latin-1"}),
        (b"{}", {"content-type": "application/json", "content-encoding": "gzip"}),
        (b"{\xff}", {"content-type": "application/json"}),
        (b"x" * 4097, {"content-type": "application/json"}),
    ],
)
def test_replay_route_local_parser_fails_closed(
    content: bytes,
    headers: dict[str, str],
) -> None:
    coordinator = _api_replay_coordinator()
    client, _, _ = build_client(
        local_responses=[], cloud_responses=[], replay_coordinator=coordinator
    )
    with client:
        response = client.post(
            "/api/v1/replay/start",
            content=content,
            headers=headers,
        )
        assert response.status_code == 422
        assert response.json() == {"code": "REPLAY_REQUEST_INVALID"}


def test_replay_strict_control_validation_rejects_bool_and_unknown_fields() -> None:
    coordinator = _api_replay_coordinator()
    client, _, _ = build_client(
        local_responses=[], cloud_responses=[], replay_coordinator=coordinator
    )
    with client:
        for payload in (
            {
                "scenario_id": REPLAY_SCENARIO_ID,
                "session_id": "session",
                "expected_control_version": True,
                "control": "STOP",
            },
            {
                "scenario_id": REPLAY_SCENARIO_ID,
                "session_id": "session",
                "expected_control_version": 1,
                "control": "START",
            },
            {"scenario_id": REPLAY_SCENARIO_ID, "extra": "forbidden"},
        ):
            path = (
                "/api/v1/replay/start"
                if "extra" in payload
                else "/api/v1/replay/control"
            )
            response = client.post(path, json=payload)
            assert response.status_code == 422
            assert response.json() == {"code": "REPLAY_REQUEST_INVALID"}


def test_replay_scenario_errors_are_code_only_without_detail_wrapper() -> None:
    coordinator = _api_replay_coordinator()
    client, _, _ = build_client(
        local_responses=[], cloud_responses=[], replay_coordinator=coordinator
    )
    with client:
        unknown = client.post(
            "/api/v1/replay/start", json={"scenario_id": "UNKNOWN"}
        )
        non_replay = client.post(
            "/api/v1/replay/start", json={"scenario_id": LIVE_SCENARIO}
        )
        assert (unknown.status_code, unknown.json()) == (
            404,
            {"code": "REPLAY_SCENARIO_NOT_FOUND"},
        )
        assert (non_replay.status_code, non_replay.json()) == (
            409,
            {"code": "REPLAY_SCENARIO_NOT_REPLAYABLE"},
        )


def test_fatal_exhaustion_precedes_even_malformed_replay_validation() -> None:
    coordinator = _api_replay_coordinator()
    client, _, _ = build_client(
        local_responses=[], cloud_responses=[], replay_coordinator=coordinator
    )
    with client:
        with coordinator._condition:
            coordinator._version_exhausted = True
        for method, path in (
            ("post", "/api/v1/replay/start"),
            ("post", "/api/v1/replay/control"),
            ("get", "/api/v1/replay/state"),
        ):
            response = getattr(client, method)(
                path,
                **(
                    {"content": b"not-json", "headers": {"content-type": "text/plain"}}
                    if method == "post"
                    else {}
                ),
            )
            assert response.status_code == 503
            assert response.json() == {"code": "REPLAY_VERSION_EXHAUSTED"}


def test_mutating_route_rechecks_exhaustion_after_body_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coordinator = _api_replay_coordinator()
    original_reader = demo_api_module._read_replay_json

    async def latch_after_validation(request):
        payload = await original_reader(request)
        with coordinator._condition:
            coordinator._version_exhausted = True
        return payload

    monkeypatch.setattr(demo_api_module, "_read_replay_json", latch_after_validation)
    client, _, _ = build_client(
        local_responses=[], cloud_responses=[], replay_coordinator=coordinator
    )
    with client:
        response = client.post(
            "/api/v1/replay/start",
            json={"scenario_id": REPLAY_SCENARIO_ID},
        )
        assert response.status_code == 503
        assert response.json() == {"code": "REPLAY_VERSION_EXHAUSTED"}
        assert coordinator._provisional_session_id is None


def test_replay_routes_do_not_change_existing_nonreplay_422_contract() -> None:
    baseline_client, _, _ = build_client(local_responses=[], cloud_responses=[])
    baseline = baseline_client.post("/api/v1/governance/typed", json={})
    coordinator = _api_replay_coordinator()
    replay_client, _, _ = build_client(
        local_responses=[], cloud_responses=[], replay_coordinator=coordinator
    )
    with replay_client:
        with_replay = replay_client.post("/api/v1/governance/typed", json={})
    assert baseline.status_code == with_replay.status_code == 422
    assert baseline.json() == with_replay.json()
