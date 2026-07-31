from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from itertools import count
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from src.prototype5.canonical_governance_runner import (
    CanonicalGovernanceRunner,
    CanonicalRunnerConfigurationV2,
)
from src.prototype5.demo_api import create_demo_app
from src.prototype5.demo_service import (
    DemoApplicationService,
    TranscriptNotReadyError,
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


ROOT = Path(__file__).resolve().parents[2]
FIXED_TIME = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)


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
    app = create_demo_app(service, frontend_dist=frontend_dist)
    app.state.demo_service = service
    return (
        TestClient(app),
        local,
        cloud,
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
            "command": (
                "Move the blue component from input tray A "
                "to assembly fixture B."
            ),
            "inference_mode": "LOCAL",
            "domain_id": "MANUFACTURING",
        },
    )
    body = response.json()
    record = body["canonical_result"]["governance_record"]

    assert response.status_code == 200
    assert len(local.calls) == 1
    assert cloud.calls == []
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


def test_healthcare_domain_is_explicitly_unavailable_in_u1():
    client, local, cloud = build_client(
        local_responses=[],
        cloud_responses=[],
    )

    response = client.post(
        "/api/v1/governance/typed",
        json={
            "command": "Move the sterile clamp.",
            "inference_mode": "LOCAL",
            "domain_id": "HEALTHCARE_SYNTHETIC",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == (
        "SYNTHETIC_HEALTHCARE_DOMAIN_NOT_IMPLEMENTED"
    )
    assert local.calls == []
    assert cloud.calls == []


def test_blank_command_and_unknown_role_are_rejected_before_provider_call():
    client, local, cloud = build_client(
        local_responses=[],
        cloud_responses=[],
    )

    blank = client.post(
        "/api/v1/governance/typed",
        json={"command": "   ", "inference_mode": "LOCAL"},
    )
    role = client.post(
        "/api/v1/governance/typed",
        json={
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
            "transcription_id": "transcription-1",
            "reviewed_transcript_text": (
                "Move the blue component from input tray A "
                "to assembly fixture B."
            ),
            "inference_mode": "LOCAL",
            "domain_id": "MANUFACTURING",
            "requester_role": "operator",
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
            "transcription_id": "transcription-1",
            "reviewed_transcript_text": "Move the blue component.",
            "inference_mode": "LOCAL",
        },
    )
    assert replay.status_code == 409
    assert replay.json()["detail"]["code"] == (
        "TRANSCRIPT_NOT_READY_OR_EXPIRED"
    )


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
