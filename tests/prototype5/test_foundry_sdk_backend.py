from src.prototype5.foundry_sdk_backend import (
    DEFAULT_PROMPT_ID,
    FoundrySDKBackend,
    ModelBackendResponse,
)
from src.prototype5.foundry_sdk_client import FoundryClientResponse


class FakeFoundryClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def chat_completion(self, user_prompt, system_prompt=None, temperature=0.0, max_tokens=256):
        self.calls.append(
            {
                "user_prompt": user_prompt,
                "system_prompt": system_prompt,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        return self.response


def successful_client_response(raw_text='{"action":"move"}'):
    return FoundryClientResponse(
        success=True,
        backend="foundry_local_openai_compatible",
        base_url="http://127.0.0.1:53402",
        model_alias="qwen2.5-coder-0.5b-instruct-generic-cpu:4",
        raw_text=raw_text,
        latency_ms=12.5,
        error_type=None,
        error_message=None,
        response_payload={"choices": [{"message": {"content": raw_text}}]},
        timestamp_utc="2026-05-28T00:00:00+00:00",
    )


def failed_client_response():
    return FoundryClientResponse(
        success=False,
        backend="foundry_local_openai_compatible",
        base_url="http://127.0.0.1:53402",
        model_alias="qwen2.5-coder-0.5b-instruct-generic-cpu:4",
        raw_text=None,
        latency_ms=3.25,
        error_type="endpoint_unavailable",
        error_message="connection refused",
        response_payload=None,
        timestamp_utc="2026-05-28T00:00:00+00:00",
    )


def test_backend_response_contract_has_required_fields():
    response = ModelBackendResponse(
        backend="foundry_local_openai_compatible",
        model_alias="model",
        prompt_id="prompt",
        raw_text=None,
        success=False,
        latency_ms=None,
        error_type="x",
        error_message="y",
        timestamp_utc="2026-05-28T00:00:00+00:00",
    )

    assert response.backend
    assert response.model_alias == "model"
    assert response.prompt_id == "prompt"
    assert response.success is False
    assert response.error_type == "x"
    assert response.timestamp_utc


def test_generate_preserves_raw_text_exactly():
    raw_text = '  {"action":"move","target":"red block"}  '
    fake_client = FakeFoundryClient(successful_client_response(raw_text=raw_text))
    backend = FoundrySDKBackend(client=fake_client)

    response = backend.generate("Move the red block.")

    assert response.success is True
    assert response.raw_text == raw_text
    assert response.backend == "foundry_local_openai_compatible"
    assert response.model_alias == "qwen2.5-coder-0.5b-instruct-generic-cpu:4"
    assert response.latency_ms == 12.5
    assert response.error_type is None
    assert response.prompt_id == DEFAULT_PROMPT_ID


def test_generate_passes_context_to_sdk_client_without_validation():
    fake_client = FakeFoundryClient(successful_client_response())
    backend = FoundrySDKBackend(client=fake_client)

    response = backend.generate(
        "Stop job",
        {
            "system_prompt": "Return JSON only.",
            "temperature": "0",
            "max_tokens": "64",
            "prompt_id": "phase1_m4_smoke_prompt",
        },
    )

    assert response.success is True
    assert response.prompt_id == "phase1_m4_smoke_prompt"
    assert fake_client.calls == [
        {
            "user_prompt": "Stop job",
            "system_prompt": "Return JSON only.",
            "temperature": 0.0,
            "max_tokens": 64,
        }
    ]


def test_generate_uses_constructor_defaults_when_context_omitted():
    fake_client = FakeFoundryClient(successful_client_response())
    backend = FoundrySDKBackend(
        client=fake_client,
        default_system_prompt="Default system prompt.",
        default_prompt_id="default_prompt",
        default_temperature=0.2,
        default_max_tokens=99,
    )

    response = backend.generate("Proceed")

    assert response.prompt_id == "default_prompt"
    assert fake_client.calls[0]["system_prompt"] == "Default system prompt."
    assert fake_client.calls[0]["temperature"] == 0.2
    assert fake_client.calls[0]["max_tokens"] == 99


def test_failed_sdk_response_fails_closed_without_raw_text():
    fake_client = FakeFoundryClient(failed_client_response())
    backend = FoundrySDKBackend(client=fake_client)

    response = backend.generate("Move it there")

    assert response.success is False
    assert response.raw_text is None
    assert response.error_type == "endpoint_unavailable"
    assert response.error_message == "connection refused"
    assert response.latency_ms == 3.25


def test_adapter_does_not_parse_or_repair_model_output():
    malformed_text = "```json\nnot valid json\n```"
    fake_client = FakeFoundryClient(successful_client_response(raw_text=malformed_text))
    backend = FoundrySDKBackend(client=fake_client)

    response = backend.generate("Return malformed output.")

    assert response.success is True
    assert response.raw_text == malformed_text
    assert not hasattr(response, "json_valid")
    assert not hasattr(response, "schema_valid")
    assert not hasattr(response, "safety_valid")
    assert not hasattr(response, "execution_eligible")


def test_from_client_response_maps_only_backend_metadata():
    client_response = successful_client_response(raw_text='{"action":"noop"}')

    response = FoundrySDKBackend.from_client_response(
        client_response,
        prompt_id="direct_map",
    )

    assert response == ModelBackendResponse(
        backend=client_response.backend,
        model_alias=client_response.model_alias,
        prompt_id="direct_map",
        raw_text=client_response.raw_text,
        success=client_response.success,
        latency_ms=client_response.latency_ms,
        error_type=client_response.error_type,
        error_message=client_response.error_message,
        timestamp_utc=client_response.timestamp_utc,
    )
