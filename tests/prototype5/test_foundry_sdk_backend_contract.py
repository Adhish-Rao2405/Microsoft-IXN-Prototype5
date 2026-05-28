import json
from pathlib import Path
import shutil

from scripts.prototype5.smoke_foundry_sdk_backend import (
    ARCHITECTURAL_BOUNDARY,
    run_smoke,
    write_json_summary,
    write_markdown_summary,
)
from src.prototype5.foundry_sdk_backend import FoundrySDKBackend, ModelBackendResponse
from src.prototype5.foundry_sdk_client import FoundryClientResponse


class FakeFoundryClient:
    def __init__(self, response):
        self.response = response

    def chat_completion(self, user_prompt, system_prompt=None, temperature=0.0, max_tokens=256):
        return self.response


def client_response(raw_text='{"status":"ok","action":"noop"}'):
    return FoundryClientResponse(
        success=True,
        backend="foundry_local_openai_compatible",
        base_url="http://127.0.0.1:53402",
        model_alias="qwen2.5-coder-0.5b-instruct-generic-cpu:4",
        raw_text=raw_text,
        latency_ms=10.5,
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
        latency_ms=2.0,
        error_type="endpoint_unavailable",
        error_message="connection refused",
        response_payload=None,
        timestamp_utc="2026-05-28T00:00:00+00:00",
    )


def test_successful_backend_response_preserves_raw_text_exactly():
    raw_text = '  {"status":"ok","action":"noop"}  '
    backend = FoundrySDKBackend(client=FakeFoundryClient(client_response(raw_text=raw_text)))

    response = backend.generate("Smoke prompt")

    assert response.raw_text == raw_text


def test_backend_metadata_is_preserved():
    backend = FoundrySDKBackend(client=FakeFoundryClient(client_response()))

    response = backend.generate("Smoke prompt")

    assert response.backend == "foundry_local_openai_compatible"
    assert response.model_alias == "qwen2.5-coder-0.5b-instruct-generic-cpu:4"
    assert response.latency_ms == 10.5
    assert response.success is True
    assert response.error_type is None
    assert response.error_message is None


def test_sdk_failure_maps_fail_closed_without_fake_raw_text():
    backend = FoundrySDKBackend(client=FakeFoundryClient(failed_client_response()))

    response = backend.generate("Smoke prompt")

    assert response.success is False
    assert response.raw_text is None
    assert response.error_type == "endpoint_unavailable"


def test_no_validation_fields_are_invented():
    response = ModelBackendResponse(
        backend="foundry_local_openai_compatible",
        model_alias="model",
        prompt_id="prompt",
        raw_text='{"status":"ok"}',
        success=True,
        latency_ms=1.0,
        error_type=None,
        error_message=None,
        timestamp_utc="2026-05-28T00:00:00+00:00",
    )

    fields = set(response.__dataclass_fields__)

    assert "schema_valid" not in fields
    assert "semantic_valid" not in fields
    assert "safety_valid" not in fields
    assert "execution_eligible" not in fields
    assert "validated" not in fields
    assert "repaired" not in fields


def test_no_execution_authority_leaks_into_backend_output():
    backend = FoundrySDKBackend(client=FakeFoundryClient(client_response()))

    response = backend.generate("Smoke prompt")

    assert not hasattr(response, "execution_eligible")
    assert not hasattr(response, "safety_valid")


def test_smoke_summary_records_architectural_boundary_without_validation():
    backend = FoundrySDKBackend(client=FakeFoundryClient(client_response()))

    summary = run_smoke(
        backend=backend,
        base_url="http://127.0.0.1:53402",
        model_alias="qwen2.5-coder-0.5b-instruct-generic-cpu:4",
    )

    assert summary["status"] == "COMPLETE_BACKEND_SMOKE"
    assert summary["prompt_count"] == 1
    assert summary["success_count"] == 1
    assert summary["failure_count"] == 0
    assert summary["architectural_boundary"] == ARCHITECTURAL_BOUNDARY
    assert summary["architectural_boundary"]["parses_json"] is False
    assert summary["architectural_boundary"]["infers_execution_eligibility"] is False
    assert summary["results"][0]["raw_text"] == '{"status":"ok","action":"noop"}'


def test_smoke_summary_missing_model_env_is_structured_failure():
    summary = run_smoke(
        backend=None,
        base_url="http://127.0.0.1:53402",
        model_alias="",
    )

    assert summary["status"] == "COMPLETE_BACKEND_SMOKE"
    assert summary["success_count"] == 0
    assert summary["failure_count"] == 1
    assert summary["results"][0]["success"] is False
    assert summary["results"][0]["raw_text"] is None
    assert summary["results"][0]["error_type"] == "missing_model_env"


def test_smoke_writers_create_machine_and_examiner_readable_outputs():
    backend = FoundrySDKBackend(client=FakeFoundryClient(client_response()))
    summary = run_smoke(
        backend=backend,
        base_url="http://127.0.0.1:53402",
        model_alias="qwen2.5-coder-0.5b-instruct-generic-cpu:4",
    )
    output_dir = Path(".pytest_cache") / "mode_sdk_contract_test"
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    json_path = write_json_summary(summary, output_dir / "backend_smoke_summary.json")
    md_path = write_markdown_summary(summary, output_dir / "backend_smoke_summary.md")

    decoded = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = md_path.read_text(encoding="utf-8")

    assert decoded["status"] == "COMPLETE_BACKEND_SMOKE"
    assert decoded["architectural_boundary"]["validates_schema"] is False
    assert "# Foundry SDK Backend Smoke Summary" in markdown
    assert "bounded adapter smoke test only" in markdown

    shutil.rmtree(output_dir)
