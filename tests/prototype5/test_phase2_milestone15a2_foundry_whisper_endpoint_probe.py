import json
import shutil
import subprocess
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from scripts.prototype5 import probe_foundry_whisper_transcription_endpoint as endpoint_probe


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "prototype5" / "probe_foundry_whisper_transcription_endpoint.py"
DOC_PATH = ROOT / "docs" / "prototype5" / "phase2_milestone15a2_foundry_whisper_endpoint_probe.md"
SUMMARY_JSON = (
    ROOT
    / "results"
    / "prototype5"
    / "mode_voice"
    / "phase2_milestone15a2_foundry_whisper_endpoint_probe_summary.json"
)
SUMMARY_MD = (
    ROOT
    / "results"
    / "prototype5"
    / "mode_voice"
    / "phase2_milestone15a2_foundry_whisper_endpoint_probe_summary.md"
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
    path = ROOT / ".pytest_m15a2_tmp" / uuid4().hex
    path.mkdir(parents=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def test_script_exists():
    assert SCRIPT.exists()


def test_docs_and_committed_summaries_exist():
    assert DOC_PATH.exists()
    assert SUMMARY_JSON.exists()
    assert SUMMARY_MD.exists()


def test_probe_is_safe_when_base_url_is_missing():
    with workspace_tmp_dir() as work_dir:
        summary = endpoint_probe.run_probe(
            work_dir / "summary.json",
            work_dir / "summary.md",
            base_url="",
            model=endpoint_probe.DEFAULT_MODEL,
            audio_dir=work_dir,
            audio_file=None,
            timeout_seconds=0.1,
        )

    assert summary["status"] == "COMPLETE_FOUNDRY_WHISPER_ENDPOINT_PROBE_BASE_URL_MISSING"
    assert summary["real_stt_attempted"] is False
    assert summary["routes_attempted"] == []


def test_404_routes_are_recorded_as_no_usable_endpoint(monkeypatch):
    with workspace_tmp_dir() as work_dir:
        audio = work_dir / "sample.m4a"
        audio.write_bytes(b"test-audio")

        monkeypatch.setattr(
            endpoint_probe,
            "get_json",
            lambda url, timeout_seconds: endpoint_probe.HttpProbeResponse(
                200,
                '{"data":[{"id":"openai-whisper-tiny-generic-cpu:2"}]}',
                1.0,
                "",
            ),
        )
        monkeypatch.setattr(
            endpoint_probe,
            "post_audio",
            lambda url, audio_path, model, timeout_seconds: endpoint_probe.HttpProbeResponse(
                404,
                "",
                1.0,
                "HTTP 404: Not Found",
            ),
        )

        summary = endpoint_probe.build_summary(
            base_url="http://127.0.0.1:53402",
            model=endpoint_probe.DEFAULT_MODEL,
            audio_path=audio,
            timeout_seconds=0.1,
        )

    assert summary["candidate_model_visible"] is True
    assert summary["status"] == "COMPLETE_FOUNDRY_WHISPER_ENDPOINT_PROBE_NO_USABLE_ENDPOINT"
    assert summary["usable_endpoint_confirmed"] is False
    assert summary["automatic_transcript"] == ""
    assert {route["http_status"] for route in summary["routes_attempted"]} == {404}


def test_2xx_transcript_like_response_is_recorded_honestly(monkeypatch):
    with workspace_tmp_dir() as work_dir:
        audio = work_dir / "sample.m4a"
        audio.write_bytes(b"test-audio")
        calls = {"count": 0}

        monkeypatch.setattr(
            endpoint_probe,
            "get_json",
            lambda url, timeout_seconds: endpoint_probe.HttpProbeResponse(
                200,
                '{"data":[{"id":"openai-whisper-tiny-generic-cpu:2"}]}',
                1.0,
                "",
            ),
        )

        def fake_post(url, audio_path, model, timeout_seconds):
            calls["count"] += 1
            if calls["count"] == 1:
                return endpoint_probe.HttpProbeResponse(200, '{"text":"Continue."}', 2.0, "")
            return endpoint_probe.HttpProbeResponse(404, "", 1.0, "HTTP 404: Not Found")

        monkeypatch.setattr(endpoint_probe, "post_audio", fake_post)

        summary = endpoint_probe.build_summary(
            base_url="http://127.0.0.1:53402",
            model=endpoint_probe.DEFAULT_MODEL,
            audio_path=audio,
            timeout_seconds=0.1,
        )

    assert summary["status"] == "COMPLETE_FOUNDRY_WHISPER_ENDPOINT_PROBE_USABLE_STT_CONFIRMED"
    assert summary["automatic_transcript"] == "Continue."
    assert summary["speech_to_text_used"] is True
    assert summary["fake_transcripts_generated"] is False


def test_committed_summary_records_bounded_safety_flags():
    payload = json.loads(SUMMARY_JSON.read_text(encoding="utf-8"))

    assert payload["milestone"] == "Phase 2 Milestone 15A.2"
    assert payload["fake_transcripts_generated"] is False
    assert payload["dependency_changes"] is False
    assert payload["live_microphone_used"] is False
    assert payload["planner_called"] is False
    assert payload["validators_called"] is False
    assert payload["robot_execution_used"] is False
    assert payload["emergency_stop_implemented"] is False
    assert payload["execution_eligible_count"] == 0
    assert payload["binary_audio_files_committed"] is False


def test_candidate_visibility_is_separate_from_endpoint_availability():
    payload = json.loads(SUMMARY_JSON.read_text(encoding="utf-8"))

    assert payload["candidate_model_visible"] is True
    assert payload["usable_endpoint_confirmed"] is False
    assert payload["automatic_transcript"] == ""


def test_documentation_contains_no_positive_robot_or_voice_claims():
    text = DOC_PATH.read_text(encoding="utf-8")
    forbidden_claims = [
        "The system supports live voice control.",
        "The robot can be controlled by speech.",
        "Emergency stop is implemented.",
        "Real robot execution is supported.",
        "The system is production ready.",
    ]
    for claim in forbidden_claims:
        assert claim not in text


def test_no_binary_audio_files_are_committed():
    completed = subprocess.run(
        ["git", "ls-files", "data/prototype5/mode_voice/audio_samples"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    tracked_audio_sample_paths = [ROOT / line for line in completed.stdout.splitlines()]

    assert not any(path.suffix.lower() in BINARY_AUDIO_SUFFIXES for path in tracked_audio_sample_paths)


def test_protected_draft_dependencies_and_config_are_not_staged():
    completed = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    staged = set(completed.stdout.splitlines())

    assert "dissertation_drafts/DISS_DRAFT_cleaned.tex" not in staged
    assert not any(path in DEPENDENCY_OR_ENV_FILES for path in staged)
    assert not any(path.startswith(".github/") for path in staged)
