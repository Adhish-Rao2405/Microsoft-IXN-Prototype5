import json
from urllib import error as urllib_error

import pytest

from src.prototype5.foundry_sdk_client import (
    DEFAULT_MODEL_ENV,
    DEFAULT_MODEL_PREFERENCE_ORDER,
    FoundryClientResponse,
    FoundryLocalClient,
)


class FakeHTTPResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def make_urlopen_sequence(monkeypatch, payloads, captured_requests=None):
    queue = list(payloads)

    def fake_urlopen(req, timeout):
        if captured_requests is not None:
            captured_requests.append((req, timeout))
        item = queue.pop(0)
        if isinstance(item, BaseException):
            raise item
        return FakeHTTPResponse(item)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    return queue


def models_payload(*aliases):
    return {"object": "list", "data": [{"id": alias} for alias in aliases]}


def chat_payload(text="ok"):
    return {
        "id": "fake",
        "object": "chat.completion",
        "choices": [{"message": {"role": "assistant", "content": text}}],
    }


def test_response_object_has_required_fields():
    response = FoundryClientResponse(
        success=False,
        backend="foundry_local_openai_compatible",
        base_url="http://127.0.0.1:53402",
        model_alias=None,
        raw_text=None,
        latency_ms=1.0,
        error_type="x",
        error_message="y",
        response_payload=None,
        timestamp_utc="2026-05-28T00:00:00+00:00",
    )

    assert response.success is False
    assert response.backend
    assert response.base_url
    assert response.error_type == "x"
    assert response.timestamp_utc


def test_uses_safe_model_preference_order_when_no_explicit_model(monkeypatch):
    monkeypatch.delenv(DEFAULT_MODEL_ENV, raising=False)
    captured = []
    make_urlopen_sequence(
        monkeypatch,
        [
            models_payload(
                "gpt-oss-20b-generic-cpu:1",
                DEFAULT_MODEL_PREFERENCE_ORDER[1],
                DEFAULT_MODEL_PREFERENCE_ORDER[0],
            ),
            chat_payload("selected safe model"),
        ],
        captured,
    )

    client = FoundryLocalClient(base_url="http://127.0.0.1:53402", timeout_seconds=1)
    response = client.chat_completion("Return JSON only.")

    assert response.success is True
    assert response.model_alias == DEFAULT_MODEL_PREFERENCE_ORDER[0]
    assert response.raw_text == "selected safe model"

    post_body = json.loads(captured[1][0].data.decode("utf-8"))
    assert post_body["model"] == DEFAULT_MODEL_PREFERENCE_ORDER[0]


def test_explicit_model_override_is_used_when_available(monkeypatch):
    explicit = "Phi-3-mini-4k-instruct-generic-cpu:3"
    captured = []

    make_urlopen_sequence(
        monkeypatch,
        [
            models_payload(DEFAULT_MODEL_PREFERENCE_ORDER[0], explicit),
            chat_payload("explicit model response"),
        ],
        captured,
    )

    client = FoundryLocalClient(
        base_url="http://127.0.0.1:53402",
        model_alias=explicit,
        timeout_seconds=1,
    )
    response = client.chat_completion("Test.")

    assert response.success is True
    assert response.model_alias == explicit

    post_body = json.loads(captured[1][0].data.decode("utf-8"))
    assert post_body["model"] == explicit


def test_bad_explicit_model_alias_fails_closed(monkeypatch):
    make_urlopen_sequence(
        monkeypatch,
        [models_payload(DEFAULT_MODEL_PREFERENCE_ORDER[0])],
    )

    client = FoundryLocalClient(
        base_url="http://127.0.0.1:53402",
        model_alias="missing-model:999",
        timeout_seconds=1,
    )
    response = client.chat_completion("Test.")

    assert response.success is False
    assert response.error_type == "bad_model_alias"
    assert response.raw_text is None


def test_bad_env_model_alias_fails_closed(monkeypatch):
    monkeypatch.setenv(DEFAULT_MODEL_ENV, "missing-model:999")
    make_urlopen_sequence(
        monkeypatch,
        [models_payload(DEFAULT_MODEL_PREFERENCE_ORDER[0])],
    )

    client = FoundryLocalClient(
        base_url="http://127.0.0.1:53402",
        timeout_seconds=1,
    )
    response = client.chat_completion("Test.")

    assert response.success is False
    assert response.error_type == "bad_model_alias"
    assert response.raw_text is None


def test_successful_response_extraction(monkeypatch):
    monkeypatch.delenv(DEFAULT_MODEL_ENV, raising=False)
    make_urlopen_sequence(
        monkeypatch,
        [
            models_payload(DEFAULT_MODEL_PREFERENCE_ORDER[0]),
            chat_payload('{"action":"noop"}'),
        ],
    )

    client = FoundryLocalClient(base_url="http://127.0.0.1:53402", timeout_seconds=1)
    response = client.chat_completion("Return a no-op action.")

    assert response.success is True
    assert response.raw_text == '{"action":"noop"}'
    assert response.error_type is None
    assert response.latency_ms is not None


def test_timeout_fails_closed(monkeypatch):
    make_urlopen_sequence(monkeypatch, [TimeoutError("timed out")])

    client = FoundryLocalClient(base_url="http://127.0.0.1:53402", timeout_seconds=0.01)
    response = client.chat_completion("Test.")

    assert response.success is False
    assert response.error_type == "timeout"
    assert response.raw_text is None


def test_http_error_fails_closed(monkeypatch):
    http_error = urllib_error.HTTPError(
        url="http://127.0.0.1:53402/v1/models",
        code=500,
        msg="Internal Server Error",
        hdrs=None,
        fp=None,
    )
    make_urlopen_sequence(monkeypatch, [http_error])

    client = FoundryLocalClient(base_url="http://127.0.0.1:53402", timeout_seconds=1)
    response = client.chat_completion("Test.")

    assert response.success is False
    assert response.error_type == "http_error"
    assert "HTTP 500" in response.error_message


def test_endpoint_unavailable_fails_closed(monkeypatch):
    make_urlopen_sequence(monkeypatch, [urllib_error.URLError("connection refused")])

    client = FoundryLocalClient(base_url="http://127.0.0.1:53402", timeout_seconds=1)
    response = client.chat_completion("Test.")

    assert response.success is False
    assert response.error_type == "endpoint_unavailable"
    assert response.raw_text is None


def test_empty_model_list_fails_closed(monkeypatch):
    monkeypatch.delenv(DEFAULT_MODEL_ENV, raising=False)
    make_urlopen_sequence(monkeypatch, [{"object": "list", "data": []}])

    client = FoundryLocalClient(base_url="http://127.0.0.1:53402", timeout_seconds=1)
    response = client.chat_completion("Test.")

    assert response.success is False
    assert response.error_type == "empty_model_list"
    assert response.raw_text is None


def test_no_preferred_model_available_fails_closed(monkeypatch):
    monkeypatch.delenv(DEFAULT_MODEL_ENV, raising=False)
    make_urlopen_sequence(monkeypatch, [models_payload("gpt-oss-20b-generic-cpu:1")])

    client = FoundryLocalClient(base_url="http://127.0.0.1:53402", timeout_seconds=1)
    response = client.chat_completion("Test.")

    assert response.success is False
    assert response.error_type == "no_preferred_model_available"
    assert response.raw_text is None


def test_no_choices_response_fails_closed(monkeypatch):
    monkeypatch.delenv(DEFAULT_MODEL_ENV, raising=False)
    make_urlopen_sequence(
        monkeypatch,
        [
            models_payload(DEFAULT_MODEL_PREFERENCE_ORDER[0]),
            {"id": "fake", "choices": []},
        ],
    )

    client = FoundryLocalClient(base_url="http://127.0.0.1:53402", timeout_seconds=1)
    response = client.chat_completion("Test.")

    assert response.success is False
    assert response.error_type == "empty_model_response"
    assert response.raw_text is None


def test_empty_text_response_fails_closed(monkeypatch):
    monkeypatch.delenv(DEFAULT_MODEL_ENV, raising=False)
    make_urlopen_sequence(
        monkeypatch,
        [
            models_payload(DEFAULT_MODEL_PREFERENCE_ORDER[0]),
            chat_payload(""),
        ],
    )

    client = FoundryLocalClient(base_url="http://127.0.0.1:53402", timeout_seconds=1)
    response = client.chat_completion("Test.")

    assert response.success is False
    assert response.error_type == "empty_model_response"
    assert response.raw_text is None


def test_missing_base_url_fails_closed(monkeypatch):
    monkeypatch.delenv("FOUNDRY_LOCAL_BASE_URL", raising=False)

    client = FoundryLocalClient(base_url="", timeout_seconds=1)
    response = client.chat_completion("Test.")

    assert response.success is False
    assert response.error_type == "missing_base_url"
    assert response.raw_text is None


def test_list_model_aliases_success(monkeypatch):
    make_urlopen_sequence(
        monkeypatch,
        [models_payload(DEFAULT_MODEL_PREFERENCE_ORDER[0], "other-model")],
    )

    client = FoundryLocalClient(base_url="http://127.0.0.1:53402", timeout_seconds=1)
    response = client.list_model_aliases()

    assert response.success is True
    assert DEFAULT_MODEL_PREFERENCE_ORDER[0] in response.raw_text
    assert response.error_type is None
