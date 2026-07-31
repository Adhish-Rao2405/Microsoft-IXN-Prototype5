from __future__ import annotations

import json
from datetime import datetime, timezone
from itertools import count
from pathlib import Path

from fastapi.testclient import TestClient

from src.prototype5.canonical_governance_runner import (
    CanonicalGovernanceRunner,
    CanonicalRunnerConfigurationV2,
)
from src.prototype5.demo_api import create_demo_app
from src.prototype5.demo_service import DemoApplicationService
from src.prototype5.foundry_sdk_backend import ModelBackendResponse
from src.prototype5.governance_contract_v2 import ProviderId
from src.prototype5.hybrid_inference_router import (
    HybridInferenceRouter,
    InferenceProviderBinding,
    ProviderAvailabilityV2,
    load_hybrid_routing_policy,
)
from src.prototype5.manufacturing_policy_v2 import load_manufacturing_policy


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
    )
    return (
        TestClient(create_demo_app(service, frontend_dist=frontend_dist)),
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
    assert body["speech_status"] == "NOT_ASSESSED"
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
