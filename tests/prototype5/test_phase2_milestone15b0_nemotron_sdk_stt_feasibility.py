import json
import shutil
import subprocess
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from scripts.prototype5 import assess_nemotron_sdk_stt_feasibility as nemotron_assess


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "prototype5" / "assess_nemotron_sdk_stt_feasibility.py"
DOC_PATH = ROOT / "docs" / "prototype5" / "phase2_milestone15b0_nemotron_sdk_stt_feasibility.md"
SUMMARY_JSON = (
    ROOT
    / "results"
    / "prototype5"
    / "mode_voice"
    / "phase2_milestone15b0_nemotron_sdk_stt_feasibility_summary.json"
)
SUMMARY_MD = (
    ROOT
    / "results"
    / "prototype5"
    / "mode_voice"
    / "phase2_milestone15b0_nemotron_sdk_stt_feasibility_summary.md"
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
    path = ROOT / ".pytest_m15b0_tmp" / uuid4().hex
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


def test_version_parser_handles_minimum_threshold():
    assert nemotron_assess.version_at_least("1.1.0", "1.1.0") is True
    assert nemotron_assess.version_at_least("1.2.0", "1.1.0") is True
    assert nemotron_assess.version_at_least("1.0.9", "1.1.0") is False
    assert nemotron_assess.version_at_least(None, "1.1.0") is False


def test_classification_prioritises_sdk_state_before_audio_format():
    assert (
        nemotron_assess.classify(
            sdk_installed=False,
            sdk_version_compatible=False,
            wav_audio_exists=False,
        )
        == "COMPLETE_NEMOTRON_SDK_ASSESSMENT_SDK_NOT_INSTALLED"
    )
    assert (
        nemotron_assess.classify(
            sdk_installed=True,
            sdk_version_compatible=False,
            wav_audio_exists=False,
        )
        == "COMPLETE_NEMOTRON_SDK_ASSESSMENT_SDK_TOO_OLD"
    )
    assert (
        nemotron_assess.classify(
            sdk_installed=True,
            sdk_version_compatible=True,
            wav_audio_exists=False,
        )
        == "COMPLETE_NEMOTRON_SDK_ASSESSMENT_BLOCKED_AUDIO_FORMAT"
    )


def test_assessment_can_run_against_temp_audio_inventory():
    with workspace_tmp_dir() as work_dir:
        (work_dir / "sample.m4a").write_bytes(b"audio")
        summary = nemotron_assess.run_assessment(
            work_dir / "summary.json",
            work_dir / "summary.md",
            audio_dir=work_dir,
        )

        assert (work_dir / "summary.json").exists()
        assert (work_dir / "summary.md").exists()

    assert summary["m4a_audio_count"] == 1
    assert summary["wav_audio_count"] == 0
    assert summary["audio_conversion_would_be_required"] is True
    assert summary["model_download_attempted"] is False
    assert summary["real_stt_attempted"] is False
    assert summary["speech_to_text_used"] is False


def test_committed_summary_records_no_runtime_or_robot_scope():
    payload = json.loads(SUMMARY_JSON.read_text(encoding="utf-8"))

    assert payload["milestone"] == "Phase 2 Milestone 15B.0"
    assert payload["model_download_attempted"] is False
    assert payload["real_stt_attempted"] is False
    assert payload["speech_to_text_used"] is False
    assert payload["fake_transcripts_generated"] is False
    assert payload["live_microphone_used"] is False
    assert payload["planner_called"] is False
    assert payload["validators_called"] is False
    assert payload["robot_execution_attempted"] is False
    assert payload["binary_audio_files_committed"] is False


def test_documentation_keeps_nemotron_as_future_extension():
    text = DOC_PATH.read_text(encoding="utf-8")

    assert "M15A.2 remains valid as negative HTTP endpoint evidence" in text
    assert "future-extension route" in text
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
