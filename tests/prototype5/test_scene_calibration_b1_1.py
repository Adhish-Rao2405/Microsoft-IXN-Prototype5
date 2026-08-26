from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import pytest

from src.prototype5 import scene_calibration_b1_1 as b1


REPOSITORY = Path(__file__).resolve().parents[2]
EVIDENCE = (
    REPOSITORY
    / "results"
    / "prototype5"
    / "scene_calibration"
    / "phase_b1_1_results.jsonl"
)
DIGEST = Path(f"{EVIDENCE}.sha256")
EXPECTED_WAYPOINTS = [
    "source_high",
    "source_tool",
    "source_high_return",
    "destination_high",
    "destination_tool",
    "destination_high_return",
]


def _load_records() -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in EVIDENCE.read_text(encoding="utf-8").splitlines()
    ]


def _records(record_type: str) -> list[dict[str, Any]]:
    return [
        record
        for record in _load_records()
        if record["record_type"] == record_type
    ]


def _metric_record(
    margin: float,
    clearance: float,
    excursion: float,
    position_error: float,
    release_error: float,
) -> dict[str, float]:
    return {
        "min_waypoint_joint_margin_rad": margin,
        "min_transfer_clearance_m": clearance,
        "max_leg_delta_rad": excursion,
        "max_waypoint_position_error_m": position_error,
        "predicted_release_center_error_m": release_error,
    }


def _fake_robot() -> b1.RobotModel:
    return b1.RobotModel(
        body_id=-1,
        controlled_joints=(0, 1, 2),
        lower_limits=(-1.0, -2.0, -3.0),
        upper_limits=(1.0, 2.0, 3.0),
        joint_ranges=(2.0, 4.0, 6.0),
        joint_names=("joint_0", "joint_1", "joint_2"),
        joint_metadata=(),
        ee_link=2,
        ee_local_inertial_position=(0.0, 0.0, 0.0),
        ee_local_inertial_orientation=(0.0, 0.0, 0.0, 1.0),
    )


def test_quaternion_distance_identical_rotations() -> None:
    assert b1.quaternion_angular_distance(
        (0.0, 0.0, 0.0, 1.0),
        (0.0, 0.0, 0.0, 1.0),
    ) == 0.0


def test_quaternion_distance_handles_double_cover() -> None:
    quaternion = (0.1, -0.2, 0.3, 0.9)
    assert b1.quaternion_angular_distance(
        quaternion,
        tuple(-value for value in quaternion),
    ) == pytest.approx(0.0, abs=1.0e-15)


def test_quaternion_distance_known_ninety_degree_rotation() -> None:
    half_angle = math.pi / 4.0
    assert b1.quaternion_angular_distance(
        (0.0, 0.0, 0.0, 1.0),
        (math.sin(half_angle), 0.0, 0.0, math.cos(half_angle)),
    ) == pytest.approx(math.pi / 2.0, abs=1.0e-15)


def test_quaternion_distance_known_one_hundred_eighty_degree_rotation() -> None:
    assert b1.quaternion_angular_distance(
        (0.0, 0.0, 0.0, 1.0),
        (1.0, 0.0, 0.0, 0.0),
    ) == pytest.approx(math.pi, abs=1.0e-15)


def test_quaternion_distance_normalizes_inputs() -> None:
    half_angle = math.pi / 8.0
    unit = (
        0.0,
        math.sin(half_angle),
        0.0,
        math.cos(half_angle),
    )
    scaled = tuple(3.7 * value for value in unit)
    assert b1.quaternion_angular_distance(
        (0.0, 0.0, 0.0, 2.5),
        scaled,
    ) == pytest.approx(math.pi / 4.0, abs=1.0e-15)


def test_quaternion_distance_previous_false_zero_regression() -> None:
    target = (1.0, 0.0, 0.0, 6.123233995736766e-17)
    actual = (
        1.0,
        0.0001823699421947822,
        -4.846076080866624e-06,
        -0.00010479281627340242,
    )
    residual = b1.quaternion_angular_distance(target, actual)
    assert residual == pytest.approx(
        0.0004207793403000842,
        rel=1.0e-13,
    )
    assert residual > 0.0


@pytest.mark.parametrize(
    "invalid",
    [
        (0.0, 0.0, 0.0, 0.0),
        (1.0e-14, 0.0, 0.0, 0.0),
    ],
)
def test_quaternion_distance_rejects_zero_or_near_zero_norm(
    invalid: tuple[float, float, float, float],
) -> None:
    with pytest.raises(ValueError, match="Quaternion norm"):
        b1.quaternion_angular_distance(
            invalid,
            (0.0, 0.0, 0.0, 1.0),
        )


def test_quaternion_distance_rejects_nonfinite_or_wrong_length() -> None:
    with pytest.raises(ValueError, match="finite"):
        b1.quaternion_angular_distance(
            (0.0, 0.0, math.nan, 1.0),
            (0.0, 0.0, 0.0, 1.0),
        )
    with pytest.raises(ValueError, match="4 values"):
        b1.quaternion_angular_distance(
            (0.0, 0.0, 1.0),
            (0.0, 0.0, 0.0, 1.0),
        )


def test_search_space_is_exact_bounded_factorial() -> None:
    candidates = b1.search_space()
    identities = {
        (
            candidate.layout.name,
            candidate.orientation_name,
            candidate.virtual_tool_offset_z_m,
            candidate.lift_offset_m,
        )
        for candidate in candidates
    }
    expected = {
        (layout, orientation, tcp, lift)
        for layout in "ABCD"
        for orientation in ("down_x_pi", "down_y_pi")
        for tcp in (0.08, 0.10)
        for lift in (0.14, 0.18)
    }
    assert len(candidates) == 32
    assert len({candidate.candidate_id for candidate in candidates}) == 32
    assert identities == expected


def test_joint_limit_violations_are_concrete_and_signed() -> None:
    violations = b1.joint_limit_violations(
        (-1.25, 0.5, 3.75),
        _fake_robot(),
    )
    assert violations == [
        {
            "joint_index": 0,
            "joint_name": "joint_0",
            "value_rad": -1.25,
            "lower_limit_rad": -1.0,
            "upper_limit_rad": 1.0,
            "limit_side": "lower",
            "signed_excess_rad": -0.25,
        },
        {
            "joint_index": 2,
            "joint_name": "joint_2",
            "value_rad": 3.75,
            "lower_limit_rad": -3.0,
            "upper_limit_rad": 3.0,
            "limit_side": "upper",
            "signed_excess_rad": 0.75,
        },
    ]


def test_pareto_dominance_respects_all_objective_directions() -> None:
    baseline = _metric_record(0.3, 0.1, 0.8, 0.002, 0.0001)
    better = _metric_record(0.4, 0.2, 0.7, 0.001, 0.00005)
    assert b1.dominates(better, baseline)
    assert not b1.dominates(baseline, better)


def test_pareto_equal_metrics_are_nondominating() -> None:
    candidate = _metric_record(0.3, 0.1, 0.8, 0.002, 0.0001)
    assert not b1.dominates(candidate, dict(candidate))


def test_pareto_mixed_tradeoff_is_nondominating() -> None:
    high_margin = _metric_record(0.4, 0.1, 0.9, 0.002, 0.0001)
    low_excursion = _metric_record(0.3, 0.1, 0.7, 0.002, 0.0001)
    assert not b1.dominates(high_margin, low_excursion)
    assert not b1.dominates(low_excursion, high_margin)


def test_write_evidence_creates_digest_and_refuses_overwrite(
    tmp_path: Path,
) -> None:
    output = tmp_path / "evidence.jsonl"
    digest = b1.write_evidence(
        [{"record_type": "test", "value": 1}],
        output,
    )
    assert hashlib.sha256(output.read_bytes()).hexdigest() == digest
    assert Path(f"{output}.sha256").read_text(encoding="ascii") == (
        f"{digest}  evidence.jsonl\n"
    )
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        b1.write_evidence([], output)


def test_runtime_evidence_digest_and_provenance() -> None:
    evidence_digest = hashlib.sha256(EVIDENCE.read_bytes()).hexdigest()
    assert DIGEST.read_text(encoding="ascii") == (
        f"{evidence_digest}  {EVIDENCE.name}\n"
    )
    provenance = _records("provenance")
    assert len(provenance) == 1
    record = provenance[0]
    assert record["evidence_schema"] == b1.EVIDENCE_SCHEMA_NAME
    assert record["evidence_schema_version"] == b1.EVIDENCE_SCHEMA_VERSION
    assert record["branch"] == b1.EXPECTED_BRANCH
    assert record["head"] == b1.EXPECTED_HEAD
    assert record["pybullet_package_version"] == b1.EXPECTED_PYBULLET_VERSION
    assert record["pybullet_binary_sha256"] == b1.EXPECTED_PYBULLET_SHA256
    assert record["kuka_urdf_sha256"] == b1.EXPECTED_KUKA_URDF_SHA256
    assert (
        record["kuka_directory_manifest_sha256"]
        == b1.EXPECTED_KUKA_MANIFEST_SHA256
    )
    assert record["generator_module_sha256"] == b1.sha256_file(
        Path(b1.__file__).resolve()
    )
    assert record["historical_b1_script_sha256"] == (
        "5b31ab305929184e6e3854169a67c673f3d7d172d7e4d65297e8711cdea125fc"
    )
    assert record["historical_b1_results_sha256"] == (
        "0025eb08dbddb958514b07db0942cf01fcf54b851966527e80141faa8936acc7"
    )


def test_runtime_evidence_has_32_summaries_and_32_details() -> None:
    summaries = _records("candidate_summary")
    details = _records("candidate_detail")
    assert len(summaries) == 32
    assert len(details) == 32
    assert len({record["candidate_id"] for record in summaries}) == 32
    assert len({record["candidate_id"] for record in details}) == 32
    assert {record["candidate_id"] for record in summaries} == {
        record["candidate_id"] for record in details
    }


def test_runtime_evidence_search_space_identity() -> None:
    summaries = _records("candidate_summary")
    represented = {
        (
            record["layout"],
            record["orientation"],
            record["virtual_tool_offset_z_m"],
            record["lift_offset_m"],
        )
        for record in summaries
    }
    expected = {
        (
            candidate.layout.name,
            candidate.orientation_name,
            candidate.virtual_tool_offset_z_m,
            candidate.lift_offset_m,
        )
        for candidate in b1.search_space()
    }
    assert represented == expected


def test_rejected_runtime_candidates_have_joint_level_attribution() -> None:
    rejected = [
        record
        for record in _records("candidate_detail")
        if not record["survives"]
    ]
    assert len(rejected) == 16
    for detail in rejected:
        assert detail["status"] == "rejected"
        assert detail["orientation"] == "down_y_pi"
        assert detail["failure_stage"] == "first_waypoint_ik"
        assert detail["failure_reason"] == "first_waypoint_out_of_limits"
        assert detail["solver_mode"] == "plain_ik_neutral_state"
        assert len(detail["raw_joint_vector"]) == 7
        assert detail["violations"]
        assert detail["trajectory_evaluated"] is False
        assert detail["transfer_clearance_evaluated"] is False
        assert detail["release_evaluated"] is False
        assert detail["reached_waypoints"] == []
        assert detail["unreached_waypoints"] == EXPECTED_WAYPOINTS
        for violation in detail["violations"]:
            value = violation["value_rad"]
            lower = violation["lower_limit_rad"]
            upper = violation["upper_limit_rad"]
            if violation["limit_side"] == "lower":
                assert value < lower
                assert violation["signed_excess_rad"] == pytest.approx(
                    value - lower,
                    abs=1.0e-15,
                )
            else:
                assert value > upper
                assert violation["signed_excess_rad"] == pytest.approx(
                    value - upper,
                    abs=1.0e-15,
                )


def test_survivor_runtime_evidence_recomputes() -> None:
    metadata = _records("robot_metadata")[0]
    lower = metadata["lower_limits_rad"]
    upper = metadata["upper_limits_rad"]
    survivors = [
        record
        for record in _records("candidate_detail")
        if record["survives"]
    ]
    assert len(survivors) == 16
    for detail in survivors:
        assert detail["status"] == "survivor"
        assert detail["orientation"] == "down_x_pi"
        assert detail["trajectory_evaluated"] is True
        assert detail["transfer_clearance_evaluated"] is True
        assert detail["release_evaluated"] is True
        waypoints = detail["waypoints"]
        assert [waypoint["name"] for waypoint in waypoints] == EXPECTED_WAYPOINTS
        assert len(detail["legs"]) == 5
        recomputed_margins: list[float] = []
        recomputed_positions: list[float] = []
        recomputed_orientations: list[float] = []
        for waypoint in waypoints:
            joint_vector = waypoint["joint_vector"]
            margin = min(
                min(value - low, high - value)
                for value, low, high in zip(joint_vector, lower, upper)
            )
            position_error = b1.euclidean_distance(
                waypoint["target_position"],
                waypoint["actual_link_frame_position"],
            )
            orientation_error = b1.quaternion_angular_distance(
                waypoint["target_orientation"],
                waypoint["actual_link_frame_orientation"],
            )
            assert waypoint["joint_margin_rad"] == pytest.approx(margin, abs=1.0e-15)
            assert waypoint["position_error_m"] == pytest.approx(
                position_error,
                abs=1.0e-15,
            )
            assert waypoint["orientation_error_rad"] == pytest.approx(
                orientation_error,
                abs=1.0e-15,
            )
            recomputed_margins.append(margin)
            recomputed_positions.append(position_error)
            recomputed_orientations.append(orientation_error)
        assert detail["min_waypoint_joint_margin_rad"] == pytest.approx(
            min(recomputed_margins),
            abs=1.0e-15,
        )
        assert detail["max_waypoint_position_error_m"] == pytest.approx(
            max(recomputed_positions),
            abs=1.0e-15,
        )
        assert detail["max_waypoint_orientation_error_rad"] == pytest.approx(
            max(recomputed_orientations),
            abs=1.0e-15,
        )
        assert 0.0 < detail["max_waypoint_orientation_error_rad"] < 0.01

        recomputed_leg_maxima: list[float] = []
        for leg, start, end in zip(detail["legs"], waypoints, waypoints[1:]):
            delta = [
                end_value - start_value
                for start_value, end_value in zip(
                    start["joint_vector"],
                    end["joint_vector"],
                )
            ]
            leg_maximum = max(abs(value) for value in delta)
            assert leg["joint_delta_rad"] == pytest.approx(delta, abs=1.0e-15)
            assert leg["max_abs_joint_delta_rad"] == pytest.approx(
                leg_maximum,
                abs=1.0e-15,
            )
            recomputed_leg_maxima.append(leg_maximum)
        assert detail["max_leg_delta_rad"] == pytest.approx(
            max(recomputed_leg_maxima),
            abs=1.0e-15,
        )

        transfer = detail["transfer_clearance_attribution"]
        assert transfer["trajectory_leg"] == {
            "from": "source_high_return",
            "to": "destination_high",
        }
        assert transfer["sample_count"] == b1.INTERPOLATION_SAMPLES_PER_LEG
        assert 0 <= transfer["sample_index"] < transfer["sample_count"]
        component_bottom = (
            transfer["carried_component_pose"]["position"][2]
            - transfer["carried_component_projected_half_extents_m"][2]
        )
        clearance = component_bottom - transfer["required_component_bottom_z_m"]
        assert transfer["component_bottom_z_m"] == pytest.approx(
            component_bottom,
            abs=1.0e-15,
        )
        assert transfer["clearance_m"] == pytest.approx(clearance, abs=1.0e-15)
        assert detail["min_transfer_clearance_m"] == pytest.approx(
            clearance,
            abs=1.0e-15,
        )

        release = detail["predicted_release_pose"]
        extents = b1.projected_half_extents_world(
            release["orientation"],
            b1.COMPONENT_HALF_EXTENTS_M,
        )
        assert detail["predicted_release_projected_half_extents_m"] == pytest.approx(
            extents,
            abs=1.0e-15,
        )
        release_error = b1.euclidean_distance(
            release["position"],
            detail["destination_component_center"],
        )
        assert detail["predicted_release_center_error_m"] == pytest.approx(
            release_error,
            abs=1.0e-15,
        )


def test_runtime_summary_detail_metrics_match_exactly() -> None:
    summaries = {
        record["candidate_id"]: record
        for record in _records("candidate_summary")
    }
    details = {
        record["candidate_id"]: record
        for record in _records("candidate_detail")
    }
    common_fields = {
        "status",
        "survives",
        "metrics_evaluated",
        "failure_stage",
        "failure_reason",
        "pareto_nondominated",
        "selection_policy_rank",
    }
    metric_fields = {
        objective.field
        for objective in b1.PARETO_OBJECTIVES
    } | {
        "max_waypoint_orientation_error_rad",
        "release_footprint_contained",
        "branch_discontinuity",
        "rejection_reasons",
    }
    for candidate_id, summary in summaries.items():
        detail = details[candidate_id]
        fields = set(common_fields)
        if summary["metrics_evaluated"]:
            fields.update(metric_fields)
        for field in fields:
            assert summary[field] == detail[field]


def test_runtime_pareto_and_selection_policy_are_separate() -> None:
    summaries = _records("candidate_summary")
    survivors = [record for record in summaries if record["survives"]]
    expected_frontier = {
        candidate["candidate_id"]
        for candidate in survivors
        if not any(
            b1.dominates(other, candidate)
            for other in survivors
            if other is not candidate
        )
    }
    pareto = _records("pareto_analysis")[0]
    assert set(pareto["nondominated_candidate_ids"]) == expected_frontier
    assert pareto["nondominated_count"] == len(expected_frontier)
    assert {
        record["candidate_id"]
        for record in survivors
        if record["pareto_nondominated"]
    } == expected_frontier
    policy = _records("selection_policy")[0]
    assert policy["classification"] == "ENGINEERING_POLICY"
    assert policy["physical_superiority_claimed"] is False
    assert len(policy["ranked_candidate_ids"]) == len(survivors)
    assert sorted(
        record["selection_policy_rank"]
        for record in survivors
    ) == list(range(1, len(survivors) + 1))


def test_runtime_topology_regression_matches_prior_evidence() -> None:
    summary = _records("runtime_summary")[0]
    assert summary == {
        "record_type": "runtime_summary",
        "total_candidates": 32,
        "candidate_summary_count": 32,
        "candidate_detail_count": 32,
        "survivor_count": 16,
        "down_x_survivor_count": 16,
        "down_y_protocol_rejection_count": 16,
        "expected_topology_matches": True,
    }
