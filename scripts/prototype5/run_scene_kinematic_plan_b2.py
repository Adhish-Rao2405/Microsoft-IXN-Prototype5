"""Generate the immutable B2 static kinematic-plan artifact."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from prototype5.scene_kinematic_plan_b2 import (  # noqa: E402
    build_b2_artifact,
    verify_companion_digest,
    write_b2_artifact,
)


DEFAULT_OUTPUT = (
    REPOSITORY_ROOT
    / "results/prototype5/scene_calibration/phase_b2_kinematic_plan.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate B2 deterministic static kinematic-plan evidence."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="New JSON artifact path; existing output or digest is rejected.",
    )
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    artifact = build_b2_artifact(REPOSITORY_ROOT)
    digest, digest_path = write_b2_artifact(arguments.output, artifact)
    verified = verify_companion_digest(arguments.output, digest_path)
    if verified != digest:
        raise RuntimeError("Post-write B2 digest verification failed")
    metrics = artifact["plan_metrics"]
    reproducibility = artifact["reproducibility"]
    home_selection = artifact["home_selection"]
    print(f"artifact={arguments.output.resolve()}")
    print(f"sha256={digest}")
    print(f"digest={digest_path.resolve()}")
    print(f"selected_home={home_selection['selected_candidate']}")
    print(f"states={metrics['state_count']}")
    print(f"legs={metrics['leg_count']}")
    print(f"trials={reproducibility['trial_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
