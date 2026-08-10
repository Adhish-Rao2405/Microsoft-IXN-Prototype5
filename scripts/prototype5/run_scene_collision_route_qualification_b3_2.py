"""Generate canonical B3.2 discrete route collision-qualification evidence."""

from __future__ import annotations

from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from prototype5.scene_collision_route_qualification_b3_2 import (  # noqa: E402
    build_b3_2_artifact,
    ensure_output_available,
    verify_artifact_digest,
    write_artifact,
)


DEFAULT_OUTPUT = (
    REPOSITORY_ROOT
    / "results/prototype5/scene_calibration/phase_b3_2_discrete_route_collision_qualification.json"
)
DESTINATION_FLOOR_PAIR_ID = "component_environment:destination_floor"


def _destination_release_observation(artifact: dict[str, object]) -> tuple[dict[str, object], dict[str, object]]:
    route = artifact["authoritative_fine_route"]
    if not isinstance(route, dict):
        raise RuntimeError("Malformed authoritative fine route")
    snapshots = route["semantic_snapshots"]
    if not isinstance(snapshots, list):
        raise RuntimeError("Malformed authoritative fine snapshots")
    matches = [
        snapshot
        for snapshot in snapshots
        if isinstance(snapshot, dict)
        and snapshot.get("route_state") == "DESTINATION_PLACE"
        and snapshot.get("phase") == "RELEASE_BOUNDARY"
        and snapshot.get("boundary_snapshot") == "POST"
    ]
    if len(matches) != 1:
        raise RuntimeError("Destination release snapshot is not unique")
    snapshot = matches[0]
    observations = snapshot.get("observations")
    if not isinstance(observations, list):
        raise RuntimeError("Malformed destination release observations")
    selected = [
        observation
        for observation in observations
        if isinstance(observation, dict)
        and observation.get("pair_id") == DESTINATION_FLOOR_PAIR_ID
    ]
    if len(selected) != 1:
        raise RuntimeError("Destination release floor observation is not unique")
    return snapshot, selected[0]


def main() -> int:
    ensure_output_available(DEFAULT_OUTPUT)
    artifact = build_b3_2_artifact(REPOSITORY_ROOT)
    digest = write_artifact(artifact, DEFAULT_OUTPUT)
    if verify_artifact_digest(DEFAULT_OUTPUT) != digest:
        raise RuntimeError("Post-write B3.2 digest verification failed")

    coarse = artifact["coarse_sensitivity_summary"]
    fine = artifact["authoritative_fine_route"]
    result = artifact["result"]
    aggregate = artifact["aggregate_clearance_summary"]
    reproducibility = artifact["reproducibility_summary"]
    if not all(
        isinstance(item, dict)
        for item in (coarse, fine, result, aggregate, reproducibility)
    ):
        raise RuntimeError("Generated B3.2 artifact sections are malformed")
    release_snapshot, release_observation = _destination_release_observation(artifact)
    digest_path = DEFAULT_OUTPUT.with_suffix(DEFAULT_OUTPUT.suffix + ".sha256")

    print(f"artifact_name={DEFAULT_OUTPUT.name}")
    print(f"artifact_bytes={DEFAULT_OUTPUT.stat().st_size}")
    print(f"sha256={digest}")
    print(f"digest_name={digest_path.name}")
    print(f"overall_result={result['overall_result']}")
    print(f"scientific_failure_count={result['scientific_failure_count']}")
    print(f"failure_codes_present={','.join(result['failure_codes_present'])}")
    print(f"coarse_route_configurations={coarse['route_configuration_count']}")
    print(f"coarse_semantic_snapshots={coarse['semantic_snapshot_count']}")
    print(f"coarse_queries={coarse['query_count']}")
    print(f"fine_route_configurations={fine['route_configuration_count']}")
    print(f"fine_semantic_snapshots={fine['semantic_snapshot_count']}")
    print(f"fine_pass_1_queries={fine['query_count']}")
    print(f"fine_pass_2_queries={reproducibility['fine_pass_2_query_count']}")
    print(f"found_queries={aggregate['found_query_count']}")
    print(f"censored_queries={aggregate['censored_no_result_count']}")
    print(
        "fine_max_found_distance_spread_m="
        f"{reproducibility['maximum_found_distance_spread_m']!r}"
    )
    print(
        "destination_release_semantic_snapshot_index="
        f"{release_snapshot['semantic_snapshot_index']}"
    )
    print(f"destination_release_pair_id={release_observation['pair_id']}")
    print(f"destination_release_found={str(release_observation['found']).lower()}")
    print(
        "destination_release_signed_distance_m="
        f"{release_observation['signed_distance_m']!r}"
    )
    print(f"destination_release_classification={release_observation['classification']}")
    print(f"destination_release_policy={release_observation['permission']}")
    print(f"destination_release_decision={release_observation['decision']}")
    print("physics_steps=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
