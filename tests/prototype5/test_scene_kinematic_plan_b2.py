from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pytest

from src.prototype5 import scene_kinematic_plan_b2 as b2


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_PATH = (
    REPOSITORY_ROOT
    / "results/prototype5/scene_calibration/phase_b2_kinematic_plan.json"
)
DIGEST_PATH = ARTIFACT_PATH.with_suffix(ARTIFACT_PATH.suffix + ".sha256")

EXPECTED_VECTORS = {
    "SOURCE_HIGH": (
        0.42030065189865085,
        1.3750633719954326,
        -1.3503357336551804,
        -1.7087453044902847,
        -1.7396162073334869,
        -1.329244396107751,
        -1.246175376911863,
    ),
    "SOURCE_PICK": (
        0.3708298487489221,
        1.5663085697240682,
        -1.170789200591093,
        -1.6386220433146097,
        -1.54709745428977,
        -1.1714886313414705,
        -1.2716528226302024,
    ),
    "SOURCE_HIGH_RETURN": (
        0.4204804535280717,
        1.3777139115376484,
        -1.3519727414463127,
        -1.7084747283715058,
        -1.7370522694704627,
        -1.331091284794471,
        -1.246672442551945,
    ),
    "DESTINATION_HIGH": (
        1.1762782906957776,
        1.3617855007486022,
        -1.3367226256125282,
        -1.708962546979064,
        -1.7517894444962279,
        -1.3147587225031792,
        -0.4849455010972315,
    ),
    "DESTINATION_PLACE": (
        1.1264968191289284,
        1.5538962796013953,
        -1.1574295784790016,
        -1.638619417006012,
        -1.5595749932684404,
        -1.1573031745582292,
        -0.510905972516669,
    ),
    "DESTINATION_HIGH_RETURN": (
        1.178346292011804,
        1.3642955535947991,
        -1.3386580662951193,
        -1.7084768780201194,
        -1.7495712535378452,
        -1.316845416044329,
        -0.4831097960375711,
    ),
}

EXPECTED_H1 = (
    0.7993234719552273,
    1.3696794627951159,
    -1.3444968999751499,
    -1.708611091255202,
    -1.744593730435666,
    -1.3230449060760399,
    -0.8646425864747171,
)


@pytest.fixture(scope="module")
def calibration() -> b2.CalibrationInput:
    return b2.load_calibration_input(REPOSITORY_ROOT)


@pytest.fixture(scope="module")
def artifact() -> dict[str, object]:
    return json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))


def wide_limits() -> tuple[b2.JointLimit, ...]:
    return tuple(
        b2.JointLimit(index, f"joint_{index}", -5.0, 5.0) for index in range(7)
    )


def vector(first: float = 0.0) -> b2.JointVector:
    return (first, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)


def test_frozen_input_literals_are_independent() -> None:
    assert b2.CALIBRATION_FREEZE_COMMIT == (
        "86c02ed3f90ad5f17a84101f35cd483d5e1afe83"
    )
    assert b2.B1_2_SHA256 == (
        "b852fcdba89a89e0a83abc83c80cdf6eceb6b5a33babaf0558fce6d479b80f2c"
    )
    assert b2.LAYOUT_NAME == "C"
    assert b2.SOURCE_XY_M == (0.50, -0.20)
    assert b2.DESTINATION_XY_M == (0.50, 0.20)
    assert b2.ORIENTATION_NAME == "down_x_pi"
    assert b2.VIRTUAL_TCP_M == 0.080
    assert b2.LIFT_M == 0.140
    assert b2.CONTROLLED_JOINTS == (0, 1, 2, 3, 4, 5, 6)
    assert b2.EE_LINK == 6


def test_b1_2_hash_and_digest_are_verified() -> None:
    artifact = REPOSITORY_ROOT / b2.B1_2_RELATIVE_PATH
    digest = REPOSITORY_ROOT / b2.B1_2_DIGEST_RELATIVE_PATH
    assert b2.sha256_file(artifact) == (
        "b852fcdba89a89e0a83abc83c80cdf6eceb6b5a33babaf0558fce6d479b80f2c"
    )
    assert digest.read_text(encoding="ascii") == (
        "b852fcdba89a89e0a83abc83c80cdf6eceb6b5a33babaf0558fce6d479b80f2c"
        "  phase_b1_2_results.jsonl\n"
    )


def test_selected_candidate_and_waypoint_names_are_exact(
    calibration: b2.CalibrationInput,
) -> None:
    assert calibration.candidate_id == "b1_1-C-down_x_pi-tcp_0p080-lift_0p140"
    assert tuple(item.name for item in calibration.task_waypoints) == (
        "SOURCE_HIGH",
        "SOURCE_PICK",
        "SOURCE_HIGH_RETURN",
        "DESTINATION_HIGH",
        "DESTINATION_PLACE",
        "DESTINATION_HIGH_RETURN",
    )
    assert tuple(item.predecessor_name for item in calibration.task_waypoints) == (
        "source_high",
        "source_tool",
        "source_high_return",
        "destination_high",
        "destination_tool",
        "destination_high_return",
    )


def test_task_vectors_equal_committed_b1_2_literals(
    calibration: b2.CalibrationInput,
) -> None:
    actual = {item.name: item.joint_vector for item in calibration.task_waypoints}
    assert actual == EXPECTED_VECTORS
    assert all(len(values) == 7 for values in actual.values())
    assert all(math.isfinite(value) for values in actual.values() for value in values)


def test_h0_is_exact_and_fails_actual_endpoint_screen(
    calibration: b2.CalibrationInput,
) -> None:
    by_name = {item.name: item for item in calibration.task_waypoints}
    evaluation = b2.evaluate_home(
        "H0",
        (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
        by_name["SOURCE_HIGH"].joint_vector,
        by_name["DESTINATION_HIGH_RETURN"].joint_vector,
        calibration.joint_limits,
    )
    assert evaluation.joint_vector == (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    assert evaluation.minimum_margin_rad == pytest.approx(2.09439510239)
    assert evaluation.outgoing_leg.max_abs_delta_rad == pytest.approx(
        1.7396162073334869
    )
    assert evaluation.incoming_leg.max_abs_delta_rad == pytest.approx(
        1.7495712535378452
    )
    assert evaluation.accepted is False


def test_h1_midpoint_is_independently_derived(
    calibration: b2.CalibrationInput,
) -> None:
    by_name = {item.name: item for item in calibration.task_waypoints}
    source = by_name["SOURCE_HIGH"].joint_vector
    destination = by_name["DESTINATION_HIGH_RETURN"].joint_vector
    midpoint = tuple((source[index] + destination[index]) / 2.0 for index in range(7))
    assert midpoint == EXPECTED_H1


def test_actual_home_policy_selects_only_h1(
    calibration: b2.CalibrationInput,
) -> None:
    by_name = {item.name: item for item in calibration.task_waypoints}
    result = b2.select_home(
        by_name["SOURCE_HIGH"].joint_vector,
        by_name["DESTINATION_HIGH_RETURN"].joint_vector,
        calibration.joint_limits,
    )
    assert result.h0.accepted is False
    assert result.h1 is not None
    assert result.h1.accepted is True
    assert result.selected_candidate == "H1"
    assert result.selected_joint_vector == EXPECTED_H1


def test_h0_pass_prevents_h1_evaluation() -> None:
    result = b2.select_home(vector(0.1), vector(-0.1), wide_limits())
    assert result.selected_candidate == "H0"
    assert result.h0.accepted is True
    assert result.h1 is None


def test_both_authorized_home_candidates_fail_closed() -> None:
    with pytest.raises(b2.HomeSelectionError, match="B2_HOLD_HOME_SELECTION"):
        b2.select_home(vector(4.0), vector(-4.0), wide_limits())


def test_joint_margin_inside_limit() -> None:
    evidence = b2.joint_value_evidence(vector(1.0), wide_limits())
    assert evidence[0].lower_margin_rad == 6.0
    assert evidence[0].upper_margin_rad == 4.0
    assert evidence[0].nearest_margin_rad == 4.0


def test_joint_exactly_at_limit_has_zero_margin() -> None:
    evidence = b2.joint_value_evidence(vector(5.0), wide_limits())
    assert evidence[0].nearest_margin_rad == 0.0


@pytest.mark.parametrize(
    ("value", "expected_margin"),
    [(-5.1, -0.1), (5.1, -0.1)],
)
def test_joint_outside_limit_has_negative_margin(
    value: float,
    expected_margin: float,
) -> None:
    evidence = b2.joint_value_evidence(vector(value), wide_limits())
    assert evidence[0].nearest_margin_rad == pytest.approx(expected_margin)


def test_joint_nonfinite_fails_closed() -> None:
    with pytest.raises(b2.NumericalContractError, match="finite"):
        b2.joint_value_evidence(vector(float("nan")), wide_limits())


@pytest.mark.parametrize(
    ("delta", "exceeded"),
    [
        (math.pi / 2.0 - 1e-9, False),
        (math.pi / 2.0, False),
        (math.pi / 2.0 + 1e-9, True),
        (-(math.pi / 2.0 + 1e-9), True),
    ],
)
def test_endpoint_delta_strict_threshold(delta: float, exceeded: bool) -> None:
    leg = b2.leg_evidence("A", vector(0.0), "B", vector(delta), wide_limits())
    assert leg.endpoint_joint_delta_exceeded is exceeded


def test_endpoint_delta_detects_one_violating_joint() -> None:
    end: b2.JointVector = (0.0, 0.0, 0.0, 0.0, 0.0, math.pi / 2 + 0.1, 0.0)
    leg = b2.leg_evidence("A", vector(), "B", end, wide_limits())
    assert leg.endpoint_joint_delta_exceeded is True
    assert leg.responsible_joint_index == 5


def test_endpoint_delta_nonfinite_fails_closed() -> None:
    with pytest.raises(b2.NumericalContractError, match="finite"):
        b2.leg_evidence("A", vector(), "B", vector(float("inf")), wide_limits())


def test_route_is_exactly_eight_states_and_seven_legs(
    calibration: b2.CalibrationInput,
) -> None:
    route = b2.build_route(EXPECTED_H1, calibration.task_waypoints)
    assert tuple(state.name for state in route) == (
        "HOME",
        "SOURCE_HIGH",
        "SOURCE_PICK",
        "SOURCE_HIGH_RETURN",
        "DESTINATION_HIGH",
        "DESTINATION_PLACE",
        "DESTINATION_HIGH_RETURN",
        "HOME",
    )
    assert len(route) == 8
    assert len(b2.build_route_legs(route, calibration.joint_limits)) == 7


def test_round_trip_home_definition_is_exact(
    calibration: b2.CalibrationInput,
) -> None:
    route = b2.build_route(EXPECTED_H1, calibration.task_waypoints)
    assert route[0].joint_vector == route[-1].joint_vector
    assert tuple(
        end - start
        for start, end in zip(route[0].joint_vector, route[-1].joint_vector)
    ) == (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)


def test_transform_composes_down_x_tcp_offset_once() -> None:
    target_link = b2.Pose(
        (0.5, -0.2, 0.265),
        (1.0, 0.0, 0.0, 0.0),
    )
    target_tcp = b2.compose_pose(target_link, b2.VIRTUAL_TCP_LOCAL_POSE)
    assert target_tcp.position == pytest.approx((0.5, -0.2, 0.185), abs=1e-15)
    assert target_tcp.orientation == pytest.approx((1.0, 0.0, 0.0, 0.0))


def test_extracted_target_tcp_applies_frozen_offset_once(
    calibration: b2.CalibrationInput,
) -> None:
    source_high = calibration.task_waypoints[0]
    assert source_high.predecessor_target_link_pose.position == (0.5, -0.2, 0.265)
    assert source_high.target_tcp_pose.position == pytest.approx(
        (0.5, -0.2, 0.185), abs=1e-15
    )


def test_quaternion_identity_and_double_cover() -> None:
    identity = (0.0, 0.0, 0.0, 1.0)
    assert b2.quaternion_angular_residual(identity, identity) == 0.0
    assert b2.quaternion_angular_residual(identity, (0.0, 0.0, 0.0, -1.0)) == 0.0


def test_quaternion_known_ninety_degrees() -> None:
    half = math.sqrt(0.5)
    assert b2.quaternion_angular_residual(
        (0.0, 0.0, 0.0, 1.0), (0.0, 0.0, half, half)
    ) == pytest.approx(math.pi / 2.0)


def test_quaternion_known_one_hundred_eighty_degrees() -> None:
    assert b2.quaternion_angular_residual(
        (0.0, 0.0, 0.0, 1.0), (1.0, 0.0, 0.0, 0.0)
    ) == pytest.approx(math.pi)


def test_quaternion_normalizes_non_unit_input() -> None:
    assert b2.quaternion_angular_residual(
        (0.0, 0.0, 0.0, 2.0), (0.0, 0.0, 0.0, 7.0)
    ) == 0.0


@pytest.mark.parametrize(
    "invalid",
    [(0.0, 0.0, 0.0, 0.0), (0.0, float("nan"), 0.0, 1.0)],
)
def test_quaternion_invalid_input_fails_closed(invalid: tuple[float, ...]) -> None:
    with pytest.raises(b2.NumericalContractError):
        b2.quaternion_angular_residual((0.0, 0.0, 0.0, 1.0), invalid)


def test_artifact_schema_and_semantic_tuple_are_exact(
    artifact: dict[str, object],
) -> None:
    assert artifact["schema_identifier"] == "prototype5.scene_kinematic_plan.b2"
    assert artifact["schema_version"] == "1.0.0"
    assert artifact["semantic_execution_tuple"] == {
        "scene_id": "manufacturing_demo_scene",
        "scene_state_version": "1.0.0",
        "operation": "MOVE",
        "object": "blue_component",
        "source": "input_tray_a",
        "destination": "assembly_fixture_b",
    }


def test_artifact_promotes_exact_b1_2_vectors_without_ik(
    artifact: dict[str, object],
) -> None:
    states = artifact["ordered_plan"]
    actual = {
        state["state"]: tuple(state["joint_vector"])
        for state in states
        if state["state"] != "HOME"
    }
    assert actual == EXPECTED_VECTORS
    source = (
        REPOSITORY_ROOT / "src/prototype5/scene_kinematic_plan_b2.py"
    ).read_text(encoding="utf-8")
    prohibited = "calculate" + "InverseKinematics"
    assert prohibited not in source


def test_fk_replay_uses_world_link_frame_not_com(
    artifact: dict[str, object],
) -> None:
    source_high = artifact["ordered_plan"][1]
    link_position = source_high["replay"]["world_link_frame_pose"]["position"]
    assert link_position == pytest.approx(
        (0.5, -0.20000000298023224, 0.26500001549720764), abs=1e-15
    )
    predecessor_position = source_high["task_waypoint"][
        "predecessor_actual_world_link_frame_pose"
    ]["position"]
    assert link_position == predecessor_position


def independent_quaternion_angle(left: list[float], right: list[float]) -> float:
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    lx, ly, lz, lw = (value / left_norm for value in left)
    rx, ry, rz, rw = (value / right_norm for value in right)
    # right * conjugate(left), scalar-last, implemented independently here.
    x = -rw * lx + rx * lw - ry * lz + rz * ly
    y = -rw * ly + rx * lz + ry * lw - rz * lx
    z = -rw * lz - rx * ly + ry * lx + rz * lw
    w = rw * lw + rx * lx + ry * ly + rz * lz
    return 2.0 * math.atan2(math.sqrt(x * x + y * y + z * z), abs(w))


def test_task_residuals_recompute_independently(
    artifact: dict[str, object],
) -> None:
    for state in artifact["ordered_plan"][1:7]:
        target = state["task_waypoint"]["target_virtual_tcp_pose"]
        actual = state["replay"]["virtual_tcp_pose"]
        position = math.sqrt(
            sum(
                (actual_value - target_value) ** 2
                for actual_value, target_value in zip(
                    actual["position"], target["position"]
                )
            )
        )
        orientation = independent_quaternion_angle(
            target["quaternion_xyzw"], actual["quaternion_xyzw"]
        )
        assert state["replay"]["position_residual_m"] == pytest.approx(
            position, abs=1e-15
        )
        assert state["replay"]["orientation_residual_rad"] == pytest.approx(
            orientation, abs=1e-10
        )
        assert position <= 0.010
        assert orientation <= 0.010


def test_reproducibility_artifact_has_ten_fresh_sessions(
    artifact: dict[str, object],
) -> None:
    reproducibility = artifact["reproducibility"]
    assert reproducibility["trial_count"] == 10
    assert reproducibility["fresh_direct_session_per_trial"] is True
    assert reproducibility["physics_steps_per_trial"] == 0
    assert len(reproducibility["trials"]) == 10
    assert all(len(trial["states"]) == 8 for trial in reproducibility["trials"])


def test_reproducibility_spreads_satisfy_literal_tolerances(
    artifact: dict[str, object],
) -> None:
    summary = artifact["reproducibility"]["summary"]
    assert summary["maximum_link_position_spread_m"] <= 1e-9
    assert summary["maximum_tcp_position_spread_m"] <= 1e-9
    assert summary["maximum_link_orientation_spread_rad"] <= 1e-9
    assert summary["maximum_tcp_orientation_spread_rad"] <= 1e-9


def replay_trials(position_delta: float = 0.0) -> tuple[b2.ReplayTrial, ...]:
    trials: list[b2.ReplayTrial] = []
    for trial_index in range(10):
        states: list[b2.StateReplay] = []
        for route_index, name in enumerate(b2.ROUTE_STATE_NAMES):
            delta = position_delta if trial_index == 9 and route_index == 3 else 0.0
            pose = b2.Pose((delta, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0))
            states.append(b2.StateReplay(route_index, name, pose, pose, None, None))
        trials.append(b2.ReplayTrial(trial_index, tuple(states)))
    return tuple(trials)


def test_reproducibility_spread_calculation_accepts_equal_trials() -> None:
    summary = b2.reproducibility_summary(replay_trials())
    assert summary.maximum_link_position_spread_m == 0.0
    assert summary.maximum_tcp_position_spread_m == 0.0
    assert summary.maximum_link_orientation_spread_rad == 0.0
    assert summary.maximum_tcp_orientation_spread_rad == 0.0


def test_reproducibility_above_tolerance_fails() -> None:
    with pytest.raises(b2.KinematicContractError, match="position spread"):
        b2.reproducibility_summary(replay_trials(1.1e-9))


def test_reproducibility_requires_exactly_ten_trials() -> None:
    with pytest.raises(b2.KinematicContractError, match="Expected 10"):
        b2.reproducibility_summary(replay_trials()[:9])


def test_deterministic_serialization() -> None:
    value = {"z": [3, 2, 1], "a": {"b": True}}
    assert b2.deterministic_json_bytes(value) == b2.deterministic_json_bytes(value)
    assert b2.deterministic_json_bytes(value).startswith(b'{\n  "a"')


@pytest.mark.parametrize("invalid", [float("nan"), float("inf")])
def test_serialization_rejects_nonfinite(invalid: float) -> None:
    with pytest.raises(b2.NumericalContractError, match="strict JSON"):
        b2.deterministic_json_bytes({"invalid": invalid})


def test_artifact_writer_refuses_overwrite(tmp_path: Path) -> None:
    output = tmp_path / "artifact.json"
    b2.write_b2_artifact(output, {"value": 1})
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        b2.write_b2_artifact(output, {"value": 2})


def test_artifact_digest_generation_and_verification(tmp_path: Path) -> None:
    output = tmp_path / "artifact.json"
    digest, digest_path = b2.write_b2_artifact(output, {"value": 1})
    independent = hashlib.sha256(output.read_bytes()).hexdigest()
    assert digest == independent
    assert digest_path.read_text(encoding="ascii") == (
        f"{independent}  artifact.json\n"
    )
    assert b2.verify_companion_digest(output, digest_path) == independent


def test_generated_artifact_digest_is_valid() -> None:
    independent = hashlib.sha256(ARTIFACT_PATH.read_bytes()).hexdigest()
    assert DIGEST_PATH.read_text(encoding="ascii") == (
        f"{independent}  {ARTIFACT_PATH.name}\n"
    )
    assert b2.verify_companion_digest(ARTIFACT_PATH, DIGEST_PATH) == independent


def test_artifact_binds_provenance_and_claim_boundaries(
    artifact: dict[str, object],
) -> None:
    provenance = artifact["provenance"]
    assert provenance["calibration_freeze_commit"] == (
        "86c02ed3f90ad5f17a84101f35cd483d5e1afe83"
    )
    assert provenance["b1_2_artifact_sha256"] == (
        "b852fcdba89a89e0a83abc83c80cdf6eceb6b5a33babaf0558fce6d479b80f2c"
    )
    assert artifact["robot"]["urdf_velocity_fields_used_as_execution_policy"] is False
    limitations = artifact["claim_boundaries"]["does_not_establish"]
    assert "collision freedom" in limitations
    assert "dynamic executability" in limitations
    assert "industrial safety" in limitations
