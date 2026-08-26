from __future__ import annotations

import argparse
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from src.prototype5.scene_calibration_b1_1 import (  # noqa: E402
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
            "Run the bounded Prototype 5 B1.1 static kinematic "
            "calibration evidence correction."
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
            / "phase_b1_1_results.jsonl"
        ),
        help="New JSONL evidence path. Existing files are never overwritten.",
    )
    parser.add_argument(
        "--historical-b1-directory",
        type=Path,
        default=DEFAULT_HISTORICAL_B1_DIRECTORY,
        help=(
            "Directory containing the immutable historical B1 script "
            "and JSONL evidence."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = _arguments(argv)
    historical_directory = arguments.historical_b1_directory.resolve()
    historical_script = historical_directory / "probe_scene_phase_b1_corrected.py"
    historical_results = historical_directory / "phase_b1_corrected_results.jsonl"
    records = generate_evidence_records(
        probe_script=Path(__file__).resolve(),
        historical_b1_script=historical_script,
        historical_b1_results=historical_results,
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
    print(f"CANDIDATE_SUMMARIES={counts.get('candidate_summary', 0)}")
    print(f"CANDIDATE_DETAILS={counts.get('candidate_detail', 0)}")
    print(f"SURVIVORS={runtime_summary['survivor_count']}")
    print(f"DOWN_X_SURVIVORS={runtime_summary['down_x_survivor_count']}")
    print(
        "DOWN_Y_PROTOCOL_REJECTIONS="
        f"{runtime_summary['down_y_protocol_rejection_count']}"
    )
    if not runtime_summary["expected_topology_matches"]:
        print("B1_1_TOPOLOGY_REGRESSION_MISMATCH", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
