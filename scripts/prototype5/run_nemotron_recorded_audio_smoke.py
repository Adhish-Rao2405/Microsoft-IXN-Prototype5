"""Run one bounded, non-retaining Nemotron recorded-audio smoke test."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from src.prototype5.governance_contract_v2 import TranscriptStatus
from src.prototype5.recorded_speech import (
    DEFAULT_MAX_AUDIO_BYTES,
    NemotronRecordedAudioClient,
    RecordedSpeechClientConfiguration,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Transcribe one 16 kHz mono 16-bit PCM WAV through the isolated "
            "Foundry Local Nemotron worker."
        )
    )
    parser.add_argument("--audio", required=True, type=Path)
    parser.add_argument(
        "--speech-python",
        type=Path,
        default=Path(
            os.getenv("PROTOTYPE5_SPEECH_PYTHON", sys.executable)
        ),
    )
    parser.add_argument("--timeout-seconds", type=float, default=900)
    parser.add_argument("--allow-model-download", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repository_root = REPOSITORY_ROOT
    audio_path = args.audio.expanduser().resolve()
    if not audio_path.is_file():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")
    if audio_path.is_relative_to(repository_root):
        raise ValueError("Smoke-test audio must remain outside the repository")
    if audio_path.stat().st_size > DEFAULT_MAX_AUDIO_BYTES:
        raise ValueError(
            f"Smoke-test audio exceeds the {DEFAULT_MAX_AUDIO_BYTES}-byte limit"
        )
    if args.output is not None:
        output = args.output.expanduser().resolve()
        if output.is_relative_to(repository_root):
            raise ValueError("Smoke-test output must remain outside the repository")
    else:
        output = None

    client = NemotronRecordedAudioClient(
        RecordedSpeechClientConfiguration(
            repository_root=repository_root,
            speech_python_executable=args.speech_python.expanduser().resolve(),
            process_timeout_seconds=args.timeout_seconds,
            allow_model_download=args.allow_model_download,
        )
    )
    result = client.transcribe_wav(
        audio_path.read_bytes(),
        original_filename=audio_path.name,
    )
    result_json = result.model_dump_json(indent=2)
    print(result_json)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(result_json + "\n", encoding="utf-8")
    return 0 if result.transcript_status is TranscriptStatus.READY else 2


if __name__ == "__main__":
    raise SystemExit(main())
