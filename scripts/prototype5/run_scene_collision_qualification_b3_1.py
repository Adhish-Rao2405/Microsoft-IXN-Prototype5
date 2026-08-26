"""Generate B3.1 collision-detector and frozen-scene evidence."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from prototype5.scene_collision_qualification_b3_1 import (  # noqa: E402
    build_b3_1_artifact,
    verify_artifact_digest,
    write_artifact,
)


DEFAULT_OUTPUT = (
    REPOSITORY_ROOT
    / "results/prototype5/scene_calibration/phase_b3_1_collision_qualification.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate B3.1 static collision-kernel and frozen-scene foundation evidence."
        )
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
    artifact = build_b3_1_artifact(REPOSITORY_ROOT)
    digest = write_artifact(artifact, arguments.output)
    verified = verify_artifact_digest(arguments.output)
    if verified != digest:
        raise RuntimeError("Post-write B3.1 digest verification failed")
    scene = artifact["frozen_scene_reconstruction"]
    kernel = artifact["collision_kernel_calibration"]
    digest_path = arguments.output.with_suffix(arguments.output.suffix + ".sha256")
    print(f"artifact_name={arguments.output.name}")
    print(f"sha256={digest}")
    print(f"digest_name={digest_path.name}")
    print(f"result={artifact['result']}")
    print(f"scene_bodies={scene['body_count']}")
    print(f"kernel_observations={len(kernel['observations'])}")
    print("b2_route_collision_evaluated=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
