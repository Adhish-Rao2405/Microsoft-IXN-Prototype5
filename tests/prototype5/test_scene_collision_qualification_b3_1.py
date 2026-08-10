from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import subprocess

import pytest

from src.prototype5 import scene_collision_qualification_b3_1 as b3


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_PATH = (
    REPOSITORY_ROOT
    / "results/prototype5/scene_calibration/phase_b3_1_collision_qualification.json"
)
DIGEST_PATH = ARTIFACT_PATH.with_suffix(ARTIFACT_PATH.suffix + ".sha256")


@pytest.fixture(scope="module")
def scene() -> dict[str, object]:
    return b3.reconstruct_frozen_scene()


@pytest.fixture(scope="module")
def kernel() -> dict[str, object]:
    return b3.qualify_distance_kernel()


@pytest.fixture(scope="module")
def self_collision() -> dict[str, object]:
    return b3.qualify_self_collision_semantics()


@pytest.fixture(scope="module")
def predecessor() -> b3.PredecessorEvidence:
    return b3.load_predecessor_evidence(REPOSITORY_ROOT)


@pytest.fixture(scope="module")
def artifact() -> dict[str, object]:
    return json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))


def test_frozen_contract_literals_are_independent() -> None:
    assert b3.STARTING_HEAD == "f0967b746afa2e027b4fe7eb524138473cb6db8b"
    assert b3.B1_2_ARTIFACT_SHA256 == (
        "b852fcdba89a89e0a83abc83c80cdf6eceb6b5a33babaf0558fce6d479b80f2c"
    )
    assert b3.B2_ARTIFACT_SHA256 == (
        "a5a468145aea5aa21a649cccd1de3d6d2f8f15349d4b326db9380a6ad1256554"
    )
    assert b3.SOURCE_XY_M == (0.50, -0.20)
    assert b3.DESTINATION_XY_M == (0.50, 0.20)
    assert b3.COMPONENT_HALF_EXTENTS_M == (0.025, 0.025, 0.025)
    assert b3.CLOSEST_POINT_QUERY_HORIZON_M == 0.050


def test_frozen_box_reconstruction_matches_literal_bounds() -> None:
    expected = {
        "source_platform": ((0.44, -0.26, 0.0), (0.56, -0.14, 0.02)),
        "destination_floor": ((0.43, 0.13, 0.0), (0.57, 0.27, 0.02)),
        "destination_wall_x_minus": ((0.43, 0.13, 0.02), (0.45, 0.27, 0.04)),
        "destination_wall_x_plus": ((0.55, 0.13, 0.02), (0.57, 0.27, 0.04)),
        "destination_wall_y_minus": ((0.45, 0.13, 0.02), (0.55, 0.15, 0.04)),
        "destination_wall_y_plus": ((0.45, 0.25, 0.02), (0.55, 0.27, 0.04)),
        "blue_component": ((0.475, -0.225, 0.02), (0.525, -0.175, 0.07)),
    }
    definitions = b3.frozen_box_definitions()
    assert len(definitions) == 7
    for definition in definitions:
        minimum, maximum = expected[definition.semantic_id]
        assert definition.minimum_m == pytest.approx(minimum, abs=1e-15)
        assert definition.maximum_m == pytest.approx(maximum, abs=1e-15)


def test_fixture_is_four_walls_and_unfilled_cavity() -> None:
    definitions = b3.frozen_box_definitions()
    walls = [item for item in definitions if item.group is b3.SemanticGroup.DESTINATION_WALL]
    assert len(walls) == 4
    assert all(not (item.minimum_m[0] < 0.50 < item.maximum_m[0] and item.minimum_m[1] < 0.20 < item.maximum_m[1]) for item in walls)


def test_runtime_scene_has_robot_and_seven_boxes_without_plane(scene: dict[str, object]) -> None:
    assert scene["body_count"] == 8
    assert scene["global_plane_loaded"] is False
    assert scene["physics_steps"] == 0
    assert len(scene["static_boxes"]) == 7


def test_kuka_inventory_includes_base_and_all_links(scene: dict[str, object]) -> None:
    robot = scene["robot"]
    assert isinstance(robot, dict)
    inventory = robot["collision_inventory"]
    assert [item["link_index"] for item in inventory] == [-1, 0, 1, 2, 3, 4, 5, 6]
    assert inventory[0]["link_name"] == "lbr_iiwa_link_0"
    assert inventory[-1]["link_name"] == "lbr_iiwa_link_7"
    assert all(len(item["collision_shapes"]) == 1 for item in inventory)


def test_kuka_pair_inventory_is_derived_and_complete(scene: dict[str, object]) -> None:
    robot = scene["robot"]
    assert isinstance(robot, dict)
    assert len(robot["all_self_pairs"]) == 28
    assert len(robot["direct_parent_pairs"]) == 7
    assert len(robot["queried_nonadjacent_pairs"]) == 21
    direct = {
        (item["first_link_index"], item["second_link_index"])
        for item in robot["direct_parent_pairs"]
    }
    assert direct == {(-1, 0), (0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6)}


def test_scene_uses_explicit_parent_exclusion_not_all_parents(scene: dict[str, object]) -> None:
    robot = scene["robot"]
    assert isinstance(robot, dict)
    assert robot["load_flags"] == (
        b3.pb.URDF_USE_SELF_COLLISION | b3.pb.URDF_USE_SELF_COLLISION_EXCLUDE_PARENT
    )
    assert robot["load_flags"] != (
        b3.pb.URDF_USE_SELF_COLLISION | b3.pb.URDF_USE_SELF_COLLISION_EXCLUDE_ALL_PARENTS
    )


@pytest.mark.parametrize(
    ("requested", "expected"),
    [(0.001, 0.001), (0.0, 0.0), (-0.000001, -0.000001), (-0.001, -0.001)],
)
def test_analytical_axis_aligned_signed_distance(requested: float, expected: float) -> None:
    actual = b3.analytical_axis_aligned_x_separation(0.0, 0.1, 0.2 + requested, 0.1)
    assert actual == pytest.approx(expected, abs=2e-17)


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_analytical_distance_rejects_nonfinite(bad: float) -> None:
    with pytest.raises(b3.NumericalInputError):
        b3.analytical_axis_aligned_x_separation(0.0, 0.1, bad, 0.1)


def test_kernel_proves_positive_touch_and_penetration_controls(kernel: dict[str, object]) -> None:
    observations = kernel["observations"]
    first_run = {item["requested_signed_separation_m"]: item for item in observations if item["repetition"] == 0}
    assert first_run[0.001]["pybullet_contact_distance_m"] > 0.0
    assert abs(first_run[0.0]["pybullet_contact_distance_m"]) < 1e-15
    assert first_run[-0.000001]["pybullet_contact_distance_m"] < 0.0
    assert first_run[-0.001]["pybullet_contact_distance_m"] < 0.0


def test_kernel_calibration_is_repeatable_and_does_not_freeze_epsilon(kernel: dict[str, object]) -> None:
    assert len(kernel["observations"]) == 90
    assert kernel["maximum_absolute_analytical_error_m"] <= 1e-15
    assert kernel["maximum_run_to_run_spread_m"] == 0.0
    assert kernel["final_contact_epsilon_frozen"] is False
    assert kernel["collision_margins_modified"] is False
    assert kernel["uncertainty_envelope_status"] == "PROPOSED_FOR_B3_2_REVIEW_NOT_CONTACT_EPSILON"


def test_query_horizon_no_result_is_a_lower_bound(kernel: dict[str, object]) -> None:
    control = kernel["horizon_no_result_control"]
    assert control["closest_point_found"] is False
    assert control["signed_distance_m"] is None
    assert control["separation_lower_bound_m"] == 0.050


def _create_collidable_pair(client_id: int) -> tuple[int, int]:
    b3.pb.resetSimulation(physicsClientId=client_id)
    body_a = b3._create_static_box(
        b3.BoxDefinition(
            "identity_a",
            b3.SemanticGroup.SOURCE_PLATFORM,
            (0.0, 0.0, 0.0),
            (0.1, 0.1, 0.1),
        ),
        client_id,
    )
    body_b = b3._create_static_box(
        b3.BoxDefinition(
            "identity_b",
            b3.SemanticGroup.DESTINATION_FLOOR,
            (0.3, 0.0, 0.0),
            (0.1, 0.1, 0.1),
        ),
        client_id,
    )
    return body_a, body_b


def test_closest_point_query_rejects_invalid_primary_identity() -> None:
    client_id = b3.pb.connect(b3.pb.DIRECT)
    try:
        body_a, body_b = _create_collidable_pair(client_id)
        for invalid_body in (None, 999, True):
            with pytest.raises(b3.DetectorQualificationError):
                b3.closest_point_query(invalid_body, body_b, client_id)
        for invalid_link in (None, 999, True):
            with pytest.raises(b3.DetectorQualificationError):
                b3.closest_point_query(
                    body_a,
                    body_b,
                    client_id,
                    link_a=invalid_link,
                )
        with pytest.raises(b3.DetectorQualificationError):
            b3.closest_point_query(body_a, body_b, client_id, link_a=0)
    finally:
        b3.pb.disconnect(physicsClientId=client_id)


def test_closest_point_query_rejects_invalid_secondary_identity() -> None:
    client_id = b3.pb.connect(b3.pb.DIRECT)
    try:
        body_a, body_b = _create_collidable_pair(client_id)
        for invalid_body in (None, 999, True):
            with pytest.raises(b3.DetectorQualificationError):
                b3.closest_point_query(body_a, invalid_body, client_id)
        for invalid_link in (None, 999, True):
            with pytest.raises(b3.DetectorQualificationError):
                b3.closest_point_query(
                    body_a,
                    body_b,
                    client_id,
                    link_b=invalid_link,
                )
        with pytest.raises(b3.DetectorQualificationError):
            b3.closest_point_query(body_a, body_b, client_id, link_b=0)
    finally:
        b3.pb.disconnect(physicsClientId=client_id)


def test_closest_point_query_rejects_collisionless_articulated_link() -> None:
    client_id = b3.pb.connect(b3.pb.DIRECT)
    try:
        body_a, _ = _create_collidable_pair(client_id)
        collisionless_body = b3.pb.createMultiBody(
            baseMass=0.0,
            baseCollisionShapeIndex=-1,
            baseVisualShapeIndex=-1,
            basePosition=(0.0, 0.0, 0.0),
            baseOrientation=(0.0, 0.0, 0.0, 1.0),
            linkMasses=[1.0],
            linkCollisionShapeIndices=[-1],
            linkVisualShapeIndices=[-1],
            linkPositions=[(0.0, 0.0, 0.1)],
            linkOrientations=[(0.0, 0.0, 0.0, 1.0)],
            linkInertialFramePositions=[(0.0, 0.0, 0.0)],
            linkInertialFrameOrientations=[(0.0, 0.0, 0.0, 1.0)],
            linkParentIndices=[0],
            linkJointTypes=[b3.pb.JOINT_FIXED],
            linkJointAxis=[(0.0, 0.0, 1.0)],
            physicsClientId=client_id,
        )
        assert b3.pb.getNumJoints(
            collisionless_body,
            physicsClientId=client_id,
        ) == 1
        assert not b3.pb.getCollisionShapeData(
            collisionless_body,
            0,
            physicsClientId=client_id,
        )
        with pytest.raises(b3.DetectorQualificationError):
            b3.closest_point_query(
                body_a,
                collisionless_body,
                client_id,
                link_b=0,
            )
    finally:
        b3.pb.disconnect(physicsClientId=client_id)


def test_valid_collidable_pair_outside_horizon_remains_a_lower_bound() -> None:
    client_id = b3.pb.connect(b3.pb.DIRECT)
    try:
        body_a, body_b = _create_collidable_pair(client_id)
        valid = b3.closest_point_query(body_a, body_b, client_id, horizon_m=0.05)
        assert valid.found is False
        assert valid.signed_distance_m is None
        assert valid.separation_lower_bound_m == 0.05
    finally:
        b3.pb.disconnect(physicsClientId=client_id)


@pytest.mark.parametrize("invalid_client_id", [None, True, -1])
def test_closest_point_query_rejects_invalid_physics_client_ids(
    invalid_client_id: int | None,
) -> None:
    with pytest.raises(b3.DetectorQualificationError):
        b3.closest_point_query(0, 0, invalid_client_id)


def test_closest_point_query_rejects_disconnected_physics_client() -> None:
    client_id = b3.pb.connect(b3.pb.DIRECT)
    b3.pb.disconnect(physicsClientId=client_id)
    with pytest.raises(b3.DetectorQualificationError):
        b3.closest_point_query(0, 0, client_id)


def test_source_support_permission_is_phase_dependent() -> None:
    pair = (b3.SemanticGroup.COMPONENT, b3.SemanticGroup.SOURCE_PLATFORM)
    assert b3.contact_permission(*pair, b3.ComponentPhase.SOURCE_SUPPORTED) is b3.ContactPermission.SUPPORT_CONTACT_PENDING_B3_2_NUMERIC_BAND
    assert b3.contact_permission(*pair, b3.ComponentPhase.CARRIED) is b3.ContactPermission.FORBIDDEN


def test_destination_support_permission_is_phase_dependent() -> None:
    pair = (b3.SemanticGroup.COMPONENT, b3.SemanticGroup.DESTINATION_FLOOR)
    assert b3.contact_permission(*pair, b3.ComponentPhase.CARRIED) is b3.ContactPermission.FORBIDDEN
    assert b3.contact_permission(*pair, b3.ComponentPhase.RELEASE_BOUNDARY) is b3.ContactPermission.SUPPORT_CONTACT_PENDING_B3_2_NUMERIC_BAND


def test_walls_and_all_robot_component_pairs_are_always_forbidden() -> None:
    for phase in b3.ComponentPhase:
        assert b3.contact_permission(b3.SemanticGroup.COMPONENT, b3.SemanticGroup.DESTINATION_WALL, phase) is b3.ContactPermission.FORBIDDEN
        assert b3.contact_permission(b3.SemanticGroup.COMPONENT, b3.SemanticGroup.ROBOT, phase) is b3.ContactPermission.FORBIDDEN


def test_contact_policy_positive_and_negative_controls() -> None:
    evidence = b3.qualify_contact_policy_controls()
    assert abs(evidence["source_support_geometric_control"]["signed_distance_m"]) < 1e-15
    assert evidence["destination_wall_intentional_penetration_control"]["signed_distance_m"] < -0.001
    assert evidence["material_penetration_permitted_for_support_pairs"] is False


def test_self_collision_flag_probe_has_positive_and_negative_controls(self_collision: dict[str, object]) -> None:
    synthetic = self_collision["synthetic_articulated_control"]
    expected = synthetic["expected_contact_pairs_by_flag"]
    assert expected["DEFAULT"] == []
    assert expected["URDF_USE_SELF_COLLISION"] == [[-1, 2], [0, 2]]
    assert expected["URDF_USE_SELF_COLLISION_EXCLUDE_PARENT"] == [[-1, 2], [0, 2]]
    assert expected["URDF_USE_SELF_COLLISION_EXCLUDE_ALL_PARENTS"] == []


def test_explicit_pair_queries_ignore_self_collision_filter_flags(self_collision: dict[str, object]) -> None:
    conclusions = self_collision["empirical_conclusions"]
    assert conclusions["explicit_pair_get_closest_points_ignores_self_collision_flags"] is True
    assert conclusions["exclude_all_parents_adopted"] is False
    assert conclusions["direct_parent_pairs_excluded_only"] is True


def test_component_attachment_reconstructs_without_snap(predecessor: b3.PredecessorEvidence) -> None:
    evidence = b3.qualify_component_transform(predecessor)
    assert evidence["attachment_boundary_position_discontinuity_m"] == pytest.approx(3.000429379518585e-08, abs=1e-15)
    assert evidence["attachment_boundary_orientation_discontinuity_rad"] == 0.0
    assert evidence["component_robot_contact_permission"] == "FORBIDDEN_FOR_ALL_ROBOT_LINKS"


def test_component_release_preserves_frozen_pose_and_floor_relation(predecessor: b3.PredecessorEvidence) -> None:
    evidence = b3.qualify_component_transform(predecessor)
    assert evidence["release_reconstruction_position_residual_m"] == 0.0
    assert evidence["release_reconstruction_orientation_residual_rad"] == 0.0
    assert evidence["release_pose_snapped_to_nominal_destination"] is False
    assert evidence["bottom_minus_destination_floor_top_m"] == -1.010435827109718e-06
    assert evidence["floor_relation_rounded_to_zero"] is False


def test_component_robot_policy_remains_forbidden_with_positive_endpoint_clearance(
    predecessor: b3.PredecessorEvidence,
) -> None:
    evidence = b3.qualify_component_robot_endpoint_clearance(predecessor)
    assert evidence["contact_policy"] == "FORBIDDEN"
    assert evidence["all_endpoint_distances_positive"] is True
    assert evidence["route_interpolation_evaluated"] is False
    assert evidence["minimum_component_robot_distance"]["signed_distance_m"] > 0.0
    assert len(evidence["audited_endpoint_states"]) == 4
    for endpoint in evidence["audited_endpoint_states"]:
        assert len(endpoint["pair_distances"]) == 8
        assert endpoint["terminal_link_6_signed_distance_m"] > 0.0


def test_quaternion_distance_known_rotation_and_double_cover() -> None:
    identity = (0.0, 0.0, 0.0, 1.0)
    quarter_turn = (0.0, 0.0, math.sin(math.pi / 4.0), math.cos(math.pi / 4.0))
    assert b3.quaternion_angular_distance(identity, quarter_turn) == pytest.approx(math.pi / 2.0, abs=1e-15)
    assert b3.quaternion_angular_distance(identity, (0.0, 0.0, 0.0, -1.0)) == 0.0


def test_quaternion_distance_rejects_nonfinite_and_zero() -> None:
    with pytest.raises(b3.NumericalInputError):
        b3.quaternion_angular_distance((0.0, 0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0))
    with pytest.raises(b3.NumericalInputError):
        b3.quaternion_angular_distance((math.nan, 0.0, 0.0, 1.0), (0.0, 0.0, 0.0, 1.0))


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ((0.0, 0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 0.0)),
        ((1e-20, 0.0, 0.0, 0.0), (1e-20, 0.0, 0.0, 0.0)),
        ((math.inf, 0.0, 0.0, 1.0), (math.inf, 0.0, 0.0, 1.0)),
        ((-math.inf, 0.0, 0.0, 1.0), (-math.inf, 0.0, 0.0, 1.0)),
        ((math.nan, 0.0, 0.0, 1.0), (math.nan, 0.0, 0.0, 1.0)),
    ],
)
def test_identical_invalid_quaternions_fail_closed(
    left: tuple[float, ...], right: tuple[float, ...]
) -> None:
    with pytest.raises(b3.NumericalInputError):
        b3.quaternion_angular_distance(left, right)


@pytest.mark.parametrize(
    "invalid",
    [None, [], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0, 0.0]],
)
def test_malformed_quaternion_shapes_fail_closed(
    invalid: list[float] | None,
) -> None:
    with pytest.raises(b3.NumericalInputError):
        b3.quaternion_angular_distance(invalid, (0.0, 0.0, 0.0, 1.0))


def test_frozen_predecessor_manifest_is_unchanged() -> None:
    observed = b3.verify_frozen_manifest(REPOSITORY_ROOT)
    assert observed == b3.FROZEN_MANIFEST


def _test_git(
    repository: Path,
    *arguments: str,
    input_text: str | None = None,
) -> str:
    completed = subprocess.run(
        ("git", *arguments),
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        input=input_text,
    )
    return completed.stdout.strip()


def _initialise_test_repository(
    root: Path,
    branch: str,
) -> tuple[Path, str]:
    repository = root / "repository"
    repository.mkdir()
    _test_git(repository, "init", "--quiet")
    _test_git(repository, "config", "user.name", "B3.1 Test")
    _test_git(repository, "config", "user.email", "b3.1-test@example.invalid")
    _test_git(repository, "checkout", "--quiet", "-b", branch)
    (repository / "baseline.txt").write_text("baseline\n", encoding="utf-8")
    _test_git(repository, "add", "baseline.txt")
    _test_git(repository, "commit", "--quiet", "-m", "baseline")
    return repository, _test_git(repository, "rev-parse", "HEAD")


def test_predecessor_ancestry_accepts_equal_and_child_but_rejects_unrelated(
    tmp_path: Path,
) -> None:
    repository, baseline = _initialise_test_repository(
        tmp_path,
        "feature-branch",
    )
    assert b3._git_commit_is_ancestor(repository, baseline, baseline)

    (repository / "child.txt").write_text("child\n", encoding="utf-8")
    _test_git(repository, "add", "child.txt")
    _test_git(repository, "commit", "--quiet", "-m", "child")
    child = _test_git(repository, "rev-parse", "HEAD")
    assert b3._git_commit_is_ancestor(repository, baseline, child)

    empty_tree = _test_git(repository, "mktree", input_text="")
    unrelated = _test_git(repository, "commit-tree", empty_tree, "-m", "unrelated")
    assert not b3._git_commit_is_ancestor(repository, baseline, unrelated)


def test_runtime_verification_is_branch_name_independent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, baseline = _initialise_test_repository(
        tmp_path,
        "feature-branch",
    )
    monkeypatch.setattr(b3, "STARTING_HEAD", baseline)

    feature_result = b3.verify_repository_and_runtime(repository)

    assert feature_result["predecessor_baseline_commit"] == baseline
    assert feature_result["lineage_contract"] == (
        "CURRENT_HEAD_DESCENDS_FROM_PREDECESSOR_BASELINE"
    )

    _test_git(
        repository,
        "checkout",
        "--quiet",
        "-b",
        "master",
    )

    master_result = b3.verify_repository_and_runtime(repository)

    assert master_result["predecessor_baseline_commit"] == baseline
    assert master_result["lineage_contract"] == (
        "CURRENT_HEAD_DESCENDS_FROM_PREDECESSOR_BASELINE"
    )


def test_runtime_provenance_uses_immutable_lineage() -> None:
    provenance = b3.verify_repository_and_runtime(REPOSITORY_ROOT)

    assert provenance["predecessor_baseline_commit"] == b3.STARTING_HEAD
    assert provenance["lineage_contract"] == (
        "CURRENT_HEAD_DESCENDS_FROM_PREDECESSOR_BASELINE"
    )
    assert "branch_contract" not in provenance
    assert "git_status_short_at_generation" not in provenance
    assert provenance["pybullet"]["binary_identity"].startswith(
        "python_environment/"
    )


def test_deterministic_serialization_and_nonfinite_rejection() -> None:
    value = {"z": [3, 2, 1], "a": {"value": 1.25}}
    assert b3.serialize_artifact(value) == b3.serialize_artifact(value)
    assert b3.serialize_artifact(value).startswith(b'{\n  "a"')
    with pytest.raises(ValueError):
        b3.serialize_artifact({"bad": math.nan})


def test_logical_artifact_paths_accept_only_approved_roots(tmp_path: Path) -> None:
    repository_root = tmp_path / "repository"
    data_root = repository_root / ".venv/Lib/site-packages/pybullet_data"
    repository_file = repository_root / "src/prototype5/example.py"
    data_file = data_root / "kuka_iiwa/model.urdf"
    outside = tmp_path / "outside/file.bin"
    assert b3._logical_artifact_path(
        repository_file,
        repository_root=repository_root,
        pybullet_data_root=data_root,
    ) == "repository/src/prototype5/example.py"
    assert b3._logical_artifact_path(
        data_file,
        repository_root=repository_root,
        pybullet_data_root=data_root,
    ) == "pybullet_data/kuka_iiwa/model.urdf"
    with pytest.raises(b3.FrozenEvidenceError):
        b3._logical_artifact_path(
            outside,
            repository_root=repository_root,
            pybullet_data_root=data_root,
        )


def test_pybullet_binary_identity_is_independent_of_environment_root(
    tmp_path: Path,
) -> None:
    filename = "pybullet.cp312-win_amd64.pyd"
    repository_binary = tmp_path / "repository/.venv/Lib/site-packages" / filename
    external_binary = tmp_path / "external-environment/site-packages" / filename
    expected = f"python_environment/{filename}"
    assert b3._python_environment_binary_identity(repository_binary) == expected
    assert b3._python_environment_binary_identity(external_binary) == expected


@pytest.mark.parametrize(
    "raw_text",
    [
        r'{"path":"C:\\Users\\person\\repo"}',
        r'{"path":"/Users/person/repo"}',
        r'{"path":"repository/Users/person"}',
        r'{"path":"repository/AppData/Local"}',
        r'{"path":"repository/Temp/result"}',
    ],
)
def test_machine_specific_evidence_paths_are_rejected(raw_text: str) -> None:
    with pytest.raises(b3.FrozenEvidenceError):
        b3.assert_portable_evidence(raw_text)


def test_portable_logical_evidence_paths_are_accepted() -> None:
    raw_text = json.dumps(
        {
            "repository_root": "repository/",
            "binary_identity": "python_environment/pybullet.pyd",
            "urdf_identity": "pybullet_data/kuka_iiwa/model.urdf",
        },
        sort_keys=True,
    )
    b3.assert_portable_evidence(raw_text)


def test_runner_stdout_contract_uses_names_not_absolute_paths() -> None:
    runner = (
        REPOSITORY_ROOT
        / "scripts/prototype5/run_scene_collision_qualification_b3_1.py"
    ).read_text(encoding="utf-8")
    assert 'print(f"artifact_name={arguments.output.name}")' in runner
    assert 'print(f"digest_name={digest_path.name}")' in runner
    assert "arguments.output.resolve()" not in runner


def test_artifact_writer_refuses_overwrite_and_verifies_digest(tmp_path: Path) -> None:
    output = tmp_path / "evidence.json"
    digest = b3.write_artifact({"finite": 1.0}, output)
    assert digest == hashlib.sha256(output.read_bytes()).hexdigest()
    assert b3.verify_artifact_digest(output) == digest
    with pytest.raises(FileExistsError):
        b3.write_artifact({"finite": 1.0}, output)


def test_artifact_records_foundation_only(artifact: dict[str, object]) -> None:
    assert artifact["schema_identifier"] == "prototype5.scene_collision_qualification.b3_1"
    assert artifact["result"] == "B3_1_PASS_DETECTOR_FOUNDATION"
    scope = artifact["scope_contract"]
    assert scope["b2_route_collision_evaluated"] is False
    assert scope["b2_route_collision_verdict"] is None
    assert scope["route_interpolation_policy_frozen"] is False
    assert scope["final_contact_epsilon_frozen"] is False


def test_artifact_companion_digest_matches_exact_bytes(artifact: dict[str, object]) -> None:
    del artifact
    expected = hashlib.sha256(ARTIFACT_PATH.read_bytes()).hexdigest()
    assert DIGEST_PATH.read_text(encoding="ascii") == f"{expected}  {ARTIFACT_PATH.name}\n"
    assert b3.verify_artifact_digest(ARTIFACT_PATH) == expected


def test_artifact_provenance_hashes_current_b3_sources(artifact: dict[str, object]) -> None:
    provenance = artifact["provenance"]
    assert provenance["source_sha256"] == b3.sha256_file(Path(b3.__file__))
    assert provenance["runner_sha256"] == b3.sha256_file(REPOSITORY_ROOT / "scripts/prototype5/run_scene_collision_qualification_b3_1.py")
    assert provenance["tests_sha256"] == b3.sha256_file(Path(__file__))


def test_no_final_epsilon_or_b2_route_verdict_is_hidden_in_artifact(artifact: dict[str, object]) -> None:
    raw = ARTIFACT_PATH.read_text(encoding="utf-8")
    assert '"final_contact_epsilon_frozen": false' in raw
    assert '"b2_route_collision_evaluated": false' in raw
    assert "collision-free" not in artifact["pass_meaning"].lower()


def test_generated_artifact_contains_no_machine_paths(tmp_path: Path) -> None:
    output = tmp_path / "b3_1.json"
    generated = b3.build_b3_1_artifact(REPOSITORY_ROOT)
    b3.write_artifact(generated, output)
    b3.assert_portable_evidence(output.read_text(encoding="utf-8"))
