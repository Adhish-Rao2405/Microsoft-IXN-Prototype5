from __future__ import annotations

import copy
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from src.prototype5 import scene_calibration_b1_1 as b1_1


EVIDENCE_SCHEMA_NAME = "prototype5.scene_calibration.b1_2"
EVIDENCE_SCHEMA_VERSION = "1.0.0"
PREDECESSOR = "B1.1"
CORRECTION_SCOPE = "evidence-contract hardening"

MIN_JOINT_MARGIN_RAD = 0.20
MAX_WAYPOINT_POSITION_ERROR_M = 0.010
MAX_WAYPOINT_ORIENTATION_ERROR_RAD = 0.010
MAX_ENDPOINT_JOINT_DELTA_RAD = math.pi / 2.0
INTERPOLATION_SAMPLES_PER_LEG = 51
DESTINATION_RIM_TOP_Z_M = 0.040
TRANSFER_CLEARANCE_MARGIN_M = 0.010
REQUIRED_COMPONENT_BOTTOM_Z_M = 0.050

EXPECTED_LAYOUTS = {
    "A": ((0.45, -0.20), (0.45, 0.20)),
    "B": ((0.45, -0.25), (0.45, 0.25)),
    "C": ((0.50, -0.20), (0.50, 0.20)),
    "D": ((0.50, -0.25), (0.50, 0.25)),
}
EXPECTED_ORIENTATIONS = ("down_x_pi", "down_y_pi")
EXPECTED_VIRTUAL_TOOL_OFFSETS_Z_M = (0.080, 0.100)
EXPECTED_LIFT_OFFSETS_M = (0.140, 0.180)

EXPECTED_B1_1_HASHES = {
    "source": (
        "src/prototype5/scene_calibration_b1_1.py",
        "c280a01ae6db91527a2988d71d2d5691f57989f1ca46d0f9dc4602153591b1fd",
    ),
    "runner": (
        "scripts/prototype5/run_scene_calibration_b1_1.py",
        "7f3033aa05c70691df141561d934acd42fecc8b92180c4ebce3d2be7cb00473f",
    ),
    "tests": (
        "tests/prototype5/test_scene_calibration_b1_1.py",
        "7e3a249dba07b1ea05c4c5993ac9b42a17d6a1755ff5aa7c1e070984508c43b3",
    ),
    "jsonl": (
        "results/prototype5/scene_calibration/phase_b1_1_results.jsonl",
        "5490ca1b869bf187cee7f17420d501830cb0f832b2f808dd31cd9152eff1b784",
    ),
    "digest": (
        "results/prototype5/scene_calibration/phase_b1_1_results.jsonl.sha256",
        "9ef55fc699b6acb4f59f6ddff5c144a9f8c7c1a20ee1590ea3972371fa076db4",
    ),
}

PROHIBITED_CURRENT_TERMS = (
    "branch_discontinuity",
    "BRANCH_DISCONTINUITY",
)

JsonRecord = dict[str, Any]

LAYOUTS = b1_1.LAYOUTS
ORIENTATION_NAMES = b1_1.ORIENTATION_NAMES
VIRTUAL_TOOL_OFFSETS_Z_M = b1_1.VIRTUAL_TOOL_OFFSETS_Z_M
LIFT_OFFSETS_M = b1_1.LIFT_OFFSETS_M
PARETO_OBJECTIVES = b1_1.PARETO_OBJECTIVES

repository_root = b1_1.repository_root
sha256_file = b1_1.sha256_file
search_space = b1_1.search_space
evidence_record_counts = b1_1.evidence_record_counts
write_evidence = b1_1.write_evidence


def endpoint_joint_delta_exceeded(
    joint_delta_rad: Sequence[float],
) -> bool:
    """Return whether any adjacent-endpoint joint delta strictly exceeds pi/2."""
    converted = tuple(float(value) for value in joint_delta_rad)
    if not all(math.isfinite(value) for value in converted):
        raise ValueError("Joint delta vector must contain only finite values")
    return any(
        abs(value) > MAX_ENDPOINT_JOINT_DELTA_RAD
        for value in converted
    )


def _verify_predecessor_contract() -> None:
    layouts = {
        layout.name: (layout.source_xy, layout.destination_xy)
        for layout in LAYOUTS
    }
    if layouts != EXPECTED_LAYOUTS:
        raise RuntimeError(f"B1.1 layout contract drifted: {layouts!r}")
    if ORIENTATION_NAMES != EXPECTED_ORIENTATIONS:
        raise RuntimeError("B1.1 orientation contract drifted")
    if VIRTUAL_TOOL_OFFSETS_Z_M != EXPECTED_VIRTUAL_TOOL_OFFSETS_Z_M:
        raise RuntimeError("B1.1 virtual TCP contract drifted")
    if LIFT_OFFSETS_M != EXPECTED_LIFT_OFFSETS_M:
        raise RuntimeError("B1.1 lift contract drifted")
    expected_scalars = {
        "min_joint_margin_rad": MIN_JOINT_MARGIN_RAD,
        "max_waypoint_position_error_m": MAX_WAYPOINT_POSITION_ERROR_M,
        "max_waypoint_orientation_error_rad": (
            MAX_WAYPOINT_ORIENTATION_ERROR_RAD
        ),
        "max_endpoint_joint_delta_rad": MAX_ENDPOINT_JOINT_DELTA_RAD,
        "interpolation_samples_per_leg": INTERPOLATION_SAMPLES_PER_LEG,
        "destination_rim_top_z_m": DESTINATION_RIM_TOP_Z_M,
        "transfer_clearance_margin_m": TRANSFER_CLEARANCE_MARGIN_M,
    }
    predecessor_scalars = {
        "min_joint_margin_rad": b1_1.MIN_JOINT_MARGIN_RAD,
        "max_waypoint_position_error_m": (
            b1_1.MAX_WAYPOINT_POSITION_ERROR_M
        ),
        "max_waypoint_orientation_error_rad": (
            b1_1.MAX_WAYPOINT_ORIENTATION_ERROR_RAD
        ),
        "max_endpoint_joint_delta_rad": b1_1.BRANCH_DISCONTINUITY_RAD,
        "interpolation_samples_per_leg": (
            b1_1.INTERPOLATION_SAMPLES_PER_LEG
        ),
        "destination_rim_top_z_m": b1_1.DESTINATION_RIM_TOP_Z_M,
        "transfer_clearance_margin_m": b1_1.TRANSFER_CLEARANCE_MARGIN_M,
    }
    if predecessor_scalars != expected_scalars:
        raise RuntimeError(
            "B1.1 numerical threshold contract drifted: "
            f"{predecessor_scalars!r}"
        )
    required_bottom = (
        b1_1.DESTINATION_RIM_TOP_Z_M
        + b1_1.TRANSFER_CLEARANCE_MARGIN_M
    )
    if not math.isclose(
        required_bottom,
        REQUIRED_COMPONENT_BOTTOM_Z_M,
        rel_tol=0.0,
        abs_tol=1.0e-15,
    ):
        raise RuntimeError("B1.1 required transfer bottom contract drifted")


def _verify_b1_1_manifest(root: Path) -> dict[str, JsonRecord]:
    manifest: dict[str, JsonRecord] = {}
    for role, (relative_path, expected_hash) in EXPECTED_B1_1_HASHES.items():
        path = root / relative_path
        if not path.is_file():
            raise FileNotFoundError(f"Missing immutable B1.1 {role}: {path}")
        actual_hash = sha256_file(path)
        if actual_hash != expected_hash:
            raise RuntimeError(
                f"Immutable B1.1 {role} hash drift: {actual_hash}; "
                f"expected {expected_hash}"
            )
        manifest[role] = {
            "path": str(path.resolve()),
            "sha256": actual_hash,
        }
    return manifest


def _migrate_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        migrated: JsonRecord = {}
        for key, item in value.items():
            migrated_key = {
                "branch_discontinuity": "endpoint_joint_delta_exceeded",
                "branch_discontinuity_rad": "max_endpoint_joint_delta_rad",
            }.get(str(key), str(key))
            if migrated_key in migrated:
                raise ValueError(f"B1.2 field collision: {migrated_key}")
            migrated[migrated_key] = _migrate_value(item)
        return migrated
    if isinstance(value, list):
        return [_migrate_value(item) for item in value]
    if isinstance(value, tuple):
        return [_migrate_value(item) for item in value]
    if value == "BRANCH_DISCONTINUITY":
        return "ENDPOINT_JOINT_DELTA_EXCEEDED"
    return copy.deepcopy(value)


def _add_evaluation_state(record: JsonRecord) -> None:
    if record.get("record_type") not in {
        "candidate_summary",
        "candidate_detail",
    }:
        return
    evaluated = bool(record.get("metrics_evaluated"))
    record["endpoint_joint_delta_evaluated"] = evaluated
    if not evaluated:
        record["endpoint_joint_delta_exceeded"] = None


def _harden_search_space(record: JsonRecord) -> None:
    thresholds = record.get("thresholds")
    if not isinstance(thresholds, dict):
        raise ValueError("B1.2 search-space thresholds are missing")
    thresholds["required_component_bottom_z_m"] = (
        REQUIRED_COMPONENT_BOTTOM_Z_M
    )
    if any("release" in key and "threshold" in key for key in thresholds):
        raise ValueError("An unsupported release-centre threshold was emitted")


def _harden_provenance(
    record: JsonRecord,
    root: Path,
    b1_1_manifest: Mapping[str, JsonRecord],
) -> None:
    generator_module = Path(__file__).resolve()
    test_module = root / "tests/prototype5/test_scene_calibration_b1_2.py"
    if not test_module.is_file():
        raise FileNotFoundError(f"Missing B1.2 test module: {test_module}")
    record.update(
        {
            "evidence_schema": EVIDENCE_SCHEMA_NAME,
            "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
            "generator_module": str(generator_module),
            "generator_module_sha256": sha256_file(generator_module),
            "b1_2_test_module": str(test_module.resolve()),
            "b1_2_test_module_sha256": sha256_file(test_module),
            "predecessor": PREDECESSOR,
            "correction_scope": CORRECTION_SCOPE,
            "numerical_experiment_changed": False,
            "numerical_kernel_module": str(Path(b1_1.__file__).resolve()),
            "numerical_kernel_module_sha256": b1_1_manifest["source"][
                "sha256"
            ],
            "b1_1_immutability_manifest": dict(b1_1_manifest),
        }
    )


def validate_b1_2_records(records: Sequence[Mapping[str, Any]]) -> None:
    counts = evidence_record_counts(records)
    expected_counts = {
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
    if counts != expected_counts or len(records) != 71:
        raise ValueError(
            f"Unexpected B1.2 artifact structure: {counts!r}, total={len(records)}"
        )
    serialized = "\n".join(
        json.dumps(dict(record), sort_keys=True, allow_nan=False)
        for record in records
    )
    for prohibited in PROHIBITED_CURRENT_TERMS:
        if prohibited in serialized:
            raise ValueError(f"Prohibited B1.1 terminology remains: {prohibited}")

    summaries = [
        record
        for record in records
        if record.get("record_type") == "candidate_summary"
    ]
    details = [
        record
        for record in records
        if record.get("record_type") == "candidate_detail"
    ]
    summary_ids = [str(record["candidate_id"]) for record in summaries]
    detail_ids = [str(record["candidate_id"]) for record in details]
    if len(set(summary_ids)) != 32 or len(set(detail_ids)) != 32:
        raise ValueError("Duplicate B1.2 candidate identity")
    if set(summary_ids) != set(detail_ids):
        raise ValueError("B1.2 summary/detail candidate identities differ")

    down_x_survivors = sum(
        bool(record["survives"])
        and record["orientation"] == "down_x_pi"
        for record in summaries
    )
    down_y_protocol_rejections = sum(
        not bool(record["survives"])
        and record["orientation"] == "down_y_pi"
        and record["failure_stage"] == "first_waypoint_ik"
        and record["failure_reason"] == "first_waypoint_out_of_limits"
        and record["solver_mode"] == "plain_ik_neutral_state"
        for record in summaries
    )
    if down_x_survivors != 16 or down_y_protocol_rejections != 16:
        raise ValueError(
            "B1.2 topology differs from B1.1: "
            f"down_x={down_x_survivors}, down_y={down_y_protocol_rejections}"
        )
    for record in summaries + details:
        evaluated = bool(record["endpoint_joint_delta_evaluated"])
        value = record["endpoint_joint_delta_exceeded"]
        if evaluated and not isinstance(value, bool):
            raise ValueError("Evaluated endpoint delta must have a boolean result")
        if not evaluated and value is not None:
            raise ValueError("Unevaluated endpoint delta must be null")


def generate_evidence_records(
    probe_script: Path,
    historical_b1_script: Path,
    historical_b1_results: Path,
) -> list[JsonRecord]:
    _verify_predecessor_contract()
    root = repository_root()
    b1_1_manifest = _verify_b1_1_manifest(root)
    predecessor_records = b1_1.generate_evidence_records(
        probe_script=probe_script,
        historical_b1_script=historical_b1_script,
        historical_b1_results=historical_b1_results,
    )
    records = [_migrate_value(record) for record in predecessor_records]
    for record in records:
        if not isinstance(record, dict):
            raise TypeError("Migrated B1.2 record is not a dictionary")
        _add_evaluation_state(record)
        if record.get("record_type") == "search_space":
            _harden_search_space(record)
        elif record.get("record_type") == "provenance":
            _harden_provenance(record, root, b1_1_manifest)
    validate_b1_2_records(records)
    return records


def iter_candidate_records(
    records: Iterable[Mapping[str, Any]],
    record_type: str,
) -> tuple[Mapping[str, Any], ...]:
    return tuple(
        record
        for record in records
        if record.get("record_type") == record_type
    )
