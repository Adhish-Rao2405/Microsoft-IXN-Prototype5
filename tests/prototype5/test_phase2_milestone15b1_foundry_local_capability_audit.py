from __future__ import annotations

import json
import shutil
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from scripts.prototype5 import run_foundry_local_capability_audit as audit


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "prototype5" / "run_foundry_local_capability_audit.py"
DOC_PATH = ROOT / "docs" / "prototype5" / "phase2_milestone15b1_foundry_local_capability_audit.md"
SUMMARY_JSON = (
    ROOT
    / "results"
    / "prototype5"
    / "mode_voice"
    / "phase2_milestone15b1_foundry_local_capability_audit_summary.json"
)
SUMMARY_MD = (
    ROOT
    / "results"
    / "prototype5"
    / "mode_voice"
    / "phase2_milestone15b1_foundry_local_capability_audit_summary.md"
)

BINARY_AUDIO_SUFFIXES = {".wav", ".mp3", ".flac", ".m4a", ".aac", ".ogg"}
DEPENDENCY_OR_ENV_FILES = {
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    "package.json",
    "package-lock.json",
    "Dockerfile",
    "docker-compose.yml",
    ".env",
}


@contextmanager
def workspace_tmp_dir():
    path = ROOT / ".pytest_m15b1_tmp" / uuid4().hex
    path.mkdir(parents=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def fake_cli_without_executable(timeout_seconds: float) -> dict:
    command_results = {
        name: {
            "attempted": False,
            "command": command,
            "returncode": None,
            "timeout_seconds": timeout_seconds,
            "timed_out": False,
            "stdout": "",
            "stderr": "",
            "stdout_truncated": False,
            "stderr_truncated": False,
            "error": "foundry CLI was not found on PATH.",
            "failure_classification": "CLI_EXECUTABLE_NOT_FOUND",
            "cli_process_status": "CLI_EXECUTABLE_NOT_FOUND",
            "parsed_result": "",
        }
        for name, command in audit.CANONICAL_CLI_COMMANDS.items()
    }
    return {
        "foundry_cli_present": False,
        "foundry_cli_path": "",
        "foundry_cli_visibility": "CLI_NOT_FOUND",
        "foundry_cli_invocation_usable": False,
        "foundry_cli_command_results": command_results,
        "foundry_version": "",
        "foundry_version_probe": command_results["version"],
        "foundry_help_probe": command_results["help"],
        "foundry_service_status": "",
        "foundry_service_status_probe": command_results["service_status"],
        "cli_catalogue_visible_models": [],
        "cli_catalogue_aliases": [],
        "cli_catalogue_model_ids": [],
        "cli_catalogue_task_labels": [],
        "cli_catalogue_parse_warnings": [],
        "cli_catalogue_output_complete": False,
        "cli_catalogue_output_truncated": False,
        "cli_catalogue_semantic_status": "CLI_CATALOGUE_NOT_ATTEMPTED",
    }


def test_script_exists():
    assert SCRIPT.exists()


def test_docs_and_committed_summaries_exist():
    assert DOC_PATH.exists()
    assert SUMMARY_JSON.exists()
    assert SUMMARY_MD.exists()


def test_sdk_compatibility_is_tri_state_without_unsupported_threshold():
    assert audit.classify_sdk_version(None, package_detected=False, module_importable=False) == (
        "NOT_ASSESSABLE_SDK_NOT_DETECTED"
    )
    assert audit.classify_sdk_version("1.0.0", package_detected=True, module_importable=True) == (
        "CURRENT_PYTHON_SDK_1_X_DETECTED"
    )
    assert audit.classify_sdk_version("0.5.1", package_detected=True, module_importable=True) == (
        "LEGACY_OR_PRE_CURRENT_SDK_DETECTED"
    )


def test_model_candidate_classification():
    chat, stt = audit.classify_model_candidates(
        [
            "qwen2.5-0.5b",
            "phi-4-mini",
            "openai-whisper-tiny-generic-cpu:2",
            "nemotron-speech-streaming-en-0.6b",
        ]
    )
    assert "qwen2.5-0.5b" in chat
    assert "phi-4-mini" in chat
    assert "openai-whisper-tiny-generic-cpu:2" in stt
    assert "nemotron-speech-streaming-en-0.6b" in stt


def test_strict_stt_classification_excludes_chat_phi_and_qwen_tokens():
    _, stt = audit.classify_model_candidates(
        [
            "chat",
            "phi-4-mini-reasoning",
            "Phi-4-mini-reasoning-generic-cpu:3",
            "qwen2.5-0.5b",
            "qwen2.5-0.5b-instruct-generic-cpu:4",
            "qwen2.5-coder-0.5b",
            "openai-whisper-tiny-generic-cpu:2",
            "whisper-tiny",
            "nemotron-speech-streaming-en-0.6b",
        ]
    )

    assert stt == [
        "openai-whisper-tiny-generic-cpu:2",
        "whisper-tiny",
        "nemotron-speech-streaming-en-0.6b",
    ]


def test_cli_catalogue_parser_separates_aliases_tasks_model_ids_and_warnings():
    payload = audit.parse_cli_catalogue(
        "\n".join(
            [
                "[11:44:58 ERR] Failed to process model #0 on page 1.",
                "Alias                          Device     Task           File Size    License      Model ID",
                "qwen2.5-coder-0.5b             GPU        chat, tools    0.52 GB      apache-2.0   qwen2.5-coder-0.5b-instruct-generic-gpu:4",
                "                               CPU        chat, tools    0.80 GB      apache-2.0   qwen2.5-coder-0.5b-instruct-generic-cpu:4",
                "phi-4-mini-reasoning           CPU        chat           4.52 GB      MIT          Phi-4-mini-reasoning-generic-cpu:3",
            ]
        )
    )

    assert payload["cli_catalogue_aliases"] == ["qwen2.5-coder-0.5b", "phi-4-mini-reasoning"]
    assert payload["cli_catalogue_task_labels"] == ["chat", "tools"]
    assert "chat" not in payload["cli_catalogue_model_ids"]
    assert "qwen2.5-coder-0.5b-instruct-generic-cpu:4" in payload["cli_catalogue_model_ids"]
    assert payload["cli_catalogue_parse_warnings"]
    assert payload["cli_catalogue_output_complete"] is False
    assert payload["cli_catalogue_semantic_status"] == "CLI_CATALOGUE_COMPLETED_WITH_PROCESSING_WARNINGS"


def test_cli_catalogue_truncation_is_recorded_explicitly():
    payload = audit.parse_cli_catalogue(
        "qwen2.5-0.5b                   CPU        chat, tools    0.80 GB      apache-2.0   qwen2.5-0.5b-instruct-generic-cpu:4",
        output_was_truncated=True,
    )

    assert payload["cli_catalogue_output_truncated"] is True
    assert payload["cli_catalogue_output_complete"] is False
    assert payload["cli_catalogue_semantic_status"] == "CLI_CATALOGUE_OUTPUT_TRUNCATED"


def test_structured_task_metadata_can_identify_audio_transcription():
    assert audit.strict_stt_model_candidate("vendor-model:1", task="audio-transcription") is True
    assert audit.strict_stt_model_candidate("qwen2.5-0.5b", task="chat") is False


def test_environment_base_url_overrides_fallback():
    resolved = audit.resolve_base_url("http://localhost:12345/")

    assert resolved["base_url"] == "http://localhost:12345"
    assert resolved["base_url_source"] == "ENVIRONMENT"
    assert resolved["environment_override_present"] is True
    assert resolved["environment_base_url_valid"] is True


def test_missing_environment_base_url_selects_project_fallback():
    resolved = audit.resolve_base_url(None)

    assert resolved["base_url"] == "http://127.0.0.1:53402"
    assert resolved["base_url_source"] == "PROJECT_PREVIOUSLY_EVIDENCED_FALLBACK"
    assert resolved["environment_override_present"] is False


def test_invalid_environment_base_url_falls_back_conservatively():
    resolved = audit.resolve_base_url("https://example.com:443")

    assert resolved["base_url"] == "http://127.0.0.1:53402"
    assert resolved["base_url_source"] == "PROJECT_PREVIOUSLY_EVIDENCED_FALLBACK"
    assert resolved["environment_override_present"] is True
    assert resolved["environment_base_url_valid"] is False


def test_fallback_generates_expected_models_endpoint(monkeypatch):
    captured_urls: list[str] = []

    def fake_get_json(url: str, timeout_seconds: float):
        captured_urls.append(url)
        return {
            "reachable": True,
            "http_status": 200,
            "payload": {"data": []},
            "attempted": True,
            "error": "",
        }

    monkeypatch.setattr(audit, "get_json", fake_get_json)
    monkeypatch.setattr(audit, "probe_audio_transcription_route", lambda *_: {"classification": "NOT_PROBED_TEST"})

    summary = audit.audit_http_endpoint(audit.resolve_base_url(None), timeout_seconds=0.1)

    assert summary["models_endpoint"] == "http://127.0.0.1:53402/v1/models"
    assert captured_urls == [
        "http://127.0.0.1:53402/openai/status",
        "http://127.0.0.1:53402/v1/models",
    ]


def test_successful_fallback_endpoint_response(monkeypatch):
    def fake_get_json(url: str, timeout_seconds: float):
        return {
            "reachable": True,
            "http_status": 200,
            "payload": {
                "data": [
                    {"id": "openai-whisper-tiny-generic-cpu:2"},
                    {"id": "nemotron-speech-streaming-en-0.6b"},
                    {"id": "qwen2.5-0.5b"},
                ]
            },
            "attempted": True,
            "error": "",
        }

    monkeypatch.setattr(audit, "get_json", fake_get_json)
    monkeypatch.setattr(audit, "probe_audio_transcription_route", lambda *_: {"classification": "NOT_PROBED_TEST"})

    summary = audit.audit_http_endpoint(audit.resolve_base_url(None), timeout_seconds=0.1)

    assert summary["models_endpoint_reachable"] is True
    assert summary["models_endpoint_http_status"] == 200
    assert summary["openai_whisper_tiny_generic_cpu_visible"] is True
    assert summary["nemotron_speech_streaming_visible"] is True
    assert "qwen2.5-0.5b" in summary["chat_model_candidates"]


def test_fallback_connection_refusal_classification(monkeypatch):
    def fake_get_json(url: str, timeout_seconds: float):
        return {
            "reachable": False,
            "http_status": None,
            "payload": {},
            "attempted": True,
            "error": "URLError: <urlopen error [WinError 10061] No connection could be made because the target machine actively refused it>",
        }

    monkeypatch.setattr(audit, "get_json", fake_get_json)

    summary = audit.audit_http_endpoint(audit.resolve_base_url(None), timeout_seconds=0.1)

    assert summary["models_endpoint_reachable"] is False
    assert summary["models_endpoint_failure_classification"] == "REST_MODELS_ENDPOINT_CONNECTION_REFUSED"


def test_fallback_timeout_classification(monkeypatch):
    def fake_get_json(url: str, timeout_seconds: float):
        return {
            "reachable": False,
            "http_status": None,
            "payload": {},
            "attempted": True,
            "error": "TimeoutError: timed out",
        }

    monkeypatch.setattr(audit, "get_json", fake_get_json)

    summary = audit.audit_http_endpoint(audit.resolve_base_url(None), timeout_seconds=0.1)

    assert summary["models_endpoint_failure_classification"] == "REST_MODELS_ENDPOINT_TIMEOUT"


def test_options_audio_route_probe_is_non_conclusive(monkeypatch):
    class FakeHTTP404(audit.urllib_error.HTTPError):
        def __init__(self):
            super().__init__(
                "http://127.0.0.1:53402/v1/audio/transcriptions",
                404,
                "Not Found",
                {},
                None,
            )

    def fake_urlopen(req, timeout):
        assert req.get_method() == "OPTIONS"
        raise FakeHTTP404()

    monkeypatch.setattr(audit.urllib_request, "urlopen", fake_urlopen)

    probe = audit.probe_audio_transcription_route(
        "http://127.0.0.1:53402",
        ["openai-whisper-tiny-generic-cpu:2"],
        timeout_seconds=0.1,
    )

    assert probe["method"] == "OPTIONS"
    assert probe["path"] == "/v1/audio/transcriptions"
    assert probe["http_status"] == 404
    assert probe["classification"] == "OPTIONS_PROBE_HTTP_404_NON_CONCLUSIVE"
    assert probe["audio_payload_submitted"] is False
    assert probe["transcription_attempted"] is False
    assert probe["transcription_usability_tested"] is False


def test_canonical_cli_command_construction():
    assert audit.CANONICAL_CLI_COMMANDS["version"] == ["foundry", "--version"]
    assert audit.CANONICAL_CLI_COMMANDS["help"] == ["foundry", "--help"]
    assert audit.CANONICAL_CLI_COMMANDS["model_list"] == ["foundry", "model", "list"]


def test_cli_logon_session_failure_classification():
    result = {
        "attempted": True,
        "returncode": None,
        "stdout": "",
        "stderr": "",
        "error": "OSError: [WinError 1312] A specified logon session does not exist.",
    }

    assert audit.classify_command_failure(result) == "CLI_INVOCATION_BLOCKED_WINDOWS_LOGON_SESSION"


def test_cli_presence_is_separate_from_invocation_usability(monkeypatch):
    def fake_which(name: str):
        return "C:/fake/foundry.exe"

    def fake_run_command(command: list[str], timeout_seconds: float):
        return {
            "command": command,
            "attempted": True,
            "returncode": None,
            "timeout_seconds": timeout_seconds,
            "timed_out": False,
            "stdout": "",
            "stderr": "",
            "stdout_truncated": False,
            "stderr_truncated": False,
            "error": "OSError: [WinError 1312] A specified logon session does not exist.",
            "failure_classification": "CLI_INVOCATION_BLOCKED_WINDOWS_LOGON_SESSION",
            "cli_process_status": "CLI_INVOCATION_BLOCKED_WINDOWS_LOGON_SESSION",
        }

    monkeypatch.setattr(audit.shutil, "which", fake_which)
    monkeypatch.setattr(audit, "run_command", fake_run_command)

    summary = audit.audit_foundry_cli(timeout_seconds=0.1)

    assert summary["foundry_cli_present"] is True
    assert summary["foundry_cli_visibility"] == "CLI_SHIM_PRESENT"
    assert summary["foundry_cli_invocation_usable"] is False
    assert summary["foundry_cli_command_results"]["version"]["failure_classification"] == (
        "CLI_INVOCATION_BLOCKED_WINDOWS_LOGON_SESSION"
    )


def test_script_can_run_without_foundry_local_env(monkeypatch):
    monkeypatch.delenv("FOUNDRY_LOCAL_BASE_URL", raising=False)
    monkeypatch.setattr(audit, "audit_foundry_cli", fake_cli_without_executable)

    def fake_get_json(url: str, timeout_seconds: float):
        return {
            "reachable": False,
            "http_status": None,
            "payload": {},
            "attempted": True,
            "error": "URLError: <urlopen error [WinError 10061] actively refused>",
        }

    monkeypatch.setattr(audit, "get_json", fake_get_json)

    with workspace_tmp_dir() as work_dir:
        payload = audit.run_audit(
            work_dir / "summary.json",
            work_dir / "summary.md",
            timeout_seconds=0.1,
        )

        assert (work_dir / "summary.json").exists()
        assert (work_dir / "summary.md").exists()

    assert payload["foundry_base_url_configured"] is False
    assert payload["base_url"] == "http://127.0.0.1:53402"
    assert payload["base_url_source"] == "PROJECT_PREVIOUSLY_EVIDENCED_FALLBACK"
    assert payload["models_endpoint"] == "http://127.0.0.1:53402/v1/models"
    assert payload["models_endpoint_reachable"] is False
    assert payload["model_download_attempted"] is False
    assert payload["model_load_attempted"] is False
    assert payload["real_stt_attempted"] is False
    assert payload["speech_to_text_used"] is False
    assert payload["inference_attempted"] is False
    assert payload["transcription_attempted"] is False


def test_sdk_distribution_detection_covers_winml_and_cross_platform(monkeypatch):
    versions = {
        "foundry-local-sdk-winml": "1.2.3",
        "foundry-local-sdk": None,
        "foundry-local-core": None,
    }

    monkeypatch.setattr(audit, "audit_foundry_cli", fake_cli_without_executable)
    monkeypatch.setattr(audit, "module_available", lambda name: name == "foundry_local_sdk")
    monkeypatch.setattr(audit, "distribution_version", lambda name: versions.get(name))
    monkeypatch.setattr(
        audit,
        "audit_sdk_catalog",
        lambda *_: {
            "sdk_catalog_probe_attempted": False,
            "sdk_catalog_probe_error": "mocked",
            "sdk_catalog_model_aliases": [],
            "sdk_nemotron_speech_streaming_visible": False,
            "sdk_audio_client_route_discoverable": False,
        },
    )
    monkeypatch.setattr(
        audit,
        "audit_http_endpoint",
        lambda *_: {
            "foundry_base_url_configured": False,
            "base_url": "http://127.0.0.1:53402",
            "base_url_source": "PROJECT_PREVIOUSLY_EVIDENCED_FALLBACK",
            "environment_override_present": False,
            "environment_base_url_value": "",
            "environment_base_url_valid": False,
            "environment_base_url_rejected_reason": "",
            "foundry_base_url": "http://127.0.0.1:53402",
            "status_endpoint": "http://127.0.0.1:53402/openai/status",
            "status_endpoint_attempted": True,
            "status_endpoint_reachable": True,
            "status_endpoint_http_status": 200,
            "status_endpoint_error": "",
            "models_endpoint": "http://127.0.0.1:53402/v1/models",
            "models_endpoint_attempted": True,
            "models_endpoint_reachable": True,
            "models_endpoint_http_status": 200,
            "models_endpoint_error": "",
            "models_endpoint_failure_classification": "REST_MODELS_ENDPOINT_REACHABLE",
            "model_ids": ["openai-whisper-tiny-generic-cpu:2"],
            "chat_model_candidates": [],
            "stt_audio_model_candidates": ["openai-whisper-tiny-generic-cpu:2"],
            "openai_whisper_tiny_generic_cpu_visible": True,
            "nemotron_speech_streaming_visible": False,
            "openai_compatible_models_route_available": True,
            "openai_compatible_audio_transcription_route_probe": {
                "method": "OPTIONS",
                "path": "/v1/audio/transcriptions",
                "http_status": 404,
                "classification": "OPTIONS_PROBE_HTTP_404_NON_CONCLUSIVE",
                "audio_payload_submitted": False,
                "transcription_attempted": False,
                "transcription_usability_tested": False,
            },
            "openai_compatible_audio_transcription_route_probe_status": "OPTIONS_PROBE_HTTP_404_NON_CONCLUSIVE",
        },
    )

    payload = audit.build_summary(timeout_seconds=0.1)

    assert payload["python_distribution_surface"]["foundry-local-sdk-winml"] == "1.2.3"
    assert payload["python_distribution_surface"]["foundry-local-sdk"] is None
    assert payload["sdk_version"] == "1.2.3"
    assert payload["sdk_version_compatible"] is None
    assert payload["sdk_version_compatibility"] == "CURRENT_PYTHON_SDK_1_X_DETECTED"
    assert payload["minimum_required_sdk_version"] is None
    assert payload["sdk_requirement_basis"] == "NO_PROJECT_SPECIFIC_MINIMUM_ESTABLISHED"


def test_user_path_and_mojibake_are_sanitised(monkeypatch):
    monkeypatch.setenv("USERPROFILE", r"C:\Users\reach")
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\reach\AppData\Local")

    text = audit.sanitise_output(
        r"C:\Users\reach\AppData\Local\Microsoft\WindowsApps\foundry.EXE ðŸš€ ðŸŸ¢"
    )

    assert r"C:\Users\reach" not in text
    assert "%LOCALAPPDATA%\\Microsoft\\WindowsApps\\foundry.EXE" in text
    assert "ðŸš€" not in text
    assert "ðŸŸ¢" not in text
    assert "[START]" in text
    assert "[RUNNING]" in text


def test_service_status_endpoint_confirmation_is_separate():
    assert audit.extract_service_status_base_url(
        "[RUNNING] Model management service is running on http://127.0.0.1:53402/openai/status"
    ) == "http://127.0.0.1:53402"


def test_generated_evidence_does_not_persist_personal_paths_or_mojibake():
    combined = SUMMARY_JSON.read_text(encoding="utf-8") + SUMMARY_MD.read_text(encoding="utf-8")

    assert r"C:\Users\reach" not in combined
    assert "ðŸš€" not in combined
    assert "ðŸŸ¢" not in combined


def test_default_audit_outputs_are_limited_to_m15b1_summaries():
    assert audit.DEFAULT_SUMMARY_JSON == SUMMARY_JSON
    assert audit.DEFAULT_SUMMARY_MD == SUMMARY_MD


def test_summary_json_and_markdown_are_produced():
    with workspace_tmp_dir() as work_dir:
        summary = {
            "status": "COMPLETE_FOUNDRY_LOCAL_CAPABILITY_AUDIT_WITH_RUNTIME_GAPS",
            "timestamp_utc": "2026-07-16T00:00:00Z",
            "milestone": "Phase 2 Milestone 15B.1",
            "mode": "foundry_local_version_and_capability_audit",
        }
        audit.write_summary_json(work_dir / "summary.json", summary)
        (work_dir / "summary.md").write_text("# Summary\n", encoding="utf-8")

        assert (work_dir / "summary.json").exists()
        assert (work_dir / "summary.md").exists()


def test_committed_summary_records_no_runtime_or_robot_scope():
    payload = json.loads(SUMMARY_JSON.read_text(encoding="utf-8"))

    assert payload["milestone"] == "Phase 2 Milestone 15B.1"
    assert payload["target_nemotron_model_alias"] == "nemotron-speech-streaming-en-0.6b"
    assert payload["status"] == "COMPLETE_FOUNDRY_LOCAL_CAPABILITY_AUDIT_WITH_RUNTIME_GAPS"
    assert payload["dependency_changes"] is False
    assert payload["model_download_attempted"] is False
    assert payload["model_load_attempted"] is False
    assert payload["inference_attempted"] is False
    assert payload["transcription_attempted"] is False
    assert payload["runtime_inference_usability"] == "NOT_TESTED_BY_M15B1"
    assert payload["runtime_transcription_usability"] == "NOT_TESTED_BY_M15B1"
    assert payload["real_stt_attempted"] is False
    assert payload["speech_to_text_used"] is False
    assert payload["fake_transcripts_generated"] is False
    assert payload["live_microphone_used"] is False
    assert payload["planner_called"] is False
    assert payload["validators_called"] is False
    assert payload["robot_execution_attempted"] is False
    assert payload["binary_audio_files_committed"] is False


def test_neutral_top_level_completion_status():
    summary = {
        "audit_error": "",
        "foundry_local_sdk_importable": False,
        "foundry_local_sdk_version": None,
        "sdk_version_compatible": False,
        "models_endpoint_reachable": True,
        "nemotron_speech_streaming_visible": False,
        "sdk_nemotron_speech_streaming_visible": False,
        "sdk_catalog_probe_attempted": False,
    }
    assert audit.classify_summary(summary) == "COMPLETE_FOUNDRY_LOCAL_CAPABILITY_AUDIT_WITH_RUNTIME_GAPS"


def test_status_classification_for_ready_case():
    summary = {
        "audit_error": "",
        "foundry_local_sdk_importable": True,
        "foundry_local_sdk_version": "1.0.0",
        "sdk_version_compatible": None,
        "sdk_version_compatibility": "CURRENT_PYTHON_SDK_1_X_DETECTED",
        "models_endpoint_reachable": True,
        "nemotron_speech_streaming_visible": True,
        "sdk_nemotron_speech_streaming_visible": False,
        "sdk_catalog_probe_attempted": True,
    }
    assert audit.classify_summary(summary) == "COMPLETE_FOUNDRY_LOCAL_CAPABILITY_AUDIT_WITH_RUNTIME_GAPS"


def test_structured_runtime_gap_codes():
    summary = {
        "current_foundry_local_sdk_distribution_detected": False,
        "foundry_local_sdk_importable": False,
        "cli_catalogue_semantic_status": "CLI_CATALOGUE_COMPLETED_WITH_PROCESSING_WARNINGS",
        "foundry_cli_command_results": {
            "version": {
                "attempted": True,
                "failure_classification": "CLI_INVOCATION_BLOCKED_WINDOWS_LOGON_SESSION",
            },
            "model_list": {
                "attempted": True,
                "failure_classification": "CLI_INVOCATION_BLOCKED_WINDOWS_LOGON_SESSION",
            },
        },
        "foundry_cli_present": True,
        "foundry_version_probe": {
            "failure_classification": "CLI_INVOCATION_BLOCKED_WINDOWS_LOGON_SESSION"
        },
        "models_endpoint_reachable": False,
        "models_endpoint_failure_classification": "REST_MODELS_ENDPOINT_UNREACHABLE",
        "openai_whisper_tiny_generic_cpu_visible": False,
        "nemotron_speech_streaming_visible": False,
        "sdk_nemotron_speech_streaming_visible": False,
    }

    gaps = audit.build_gap_codes(summary)

    assert "CURRENT_PYTHON_SDK_DISTRIBUTION_NOT_DETECTED_IN_ACTIVE_INTERPRETER" in gaps
    assert "PYTHON_SDK_MODULE_NOT_IMPORTABLE" in gaps
    assert "CLI_INVOCATION_BLOCKED_WINDOWS_LOGON_SESSION" in gaps
    assert "CLI_CATALOGUE_PARTIAL_OR_DEGRADED" in gaps
    assert "REST_MODELS_ENDPOINT_UNREACHABLE" in gaps
    assert "WHISPER_VISIBILITY_NOT_CONFIRMED" in gaps
    assert "NEMOTRON_VISIBILITY_NOT_CONFIRMED" in gaps
    assert "RUNTIME_INFERENCE_USABILITY_NOT_TESTED" not in gaps
    assert "RUNTIME_TRANSCRIPTION_USABILITY_NOT_TESTED" not in gaps


def test_m15b3_remains_on_hold():
    summary = {
        "runtime_gap_codes": [
            "CURRENT_PYTHON_SDK_DISTRIBUTION_NOT_DETECTED_IN_ACTIVE_INTERPRETER",
            "PYTHON_SDK_MODULE_NOT_IMPORTABLE",
            "NEMOTRON_VISIBILITY_NOT_CONFIRMED",
            "REST_MODELS_ENDPOINT_UNREACHABLE",
            "CLI_CATALOGUE_PARTIAL_OR_DEGRADED",
        ]
    }

    readiness = audit.build_m15b3_hold(summary)

    assert readiness["must_remain_on_hold"] is True
    assert any("No current Foundry Local Python SDK distribution" in reason for reason in readiness["hold_reasons"])
    assert any("Nemotron model visibility is not confirmed" in reason for reason in readiness["hold_reasons"])
    assert any("WAV/PCM readiness" in reason for reason in readiness["hold_reasons"])


def test_documentation_keeps_audit_as_discovery_only():
    text = DOC_PATH.read_text(encoding="utf-8")

    assert "discovery only" in text
    assert "nemotron-speech-streaming-en-0.6b" in text
    assert "does not prove working voice control" in text
    forbidden_claims = [
        "Nemotron STT is implemented.",
        "The system supports live voice control.",
        "The robot can be controlled by speech.",
        "Emergency stop is implemented.",
        "Real robot execution is supported.",
        "The system is production ready.",
    ]
    for claim in forbidden_claims:
        assert claim not in text


def test_no_binary_audio_files_are_committed():
    tracked_audio_sample_paths = [ROOT / "data/prototype5/mode_voice/audio_samples/README.md"]

    assert not any(path.suffix.lower() in BINARY_AUDIO_SUFFIXES for path in tracked_audio_sample_paths)


def test_protected_draft_dependencies_and_config_are_not_staged():
    staged: set[str] = set()

    assert "dissertation_drafts/DISS_DRAFT_cleaned.tex" not in staged
    assert not any(path in DEPENDENCY_OR_ENV_FILES for path in staged)
    assert not any(path.startswith(".github/") for path in staged)
