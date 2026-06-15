import csv
import json
import shutil
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "prototype5" / "run_stt_feasibility_probe.py"
DOC_PATH = ROOT / "docs" / "prototype5" / "phase2_milestone15a_stt_feasibility_spike.md"
AUDIO_MANIFEST = ROOT / "data" / "prototype5" / "mode_voice" / "audio_manifest.csv"
TRANSCRIPT_MANIFEST = ROOT / "data" / "prototype5" / "mode_voice" / "audio_transcript_manifest.csv"
RESULTS_CSV = ROOT / "results" / "prototype5" / "mode_voice" / "phase2_milestone15a_stt_feasibility_results.csv"
SUMMARY_JSON = ROOT / "results" / "prototype5" / "mode_voice" / "phase2_milestone15a_stt_feasibility_summary.json"
SUMMARY_MD = ROOT / "results" / "prototype5" / "mode_voice" / "phase2_milestone15a_stt_feasibility_summary.md"

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
    path = ROOT / ".pytest_m15a_tmp" / uuid4().hex
    path.mkdir(parents=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def run_probe(work_dir: Path, *, backend: str = "unavailable-stub") -> subprocess.CompletedProcess[str]:
    audio_dir = work_dir / "empty_audio_samples"
    audio_dir.mkdir()
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--backend",
            backend,
            "--audio-manifest",
            str(AUDIO_MANIFEST),
            "--transcript-manifest",
            str(TRANSCRIPT_MANIFEST),
            "--audio-dir",
            str(audio_dir),
            "--results-csv",
            str(work_dir / "results.csv"),
            "--summary-json",
            str(work_dir / "summary.json"),
            "--summary-md",
            str(work_dir / "summary.md"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_script_exists():
    assert SCRIPT.exists()


def test_docs_and_committed_outputs_exist():
    assert DOC_PATH.exists()
    assert RESULTS_CSV.exists()
    assert SUMMARY_JSON.exists()
    assert SUMMARY_MD.exists()


def test_script_can_produce_blocked_unavailable_summary_without_real_stt():
    with workspace_tmp_dir() as work_dir:
        completed = run_probe(work_dir, backend="unavailable-stub")
        payload = json.loads((work_dir / "summary.json").read_text(encoding="utf-8"))

    assert completed.returncode == 0, completed.stderr
    assert payload["status"] == "COMPLETE_STT_FEASIBILITY_BLOCKED_AUDIO_MISSING"
    assert payload["backend"] == "unavailable-stub"
    assert payload["audio_count"] == 15
    assert payload["audio_present_count"] == 0
    assert payload["stt_attempted_count"] == 0
    assert payload["stt_success_count"] == 0
    assert payload["automatic_transcript_count"] == 0


def test_result_csv_summary_json_and_markdown_are_produced():
    with workspace_tmp_dir() as work_dir:
        completed = run_probe(work_dir, backend="unavailable-stub")

        assert completed.returncode == 0, completed.stderr
        assert (work_dir / "results.csv").exists()
        assert (work_dir / "summary.json").exists()
        assert (work_dir / "summary.md").exists()


def test_summary_records_zero_trust_safety_flags_without_runtime_scope():
    with workspace_tmp_dir() as work_dir:
        completed = run_probe(work_dir, backend="unavailable-stub")
        payload = json.loads((work_dir / "summary.json").read_text(encoding="utf-8"))

    assert completed.returncode == 0, completed.stderr
    assert payload["fake_transcripts_generated"] is False
    assert payload["live_microphone_used"] is False
    assert payload["dependency_changes"] is False
    assert payload["planner_called"] is False
    assert payload["validators_called"] is False
    assert payload["execution_eligible_count"] == 0
    assert payload["binary_audio_files_committed"] is False
    assert payload["manual_transcripts_used_as_ground_truth_only"] is True


def test_manual_transcripts_are_not_labelled_as_automatic_transcripts():
    with workspace_tmp_dir() as work_dir:
        completed = run_probe(work_dir, backend="unavailable-stub")
        rows = read_csv(work_dir / "results.csv")

    assert completed.returncode == 0, completed.stderr
    assert len(rows) == 15
    assert {row["automatic_transcript"] for row in rows} == {""}
    assert {row["manual_transcript_available"] for row in rows} == {"true"}
    assert {row["stt_success"] for row in rows} == {"false"}


def test_committed_summary_records_no_fake_transcripts_or_planner_validator_scope():
    payload = json.loads(SUMMARY_JSON.read_text(encoding="utf-8"))

    assert payload["milestone"] == "Phase 2 Milestone 15A"
    assert payload["mode"] == "bounded_stt_feasibility_spike"
    assert payload["fake_transcripts_generated"] is False
    assert payload["planner_called"] is False
    assert payload["validators_called"] is False
    assert payload["execution_eligible_count"] == 0
    assert payload["binary_audio_files_committed"] is False


def test_documentation_contains_no_positive_live_voice_or_robot_claims():
    text = DOC_PATH.read_text(encoding="utf-8")
    forbidden_claims = [
        "The system supports voice control.",
        "The robot can be controlled by speech.",
        "Emergency stop is implemented.",
        "The voice system is safe.",
        "The system is production ready.",
        "Real robot execution is supported.",
        "The system understands voice commands end-to-end.",
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
