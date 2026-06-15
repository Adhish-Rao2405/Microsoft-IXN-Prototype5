import json
import os
import shutil
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from scripts.prototype5 import discover_stt_backend


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "prototype5" / "discover_stt_backend.py"
DOC_PATH = ROOT / "docs" / "prototype5" / "phase2_milestone15a1_stt_backend_discovery.md"
SUMMARY_JSON = (
    ROOT
    / "results"
    / "prototype5"
    / "mode_voice"
    / "phase2_milestone15a1_stt_backend_discovery_summary.json"
)
SUMMARY_MD = (
    ROOT
    / "results"
    / "prototype5"
    / "mode_voice"
    / "phase2_milestone15a1_stt_backend_discovery_summary.md"
)

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
BINARY_AUDIO_SUFFIXES = {".wav", ".mp3", ".flac", ".m4a", ".aac", ".ogg"}


@contextmanager
def workspace_tmp_dir():
    path = ROOT / ".pytest_m15a1_tmp" / uuid4().hex
    path.mkdir(parents=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def run_discovery(work_dir: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    for name in (
        "FOUNDRY_LOCAL_BASE_URL",
        "FOUNDRY_LOCAL_MODEL",
        "FOUNDRY_LOCAL_STT_MODEL",
        "PROTOTYPE5_STT_BACKEND",
        "PROTOTYPE5_STT_MODEL",
        "WHISPER_MODEL",
    ):
        env.pop(name, None)

    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--summary-json",
            str(work_dir / "summary.json"),
            "--summary-md",
            str(work_dir / "summary.md"),
            "--timeout-seconds",
            "0.1",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )


def test_script_exists():
    assert SCRIPT.exists()


def test_docs_and_committed_summaries_exist():
    assert DOC_PATH.exists()
    assert SUMMARY_JSON.exists()
    assert SUMMARY_MD.exists()


def test_script_can_run_without_foundry_local():
    with workspace_tmp_dir() as work_dir:
        completed = run_discovery(work_dir)
        payload = json.loads((work_dir / "summary.json").read_text(encoding="utf-8"))

    assert completed.returncode == 0, completed.stderr
    assert payload["foundry_base_url_configured"] is False
    assert payload["foundry_models_endpoint_reachable"] is False
    assert payload["candidate_foundry_stt_models"] == []
    assert payload["audio_transcription_endpoint_probe_status"] == "NOT_PROBED_BASE_URL_NOT_CONFIGURED"


def test_summary_json_and_markdown_are_produced():
    with workspace_tmp_dir() as work_dir:
        completed = run_discovery(work_dir)

        assert completed.returncode == 0, completed.stderr
        assert (work_dir / "summary.json").exists()
        assert (work_dir / "summary.md").exists()


def test_discovery_records_no_runtime_stt_or_planning_scope():
    with workspace_tmp_dir() as work_dir:
        completed = run_discovery(work_dir)
        payload = json.loads((work_dir / "summary.json").read_text(encoding="utf-8"))

    assert completed.returncode == 0, completed.stderr
    assert payload["real_stt_attempted"] is False
    assert payload["speech_to_text_used"] is False
    assert payload["fake_transcripts_generated"] is False
    assert payload["dependency_changes"] is False
    assert payload["live_microphone_used"] is False
    assert payload["planner_called"] is False
    assert payload["validators_called"] is False
    assert payload["execution_eligible_count"] == 0
    assert payload["binary_audio_files_committed"] is False


def test_classification_distinguishes_foundry_candidate_with_missing_endpoint():
    status, notes = discover_stt_backend.classify_discovery(
        base_url="http://127.0.0.1:53402",
        foundry_reachable=True,
        candidate_models=["openai-whisper-tiny-generic-cpu:2"],
        endpoint_probe_status="NOT_FOUND_HTTP_404",
        recommended_backend="none",
        foundry_error="",
    )

    assert status == "COMPLETE_STT_BACKEND_DISCOVERY_CANDIDATE_FOUND_ENDPOINT_UNAVAILABLE"
    assert "exposes an STT/Whisper model candidate" in notes
    assert "NOT_FOUND_HTTP_404" in notes


def test_recommend_backend_does_not_select_foundry_when_endpoint_is_404():
    backend = discover_stt_backend.recommend_backend(
        ["openai-whisper-tiny-generic-cpu:2"],
        "NOT_FOUND_HTTP_404",
        {"whisper": None, "whisper-cli": None, "faster-whisper": None, "ffmpeg": None},
        {"whisper": False, "faster_whisper": False, "openai": False},
    )

    assert backend == "none"


def test_classification_marks_reachable_endpoint_as_candidate_found():
    backend = discover_stt_backend.recommend_backend(
        ["openai-whisper-tiny-generic-cpu:2"],
        "ENDPOINT_PRESENT_OR_PROTECTED_HTTP_405",
        {"whisper": None, "whisper-cli": None, "faster-whisper": None, "ffmpeg": None},
        {"whisper": False, "faster_whisper": False, "openai": False},
    )
    status, _ = discover_stt_backend.classify_discovery(
        base_url="http://127.0.0.1:53402",
        foundry_reachable=True,
        candidate_models=["openai-whisper-tiny-generic-cpu:2"],
        endpoint_probe_status="ENDPOINT_PRESENT_OR_PROTECTED_HTTP_405",
        recommended_backend=backend,
        foundry_error="",
    )

    assert backend == "foundry-whisper-candidate"
    assert status == "COMPLETE_STT_BACKEND_DISCOVERY_CANDIDATE_FOUND"


def test_committed_summary_records_expected_safety_boundary():
    payload = json.loads(SUMMARY_JSON.read_text(encoding="utf-8"))

    assert payload["milestone"] == "Phase 2 Milestone 15A.1"
    assert payload["mode"] == "stt_backend_discovery_spike"
    assert payload["real_stt_attempted"] is False
    assert payload["speech_to_text_used"] is False
    assert payload["fake_transcripts_generated"] is False
    assert payload["dependency_changes"] is False
    assert payload["live_microphone_used"] is False
    assert payload["planner_called"] is False
    assert payload["validators_called"] is False
    assert payload["execution_eligible_count"] == 0


def test_documentation_contains_no_positive_voice_or_robot_claims():
    text = DOC_PATH.read_text(encoding="utf-8")
    forbidden_claims = [
        "Speech recognition works.",
        "The system supports voice control.",
        "The robot can be controlled by speech.",
        "Emergency stop is implemented.",
        "The voice system is safe.",
        "The system is production ready.",
        "Real robot execution is supported.",
        "Production voice interface is implemented.",
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
