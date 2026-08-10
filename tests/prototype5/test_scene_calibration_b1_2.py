from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import pytest

from src.prototype5 import scene_calibration_b1_2 as b1_2


REPOSITORY = Path(__file__).resolve().parents[2]
B1_1_EVIDENCE = (
    REPOSITORY
    / "results/prototype5/scene_calibration/phase_b1_1_results.jsonl"
)
B1_2_EVIDENCE = (
    REPOSITORY
    / "results/prototype5/scene_calibration/phase_b1_2_results.jsonl"
)
B1_2_DIGEST = Path(f"{B1_2_EVIDENCE}.sha256")

EXPECTED_LAYOUTS = {
    "A": ((0.45, -0.20), (0.45, +0.20)),
    "B": ((0.45, -0.25), (0.45, +0.25)),
    "C": ((0.50, -0.20), (0.50, +0.20)),
    "D": ((0.50, -0.25), (0.50, +0.25)),
}
EXPECTED_ORIENTATIONS = ("down_x_pi", "down_y_pi")
EXPECTED_TCP_M = (0.080, 0.100)
EXPECTED_LIFT_M = (0.140, 0.180)
EXPECTED_B1_1_HASHES = {
    "src/prototype5/scene_calibration_b1_1.py": (
        "c280a01ae6db91527a2988d71d2d5691f57989f1ca46d0f9dc4602153591b1fd"
    ),
    "scripts/prototype5/run_scene_calibration_b1_1.py": (
        "7f3033aa05c70691df141561d934acd42fecc8b92180c4ebce3d2be7cb00473f"
    ),
    "tests/prototype5/test_scene_calibration_b1_1.py": (
        "7e3a249dba07b1ea05c4c5993ac9b42a17d6a1755ff5aa7c1e070984508c43b3"
    ),
    "results/prototype5/scene_calibration/phase_b1_1_results.jsonl": (
        "5490ca1b869bf187cee7f17420d501830cb0f832b2f808dd31cd9152eff1b784"
    ),
    "results/prototype5/scene_calibration/phase_b1_1_results.jsonl.sha256": (
        "9ef55fc699b6acb4f59f6ddff5c144a9f8c7c1a20ee1590ea3972371fa076db4"
    ),
}
SCALAR_METRICS = (
    "min_waypoint_joint_margin_rad",
    "min_transfer_clearance_m",
    "max_leg_delta_rad",
    "max_waypoint_position_error_m",
    "max_waypoint_orientation_error_rad",
    "predicted_release_center_error_m",
)


def _load(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
    ]


def _records(
    records: list[dict[str, Any]],
    record_type: str,
) -> list[dict[str, Any]]:
    return [
        record
        for record in records
        if record["record_type"] == record_type
    ]


def _candidate_map(
    records: list[dict[str, Any]],
    record_type: str,
) -> dict[str, dict[str, Any]]:
    return {
        record["candidate_id"]: record
        for record in _records(records, record_type)
    }


def test_production_layouts_match_literal_historical_coordinates() -> None:
    actual = {
        layout.name: (layout.source_xy, layout.destination_xy)
        for layout in b1_2.LAYOUTS
    }
    assert actual == EXPECTED_LAYOUTS


def test_complete_candidate_factorial_includes_literal_coordinates() -> None:
    represented = {
        (
            candidate.layout.name,
            candidate.layout.source_xy,
            candidate.layout.destination_xy,
            candidate.orientation_name,
            candidate.virtual_tool_offset_z_m,
            candidate.lift_offset_m,
        )
        for candidate in b1_2.search_space()
    }
    expected = {
        (layout, source, destination, orientation, tcp, lift)
        for layout, (source, destination) in EXPECTED_LAYOUTS.items()
        for orientation in EXPECTED_ORIENTATIONS
        for tcp in EXPECTED_TCP_M
        for lift in EXPECTED_LIFT_M
    }
    assert represented == expected
    assert len(represented) == 32


def test_literal_historical_thresholds_are_pinned() -> None:
    assert b1_2.MIN_JOINT_MARGIN_RAD == 0.20
    assert b1_2.MAX_WAYPOINT_POSITION_ERROR_M == 0.010
    assert b1_2.MAX_WAYPOINT_ORIENTATION_ERROR_RAD == 0.010
    assert b1_2.MAX_ENDPOINT_JOINT_DELTA_RAD == math.pi / 2.0
    assert b1_2.INTERPOLATION_SAMPLES_PER_LEG == 51
    assert b1_2.DESTINATION_RIM_TOP_Z_M == 0.040
    assert b1_2.TRANSFER_CLEARANCE_MARGIN_M == 0.010
    assert b1_2.REQUIRED_COMPONENT_BOTTOM_Z_M == 0.050
    assert 0.040 + 0.010 == pytest.approx(0.050, abs=1.0e-15)


@pytest.mark.parametrize(
    ("joint_delta", "expected"),
    [
        ((math.pi / 2.0 - 1.0e-12,), False),
        ((math.pi / 2.0,), False),
        ((math.pi / 2.0 + 1.0e-12,), True),
        ((-math.pi / 2.0 - 1.0e-12,), True),
        ((0.0, 0.1, math.pi / 2.0 + 1.0e-12, -0.2), True),
    ],
)
def test_endpoint_joint_delta_strict_threshold_semantics(
    joint_delta: tuple[float, ...],
    expected: bool,
) -> None:
    assert b1_2.endpoint_joint_delta_exceeded(joint_delta) is expected


def test_endpoint_joint_delta_rejects_nonfinite_input() -> None:
    with pytest.raises(ValueError, match="finite"):
        b1_2.endpoint_joint_delta_exceeded((0.0, math.nan))


def test_live_b1_1_immutability_manifest() -> None:
    for relative_path, expected_hash in EXPECTED_B1_1_HASHES.items():
        actual = hashlib.sha256(
            (REPOSITORY / relative_path).read_bytes()
        ).hexdigest()
        assert actual == expected_hash


def test_b1_2_digest_and_lineage_provenance() -> None:
    digest = hashlib.sha256(B1_2_EVIDENCE.read_bytes()).hexdigest()
    assert B1_2_DIGEST.read_text(encoding="ascii") == (
        f"{digest}  {B1_2_EVIDENCE.name}\n"
    )
    records = _load(B1_2_EVIDENCE)
    provenance = _records(records, "provenance")
    assert len(provenance) == 1
    record = provenance[0]
    assert record["evidence_schema"] == "prototype5.scene_calibration.b1_2"
    assert record["evidence_schema_version"] == "1.0.0"
    assert record["predecessor"] == "B1.1"
    assert record["correction_scope"] == "evidence-contract hardening"
    assert record["numerical_experiment_changed"] is False
    expected_by_role = {
        "source": EXPECTED_B1_1_HASHES[
            "src/prototype5/scene_calibration_b1_1.py"
        ],
        "runner": EXPECTED_B1_1_HASHES[
            "scripts/prototype5/run_scene_calibration_b1_1.py"
        ],
        "tests": EXPECTED_B1_1_HASHES[
            "tests/prototype5/test_scene_calibration_b1_1.py"
        ],
        "jsonl": EXPECTED_B1_1_HASHES[
            "results/prototype5/scene_calibration/phase_b1_1_results.jsonl"
        ],
        "digest": EXPECTED_B1_1_HASHES[
            "results/prototype5/scene_calibration/phase_b1_1_results.jsonl.sha256"
        ],
    }
    manifest = record["b1_1_immutability_manifest"]
    assert {
        role: entry["sha256"]
        for role, entry in manifest.items()
    } == expected_by_role
    assert record["numerical_kernel_module_sha256"] == expected_by_role["source"]


def test_b1_2_artifact_structure_and_candidate_identity() -> None:
    records = _load(B1_2_EVIDENCE)
    assert len(records) == 71
    assert Counter(record["record_type"] for record in records) == {
        "provenance": 1,
        "search_space": 1,
        "robot_metadata": 1,
        "selection_policy": 1,
        "candidate_summary": 32,
        "candidate_detail": 32,
        "pareto_analysis": 1,
        "runtime_summary": 1,
        "repository_integrity": 1,
    }
    summaries = _candidate_map(records, "candidate_summary")
    details = _candidate_map(records, "candidate_detail")
    assert len(summaries) == 32
    assert len(details) == 32
    assert set(summaries) == set(details)


def test_b1_2_artifact_contains_no_prohibited_current_terminology() -> None:
    raw = B1_2_EVIDENCE.read_text(encoding="utf-8")
    assert "branch_discontinuity" not in raw
    assert "BRANCH_DISCONTINUITY" not in raw


def test_b1_2_artifact_pins_literal_search_contract() -> None:
    search = _records(_load(B1_2_EVIDENCE), "search_space")[0]
    actual_layouts = {
        record["name"]: (
            tuple(record["source_xy_m"]),
            tuple(record["destination_xy_m"]),
        )
        for record in search["layouts"]
    }
    assert actual_layouts == EXPECTED_LAYOUTS
    assert tuple(search["orientations"]) == EXPECTED_ORIENTATIONS
    assert tuple(search["virtual_tool_offsets_z_m"]) == EXPECTED_TCP_M
    assert tuple(search["lift_offsets_m"]) == EXPECTED_LIFT_M
    assert search["candidate_count"] == 32
    thresholds = search["thresholds"]
    assert thresholds == {
        "min_joint_margin_rad": 0.20,
        "max_endpoint_joint_delta_rad": math.pi / 2.0,
        "max_waypoint_position_error_m": 0.010,
        "max_waypoint_orientation_error_rad": 0.010,
        "interpolation_samples_per_leg": 51,
        "required_component_bottom_z_m": 0.050,
    }
    geometry = search["geometry"]
    assert geometry["destination_rim_top_z_m"] == 0.040
    assert geometry["transfer_clearance_margin_m"] == 0.010
    assert not any("release" in key for key in thresholds)


def test_b1_2_topology_and_endpoint_delta_evaluation_state() -> None:
    records = _load(B1_2_EVIDENCE)
    summaries = _records(records, "candidate_summary")
    down_x = [r for r in summaries if r["orientation"] == "down_x_pi"]
    down_y = [r for r in summaries if r["orientation"] == "down_y_pi"]
    assert len(down_x) == 16
    assert len(down_y) == 16
    assert all(record["survives"] for record in down_x)
    assert all(not record["survives"] for record in down_y)
    assert all(record["endpoint_joint_delta_evaluated"] for record in down_x)
    assert all(
        record["endpoint_joint_delta_exceeded"] is False
        for record in down_x
    )
    assert all(
        record["endpoint_joint_delta_evaluated"] is False
        and record["endpoint_joint_delta_exceeded"] is None
        and record["failure_stage"] == "first_waypoint_ik"
        and record["failure_reason"] == "first_waypoint_out_of_limits"
        and record["solver_mode"] == "plain_ik_neutral_state"
        for record in down_y
    )


def _assert_numeric_sequence_equal(
    left: list[float],
    right: list[float],
) -> None:
    assert left == pytest.approx(right, rel=0.0, abs=1.0e-12)


def test_b1_1_b1_2_candidate_numerics_are_equivalent() -> None:
    predecessor = _candidate_map(_load(B1_1_EVIDENCE), "candidate_detail")
    current = _candidate_map(_load(B1_2_EVIDENCE), "candidate_detail")
    assert set(predecessor) == set(current)
    for candidate_id, old in predecessor.items():
        new = current[candidate_id]
        assert old["survives"] is new["survives"]
        if not old["survives"]:
            _assert_numeric_sequence_equal(
                old["raw_joint_vector"],
                new["raw_joint_vector"],
            )
            for old_violation, new_violation in zip(
                old["violations"],
                new["violations"],
                strict=True,
            ):
                for field in (
                    "value_rad",
                    "lower_limit_rad",
                    "upper_limit_rad",
                    "signed_excess_rad",
                ):
                    assert old_violation[field] == pytest.approx(
                        new_violation[field],
                        rel=0.0,
                        abs=1.0e-12,
                    )
            continue
        for field in SCALAR_METRICS:
            assert old[field] == pytest.approx(
                new[field],
                rel=0.0,
                abs=1.0e-12,
            )
        _assert_numeric_sequence_equal(
            old["predicted_release_projected_half_extents_m"],
            new["predicted_release_projected_half_extents_m"],
        )
        for old_waypoint, new_waypoint in zip(
            old["waypoints"],
            new["waypoints"],
            strict=True,
        ):
            for field in (
                "joint_vector",
                "target_position",
                "target_orientation",
                "actual_link_frame_position",
                "actual_link_frame_orientation",
            ):
                _assert_numeric_sequence_equal(
                    old_waypoint[field],
                    new_waypoint[field],
                )
            for field in (
                "joint_margin_rad",
                "position_error_m",
                "orientation_error_rad",
            ):
                assert old_waypoint[field] == pytest.approx(
                    new_waypoint[field],
                    rel=0.0,
                    abs=1.0e-12,
                )
        for old_leg, new_leg in zip(
            old["legs"],
            new["legs"],
            strict=True,
        ):
            _assert_numeric_sequence_equal(
                old_leg["joint_delta_rad"],
                new_leg["joint_delta_rad"],
            )
            for field in (
                "max_abs_joint_delta_rad",
                "min_endpoint_joint_margin_rad",
            ):
                assert old_leg[field] == pytest.approx(
                    new_leg[field],
                    rel=0.0,
                    abs=1.0e-12,
                )
        assert old["transfer_clearance_attribution"][
            "clearance_m"
        ] == pytest.approx(
            new["transfer_clearance_attribution"]["clearance_m"],
            rel=0.0,
            abs=1.0e-12,
        )


def test_corrected_orientation_evidence_is_preserved() -> None:
    details = _records(_load(B1_2_EVIDENCE), "candidate_detail")
    residuals = [
        waypoint["orientation_error_rad"]
        for detail in details
        if detail["survives"]
        for waypoint in detail["waypoints"]
    ]
    assert len(residuals) == 96
    assert min(residuals) == pytest.approx(
        1.9688078257972602e-08,
        rel=0.0,
        abs=1.0e-20,
    )
    assert max(residuals) == pytest.approx(
        0.0004207793403000842,
        rel=0.0,
        abs=1.0e-15,
    )
    assert sum(value == 0.0 for value in residuals) == 0
    assert all(value < 0.010 for value in residuals)


def test_endpoint_delta_artifact_values_recompute_from_literal_threshold() -> None:
    details = _records(_load(B1_2_EVIDENCE), "candidate_detail")
    for detail in details:
        if not detail["survives"]:
            continue
        candidate_exceeded = False
        for leg in detail["legs"]:
            independently_exceeded = any(
                abs(value) > math.pi / 2.0
                for value in leg["joint_delta_rad"]
            )
            assert leg["endpoint_joint_delta_exceeded"] is (
                independently_exceeded
            )
            candidate_exceeded = candidate_exceeded or independently_exceeded
        assert detail["endpoint_joint_delta_exceeded"] is candidate_exceeded


def test_pareto_frontier_is_independently_recomputed() -> None:
    records = _load(B1_2_EVIDENCE)
    survivors = [
        record
        for record in _records(records, "candidate_summary")
        if record["survives"]
    ]
    fields = (
        "min_waypoint_joint_margin_rad",
        "min_transfer_clearance_m",
        "max_leg_delta_rad",
        "max_waypoint_position_error_m",
        "predicted_release_center_error_m",
    )
    signs = (1.0, 1.0, -1.0, -1.0, -1.0)

    def dominates(left: dict[str, Any], right: dict[str, Any]) -> bool:
        left_values = [sign * left[field] for field, sign in zip(fields, signs)]
        right_values = [sign * right[field] for field, sign in zip(fields, signs)]
        return all(
            left_value >= right_value
            for left_value, right_value in zip(left_values, right_values)
        ) and any(
            left_value > right_value
            for left_value, right_value in zip(left_values, right_values)
        )

    frontier = {
        candidate["candidate_id"]
        for candidate in survivors
        if not any(
            dominates(other, candidate)
            for other in survivors
            if other["candidate_id"] != candidate["candidate_id"]
        )
    }
    expected = {
        f"b1_1-{layout}-down_x_pi-tcp_{tcp}-lift_{lift}"
        for layout in ("C", "D")
        for tcp in ("0p080", "0p100")
        for lift in ("0p140", "0p180")
    }
    assert frontier == expected
    pareto = _records(records, "pareto_analysis")[0]
    assert set(pareto["nondominated_candidate_ids"]) == expected
    policy = _records(records, "selection_policy")[0]
    assert policy["classification"] == "ENGINEERING_POLICY"
    assert policy["physical_superiority_claimed"] is False


def test_down_y_protocol_rejections_retain_concrete_attribution() -> None:
    details = _records(_load(B1_2_EVIDENCE), "candidate_detail")
    rejected = [record for record in details if not record["survives"]]
    assert len(rejected) == 16
    assert sum(len(record["violations"]) for record in rejected) == 32
    for detail in rejected:
        assert detail["orientation"] == "down_y_pi"
        assert len(detail["raw_joint_vector"]) == 7
        assert len(detail["violations"]) == 2
        for violation in detail["violations"]:
            if violation["limit_side"] == "lower":
                expected = (
                    violation["value_rad"] - violation["lower_limit_rad"]
                )
                assert expected < 0.0
            else:
                expected = (
                    violation["value_rad"] - violation["upper_limit_rad"]
                )
                assert expected > 0.0
            assert violation["signed_excess_rad"] == pytest.approx(
                expected,
                rel=0.0,
                abs=1.0e-15,
            )


def test_c_working_candidate_is_preserved_without_optimality_claim() -> None:
    records = _load(B1_2_EVIDENCE)
    details = _candidate_map(records, "candidate_detail")
    candidate = details["b1_1-C-down_x_pi-tcp_0p080-lift_0p140"]
    assert tuple(candidate["source_xy"]) == (0.50, -0.20)
    assert tuple(candidate["destination_xy"]) == (0.50, 0.20)
    assert candidate["survives"] is True
    assert candidate["pareto_nondominated"] is True
    assert candidate["selection_policy_rank"] == 7
    expected_metrics = {
        "min_waypoint_joint_margin_rad": 0.38543255541093613,
        "min_transfer_clearance_m": 0.10928637417724447,
        "max_leg_delta_rad": 0.76172694145471365,
        "max_waypoint_position_error_m": 0.0010322311462864389,
        "max_waypoint_orientation_error_rad": 0.00031009173460671348,
        "predicted_release_center_error_m": 3.548121792015504e-05,
    }
    for field, expected in expected_metrics.items():
        assert candidate[field] == pytest.approx(
            expected,
            rel=0.0,
            abs=1.0e-15,
        )
    assert candidate["release_footprint_contained"] is True


def test_b1_2_provenance_hashes_live_source_runner_and_tests() -> None:
    record = _records(_load(B1_2_EVIDENCE), "provenance")[0]
    source = REPOSITORY / "src/prototype5/scene_calibration_b1_2.py"
    runner = REPOSITORY / "scripts/prototype5/run_scene_calibration_b1_2.py"
    tests = REPOSITORY / "tests/prototype5/test_scene_calibration_b1_2.py"
    assert record["generator_module_sha256"] == hashlib.sha256(
        source.read_bytes()
    ).hexdigest()
    assert record["probe_script_sha256"] == hashlib.sha256(
        runner.read_bytes()
    ).hexdigest()
    assert record["b1_2_test_module_sha256"] == hashlib.sha256(
        tests.read_bytes()
    ).hexdigest()
