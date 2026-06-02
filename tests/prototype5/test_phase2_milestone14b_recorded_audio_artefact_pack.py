import csv
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
M14A_CASES = ROOT / "data" / "prototype5" / "mode_voice" / "manual_voice_transcript_cases.csv"
AUDIO_MANIFEST = ROOT / "data" / "prototype5" / "mode_voice" / "audio_manifest.csv"
TRANSCRIPT_MANIFEST = ROOT / "data" / "prototype5" / "mode_voice" / "audio_transcript_manifest.csv"
AUDIO_SAMPLES_DIR = ROOT / "data" / "prototype5" / "mode_voice" / "audio_samples"
DOC_PATH = ROOT / "docs" / "prototype5" / "phase2_milestone14b_recorded_audio_artefact_pack.md"
SUMMARY_JSON = ROOT / "results" / "prototype5" / "mode_voice" / "phase2_milestone14b_audio_artefact_summary.json"
SUMMARY_MD = ROOT / "results" / "prototype5" / "mode_voice" / "phase2_milestone14b_audio_artefact_summary.md"

REQUIRED_AUDIO_COLUMNS = {
    "audio_id",
    "case_id",
    "scenario_family",
    "intended_spoken_command",
    "expected_audio_filename",
    "audio_storage_status",
    "audio_format",
    "sample_rate_hz",
    "channels",
    "speaker_id",
    "recording_environment",
    "recording_device",
    "recording_date",
    "consent_or_self_recorded",
    "notes",
}

REQUIRED_TRANSCRIPT_COLUMNS = {
    "audio_id",
    "case_id",
    "manual_transcript",
    "transcript_source",
    "transcript_confidence_assumption",
    "linked_m14a_case",
    "expected_intent",
    "expected_voice_eligible_for_planning",
    "expected_planner_called",
    "expected_primary_risk_flag",
    "notes",
}

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


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_audio_manifest_exists_and_has_required_columns():
    assert AUDIO_MANIFEST.exists()
    with AUDIO_MANIFEST.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert REQUIRED_AUDIO_COLUMNS.issubset(set(reader.fieldnames or []))


def test_audio_transcript_manifest_exists_and_has_required_columns():
    assert TRANSCRIPT_MANIFEST.exists()
    with TRANSCRIPT_MANIFEST.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert REQUIRED_TRANSCRIPT_COLUMNS.issubset(set(reader.fieldnames or []))


def test_manifests_link_to_all_m14a_case_ids():
    m14a_rows = read_csv(M14A_CASES)
    audio_rows = read_csv(AUDIO_MANIFEST)
    transcript_rows = read_csv(TRANSCRIPT_MANIFEST)

    m14a_case_ids = {row["case_id"] for row in m14a_rows}
    audio_case_ids = {row["case_id"] for row in audio_rows}
    transcript_case_ids = {row["case_id"] for row in transcript_rows}
    linked_case_ids = {row["linked_m14a_case"] for row in transcript_rows}

    assert len(m14a_rows) == 15
    assert len(audio_rows) >= 15
    assert len(transcript_rows) >= 15
    assert audio_case_ids == m14a_case_ids
    assert transcript_case_ids == m14a_case_ids
    assert linked_case_ids == m14a_case_ids


def test_every_audio_id_and_case_id_is_unique():
    audio_rows = read_csv(AUDIO_MANIFEST)
    transcript_rows = read_csv(TRANSCRIPT_MANIFEST)

    assert len({row["audio_id"] for row in audio_rows}) == len(audio_rows)
    assert len({row["case_id"] for row in audio_rows}) == len(audio_rows)
    assert len({row["audio_id"] for row in transcript_rows}) == len(transcript_rows)
    assert len({row["case_id"] for row in transcript_rows}) == len(transcript_rows)


def test_audio_manifest_uses_placeholder_storage_and_stable_wav_names():
    rows = read_csv(AUDIO_MANIFEST)

    assert {row["audio_storage_status"] for row in rows} == {"placeholder_not_recorded"}
    assert all(row["expected_audio_filename"].endswith(".wav") for row in rows)
    assert all(row["expected_audio_filename"] == row["expected_audio_filename"].lower() for row in rows)
    assert all(" " not in row["expected_audio_filename"] for row in rows)


def test_no_binary_audio_file_is_required_or_committed():
    assert AUDIO_SAMPLES_DIR.exists()
    files = [path for path in AUDIO_SAMPLES_DIR.rglob("*") if path.is_file()]

    assert files == [AUDIO_SAMPLES_DIR / "README.md"]
    assert not any(path.suffix.lower() in BINARY_AUDIO_SUFFIXES for path in files)


def test_summary_outputs_exist():
    assert SUMMARY_JSON.exists()
    assert SUMMARY_MD.exists()


def test_summary_json_records_no_runtime_stt_microphone_dependency_or_binary_audio():
    payload = json.loads(SUMMARY_JSON.read_text(encoding="utf-8"))

    assert payload["status"] == "COMPLETE_AUDIO_ARTEFACT_MANIFEST"
    assert payload["milestone"] == "Phase 2 Milestone 14B"
    assert payload["mode"] == "recorded_audio_artefact_pack_without_runtime_transcription"
    assert payload["linked_m14a_case_count"] == 15
    assert payload["audio_manifest_rows"] == 15
    assert payload["transcript_manifest_rows"] == 15
    assert payload["audio_files_committed_count"] == 0
    assert payload["audio_files_required_later_count"] == 15
    assert payload["audio_runtime_used"] is False
    assert payload["speech_to_text_used"] is False
    assert payload["live_microphone_used"] is False
    assert payload["dependency_changes"] is False
    assert payload["binary_audio_committed"] is False


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


def test_audio_artefact_pack_does_not_add_runtime_or_stt_imports():
    checked_paths = [DOC_PATH, SUMMARY_MD, AUDIO_SAMPLES_DIR / "README.md"]
    combined_text = "\n".join(path.read_text(encoding="utf-8").lower() for path in checked_paths)
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
