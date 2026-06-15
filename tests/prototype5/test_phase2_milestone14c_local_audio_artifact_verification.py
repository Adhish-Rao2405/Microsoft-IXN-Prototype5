import json
import shutil
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "prototype5" / "verify_local_voice_audio_artifacts.py"
MANIFEST = ROOT / "data" / "prototype5" / "mode_voice" / "audio_manifest.csv"
DOC_PATH = ROOT / "docs" / "prototype5" / "phase2_milestone14c_local_audio_artifact_verification.md"
SUMMARY_JSON = (
    ROOT
    / "results"
    / "prototype5"
    / "mode_voice"
    / "phase2_milestone14c_local_audio_artifact_verification_summary.json"
)
SUMMARY_MD = (
    ROOT
    / "results"
    / "prototype5"
    / "mode_voice"
    / "phase2_milestone14c_local_audio_artifact_verification_summary.md"
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
    path = ROOT / ".pytest_m14c_tmp" / uuid4().hex
    path.mkdir(parents=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def run_verifier(work_dir: Path, *, strict: bool = False) -> subprocess.CompletedProcess[str]:
    audio_dir = work_dir / "empty_audio_samples"
    audio_dir.mkdir()
    summary_json = work_dir / "summary.json"
    summary_md = work_dir / "summary.md"

    command = [
        sys.executable,
        str(SCRIPT),
        "--manifest",
        str(MANIFEST),
        "--audio-dir",
        str(audio_dir),
        "--summary-json",
        str(summary_json),
        "--summary-md",
        str(summary_md),
    ]
    if strict:
        command.append("--strict")

    return subprocess.run(command, cwd=ROOT, capture_output=True, text=True)


def test_verification_script_exists():
    assert SCRIPT.exists()


def test_documentation_and_committed_summaries_exist():
    assert DOC_PATH.exists()
    assert SUMMARY_JSON.exists()
    assert SUMMARY_MD.exists()


def test_script_can_run_in_non_strict_mode_without_binary_audio_files():
    with workspace_tmp_dir() as work_dir:
        completed = run_verifier(work_dir, strict=False)
        payload = json.loads((work_dir / "summary.json").read_text(encoding="utf-8"))

    assert completed.returncode == 0, completed.stderr
    assert payload["status"] == "COMPLETE_LOCAL_AUDIO_VERIFICATION_MISSING_LOCAL_FILES"
    assert payload["expected_audio_count"] == 15
    assert payload["present_audio_count"] == 0
    assert payload["missing_audio_count"] == 15
    assert payload["strict_mode"] is False


def test_summary_json_and_markdown_are_produced():
    with workspace_tmp_dir() as work_dir:
        completed = run_verifier(work_dir, strict=False)

        assert completed.returncode == 0, completed.stderr
        assert (work_dir / "summary.json").exists()
        assert (work_dir / "summary.md").exists()


def test_summary_json_records_no_runtime_stt_microphone_or_dependency_changes():
    with workspace_tmp_dir() as work_dir:
        completed = run_verifier(work_dir, strict=False)
        payload = json.loads((work_dir / "summary.json").read_text(encoding="utf-8"))

    assert completed.returncode == 0, completed.stderr
    assert payload["milestone"] == "Phase 2 Milestone 14C"
    assert payload["mode"] == "local_audio_artifact_verification"
    assert payload["audio_runtime_used"] is False
    assert payload["speech_to_text_used"] is False
    assert payload["live_microphone_used"] is False
    assert payload["dependency_changes"] is False
    assert payload["binary_audio_files_committed"] is False


def test_script_does_not_require_committed_audio_files_for_ci():
    with workspace_tmp_dir() as work_dir:
        completed = run_verifier(work_dir, strict=False)
        payload = json.loads((work_dir / "summary.json").read_text(encoding="utf-8"))

    assert completed.returncode == 0, completed.stderr
    assert payload["missing_audio_count"] == payload["expected_audio_count"]
    assert payload["missing_audio_count"] == len(payload["missing_files"])
    assert payload["present_files"] == []


def test_strict_mode_detects_missing_audio_files():
    with workspace_tmp_dir() as work_dir:
        completed = run_verifier(work_dir, strict=True)
        payload = json.loads((work_dir / "summary.json").read_text(encoding="utf-8"))

    assert completed.returncode == 1
    assert payload["status"] == "COMPLETE_LOCAL_AUDIO_VERIFICATION_MISSING_LOCAL_FILES"
    assert payload["strict_mode"] is True
    assert payload["expected_audio_count"] == 15
    assert payload["missing_audio_count"] == 15


def test_documentation_contains_no_positive_live_voice_or_robot_claims():
    text = DOC_PATH.read_text(encoding="utf-8")
    forbidden_claims = [
        "The system supports voice control.",
        "The robot can be controlled by speech.",
        "Speech recognition is implemented.",
        "Emergency stop is implemented.",
        "The voice system is safe.",
        "The system is production ready.",
        "Real robot execution is supported.",
        "The system understands voice commands end-to-end.",
    ]

    for claim in forbidden_claims:
        assert claim not in text


def test_verifier_does_not_add_audio_runtime_or_stt_imports():
    combined_text = "\n".join(
        [
            SCRIPT.read_text(encoding="utf-8").lower(),
            DOC_PATH.read_text(encoding="utf-8").lower(),
            SUMMARY_MD.read_text(encoding="utf-8").lower(),
        ]
    )
    runtime_terms = [
        "import whisper",
        "speech_recognition",
        "pyaudio",
        "sounddevice",
        "azure.cognitiveservices.speech",
        "wave.open",
        "librosa",
    ]

    for term in runtime_terms:
        assert term not in combined_text


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


def test_protected_draft_and_dependency_files_are_not_staged():
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
