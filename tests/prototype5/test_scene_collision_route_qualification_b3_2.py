from __future__ import annotations

import ast
import copy
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path

import pytest

from src.prototype5 import scene_collision_route_qualification_b3_2 as b32


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SOURCE_PATH = REPOSITORY_ROOT / "src/prototype5/scene_collision_route_qualification_b3_2.py"
RUNNER_PATH = REPOSITORY_ROOT / "scripts/prototype5/run_scene_collision_route_qualification_b3_2.py"
ARTIFACT_PATH = REPOSITORY_ROOT / "results/prototype5/scene_calibration/phase_b3_2_discrete_route_collision_qualification.json"


@pytest.fixture(scope="module")
def inputs() -> b32.FrozenInputs:
    return b32.load_frozen_inputs(REPOSITORY_ROOT)


@pytest.fixture(scope="module")
def pairs(inputs: b32.FrozenInputs) -> tuple[b32.CollisionPair, ...]:
    return b32.build_collision_pair_inventory(inputs.self_collision_pairs)


@pytest.fixture(scope="module")
def live_artifact() -> dict[str, object]:
    return b32.build_b3_2_artifact(REPOSITORY_ROOT)


def _copy_snapshots_for_mutation(
    artifact: dict[str, object],
    *semantic_snapshot_indexes: int,
) -> tuple[dict[str, object], dict[int, dict[str, object]]]:
    mutated = dict(artifact)
    fine = dict(artifact["authoritative_fine_route"])
    snapshots = list(fine["semantic_snapshots"])
    copied: dict[int, dict[str, object]] = {}
    for semantic_snapshot_index in semantic_snapshot_indexes:
        snapshot = dict(snapshots[semantic_snapshot_index])
        snapshots[semantic_snapshot_index] = snapshot
        copied[semantic_snapshot_index] = snapshot
    fine["semantic_snapshots"] = snapshots
    mutated["authoritative_fine_route"] = fine
    return mutated, copied


def _copy_observation_for_mutation(
    artifact: dict[str, object],
    semantic_snapshot_index: int,
    pair_index: int,
) -> tuple[dict[str, object], dict[str, object]]:
    mutated, copied = _copy_snapshots_for_mutation(
        artifact,
        semantic_snapshot_index,
    )
    snapshot = copied[semantic_snapshot_index]
    observations = list(snapshot["observations"])
    observation = dict(observations[pair_index])
    observations[pair_index] = observation
    snapshot["observations"] = observations
    return mutated, observation


def _write_raw_evidence_pair(output: Path, payload: bytes) -> None:
    output.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    output.with_suffix(".json.sha256").write_bytes(
        f"{digest}  {output.name}\n".encode("ascii")
    )


@pytest.mark.parametrize(
    ("distance", "expected"),
    [
        (
            math.nextafter(-b32.NUMERICAL_CONTACT_EPSILON_M, -math.inf),
            b32.DistanceClassification.MATERIAL_PENETRATION,
        ),
        (-b32.NUMERICAL_CONTACT_EPSILON_M, b32.DistanceClassification.NUMERICAL_CONTACT_BAND),
        (0.0, b32.DistanceClassification.NUMERICAL_CONTACT_BAND),
        (b32.NUMERICAL_CONTACT_EPSILON_M, b32.DistanceClassification.NUMERICAL_CONTACT_BAND),
        (
            math.nextafter(b32.NUMERICAL_CONTACT_EPSILON_M, math.inf),
            b32.DistanceClassification.SEPARATED,
        ),
        (0.001, b32.DistanceClassification.SEPARATED),
    ],
)
def test_exact_numeric_contact_boundaries(
    distance: float,
    expected: b32.DistanceClassification,
) -> None:
    assert b32.classify_signed_distance(distance) is expected


@pytest.mark.parametrize("invalid", [None, True, False, "0", math.nan, math.inf, -math.inf])
def test_nonfinite_and_nonnumeric_distances_fail_closed(invalid: object) -> None:
    with pytest.raises(b32.B3_2_InfrastructureError):
        b32.classify_signed_distance(invalid)


def test_empty_closest_point_result_is_censored_beyond_horizon() -> None:
    result = b32.b31.ClosestPointResult(False, None, 0.050)
    assert b32.classify_closest_point(result) is b32.DistanceClassification.SEPARATED_BEYOND_QUERY_HORIZON


@pytest.mark.parametrize(
    "result",
    [
        b32.b31.ClosestPointResult(True, None, None),
        b32.b31.ClosestPointResult(True, 0.0, 0.050),
        b32.b31.ClosestPointResult(False, 0.0, 0.050),
        b32.b31.ClosestPointResult(False, None, 0.049),
        b32.b31.ClosestPointResult(True, math.nan, None),
    ],
)
def test_malformed_closest_point_results_fail_closed(
    result: b32.b31.ClosestPointResult,
) -> None:
    with pytest.raises(b32.B3_2_InfrastructureError):
        b32.classify_closest_point(result)


@pytest.mark.parametrize(
    ("policy", "classification", "decision"),
    [
        (b32.PairPolicy.FORBIDDEN, b32.DistanceClassification.MATERIAL_PENETRATION, b32.SCIENTIFIC_FAILURE_CODES[0]),
        (b32.PairPolicy.FORBIDDEN, b32.DistanceClassification.NUMERICAL_CONTACT_BAND, b32.SCIENTIFIC_FAILURE_CODES[0]),
        (b32.PairPolicy.FORBIDDEN, b32.DistanceClassification.SEPARATED, "PASS"),
        (b32.PairPolicy.FORBIDDEN, b32.DistanceClassification.SEPARATED_BEYOND_QUERY_HORIZON, "PASS"),
        (b32.PairPolicy.PERMITTED_SUPPORT, b32.DistanceClassification.MATERIAL_PENETRATION, b32.SCIENTIFIC_FAILURE_CODES[1]),
        (b32.PairPolicy.PERMITTED_SUPPORT, b32.DistanceClassification.NUMERICAL_CONTACT_BAND, "PASS"),
        (b32.PairPolicy.PERMITTED_SUPPORT, b32.DistanceClassification.SEPARATED, "PASS"),
        (b32.PairPolicy.PERMITTED_SUPPORT, b32.DistanceClassification.SEPARATED_BEYOND_QUERY_HORIZON, "PASS"),
        (b32.PairPolicy.REQUIRED_SUPPORT, b32.DistanceClassification.MATERIAL_PENETRATION, b32.SCIENTIFIC_FAILURE_CODES[1]),
        (b32.PairPolicy.REQUIRED_SUPPORT, b32.DistanceClassification.NUMERICAL_CONTACT_BAND, "PASS"),
        (b32.PairPolicy.REQUIRED_SUPPORT, b32.DistanceClassification.SEPARATED, b32.SCIENTIFIC_FAILURE_CODES[2]),
        (b32.PairPolicy.REQUIRED_SUPPORT, b32.DistanceClassification.SEPARATED_BEYOND_QUERY_HORIZON, b32.SCIENTIFIC_FAILURE_CODES[2]),
    ],
)
def test_complete_contact_decision_matrix(
    policy: b32.PairPolicy,
    classification: b32.DistanceClassification,
    decision: str,
) -> None:
    assert b32.decide_contact(policy, classification) == decision


def test_source_support_boundary_policies() -> None:
    assert b32.component_environment_policy(
        "source_platform", b32.ComponentPhase.SOURCE_SUPPORTED, b32.BoundarySnapshot.NONE
    ) is b32.PairPolicy.REQUIRED_SUPPORT
    assert b32.component_environment_policy(
        "source_platform", b32.ComponentPhase.ATTACHMENT_BOUNDARY, b32.BoundarySnapshot.PRE
    ) is b32.PairPolicy.REQUIRED_SUPPORT
    assert b32.component_environment_policy(
        "source_platform", b32.ComponentPhase.ATTACHMENT_BOUNDARY, b32.BoundarySnapshot.POST
    ) is b32.PairPolicy.PERMITTED_SUPPORT
    assert b32.component_environment_policy(
        "source_platform", b32.ComponentPhase.CARRIED, b32.BoundarySnapshot.NONE
    ) is b32.PairPolicy.FORBIDDEN


def test_destination_support_boundary_policies() -> None:
    assert b32.component_environment_policy(
        "destination_floor", b32.ComponentPhase.RELEASE_BOUNDARY, b32.BoundarySnapshot.PRE
    ) is b32.PairPolicy.PERMITTED_SUPPORT
    assert b32.component_environment_policy(
        "destination_floor", b32.ComponentPhase.RELEASE_BOUNDARY, b32.BoundarySnapshot.POST
    ) is b32.PairPolicy.REQUIRED_SUPPORT
    assert b32.component_environment_policy(
        "destination_floor", b32.ComponentPhase.DESTINATION_SUPPORTED, b32.BoundarySnapshot.NONE
    ) is b32.PairPolicy.REQUIRED_SUPPORT
    assert b32.component_environment_policy(
        "destination_floor", b32.ComponentPhase.CARRIED, b32.BoundarySnapshot.NONE
    ) is b32.PairPolicy.FORBIDDEN


def test_walls_and_component_robot_are_always_forbidden(
    pairs: tuple[b32.CollisionPair, ...],
) -> None:
    walls = [item for item in pairs if item.pair_id.startswith("component_environment:destination_wall")]
    component_robot = [item for item in pairs if item.category is b32.PairCategory.COMPONENT_ROBOT]
    assert len(walls) == 4
    assert len(component_robot) == 8
    for pair in walls + component_robot:
        for phase, boundary in (
            (b32.ComponentPhase.SOURCE_SUPPORTED, b32.BoundarySnapshot.NONE),
            (b32.ComponentPhase.ATTACHMENT_BOUNDARY, b32.BoundarySnapshot.PRE),
            (b32.ComponentPhase.ATTACHMENT_BOUNDARY, b32.BoundarySnapshot.POST),
            (b32.ComponentPhase.CARRIED, b32.BoundarySnapshot.NONE),
            (b32.ComponentPhase.RELEASE_BOUNDARY, b32.BoundarySnapshot.PRE),
            (b32.ComponentPhase.RELEASE_BOUNDARY, b32.BoundarySnapshot.POST),
            (b32.ComponentPhase.DESTINATION_SUPPORTED, b32.BoundarySnapshot.NONE),
        ):
            assert b32.pair_policy(pair, phase, boundary) is b32.PairPolicy.FORBIDDEN


def test_exact_sampling_cardinalities(inputs: b32.FrozenInputs) -> None:
    assert b32.interval_counts(inputs.route, refinement_factor=1) == (39, 20, 19, 77, 20, 19, 39)
    assert b32.interval_counts(inputs.route, refinement_factor=2) == (78, 40, 38, 154, 40, 38, 78)
    coarse = b32.sample_route(inputs.route, refinement_factor=1)
    fine = b32.sample_route(inputs.route, refinement_factor=2)
    assert sum(b32.EXPECTED_COARSE_INTERVALS) == 233
    assert sum(b32.EXPECTED_FINE_INTERVALS) == 466
    assert len(coarse) == 234
    assert len(fine) == 467
    assert len(b32.semantic_snapshots(inputs.route, refinement_factor=1)) == 236
    assert len(b32.semantic_snapshots(inputs.route, refinement_factor=2)) == 469


def test_frozen_reproducibility_repeat_count_literal() -> None:
    assert b32.ROUTE_REPRODUCIBILITY_REPEAT_COUNT == 2


def test_first_segment_includes_k0_and_later_segments_omit_it(
    inputs: b32.FrozenInputs,
) -> None:
    coarse = b32.sample_route(inputs.route, refinement_factor=1)
    assert coarse[0].segment_index == 0
    assert coarse[0].segment_sample_index == 0
    for segment_index in range(1, 7):
        samples = [item.segment_sample_index for item in coarse if item.segment_index == segment_index]
        assert samples[0] == 1
        assert 0 not in samples


def test_segment_endpoints_are_exact_and_route_states_are_not_inferred(
    inputs: b32.FrozenInputs,
) -> None:
    coarse = b32.sample_route(inputs.route, refinement_factor=1)
    assert coarse[0].joint_vector is inputs.route[0].joint_vector
    for segment_index in range(7):
        endpoint = [item for item in coarse if item.segment_index == segment_index][-1]
        assert endpoint.joint_vector is inputs.route[segment_index + 1].joint_vector
        assert endpoint.route_state == inputs.route[segment_index + 1].state
    assert all(
        item.route_state == "INTERPOLATED"
        for item in coarse
        if 0.0 < item.alpha < 1.0
    )


def test_fine_grid_exactly_nests_coarse_grid(inputs: b32.FrozenInputs) -> None:
    coarse = b32.sample_route(inputs.route, refinement_factor=1)
    fine = b32.sample_route(inputs.route, refinement_factor=2)
    fine_by_key = {
        (item.segment_index, Fraction(item.segment_sample_index, item.segment_interval_count)): item
        for item in fine
    }
    assert len(fine_by_key) == len(fine)
    for item in coarse:
        nested = fine_by_key[
            (item.segment_index, Fraction(item.segment_sample_index, item.segment_interval_count))
        ]
        assert item.joint_vector == nested.joint_vector
        assert item.route_state == nested.route_state


def test_semantic_boundary_snapshots_and_component_lifecycle(
    inputs: b32.FrozenInputs,
) -> None:
    snapshots = b32.semantic_snapshots(inputs.route, refinement_factor=1)
    source_pick = [item for item in snapshots if item.route_state == "SOURCE_PICK"]
    destination_place = [item for item in snapshots if item.route_state == "DESTINATION_PLACE"]
    assert [(item.phase.value, item.boundary_snapshot.value) for item in source_pick] == [
        ("ATTACHMENT_BOUNDARY", "PRE"),
        ("ATTACHMENT_BOUNDARY", "POST"),
    ]
    assert [(item.phase.value, item.boundary_snapshot.value) for item in destination_place] == [
        ("RELEASE_BOUNDARY", "PRE"),
        ("RELEASE_BOUNDARY", "POST"),
    ]
    assert source_pick[0].joint_vector == source_pick[1].joint_vector
    assert destination_place[0].joint_vector == destination_place[1].joint_vector
    assert any(item.phase is b32.ComponentPhase.SOURCE_SUPPORTED and item.route_state == "INTERPOLATED" for item in snapshots)
    assert any(item.phase is b32.ComponentPhase.CARRIED and item.route_state == "INTERPOLATED" for item in snapshots)
    assert snapshots[-1].phase is b32.ComponentPhase.DESTINATION_SUPPORTED
    assert snapshots[-1].route_state == "HOME"


def test_route_configuration_and_semantic_indexes_are_contiguous(
    inputs: b32.FrozenInputs,
) -> None:
    configurations = b32.sample_route(inputs.route, refinement_factor=2)
    snapshots = b32.semantic_snapshots(inputs.route, refinement_factor=2)
    assert [item.route_configuration_index for item in configurations] == list(range(467))
    assert [item.semantic_snapshot_index for item in snapshots] == list(range(469))


def test_invalid_routes_and_refinement_fail_closed(inputs: b32.FrozenInputs) -> None:
    with pytest.raises(b32.B3_2_InfrastructureError):
        b32.interval_counts((), refinement_factor=1)
    with pytest.raises(b32.B3_2_InfrastructureError):
        b32.interval_counts(inputs.route, refinement_factor=3)
    malformed = b32.RouteState("HOME", (0.0,) * 6, (0.0,) * 7, (1.0,) * 7)
    with pytest.raises(b32.B3_2_InfrastructureError):
        b32.interval_counts((malformed,) * 8, refinement_factor=1)
    nonfinite = b32.RouteState("HOME", (math.nan,) + (0.0,) * 6, (-1.0,) * 7, (1.0,) * 7)
    with pytest.raises(b32.B3_2_InfrastructureError):
        b32.interval_counts((nonfinite,) * 8, refinement_factor=1)
    eight_joint = b32.RouteState("HOME", (0.0,) * 8, (-1.0,) * 8, (1.0,) * 8)
    with pytest.raises(b32.B3_2_InfrastructureError):
        b32.interval_counts((eight_joint,) * 8, refinement_factor=1)


@pytest.mark.parametrize(
    ("delta", "expected_first_interval_count"),
    [
        (0.0, 1),
        (0.010, 1),
        (math.nextafter(0.010, math.inf), 2),
        (-0.025, 3),
    ],
)
def test_interval_algorithm_zero_exact_over_step_and_signed_delta(
    delta: float,
    expected_first_interval_count: int,
) -> None:
    limits = (-10.0,) * 7
    upper = (10.0,) * 7
    start = b32.RouteState("A", (0.0,) * 7, limits, upper)
    end = b32.RouteState("B", (delta, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0), limits, upper)
    route = (start, end, end, end, end, end, end, end)
    assert b32.interval_counts(route, refinement_factor=1)[0] == expected_first_interval_count


def test_fine_maximum_joint_increment_does_not_exceed_five_milliradians(
    inputs: b32.FrozenInputs,
) -> None:
    fine = b32.sample_route(inputs.route, refinement_factor=2)
    maximum = 0.0
    for previous, current in zip(fine, fine[1:]):
        if previous.segment_index != current.segment_index:
            continue
        maximum = max(
            maximum,
            max(
                abs(right - left)
                for left, right in zip(previous.joint_vector, current.joint_vector, strict=True)
            ),
        )
    assert maximum <= 0.005


@pytest.mark.parametrize(
    "field",
    [
        "route_segments",
        "fine_route_configurations",
        "fine_semantic_snapshots",
        "pairs_per_snapshot",
        "total_queries",
    ],
)
def test_each_defensive_protocol_cap_fails_closed(field: str) -> None:
    values = {
        "route_segments": b32.MAX_ROUTE_SEGMENTS,
        "fine_route_configurations": b32.MAX_FINE_ROUTE_CONFIGURATIONS,
        "fine_semantic_snapshots": b32.MAX_FINE_SEMANTIC_SNAPSHOTS,
        "pairs_per_snapshot": b32.MAX_PAIR_QUERIES_PER_SEMANTIC_SNAPSHOT,
        "total_queries": b32.MAX_TOTAL_COLLISION_QUERIES,
    }
    b32.enforce_protocol_caps(**values)
    values[field] += 1
    with pytest.raises(b32.B3_2_InfrastructureError):
        b32.enforce_protocol_caps(**values)


def test_missing_and_explicit_null_required_fields_are_distinct_failures() -> None:
    with pytest.raises(b32.B3_2_InfrastructureError, match="Missing required field"):
        b32._required({}, "value", "record")
    with pytest.raises(b32.B3_2_InfrastructureError, match="Required field is null"):
        b32._required({"value": None}, "value", "record")


def test_collision_pair_inventory_is_exact(
    pairs: tuple[b32.CollisionPair, ...],
    inputs: b32.FrozenInputs,
) -> None:
    assert len(pairs) == 83
    assert [item.pair_index for item in pairs] == list(range(83))
    assert len({item.pair_id for item in pairs}) == 83
    assert [item.category for item in pairs[:21]] == [b32.PairCategory.ROBOT_SELF] * 21
    assert [item.category for item in pairs[21:69]] == [b32.PairCategory.ROBOT_ENVIRONMENT] * 48
    assert [item.category for item in pairs[69:77]] == [b32.PairCategory.COMPONENT_ROBOT] * 8
    assert [item.category for item in pairs[77:]] == [b32.PairCategory.COMPONENT_ENVIRONMENT] * 6
    assert [(item.first_robot_link, item.second_robot_link) for item in pairs[:21]] == [
        (item.first, item.second) for item in inputs.self_collision_pairs
    ]
    expected_pair_ids = [
        *(f"robot_self:{item.first}:{item.second}" for item in inputs.self_collision_pairs),
        *(
            f"robot_environment:{robot_link}:{environment}"
            for robot_link in b32.ROBOT_LINK_INDICES
            for environment in b32.ENVIRONMENT_SEMANTIC_IDS
        ),
        *(f"component_robot:{robot_link}" for robot_link in b32.ROBOT_LINK_INDICES),
        *(
            f"component_environment:{environment}"
            for environment in b32.ENVIRONMENT_SEMANTIC_IDS
        ),
    ]
    assert [item.pair_id for item in pairs] == expected_pair_ids


def test_empty_or_duplicate_pair_inventory_fails_closed(inputs: b32.FrozenInputs) -> None:
    with pytest.raises(b32.B3_2_InfrastructureError):
        b32.build_collision_pair_inventory(())
    duplicates = (inputs.self_collision_pairs[0],) * 21
    with pytest.raises(b32.B3_2_InfrastructureError):
        b32.build_collision_pair_inventory(duplicates)


def test_query_directions_horizon_and_explicit_client(
    monkeypatch: pytest.MonkeyPatch,
    pairs: tuple[b32.CollisionPair, ...],
) -> None:
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def fake_query(*args: object, **kwargs: object) -> b32.b31.ClosestPointResult:
        calls.append((args, kwargs))
        return b32.b31.ClosestPointResult(False, None, 0.050)

    monkeypatch.setattr(b32.b31, "closest_point_query", fake_query)
    scene = b32.RuntimeScene(
        client_id=17,
        robot_body=100,
        component_body=200,
        environment_bodies={name: 300 + index for index, name in enumerate(b32.ENVIRONMENT_SEMANTIC_IDS)},
    )
    for pair in pairs:
        b32._query_pair(scene, pair)
    assert len(calls) == 83
    assert all(args[2] == 17 for args, _ in calls)
    assert all(kwargs["horizon_m"] == 0.050 for _, kwargs in calls)
    assert calls[0] == ((100, 100, 17), {"link_a": -1, "link_b": 1, "horizon_m": 0.050})
    assert calls[21] == ((100, 300, 17), {"link_a": -1, "link_b": -1, "horizon_m": 0.050})
    assert calls[69] == ((200, 100, 17), {"link_a": -1, "link_b": -1, "horizon_m": 0.050})
    assert calls[77] == ((200, 300, 17), {"link_a": -1, "link_b": -1, "horizon_m": 0.050})


def test_carried_transform_uses_link_frame_fields_4_and_5_only() -> None:
    identity = b32.b31.Pose((0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0))
    state_a: tuple[object, ...] = (
        (99.0, 98.0, 97.0),
        (0.5, 0.5, 0.5, 0.5),
        None,
        None,
        (1.0, 2.0, 3.0),
        (0.0, 0.0, 0.0, 1.0),
    )
    state_b = (
        (-99.0, -98.0, -97.0),
        (1.0, 0.0, 0.0, 0.0),
        None,
        None,
        (1.0, 2.0, 3.0),
        (0.0, 0.0, 0.0, 1.0),
    )
    first = b32.carried_pose_from_link_state(state_a, identity)
    second = b32.carried_pose_from_link_state(state_b, identity)
    assert first == second
    assert first.position == pytest.approx((1.0, 2.0, 3.0))


@pytest.mark.parametrize(
    "malformed",
    [None, 0, 1.0, object(), "malformed", b"malformed", (), (None,) * 5],
)
def test_malformed_link_states_fail_closed(malformed: object) -> None:
    identity = b32.b31.Pose((0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0))
    with pytest.raises(b32.B3_2_InfrastructureError, match="Malformed PyBullet link state"):
        b32.carried_pose_from_link_state(malformed, identity)  # type: ignore[arg-type]


def test_post_release_snapshots_use_exact_predicted_release_pose(
    inputs: b32.FrozenInputs,
) -> None:
    snapshots = b32.semantic_snapshots(inputs.route, refinement_factor=2)
    release_post = [
        snapshot
        for snapshot in snapshots
        if snapshot.phase is b32.ComponentPhase.RELEASE_BOUNDARY
        and snapshot.boundary_snapshot is b32.BoundarySnapshot.POST
    ]
    destination_supported = [
        snapshot
        for snapshot in snapshots
        if snapshot.phase is b32.ComponentPhase.DESTINATION_SUPPORTED
    ]
    assert len(release_post) == 1
    assert destination_supported
    scene = b32.RuntimeScene(-1, -1, -1, {})
    for snapshot in [*release_post, *destination_supported]:
        assert b32._component_pose(scene, snapshot, inputs.predecessor) == (
            inputs.predecessor.predicted_release_pose
        )
    nominal_snapped_pose = b32.b31.Pose(
        (0.5, 0.2, 0.045),
        (0.0, 0.0, 0.0, 1.0),
    )
    assert inputs.predecessor.predicted_release_pose != nominal_snapped_pose


def test_result_vocabulary_and_failure_validation() -> None:
    assert b32.overall_result(()) == b32.PASS_RESULT
    failure = {"failure_code": b32.SCIENTIFIC_FAILURE_CODES[0]}
    assert b32.overall_result((failure,)) == b32.FAIL_RESULT
    with pytest.raises(b32.B3_2_InfrastructureError):
        b32.overall_result(({"failure_code": "FAIL"},))


@pytest.mark.parametrize("first_code", b32.SCIENTIFIC_FAILURE_CODES)
def test_multiple_failure_categories_remain_complete_and_first_ordered(
    first_code: str,
) -> None:
    ordered_codes = [
        first_code,
        *(code for code in b32.SCIENTIFIC_FAILURE_CODES if code != first_code),
    ]
    failures = [
        {
            "semantic_snapshot_index": 0,
            "pair_index": pair_index,
            "pair_id": f"synthetic:{pair_index}",
            "failure_code": code,
            "route_state": "HOME",
            "phase": "SOURCE_SUPPORTED",
            "boundary_snapshot": "NONE",
        }
        for pair_index, code in enumerate(ordered_codes)
    ]
    result = b32._result_json(failures)
    assert result["overall_result"] == b32.FAIL_RESULT
    assert result["scientific_failures"] == failures
    assert result["failure_codes_present"] == ordered_codes
    assert result["failure_summary"] == {
        code: 1 for code in b32.SCIENTIFIC_FAILURE_CODES
    }
    assert result["primary_failure"] == failures[0]


def test_live_protocol_exact_query_accounting_and_non_short_circuit(
    live_artifact: dict[str, object],
) -> None:
    coarse = live_artifact["coarse_sensitivity_summary"]
    fine = live_artifact["authoritative_fine_route"]
    reproducibility = live_artifact["reproducibility_summary"]
    assert isinstance(coarse, dict) and isinstance(fine, dict) and isinstance(reproducibility, dict)
    assert coarse["query_count"] == 19_588
    assert fine["query_count"] == 38_927
    assert reproducibility["fine_pass_2_query_count"] == 38_927
    assert coarse["query_count"] + fine["query_count"] + reproducibility["fine_pass_2_query_count"] == 97_442
    assert fine["semantic_snapshot_count"] == 469
    assert fine["route_configuration_count"] == 467


def test_live_scientific_failures_are_complete_ordered_and_canonical(
    live_artifact: dict[str, object],
) -> None:
    result = live_artifact["result"]
    assert isinstance(result, dict)
    failures = result["scientific_failures"]
    assert isinstance(failures, list)
    expected = sorted(
        failures,
        key=lambda item: (item["semantic_snapshot_index"], item["pair_index"], item["failure_code"]),
    )
    assert failures == expected
    assert set(result["failure_codes_present"]).issubset(set(b32.SCIENTIFIC_FAILURE_CODES))
    assert result["overall_result"] in {b32.PASS_RESULT, b32.FAIL_RESULT}
    assert (result["overall_result"] == b32.PASS_RESULT) == (len(failures) == 0)


def test_destination_release_observation_is_measured_not_hard_coded(
    live_artifact: dict[str, object],
) -> None:
    fine = live_artifact["authoritative_fine_route"]
    assert isinstance(fine, dict)
    snapshots = fine["semantic_snapshots"]
    release = [
        item
        for item in snapshots
        if item["route_state"] == "DESTINATION_PLACE"
        and item["phase"] == "RELEASE_BOUNDARY"
        and item["boundary_snapshot"] == "POST"
    ]
    assert len(release) == 1
    observations = [
        item
        for item in release[0]["observations"]
        if item["pair_id"] == "component_environment:destination_floor"
    ]
    assert len(observations) == 1
    observation = observations[0]
    assert observation["permission"] == b32.PairPolicy.REQUIRED_SUPPORT.value
    classification = b32.classify_closest_point(
        b32.b31.ClosestPointResult(
            observation["found"],
            observation["signed_distance_m"],
            observation["separation_lower_bound_m"],
        )
    )
    assert observation["classification"] == classification.value
    assert observation["decision"] == b32.decide_contact(b32.PairPolicy.REQUIRED_SUPPORT, classification)


def test_live_reproducibility_and_nested_coarse_agreement(
    live_artifact: dict[str, object],
) -> None:
    reproducibility = live_artifact["reproducibility_summary"]
    coarse = live_artifact["coarse_sensitivity_summary"]
    assert isinstance(reproducibility, dict) and isinstance(coarse, dict)
    assert reproducibility["fresh_independent_direct_sessions"] is True
    assert reproducibility["maximum_found_distance_spread_m"] <= 1.0e-12
    assert reproducibility["found_state_mismatch_count"] == 0
    assert reproducibility["decision_mismatch_count"] == 0
    assert reproducibility["scientific_failure_mismatch"] is False
    assert reproducibility["overall_result_mismatch"] is False
    nested = coarse["nested_authoritative_comparison"]
    assert nested == {
        "nested_semantic_snapshot_comparison_count": 236,
        "nested_decision_comparison_count": 19_588,
        "decision_disagreement_count": 0,
        "coarse_grid_exactly_nested": True,
    }


def _minimal_snapshot(found: bool, distance: float | None) -> dict[str, object]:
    return {
        "route_configuration_index": 0,
        "semantic_snapshot_index": 0,
        "segment_index": 0,
        "segment_sample_index": 0,
        "segment_interval_count": 1,
        "alpha": 0.0,
        "route_state": "HOME",
        "phase": "SOURCE_SUPPORTED",
        "boundary_snapshot": "NONE",
        "joint_vector": [0.0] * 7,
        "component_pose": {"position_m": [0.0] * 3, "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0]},
        "observations": [
            {
                "pair_index": 0,
                "pair_id": "robot_self:-1:1",
                "found": found,
                "signed_distance_m": distance,
                "separation_lower_bound_m": None if found else 0.050,
                "classification": "SEPARATED" if found else "SEPARATED_BEYOND_QUERY_HORIZON",
                "permission": "FORBIDDEN",
                "decision": "PASS",
            }
        ],
    }


def test_found_no_result_reproducibility_mismatch_fails_closed() -> None:
    first = b32.PassEvidence(b32.PassName.FINE_PASS_1, (2,), 1, (_minimal_snapshot(True, 0.01),), (), 1, b32.PASS_RESULT)
    second = b32.PassEvidence(b32.PassName.FINE_PASS_2, (2,), 1, (_minimal_snapshot(False, None),), (), 1, b32.PASS_RESULT)
    with pytest.raises(b32.B3_2_InfrastructureError):
        b32.compare_fine_passes(first, second)


def test_found_distance_reproducibility_spread_fails_closed() -> None:
    first = b32.PassEvidence(b32.PassName.FINE_PASS_1, (2,), 1, (_minimal_snapshot(True, 0.01),), (), 1, b32.PASS_RESULT)
    second = b32.PassEvidence(b32.PassName.FINE_PASS_2, (2,), 1, (_minimal_snapshot(True, 0.01 + 2e-12),), (), 1, b32.PASS_RESULT)
    with pytest.raises(b32.B3_2_InfrastructureError):
        b32.compare_fine_passes(first, second)


def test_aggregate_is_authoritative_fine_pass_1_only_and_exact_schema(
    live_artifact: dict[str, object],
) -> None:
    aggregate = live_artifact["aggregate_clearance_summary"]
    assert isinstance(aggregate, dict)
    assert set(aggregate) == {
        "total_query_count",
        "found_query_count",
        "censored_no_result_count",
        "minimum_observed_signed_distance",
        "minimum_forbidden_observed_signed_distance",
        "contact_band_event_count",
        "material_penetration_event_count",
        "forbidden_failure_count",
        "support_material_penetration_count",
        "required_support_missing_count",
    }
    assert aggregate["total_query_count"] == 38_927
    assert aggregate["found_query_count"] + aggregate["censored_no_result_count"] == 38_927
    fine = live_artifact["authoritative_fine_route"]
    assert isinstance(fine, dict)
    assert aggregate["forbidden_failure_count"] == fine["failure_summary"][b32.SCIENTIFIC_FAILURE_CODES[0]]
    assert aggregate["support_material_penetration_count"] == fine["failure_summary"][b32.SCIENTIFIC_FAILURE_CODES[1]]
    assert aggregate["required_support_missing_count"] == fine["failure_summary"][b32.SCIENTIFIC_FAILURE_CODES[2]]


def test_live_artifact_schema_provenance_and_required_sections(
    live_artifact: dict[str, object],
) -> None:
    assert live_artifact["schema_identifier"] == b32.SCHEMA_IDENTIFIER
    assert live_artifact["schema_version"] == "1.0.0"
    assert live_artifact["gate_identifier"] == b32.GATE_IDENTIFIER
    required = {
        "provenance",
        "frozen_input_contract",
        "numeric_contact_contract",
        "interpolation_contract",
        "collision_pair_inventory",
        "component_phase_contract",
        "coarse_sensitivity_summary",
        "authoritative_fine_route",
        "reproducibility_summary",
        "aggregate_clearance_summary",
        "result",
        "claim_boundaries",
    }
    assert required.issubset(live_artifact)
    provenance = live_artifact["provenance"]
    assert isinstance(provenance, dict)
    assert provenance["specification"]["sha256"] == b32.SPECIFICATION_SHA256
    assert provenance["specification"]["git_blob"] == b32.SPECIFICATION_GIT_BLOB
    assert provenance["source_sha256"] == b32.b31.sha256_file(SOURCE_PATH)
    assert provenance["runner_sha256"] == b32.b31.sha256_file(RUNNER_PATH)
    assert provenance["tests_sha256"] == b32.b31.sha256_file(Path(__file__))


def test_predecessor_artifacts_are_byte_identical() -> None:
    assert b32.b31.sha256_file(REPOSITORY_ROOT / b32.B1_2_ARTIFACT) == b32.B1_2_ARTIFACT_SHA256
    assert b32.b31.sha256_file(REPOSITORY_ROOT / b32.B2_ARTIFACT) == b32.B2_ARTIFACT_SHA256
    assert b32.b31.sha256_file(REPOSITORY_ROOT / b32.B3_1_ARTIFACT) == b32.B3_1_ARTIFACT_SHA256


def test_canonical_serialization_is_deterministic_finite_utf8_lf(
    live_artifact: dict[str, object],
) -> None:
    first = b32.serialize_artifact(live_artifact)
    second = b32.serialize_artifact(live_artifact)
    assert first == second
    assert hashlib.sha256(first).digest() == hashlib.sha256(second).digest()
    assert not first.startswith(b"\xef\xbb\xbf")
    assert b"\r" not in first
    assert first.endswith(b"\n")
    assert not first.endswith(b"\n\n")
    decoded = first.decode("utf-8")
    assert json.loads(decoded) == live_artifact
    assert "C:\\Users\\" not in decoded
    assert "/Users/" not in decoded


@pytest.mark.parametrize("invalid", [math.nan, math.inf, -math.inf])
def test_serialization_rejects_nonfinite_numbers(invalid: float) -> None:
    with pytest.raises(b32.B3_2_InfrastructureError):
        b32.serialize_artifact({"schema_identifier": b32.SCHEMA_IDENTIFIER, "value": invalid})


def test_exclusive_writer_digest_and_overwrite_refusal(
    tmp_path: Path,
    live_artifact: dict[str, object],
) -> None:
    artifact = live_artifact
    output = tmp_path / "evidence.json"
    digest = b32.write_artifact(artifact, output)
    payload = b32.serialize_artifact(artifact)
    assert digest == hashlib.sha256(payload).hexdigest()
    assert output.read_bytes() == payload
    assert output.with_suffix(".json.sha256").read_text(encoding="ascii") == f"{digest}  evidence.json\n"
    assert b32.verify_artifact_digest(output) == digest
    with pytest.raises(FileExistsError):
        b32.write_artifact(artifact, output)


def test_json_race_preserves_foreign_json_and_creates_no_digest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    live_artifact: dict[str, object],
) -> None:
    output = tmp_path / "evidence.json"
    digest_path = output.with_suffix(".json.sha256")
    foreign_json = b"foreign-json-owner\n"
    original = b32._write_exclusive_fsync
    calls = 0

    def race_first_exclusive_create(path: Path, payload: bytes) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            path.write_bytes(foreign_json)
        original(path, payload)

    monkeypatch.setattr(b32, "_write_exclusive_fsync", race_first_exclusive_create)
    with pytest.raises(FileExistsError):
        b32.write_artifact(live_artifact, output)
    assert output.read_bytes() == foreign_json
    assert not digest_path.exists()


def test_digest_race_removes_owned_json_and_preserves_foreign_digest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    live_artifact: dict[str, object],
) -> None:
    output = tmp_path / "evidence.json"
    digest_path = output.with_suffix(".json.sha256")
    foreign_digest = b"foreign-digest-owner\n"
    original = b32._write_exclusive_fsync
    calls = 0

    def race_digest_exclusive_create(path: Path, payload: bytes) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            path.write_bytes(foreign_digest)
        original(path, payload)

    monkeypatch.setattr(b32, "_write_exclusive_fsync", race_digest_exclusive_create)
    with pytest.raises(FileExistsError):
        b32.write_artifact(live_artifact, output)
    assert not output.exists()
    assert digest_path.read_bytes() == foreign_digest


def test_handled_digest_failure_removes_new_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    live_artifact: dict[str, object],
) -> None:
    output = tmp_path / "evidence.json"
    original = b32._write_exclusive_fsync
    calls = 0

    def failing_second_write(path: Path, payload: bytes) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("digest write failed")
        original(path, payload)

    monkeypatch.setattr(b32, "_write_exclusive_fsync", failing_second_write)
    with pytest.raises(OSError):
        b32.write_artifact(live_artifact, output)
    assert not output.exists()
    assert not output.with_suffix(".json.sha256").exists()


def test_post_write_verification_failure_removes_both_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    live_artifact: dict[str, object],
) -> None:
    output = tmp_path / "evidence.json"

    def fail_verification(_: Path) -> str:
        raise b32.B3_2_InfrastructureError("verification failed")

    monkeypatch.setattr(b32, "verify_artifact_digest", fail_verification)
    with pytest.raises(b32.B3_2_InfrastructureError):
        b32.write_artifact(live_artifact, output)
    assert not output.exists()
    assert not output.with_suffix(".json.sha256").exists()


def test_incomplete_evidence_cannot_be_written_as_canonical(tmp_path: Path) -> None:
    output = tmp_path / "evidence.json"
    incomplete = {
        "schema_identifier": b32.SCHEMA_IDENTIFIER,
        "schema_version": b32.SCHEMA_VERSION,
        "gate_identifier": b32.GATE_IDENTIFIER,
    }
    with pytest.raises(b32.B3_2_InfrastructureError):
        b32.write_artifact(incomplete, output)
    assert not output.exists()
    assert not output.with_suffix(".json.sha256").exists()


def test_incomplete_evidence_with_correct_digest_cannot_verify(tmp_path: Path) -> None:
    output = tmp_path / "evidence.json"
    incomplete = {
        "schema_identifier": b32.SCHEMA_IDENTIFIER,
        "schema_version": b32.SCHEMA_VERSION,
        "gate_identifier": b32.GATE_IDENTIFIER,
    }
    payload = b32.serialize_artifact(incomplete)
    output.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    output.with_suffix(".json.sha256").write_bytes(
        f"{digest}  {output.name}\n".encode("ascii")
    )
    with pytest.raises(b32.B3_2_InfrastructureError):
        b32.verify_artifact_digest(output)


@pytest.mark.parametrize("orphan", ["json", "digest"])
def test_orphan_evidence_is_rejected(tmp_path: Path, orphan: str) -> None:
    output = tmp_path / "evidence.json"
    digest_path = output.with_suffix(".json.sha256")
    if orphan == "json":
        output.write_bytes(b"{}\n")
    else:
        digest_path.write_bytes(f"{'0' * 64}  {output.name}\n".encode("ascii"))
    with pytest.raises(b32.B3_2_InfrastructureError):
        b32.verify_artifact_digest(output)


def test_canonical_validator_rejects_unsorted_failures(
    live_artifact: dict[str, object],
) -> None:
    malformed = dict(live_artifact)
    result = dict(live_artifact["result"])
    failures = list(result["scientific_failures"])
    assert len(failures) >= 2
    failures[0], failures[1] = failures[1], failures[0]
    result["scientific_failures"] = failures
    malformed["result"] = result
    with pytest.raises(b32.B3_2_InfrastructureError, match="canonically ordered"):
        b32.validate_canonical_artifact(malformed)


def test_canonical_validator_rejects_empty_provenance(
    live_artifact: dict[str, object],
) -> None:
    mutated = dict(live_artifact)
    mutated["provenance"] = {}
    with pytest.raises(b32.B3_2_InfrastructureError):
        b32.validate_canonical_artifact(mutated)


def test_canonical_validator_rejects_missing_semantic_snapshot_field(
    live_artifact: dict[str, object],
) -> None:
    mutated, _ = _copy_observation_for_mutation(live_artifact, 0, 0)
    fine = mutated["authoritative_fine_route"]
    snapshot = fine["semantic_snapshots"][0]
    snapshot.pop("joint_vector")
    with pytest.raises(b32.B3_2_InfrastructureError, match="snapshot fields"):
        b32.validate_canonical_artifact(mutated)


def test_canonical_validator_rejects_observation_pair_id_drift(
    live_artifact: dict[str, object],
) -> None:
    mutated, observation = _copy_observation_for_mutation(live_artifact, 0, 0)
    observation["pair_id"] = "robot_self:-1:2"
    with pytest.raises(b32.B3_2_InfrastructureError, match="inventory index"):
        b32.validate_canonical_artifact(mutated)


def test_canonical_validator_rejects_classification_distance_contradiction(
    live_artifact: dict[str, object],
) -> None:
    mutated, observation = _copy_observation_for_mutation(live_artifact, 0, 0)
    assert observation["found"] is False
    observation["classification"] = b32.DistanceClassification.SEPARATED.value
    with pytest.raises(b32.B3_2_InfrastructureError, match="classification"):
        b32.validate_canonical_artifact(mutated)


def test_canonical_validator_rejects_permission_policy_contradiction(
    live_artifact: dict[str, object],
) -> None:
    mutated, observation = _copy_observation_for_mutation(live_artifact, 352, 78)
    assert observation["permission"] == b32.PairPolicy.REQUIRED_SUPPORT.value
    observation["permission"] = b32.PairPolicy.PERMITTED_SUPPORT.value
    with pytest.raises(b32.B3_2_InfrastructureError, match="permission"):
        b32.validate_canonical_artifact(mutated)


def test_canonical_validator_rejects_manufactured_pass_with_synchronized_metadata(
    live_artifact: dict[str, object],
) -> None:
    mutated = copy.deepcopy(live_artifact)
    fine = mutated["authoritative_fine_route"]
    changed_decisions = 0
    for snapshot in fine["semantic_snapshots"]:
        for observation in snapshot["observations"]:
            if observation["decision"] != "PASS":
                observation["decision"] = "PASS"
                changed_decisions += 1
    assert changed_decisions == 118
    zero_summary = {code: 0 for code in b32.SCIENTIFIC_FAILURE_CODES}
    fine["failure_summary"] = zero_summary
    fine["scientific_failure_count"] = 0
    fine["overall_result"] = b32.PASS_RESULT
    mutated["result"] = {
        "overall_result": b32.PASS_RESULT,
        "scientific_failures": [],
        "scientific_failure_count": 0,
        "failure_summary": zero_summary,
        "failure_codes_present": [],
        "primary_failure": None,
    }
    aggregate = dict(mutated["aggregate_clearance_summary"])
    aggregate["forbidden_failure_count"] = 0
    aggregate["support_material_penetration_count"] = 0
    aggregate["required_support_missing_count"] = 0
    mutated["aggregate_clearance_summary"] = aggregate
    reproducibility = dict(mutated["reproducibility_summary"])
    reproducibility["fine_pass_2_result"] = b32.PASS_RESULT
    mutated["reproducibility_summary"] = reproducibility
    with pytest.raises(b32.B3_2_InfrastructureError, match="decision"):
        b32.validate_canonical_artifact(mutated)


def test_canonical_validator_rejects_aggregate_count_corruption(
    live_artifact: dict[str, object],
) -> None:
    mutated = dict(live_artifact)
    aggregate = dict(live_artifact["aggregate_clearance_summary"])
    aggregate["found_query_count"] += 1
    aggregate["censored_no_result_count"] -= 1
    mutated["aggregate_clearance_summary"] = aggregate
    with pytest.raises(b32.B3_2_InfrastructureError, match="authoritative observations"):
        b32.validate_canonical_artifact(mutated)


def test_canonical_validator_rejects_null_forbidden_minimum_with_found_population(
    live_artifact: dict[str, object],
) -> None:
    mutated = dict(live_artifact)
    aggregate = dict(live_artifact["aggregate_clearance_summary"])
    assert aggregate["minimum_forbidden_observed_signed_distance"] is not None
    aggregate["minimum_forbidden_observed_signed_distance"] = None
    mutated["aggregate_clearance_summary"] = aggregate
    with pytest.raises(b32.B3_2_InfrastructureError, match="cannot be null"):
        b32.validate_canonical_artifact(mutated)


def test_digest_verification_rejects_machine_local_path_with_correct_digest(
    tmp_path: Path,
    live_artifact: dict[str, object],
) -> None:
    mutated = dict(live_artifact)
    provenance = dict(live_artifact["provenance"])
    provenance["machine_local_path"] = "C:\\Users\\attacker\\evidence.json"
    mutated["provenance"] = provenance
    payload = (
        json.dumps(
            mutated,
            sort_keys=True,
            indent=2,
            allow_nan=False,
            ensure_ascii=False,
        )
        + "\n"
    ).encode("utf-8")
    output = tmp_path / "evidence.json"
    _write_raw_evidence_pair(output, payload)
    with pytest.raises(b32.B3_2_InfrastructureError):
        b32.verify_artifact_digest(output)


def test_digest_verification_rejects_noncanonical_format_with_correct_digest(
    tmp_path: Path,
    live_artifact: dict[str, object],
) -> None:
    payload = (
        json.dumps(
            live_artifact,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
            ensure_ascii=False,
        )
        + "\n"
    ).encode("utf-8")
    assert payload != b32.serialize_artifact(live_artifact)
    output = tmp_path / "evidence.json"
    _write_raw_evidence_pair(output, payload)
    with pytest.raises(b32.B3_2_InfrastructureError, match="canonical serialization"):
        b32.verify_artifact_digest(output)


def test_claim_validation_rejects_missing_discrete_sampling_limitation(
    live_artifact: dict[str, object],
) -> None:
    mutated = dict(live_artifact)
    claims = dict(live_artifact["claim_boundaries"])
    claims.pop("discrete_sampling_limitation")
    mutated["claim_boundaries"] = claims
    with pytest.raises(b32.B3_2_InfrastructureError, match="claim boundaries"):
        b32.validate_canonical_artifact(mutated)


def test_claim_validation_rejects_maximum_pass_overclaim(
    live_artifact: dict[str, object],
) -> None:
    mutated = dict(live_artifact)
    claims = dict(live_artifact["claim_boundaries"])
    claims["maximum_pass_claim"] = "The trajectory is continuously collision free."
    mutated["claim_boundaries"] = claims
    with pytest.raises(b32.B3_2_InfrastructureError, match="claim boundaries"):
        b32.validate_canonical_artifact(mutated)


def test_claim_validation_rejects_arbitrary_sampling_limitation(
    live_artifact: dict[str, object],
) -> None:
    mutated = dict(live_artifact)
    claims = dict(live_artifact["claim_boundaries"])
    claims["discrete_sampling_limitation"] = "Sampling has limitations."
    mutated["claim_boundaries"] = claims
    with pytest.raises(b32.B3_2_InfrastructureError, match="claim boundaries"):
        b32.validate_canonical_artifact(mutated)


def test_component_phase_contract_content_is_canonical(
    live_artifact: dict[str, object],
) -> None:
    mutated = dict(live_artifact)
    contract = dict(live_artifact["component_phase_contract"])
    contract["component_robot_policy"] = b32.PairPolicy.PERMITTED_SUPPORT.value
    mutated["component_phase_contract"] = contract
    with pytest.raises(b32.B3_2_InfrastructureError, match="component phase contract"):
        b32.validate_canonical_artifact(mutated)


def test_semantic_sequence_rejects_source_supported_relabelled_carried(
    live_artifact: dict[str, object],
) -> None:
    snapshots = live_artifact["authoritative_fine_route"]["semantic_snapshots"]
    index = next(
        index
        for index, snapshot in enumerate(snapshots)
        if snapshot["phase"] == b32.ComponentPhase.SOURCE_SUPPORTED.value
    )
    mutated, copied = _copy_snapshots_for_mutation(live_artifact, index)
    copied[index]["phase"] = b32.ComponentPhase.CARRIED.value
    with pytest.raises(b32.B3_2_InfrastructureError, match="semantic phase sequence"):
        b32.validate_canonical_artifact(mutated)


def test_semantic_sequence_rejects_destination_supported_relabelled_carried(
    live_artifact: dict[str, object],
) -> None:
    snapshots = live_artifact["authoritative_fine_route"]["semantic_snapshots"]
    index = next(
        index
        for index, snapshot in enumerate(snapshots)
        if snapshot["phase"] == b32.ComponentPhase.DESTINATION_SUPPORTED.value
    )
    mutated, copied = _copy_snapshots_for_mutation(live_artifact, index)
    copied[index]["phase"] = b32.ComponentPhase.CARRIED.value
    with pytest.raises(b32.B3_2_InfrastructureError, match="semantic phase sequence"):
        b32.validate_canonical_artifact(mutated)


def test_semantic_sequence_rejects_boundary_pre_post_reversal(
    live_artifact: dict[str, object],
) -> None:
    snapshots = live_artifact["authoritative_fine_route"]["semantic_snapshots"]
    pre_index = next(
        index
        for index, snapshot in enumerate(snapshots)
        if snapshot["phase"] == b32.ComponentPhase.ATTACHMENT_BOUNDARY.value
        and snapshot["boundary_snapshot"] == b32.BoundarySnapshot.PRE.value
    )
    post_index = pre_index + 1
    mutated, copied = _copy_snapshots_for_mutation(
        live_artifact,
        pre_index,
        post_index,
    )
    copied[pre_index]["boundary_snapshot"] = b32.BoundarySnapshot.POST.value
    copied[post_index]["boundary_snapshot"] = b32.BoundarySnapshot.PRE.value
    with pytest.raises(b32.B3_2_InfrastructureError, match="semantic phase sequence"):
        b32.validate_canonical_artifact(mutated)


def test_semantic_sequence_rejects_endpoint_relabelled_interpolated(
    live_artifact: dict[str, object],
) -> None:
    snapshots = live_artifact["authoritative_fine_route"]["semantic_snapshots"]
    index = next(
        index
        for index, snapshot in enumerate(snapshots)
        if snapshot["route_state"] == "SOURCE_HIGH"
    )
    mutated, copied = _copy_snapshots_for_mutation(live_artifact, index)
    copied[index]["route_state"] = "INTERPOLATED"
    with pytest.raises(b32.B3_2_InfrastructureError, match="semantic phase sequence"):
        b32.validate_canonical_artifact(mutated)


def test_semantic_sequence_rejects_later_segment_sample_zero(
    live_artifact: dict[str, object],
) -> None:
    snapshots = live_artifact["authoritative_fine_route"]["semantic_snapshots"]
    index = next(
        index
        for index, snapshot in enumerate(snapshots)
        if snapshot["segment_index"] == 2 and snapshot["segment_sample_index"] == 1
    )
    mutated, copied = _copy_snapshots_for_mutation(live_artifact, index)
    copied[index]["segment_sample_index"] = 0
    copied[index]["alpha"] = 0.0
    with pytest.raises(b32.B3_2_InfrastructureError, match="semantic phase sequence"):
        b32.validate_canonical_artifact(mutated)


def test_checked_in_fail_evidence_is_retained_and_byte_reproducible(
    live_artifact: dict[str, object],
) -> None:
    payload = b32.serialize_artifact(live_artifact)
    assert payload == ARTIFACT_PATH.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    assert b32.verify_artifact_digest(ARTIFACT_PATH) == digest
    result = live_artifact["result"]
    assert isinstance(result, dict)
    assert result["overall_result"] == b32.FAIL_RESULT
    assert result["scientific_failure_count"] == 118
    assert result["failure_codes_present"] == [
        "B3_2_FAIL_SUPPORT_MATERIAL_PENETRATION"
    ]


def test_prohibited_execution_apis_are_absent_from_executable_ast() -> None:
    tree = ast.parse(SOURCE_PATH.read_text(encoding="utf-8"))
    called_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                called_names.add(node.func.attr)
            elif isinstance(node.func, ast.Name):
                called_names.add(node.func.id)
    prohibited = {
        "stepSimulation",
        "setRealTimeSimulation",
        "calculateInverseKinematics",
        "createConstraint",
        "setJointMotorControl",
        "setJointMotorControl2",
        "setJointMotorControlArray",
        "getContactPoints",
    }
    assert called_names.isdisjoint(prohibited)


def test_no_async_network_threads_timers_or_nondeterministic_identity() -> None:
    tree = ast.parse(SOURCE_PATH.read_text(encoding="utf-8"))
    imported_roots = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_roots.update(
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    )
    assert imported_roots.isdisjoint(
        {"asyncio", "threading", "multiprocessing", "socket", "requests", "httpx", "time", "uuid"}
    )


def test_claim_boundaries_never_expand_discrete_scope(
    live_artifact: dict[str, object],
) -> None:
    claims = live_artifact["claim_boundaries"]
    assert isinstance(claims, dict)
    assert claims["maximum_pass_claim"] == (
        "No forbidden collision/contact was observed at any configuration sampled "
        "along the frozen B2 route under the declared deterministic discrete B3.2 "
        "protocol."
    )
    assert claims["scientific_fail_claim"] == (
        "Only the recorded discrete geometric failures under the frozen B3.2 protocol "
        "are established."
    )
    assert claims["discrete_sampling_limitation"] == (
        "Discrete sampling cannot prove the absence of collision between evaluated "
        "configurations."
    )
    assert claims["continuous_collision_freedom_claimed"] is False
    assert claims["dynamic_executability_claimed"] is False
    assert claims["physical_robot_safety_claimed"] is False
    assert claims["industrial_certification_claimed"] is False
    assert claims["sim_to_real_validity_claimed"] is False

def test_b3_2_frozen_external_contract_literals() -> None:
    """Guard the remotely frozen B3.2 specification independently."""

    assert b32.SCHEMA_IDENTIFIER == (
        "prototype5.scene_collision_route_qualification.b3_2"
    )
    assert b32.SCHEMA_VERSION == "1.0.0"
    assert b32.GATE_IDENTIFIER == (
        "B3_2_DISCRETE_ROUTE_COLLISION_QUALIFICATION"
    )

    assert b32.PASS_RESULT == (
        "B3_2_PASS_DISCRETE_ROUTE_QUALIFICATION"
    )
    assert b32.FAIL_RESULT == (
        "B3_2_FAIL_DISCRETE_ROUTE_QUALIFICATION"
    )

    assert b32.SCIENTIFIC_FAILURE_CODES == (
        "B3_2_FAIL_FORBIDDEN_CONTACT",
        "B3_2_FAIL_SUPPORT_MATERIAL_PENETRATION",
        "B3_2_FAIL_REQUIRED_SUPPORT_MISSING",
    )

    assert b32.NUMERICAL_CONTACT_EPSILON_M == 1.0e-12
    assert b32.CLOSEST_POINT_QUERY_HORIZON_M == 0.050
    assert b32.BASE_MAX_JOINT_STEP_RAD == 0.010
    assert b32.ROBOT_LINK_INDICES == (-1, 0, 1, 2, 3, 4, 5, 6)
    assert b32.ENVIRONMENT_SEMANTIC_IDS == (
        "source_platform",
        "destination_floor",
        "destination_wall_x_minus",
        "destination_wall_x_plus",
        "destination_wall_y_minus",
        "destination_wall_y_plus",
    )

    assert b32.EXPECTED_ROUTE_STATES == (
        "HOME",
        "SOURCE_HIGH",
        "SOURCE_PICK",
        "SOURCE_HIGH_RETURN",
        "DESTINATION_HIGH",
        "DESTINATION_PLACE",
        "DESTINATION_HIGH_RETURN",
        "HOME",
    )

    assert b32.EXPECTED_COARSE_INTERVALS == (
        39, 20, 19, 77, 20, 19, 39
    )
    assert b32.EXPECTED_FINE_INTERVALS == (
        78, 40, 38, 154, 40, 38, 78
    )

    assert b32.EXPECTED_COARSE_ROUTE_CONFIGURATIONS == 234
    assert b32.EXPECTED_FINE_ROUTE_CONFIGURATIONS == 467
    assert b32.EXPECTED_COARSE_SEMANTIC_SNAPSHOTS == 236
    assert b32.EXPECTED_FINE_SEMANTIC_SNAPSHOTS == 469

    assert (
        b32.EXPECTED_PAIR_QUERIES_PER_SEMANTIC_SNAPSHOT
        == 83
    )
    assert b32.EXPECTED_COARSE_QUERY_COUNT == 19_588
    assert b32.EXPECTED_FINE_QUERY_COUNT == 38_927
    assert b32.EXPECTED_TOTAL_QUERY_COUNT == 97_442

    assert b32.MAX_ROUTE_SEGMENTS == 7
    assert b32.MAX_FINE_ROUTE_CONFIGURATIONS == 1024
    assert b32.MAX_FINE_SEMANTIC_SNAPSHOTS == 1024
    assert (
        b32.MAX_PAIR_QUERIES_PER_SEMANTIC_SNAPSHOT
        == 83
    )
    assert b32.MAX_TOTAL_COLLISION_QUERIES == 150_000

    assert b32.overall_result(()) == (
        "B3_2_PASS_DISCRETE_ROUTE_QUALIFICATION"
    )

    failure = {
        "failure_code":
            "B3_2_FAIL_SUPPORT_MATERIAL_PENETRATION"
    }

    assert b32.overall_result((failure,)) == (
        "B3_2_FAIL_DISCRETE_ROUTE_QUALIFICATION"
    )
