from __future__ import annotations

import argparse
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from src.prototype5.scene_calibration_b1_2 import (  # noqa: E402
    evidence_record_counts,
    generate_evidence_records,
    repository_root,
    write_evidence,
)


DEFAULT_HISTORICAL_B1_DIRECTORY = Path(
    r"C:\Users\reach\Prototype5-S1-Scene-Calibration-Scratch"
)


def _arguments(argv: list[str] | None) -> argparse.Namespace:
    root = repository_root()
    parser = argparse.ArgumentParser(
        description=(
            "Run the bounded Prototype 5 B1.2 evidence-contract hardening pass."
        )
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=(
            root
            / "results"
            / "prototype5"
            / "scene_calibration"
            / "phase_b1_2_results.jsonl"
        ),
        help="New B1.2 JSONL path. Existing files are never overwritten.",
    )
    parser.add_argument(
        "--historical-b1-directory",
        type=Path,
        default=DEFAULT_HISTORICAL_B1_DIRECTORY,
        help="Directory containing immutable historical B1 inputs.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = _arguments(argv)
    historical_directory = arguments.historical_b1_directory.resolve()
    records = generate_evidence_records(
        probe_script=Path(__file__).resolve(),
        historical_b1_script=(
            historical_directory / "probe_scene_phase_b1_corrected.py"
        ),
        historical_b1_results=(
            historical_directory / "phase_b1_corrected_results.jsonl"
        ),
    )
    counts = evidence_record_counts(records)
    runtime_summary = next(
        record
        for record in records
        if record["record_type"] == "runtime_summary"
    )
    evidence_sha256 = write_evidence(records, arguments.output)
    print(f"OUTPUT={arguments.output.resolve()}")
    print(f"SHA256={evidence_sha256}")
    print(f"TOTAL_RECORDS={len(records)}")
    print(f"CANDIDATE_SUMMARIES={counts['candidate_summary']}")
    print(f"CANDIDATE_DETAILS={counts['candidate_detail']}")
    print(f"DOWN_X_SURVIVORS={runtime_summary['down_x_survivor_count']}")
    print(
        "DOWN_Y_PROTOCOL_REJECTIONS="
        f"{runtime_summary['down_y_protocol_rejection_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
