from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.prototype5.voice_intent_policy import build_mock_voice_transcript  # noqa: E402


def parse_bool(value: str) -> bool:
    normalised = value.strip().lower()
    if normalised in {"1", "true", "yes"}:
        return True
    if normalised in {"0", "false", "no"}:
        return False
    raise argparse.ArgumentTypeError("--partial must be true or false")


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe the mocked Prototype 5 voice transcript policy.")
    parser.add_argument("--text", required=True, help="Mocked transcript text.")
    parser.add_argument("--confidence", type=float, default=1.0, help="Transcript confidence from 0.0 to 1.0.")
    parser.add_argument("--partial", type=parse_bool, default=False, help="Whether the transcript is partial.")
    args = parser.parse_args()

    transcript = build_mock_voice_transcript(
        args.text,
        transcript_confidence=args.confidence,
        is_partial=args.partial,
    )
    print(json.dumps(transcript.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
