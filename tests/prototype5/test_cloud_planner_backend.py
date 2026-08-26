from __future__ import annotations

import json
from urllib import error as urllib_error

from src.prototype5.cloud_planner_backend import (
    CloudPlannerBackend,
    CloudPlannerConfiguration,
)


class FakeHttpResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def backend(*, api_key: str = "test-secret") -> CloudPlannerBackend:
    return CloudPlannerBackend(
        CloudPlannerConfiguration(
            base_url="https://example.test/v1",
            api_key=api_key,
            model_id="qualified-cloud-model",
            timeout_seconds=2,
            system_prompt="Return only the bounded task proposal JSON.",
        )
    )


def test_cloud_backend_returns_raw_text_without_governance(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeHttpResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"actions":[{"action":"STOP"}]}'
                            )
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr(
        "src.prototype5.cloud_planner_backend.urllib_request.urlopen",
        fake_urlopen,
    )

    result = backend().generate(
        "Stop.",
        {
            "prompt_id": "demo-prompt",
            "domain_id": "MANUFACTURING",
            "scene": {"scene_id": "synthetic"},
        },
    )

    assert result.success is True
    assert result.raw_text == '{"actions":[{"action":"STOP"}]}'
    assert result.model_alias == "qualified-cloud-model"
    assert result.prompt_id == "demo-prompt"
    assert captured["timeout"] == 2
    assert captured["request"].get_header("Authorization") == "Bearer test-secret"
    assert not hasattr(result, "execution_eligible")


def test_cloud_backend_does_not_send_requester_identity(monkeypatch):
    captured_body = {}

    def fake_urlopen(request, timeout):
        captured_body.update(json.loads(request.data.decode("utf-8")))
        return FakeHttpResponse(
            {"choices": [{"message": {"content": '{"actions":[{"action":"STOP"}]}'}}]}
        )

    monkeypatch.setattr(
        "src.prototype5.cloud_planner_backend.urllib_request.urlopen",
        fake_urlopen,
    )

    backend().generate(
        "Stop.",
        {
            "domain_id": "MANUFACTURING",
            "scene": {"scene_id": "synthetic"},
            "requester": {"requester_id": "private-user", "role": "operator"},
        },
    )

    serialised = json.dumps(captured_body)
    assert "private-user" not in serialised
    assert "test-secret" not in serialised


def test_missing_cloud_credentials_fail_without_network(monkeypatch):
    monkeypatch.setattr(
        "src.prototype5.cloud_planner_backend.urllib_request.urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("network must not be called")
        ),
    )

    result = backend(api_key="").generate("Stop.")

    assert result.success is False
    assert result.error_type == "authentication_failed"
    assert result.raw_text is None


def test_cloud_authentication_failure_is_explicit(monkeypatch):
    def fake_urlopen(request, timeout):
        raise urllib_error.HTTPError(
            request.full_url,
            401,
            "Unauthorized",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr(
        "src.prototype5.cloud_planner_backend.urllib_request.urlopen",
        fake_urlopen,
    )

    result = backend().generate("Stop.")

    assert result.success is False
    assert result.error_type == "authentication_failed"
    assert result.raw_text is None


def test_malformed_cloud_payload_fails_closed(monkeypatch):
    monkeypatch.setattr(
        "src.prototype5.cloud_planner_backend.urllib_request.urlopen",
        lambda request, timeout: FakeHttpResponse({"choices": []}),
    )

    result = backend().generate("Stop.")

    assert result.success is False
    assert result.error_type == "empty_model_response"
    assert result.raw_text is None
