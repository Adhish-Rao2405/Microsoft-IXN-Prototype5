"""B2 deterministic kinematic-plan evidence for the frozen scene.

This module promotes the committed B1.2 task joint vectors without invoking
inverse kinematics.  It selects one bounded simulation HOME state, replays
forward kinematics in fresh PyBullet DIRECT sessions, and serializes the
resulting static plan contract.  Collision and dynamic execution are outside
this module's scope.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
from typing import Any, NoReturn, Sequence

import pybullet as pb
import pybullet_data


SCHEMA_IDENTIFIER = "prototype5.scene_kinematic_plan.b2"
SCHEMA_VERSION = "1.0.0"
GATE_IDENTIFIER = "B2_HOME_AND_KINEMATIC_PLAN"

CALIBRATION_FREEZE_COMMIT = "86c02ed3f90ad5f17a84101f35cd483d5e1afe83"
EXPECTED_BRANCH = "feature/s1-pybullet-governed-simulation"
B1_2_RELATIVE_PATH = Path(
    "results/prototype5/scene_calibration/phase_b1_2_results.jsonl"
)
B1_2_DIGEST_RELATIVE_PATH = B1_2_RELATIVE_PATH.with_suffix(
    B1_2_RELATIVE_PATH.suffix + ".sha256"
)
B1_2_SHA256 = "b852fcdba89a89e0a83abc83c80cdf6eceb6b5a33babaf0558fce6d479b80f2c"
B1_2_DIGEST_SHA256 = (
    "c81946e7e4f06bf51617d2e72ca84275e35abd2ee345f0dd993a1d8639b62781"
)
SELECTED_CANDIDATE_ID = "b1_1-C-down_x_pi-tcp_0p080-lift_0p140"

ROBOT_URDF_RELATIVE = Path("kuka_iiwa/model.urdf")
ROBOT_URDF_SHA256 = "5c13c5b4bb88b5265223e0ec9a7706cbf81e9bb21cc0e18534273755a041788c"
PYBULLET_BINARY_SHA256 = (
    "e8a99694353e508f9e934a57494c177ddb9317cde94781da8bb68670c2334e40"
)
PYBULLET_PACKAGE_VERSION = "3.2.7"
PYBULLET_API_VERSION = 202010061
CONTROLLED_JOINTS = (0, 1, 2, 3, 4, 5, 6)
EE_LINK = 6
BASE_POSITION = (0.0, 0.0, 0.0)

LAYOUT_NAME = "C"
SOURCE_XY_M = (0.50, -0.20)
DESTINATION_XY_M = (0.50, 0.20)
ORIENTATION_NAME = "down_x_pi"
VIRTUAL_TCP_M = 0.080
LIFT_M = 0.140

MIN_JOINT_MARGIN_RAD = 0.20
MAX_WAYPOINT_POSITION_ERROR_M = 0.010
MAX_WAYPOINT_ORIENTATION_ERROR_RAD = 0.010
MAX_ENDPOINT_JOINT_DELTA_RAD = math.pi / 2.0
REPLAY_TRIAL_COUNT = 10
REPRODUCIBILITY_POSITION_TOLERANCE_M = 1e-9
REPRODUCIBILITY_ORIENTATION_TOLERANCE_RAD = 1e-9

TASK_STATE_NAMES = (
    "SOURCE_HIGH",
    "SOURCE_PICK",
    "SOURCE_HIGH_RETURN",
    "DESTINATION_HIGH",
    "DESTINATION_PLACE",
    "DESTINATION_HIGH_RETURN",
)
PREDECESSOR_WAYPOINT_NAMES = (
    "source_high",
    "source_tool",
    "source_high_return",
    "destination_high",
    "destination_tool",
    "destination_high_return",
)
ROUTE_STATE_NAMES = (
    "HOME",
    *TASK_STATE_NAMES,
    "HOME",
)

JointVector = tuple[float, float, float, float, float, float, float]
Vector3 = tuple[float, float, float]
Quaternion = tuple[float, float, float, float]
JsonObject = dict[str, object]


class B2Error(RuntimeError):
    """Base class for explicit B2 failures."""


class CalibrationArtifactError(B2Error):
    """The committed calibration artifact violates the frozen input contract."""


class NumericalContractError(B2Error):
    """A non-finite or structurally invalid numerical value was supplied."""


class HomeSelectionError(B2Error):
    """Neither authorized HOME candidate satisfies the B2 screens."""


class KinematicContractError(B2Error):
    """The frozen route fails a required static kinematic screen."""


class InfrastructureError(B2Error):
    """Repository, PyBullet, or filesystem infrastructure is invalid."""


@dataclass(frozen=True)
class Pose:
    position: Vector3
    orientation: Quaternion


@dataclass(frozen=True)
class JointLimit:
    index: int
    name: str
    lower_rad: float
    upper_rad: float


@dataclass(frozen=True)
class TaskWaypoint:
    name: str
    predecessor_name: str
    joint_vector: JointVector
    predecessor_target_link_pose: Pose
    target_tcp_pose: Pose
    predecessor_actual_link_pose: Pose
    predecessor_joint_margin_rad: float
    predecessor_position_residual_m: float
    predecessor_orientation_residual_rad: float


@dataclass(frozen=True)
class CalibrationInput:
    candidate_id: str
    joint_limits: tuple[JointLimit, ...]
    task_waypoints: tuple[TaskWaypoint, ...]


@dataclass(frozen=True)
class JointValueEvidence:
    index: int
    name: str
    value_rad: float
    lower_rad: float
    upper_rad: float
    lower_margin_rad: float
    upper_margin_rad: float
    nearest_margin_rad: float


@dataclass(frozen=True)
class LegEvidence:
    start: str
    end: str
    signed_delta_rad: JointVector
    absolute_delta_rad: JointVector
    max_abs_delta_rad: float
    responsible_joint_index: int
    responsible_joint_name: str
    responsible_signed_delta_rad: float
    endpoint_joint_delta_exceeded: bool


@dataclass(frozen=True)
class HomeEvaluation:
    candidate: str
    joint_vector: JointVector
    joint_values: tuple[JointValueEvidence, ...]
    minimum_margin_rad: float
    outgoing_leg: LegEvidence
    incoming_leg: LegEvidence
    accepted: bool
    rejection_reasons: tuple[str, ...]


@dataclass(frozen=True)
class HomeSelection:
    h0: HomeEvaluation
    h1: HomeEvaluation | None
    selected_candidate: str
    selected_joint_vector: JointVector


@dataclass(frozen=True)
class PlanState:
    route_index: int
    name: str
    joint_vector: JointVector
    task_waypoint: TaskWaypoint | None


@dataclass(frozen=True)
class StateReplay:
    route_index: int
    name: str
    link_pose: Pose
    tcp_pose: Pose
    position_residual_m: float | None
    orientation_residual_rad: float | None


@dataclass(frozen=True)
class ReplayTrial:
    trial_index: int
    states: tuple[StateReplay, ...]


@dataclass(frozen=True)
class ReproducibilitySummary:
    maximum_link_position_spread_m: float
    link_position_state: str
    maximum_tcp_position_spread_m: float
    tcp_position_state: str
    maximum_link_orientation_spread_rad: float
    link_orientation_state: str
    maximum_tcp_orientation_spread_rad: float
    tcp_orientation_state: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _reject_json_constant(token: str) -> NoReturn:
    raise CalibrationArtifactError(f"Non-finite JSON constant: {token}")


def _finite_float(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise NumericalContractError(f"{field} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise NumericalContractError(f"{field} must be finite")
    return result


def _sequence(value: object, field: str, length: int) -> Sequence[object]:
    if not isinstance(value, (list, tuple)) or len(value) != length:
        raise CalibrationArtifactError(f"{field} must contain {length} values")
    return value


def vector3(value: object, field: str) -> Vector3:
    values = _sequence(value, field, 3)
    return (
        _finite_float(values[0], f"{field}[0]"),
        _finite_float(values[1], f"{field}[1]"),
        _finite_float(values[2], f"{field}[2]"),
    )


def joint_vector(value: object, field: str) -> JointVector:
    values = _sequence(value, field, 7)
    return (
        _finite_float(values[0], f"{field}[0]"),
        _finite_float(values[1], f"{field}[1]"),
        _finite_float(values[2], f"{field}[2]"),
        _finite_float(values[3], f"{field}[3]"),
        _finite_float(values[4], f"{field}[4]"),
        _finite_float(values[5], f"{field}[5]"),
        _finite_float(values[6], f"{field}[6]"),
    )


def normalize_quaternion(value: object, field: str = "quaternion") -> Quaternion:
    values = _sequence(value, field, 4)
    quaternion = tuple(
        _finite_float(component, f"{field}[{index}]")
        for index, component in enumerate(values)
    )
    norm = math.sqrt(sum(component * component for component in quaternion))
    if norm <= 1e-15:
        raise NumericalContractError(f"{field} has zero or near-zero norm")
    return (
        quaternion[0] / norm,
        quaternion[1] / norm,
        quaternion[2] / norm,
        quaternion[3] / norm,
    )


def quaternion_multiply(left: Quaternion, right: Quaternion) -> Quaternion:
    lx, ly, lz, lw = left
    rx, ry, rz, rw = right
    return (
        lw * rx + lx * rw + ly * rz - lz * ry,
        lw * ry - lx * rz + ly * rw + lz * rx,
        lw * rz + lx * ry - ly * rx + lz * rw,
        lw * rw - lx * rx - ly * ry - lz * rz,
    )


def quaternion_conjugate(value: Quaternion) -> Quaternion:
    return (-value[0], -value[1], -value[2], value[3])


def quaternion_angular_residual(
    target: object,
    actual: object,
) -> float:
    target_normalized = normalize_quaternion(target, "target_quaternion")
    actual_normalized = normalize_quaternion(actual, "actual_quaternion")
    if actual_normalized == target_normalized or actual_normalized == tuple(
        -component for component in target_normalized
    ):
        return 0.0
    relative = quaternion_multiply(
        actual_normalized,
        quaternion_conjugate(target_normalized),
    )
    vector_norm = math.sqrt(sum(component * component for component in relative[:3]))
    angle = 2.0 * math.atan2(vector_norm, abs(relative[3]))
    if not math.isfinite(angle) or not 0.0 <= angle <= math.pi:
        raise NumericalContractError(f"Invalid quaternion residual: {angle}")
    return angle


def rotate_vector(orientation: Quaternion, vector: Vector3) -> Vector3:
    vector_quaternion: Quaternion = (vector[0], vector[1], vector[2], 0.0)
    rotated = quaternion_multiply(
        quaternion_multiply(orientation, vector_quaternion),
        quaternion_conjugate(orientation),
    )
    return (rotated[0], rotated[1], rotated[2])


def compose_pose(parent: Pose, local: Pose) -> Pose:
    parent_orientation = normalize_quaternion(
        list(parent.orientation), "parent.orientation"
    )
    local_orientation = normalize_quaternion(
        list(local.orientation), "local.orientation"
    )
    translated = rotate_vector(parent_orientation, local.position)
    return Pose(
        position=(
            parent.position[0] + translated[0],
            parent.position[1] + translated[1],
            parent.position[2] + translated[2],
        ),
        orientation=normalize_quaternion(
            list(quaternion_multiply(parent_orientation, local_orientation)),
            "composed.orientation",
        ),
    )


VIRTUAL_TCP_LOCAL_POSE = Pose(
    position=(0.0, 0.0, VIRTUAL_TCP_M),
    orientation=(0.0, 0.0, 0.0, 1.0),
)


def position_distance(left: Vector3, right: Vector3) -> float:
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(left, right)))


def joint_value_evidence(
    values: JointVector,
    limits: tuple[JointLimit, ...],
) -> tuple[JointValueEvidence, ...]:
    if len(limits) != 7:
        raise NumericalContractError("Exactly seven joint limits are required")
    evidence: list[JointValueEvidence] = []
    for value, limit in zip(values, limits):
        value = _finite_float(value, f"joint[{limit.index}]")
        lower_margin = value - limit.lower_rad
        upper_margin = limit.upper_rad - value
        evidence.append(
            JointValueEvidence(
                index=limit.index,
                name=limit.name,
                value_rad=value,
                lower_rad=limit.lower_rad,
                upper_rad=limit.upper_rad,
                lower_margin_rad=lower_margin,
                upper_margin_rad=upper_margin,
                nearest_margin_rad=min(lower_margin, upper_margin),
            )
        )
    return tuple(evidence)


def leg_evidence(
    start_name: str,
    start: JointVector,
    end_name: str,
    end: JointVector,
    limits: tuple[JointLimit, ...],
) -> LegEvidence:
    if len(limits) != 7:
        raise NumericalContractError("Exactly seven joint limits are required")
    signed = tuple(
        _finite_float(end_value - start_value, f"delta[{index}]")
        for index, (start_value, end_value) in enumerate(zip(start, end))
    )
    signed_vector = joint_vector(list(signed), "signed_delta_rad")
    absolute_vector = joint_vector(
        [abs(value) for value in signed_vector], "absolute_delta_rad"
    )
    responsible_index = max(range(7), key=lambda index: absolute_vector[index])
    maximum = absolute_vector[responsible_index]
    return LegEvidence(
        start=start_name,
        end=end_name,
        signed_delta_rad=signed_vector,
        absolute_delta_rad=absolute_vector,
        max_abs_delta_rad=maximum,
        responsible_joint_index=responsible_index,
        responsible_joint_name=limits[responsible_index].name,
        responsible_signed_delta_rad=signed_vector[responsible_index],
        endpoint_joint_delta_exceeded=maximum > MAX_ENDPOINT_JOINT_DELTA_RAD,
    )


def evaluate_home(
    candidate: str,
    values: JointVector,
    source_high: JointVector,
    destination_high_return: JointVector,
    limits: tuple[JointLimit, ...],
) -> HomeEvaluation:
    joint_values = joint_value_evidence(values, limits)
    minimum_margin = min(item.nearest_margin_rad for item in joint_values)
    outgoing = leg_evidence("HOME", values, "SOURCE_HIGH", source_high, limits)
    incoming = leg_evidence(
        "DESTINATION_HIGH_RETURN",
        destination_high_return,
        "HOME",
        values,
        limits,
    )
    reasons: list[str] = []
    if any(item.nearest_margin_rad < 0.0 for item in joint_values):
        reasons.append("HOME_JOINT_OUT_OF_LIMITS")
    if minimum_margin < MIN_JOINT_MARGIN_RAD:
        reasons.append("HOME_JOINT_MARGIN_BELOW_MINIMUM")
    if outgoing.endpoint_joint_delta_exceeded:
        reasons.append("HOME_TO_SOURCE_HIGH_ENDPOINT_JOINT_DELTA_EXCEEDED")
    if incoming.endpoint_joint_delta_exceeded:
        reasons.append("DESTINATION_HIGH_RETURN_TO_HOME_ENDPOINT_JOINT_DELTA_EXCEEDED")
    return HomeEvaluation(
        candidate=candidate,
        joint_vector=values,
        joint_values=joint_values,
        minimum_margin_rad=minimum_margin,
        outgoing_leg=outgoing,
        incoming_leg=incoming,
        accepted=not reasons,
        rejection_reasons=tuple(reasons),
    )


def select_home(
    source_high: JointVector,
    destination_high_return: JointVector,
    limits: tuple[JointLimit, ...],
) -> HomeSelection:
    h0: JointVector = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    h0_evaluation = evaluate_home(
        "H0", h0, source_high, destination_high_return, limits
    )
    if h0_evaluation.accepted:
        return HomeSelection(h0_evaluation, None, "H0", h0)
    h1 = joint_vector(
        [
            (source_value + destination_value) / 2.0
            for source_value, destination_value in zip(
                source_high, destination_high_return
            )
        ],
        "H1",
    )
    h1_evaluation = evaluate_home(
        "H1", h1, source_high, destination_high_return, limits
    )
    if not h1_evaluation.accepted:
        raise HomeSelectionError(
            "B2_HOLD_HOME_SELECTION: H0 and the sole authorized H1 failed"
        )
    return HomeSelection(h0_evaluation, h1_evaluation, "H1", h1)


def _strict_json_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                raise CalibrationArtifactError(
                    f"Blank line in calibration artifact at {line_number}"
                )
            value = json.loads(line, parse_constant=_reject_json_constant)
            if not isinstance(value, dict):
                raise CalibrationArtifactError(
                    f"Calibration record {line_number} is not an object"
                )
            records.append(value)
    return records


def _one_record(
    records: Sequence[dict[str, Any]],
    record_type: str,
) -> dict[str, Any]:
    matches = [record for record in records if record.get("record_type") == record_type]
    if len(matches) != 1:
        raise CalibrationArtifactError(
            f"Expected one {record_type} record; found {len(matches)}"
        )
    return matches[0]


def _verify_digest_file(
    artifact_path: Path,
    digest_path: Path,
    expected_artifact_sha: str,
) -> None:
    if sha256_file(artifact_path) != expected_artifact_sha:
        raise CalibrationArtifactError("B2_HARD_BLOCKER_CALIBRATION_DRIFT: JSONL hash")
    if sha256_file(digest_path) != B1_2_DIGEST_SHA256:
        raise CalibrationArtifactError(
            "B2_HARD_BLOCKER_CALIBRATION_DRIFT: digest-file hash"
        )
    content = digest_path.read_text(encoding="ascii")
    expected_content = f"{expected_artifact_sha}  {artifact_path.name}\n"
    if content != expected_content:
        raise CalibrationArtifactError(
            "B2_HARD_BLOCKER_CALIBRATION_DRIFT: digest content"
        )


def _parse_joint_limits(robot: dict[str, Any]) -> tuple[JointLimit, ...]:
    if tuple(robot.get("controlled_joints", ())) != CONTROLLED_JOINTS:
        raise CalibrationArtifactError("Unexpected controlled joint indices")
    if robot.get("ee_link") != EE_LINK:
        raise CalibrationArtifactError("Unexpected end-effector link")
    base = vector3(robot.get("world_base_mount_position"), "world_base_mount_position")
    if base != BASE_POSITION:
        raise CalibrationArtifactError(f"Unexpected base position: {base}")
    metadata = _sequence(robot.get("joint_metadata"), "joint_metadata", 7)
    limits: list[JointLimit] = []
    for expected_index, raw in enumerate(metadata):
        if not isinstance(raw, dict):
            raise CalibrationArtifactError("Joint metadata entry must be an object")
        index = raw.get("index")
        name = raw.get("joint_name")
        if index != expected_index or not isinstance(name, str) or not name:
            raise CalibrationArtifactError("Invalid joint metadata identity")
        lower = _finite_float(raw.get("lower_limit_rad"), f"joint[{index}].lower")
        upper = _finite_float(raw.get("upper_limit_rad"), f"joint[{index}].upper")
        if lower >= upper:
            raise CalibrationArtifactError(f"Invalid joint limits for joint {index}")
        limits.append(JointLimit(index, name, lower, upper))
    return tuple(limits)


def _verify_search_space(search: dict[str, Any]) -> None:
    layouts = _sequence(search.get("layouts"), "layouts", 4)
    matching_layouts = [
        layout
        for layout in layouts
        if isinstance(layout, dict) and layout.get("name") == LAYOUT_NAME
    ]
    if len(matching_layouts) != 1:
        raise CalibrationArtifactError("Frozen layout C is not unique")
    layout = matching_layouts[0]
    if vector3([*layout.get("source_xy_m", []), 0.0], "source_xy")[:2] != SOURCE_XY_M:
        raise CalibrationArtifactError("Frozen source coordinates changed")
    if (
        vector3([*layout.get("destination_xy_m", []), 0.0], "destination_xy")[:2]
        != DESTINATION_XY_M
    ):
        raise CalibrationArtifactError("Frozen destination coordinates changed")
    if search.get("orientations") != ["down_x_pi", "down_y_pi"]:
        raise CalibrationArtifactError("Frozen orientations changed")
    if search.get("virtual_tool_offsets_z_m") != [0.08, 0.1]:
        raise CalibrationArtifactError("Frozen virtual TCP values changed")
    if search.get("lift_offsets_m") != [0.14, 0.18]:
        raise CalibrationArtifactError("Frozen lift values changed")
    thresholds = search.get("thresholds")
    if not isinstance(thresholds, dict):
        raise CalibrationArtifactError("Missing calibration thresholds")
    expected = {
        "min_joint_margin_rad": MIN_JOINT_MARGIN_RAD,
        "max_waypoint_position_error_m": MAX_WAYPOINT_POSITION_ERROR_M,
        "max_waypoint_orientation_error_rad": MAX_WAYPOINT_ORIENTATION_ERROR_RAD,
        "max_endpoint_joint_delta_rad": MAX_ENDPOINT_JOINT_DELTA_RAD,
    }
    for key, value in expected.items():
        if _finite_float(thresholds.get(key), key) != value:
            raise CalibrationArtifactError(f"Frozen threshold changed: {key}")


def _pose_from_record(
    record: dict[str, Any],
    position_key: str,
    orientation_key: str,
    field: str,
) -> Pose:
    return Pose(
        vector3(record.get(position_key), f"{field}.{position_key}"),
        normalize_quaternion(
            record.get(orientation_key), f"{field}.{orientation_key}"
        ),
    )


def _parse_task_waypoints(
    detail: dict[str, Any],
    limits: tuple[JointLimit, ...],
) -> tuple[TaskWaypoint, ...]:
    raw_waypoints = _sequence(detail.get("waypoints"), "waypoints", 6)
    result: list[TaskWaypoint] = []
    for state_name, predecessor_name, raw in zip(
        TASK_STATE_NAMES, PREDECESSOR_WAYPOINT_NAMES, raw_waypoints
    ):
        if not isinstance(raw, dict) or raw.get("name") != predecessor_name:
            raise CalibrationArtifactError(
                f"Expected predecessor waypoint {predecessor_name}"
            )
        values = joint_vector(raw.get("joint_vector"), f"{predecessor_name}.joints")
        joint_values = joint_value_evidence(values, limits)
        if any(item.nearest_margin_rad < 0.0 for item in joint_values):
            raise CalibrationArtifactError(f"{predecessor_name} is outside joint limits")
        target_link = _pose_from_record(
            raw, "target_position", "target_orientation", predecessor_name
        )
        actual_link = _pose_from_record(
            raw,
            "actual_link_frame_position",
            "actual_link_frame_orientation",
            predecessor_name,
        )
        stored_margin = _finite_float(
            raw.get("joint_margin_rad"), f"{predecessor_name}.joint_margin_rad"
        )
        recomputed_margin = min(item.nearest_margin_rad for item in joint_values)
        if abs(stored_margin - recomputed_margin) > 1e-12:
            raise CalibrationArtifactError(
                f"Stored joint margin mismatch for {predecessor_name}"
            )
        result.append(
            TaskWaypoint(
                name=state_name,
                predecessor_name=predecessor_name,
                joint_vector=values,
                predecessor_target_link_pose=target_link,
                target_tcp_pose=compose_pose(target_link, VIRTUAL_TCP_LOCAL_POSE),
                predecessor_actual_link_pose=actual_link,
                predecessor_joint_margin_rad=stored_margin,
                predecessor_position_residual_m=_finite_float(
                    raw.get("position_error_m"), f"{predecessor_name}.position_error_m"
                ),
                predecessor_orientation_residual_rad=_finite_float(
                    raw.get("orientation_error_rad"),
                    f"{predecessor_name}.orientation_error_rad",
                ),
            )
        )
    if tuple(item.name for item in result) != TASK_STATE_NAMES:
        raise CalibrationArtifactError("Task waypoint ordering changed")
    return tuple(result)


def load_calibration_input(repository_root: Path) -> CalibrationInput:
    artifact_path = repository_root / B1_2_RELATIVE_PATH
    digest_path = repository_root / B1_2_DIGEST_RELATIVE_PATH
    if not artifact_path.is_file() or not digest_path.is_file():
        raise CalibrationArtifactError("B1.2 artifact or companion digest is missing")
    _verify_digest_file(artifact_path, digest_path, B1_2_SHA256)
    records = _strict_json_records(artifact_path)
    if len(records) != 71:
        raise CalibrationArtifactError(f"Expected 71 B1.2 records; found {len(records)}")
    _verify_search_space(_one_record(records, "search_space"))
    limits = _parse_joint_limits(_one_record(records, "robot_metadata"))

    summaries = [
        record
        for record in records
        if record.get("record_type") == "candidate_summary"
        and record.get("candidate_id") == SELECTED_CANDIDATE_ID
    ]
    details = [
        record
        for record in records
        if record.get("record_type") == "candidate_detail"
        and record.get("candidate_id") == SELECTED_CANDIDATE_ID
    ]
    if len(summaries) != 1 or len(details) != 1:
        raise CalibrationArtifactError(
            "B2_HARD_BLOCKER_CALIBRATION_ARTIFACT: candidate is not unique"
        )
    summary = summaries[0]
    detail = details[0]
    expected_fields: dict[str, object] = {
        "layout": LAYOUT_NAME,
        "orientation": ORIENTATION_NAME,
        "virtual_tool_offset_z_m": VIRTUAL_TCP_M,
        "lift_offset_m": LIFT_M,
        "survives": True,
        "status": "survivor",
    }
    for key, expected in expected_fields.items():
        if summary.get(key) != expected or detail.get(key) != expected:
            raise CalibrationArtifactError(f"Candidate field changed: {key}")
    source = _sequence(detail.get("source_xy"), "source_xy", 2)
    destination = _sequence(detail.get("destination_xy"), "destination_xy", 2)
    source_xy = tuple(_finite_float(value, "source_xy") for value in source)
    destination_xy = tuple(
        _finite_float(value, "destination_xy") for value in destination
    )
    if source_xy != SOURCE_XY_M or destination_xy != DESTINATION_XY_M:
        raise CalibrationArtifactError("Selected candidate coordinates changed")
    target_orientation = normalize_quaternion(
        detail.get("target_orientation"), "candidate.target_orientation"
    )
    expected_orientation = normalize_quaternion(
        list(pb.getQuaternionFromEuler((math.pi, 0.0, 0.0))),
        "expected_orientation",
    )
    if quaternion_angular_residual(expected_orientation, target_orientation) > 1e-15:
        raise CalibrationArtifactError("Selected candidate orientation changed")
    task_waypoints = _parse_task_waypoints(detail, limits)
    return CalibrationInput(SELECTED_CANDIDATE_ID, limits, task_waypoints)


def build_route(
    selected_home: JointVector,
    task_waypoints: tuple[TaskWaypoint, ...],
) -> tuple[PlanState, ...]:
    if len(task_waypoints) != 6:
        raise KinematicContractError("Exactly six task waypoints are required")
    route = [PlanState(0, "HOME", selected_home, None)]
    route.extend(
        PlanState(index, waypoint.name, waypoint.joint_vector, waypoint)
        for index, waypoint in enumerate(task_waypoints, start=1)
    )
    route.append(PlanState(7, "HOME", selected_home, None))
    result = tuple(route)
    if tuple(state.name for state in result) != ROUTE_STATE_NAMES:
        raise KinematicContractError("B2 route ordering is invalid")
    if result[0].joint_vector != result[-1].joint_vector:
        raise KinematicContractError("Initial and final HOME definitions differ")
    return result


def build_route_legs(
    route: tuple[PlanState, ...],
    limits: tuple[JointLimit, ...],
) -> tuple[LegEvidence, ...]:
    if len(route) != 8:
        raise KinematicContractError("Exactly eight route states are required")
    legs = tuple(
        leg_evidence(
            start.name,
            start.joint_vector,
            end.name,
            end.joint_vector,
            limits,
        )
        for start, end in zip(route, route[1:])
    )
    if len(legs) != 7:
        raise KinematicContractError("Exactly seven route legs are required")
    if any(leg.endpoint_joint_delta_exceeded for leg in legs):
        raise KinematicContractError("B2 endpoint joint-delta screen failed")
    return legs


def _validate_loaded_robot(
    body_id: int,
    client_id: int,
    expected_limits: tuple[JointLimit, ...],
) -> None:
    if pb.getNumJoints(body_id, physicsClientId=client_id) != 7:
        raise InfrastructureError("Loaded KUKA model does not contain seven joints")
    observed: list[JointLimit] = []
    for index in CONTROLLED_JOINTS:
        info = pb.getJointInfo(body_id, index, physicsClientId=client_id)
        if int(info[2]) != pb.JOINT_REVOLUTE:
            raise InfrastructureError(f"Joint {index} is not revolute")
        observed.append(
            JointLimit(
                index=index,
                name=info[1].decode("utf-8"),
                lower_rad=float(info[8]),
                upper_rad=float(info[9]),
            )
        )
    if tuple(observed) != expected_limits:
        raise InfrastructureError("Runtime URDF joint metadata differs from B1.2")


def _state_replay(
    state: PlanState,
    body_id: int,
    client_id: int,
) -> StateReplay:
    for index, value in enumerate(state.joint_vector):
        pb.resetJointState(
            body_id,
            index,
            targetValue=value,
            targetVelocity=0.0,
            physicsClientId=client_id,
        )
    link_state = pb.getLinkState(
        body_id,
        EE_LINK,
        computeForwardKinematics=True,
        physicsClientId=client_id,
    )
    # Indices 4/5 are the world URDF link-frame pose; 0/1 are COM/inertial.
    link_pose = Pose(
        vector3(link_state[4], f"{state.name}.link_position"),
        normalize_quaternion(link_state[5], f"{state.name}.link_orientation"),
    )
    tcp_pose = compose_pose(link_pose, VIRTUAL_TCP_LOCAL_POSE)
    if state.task_waypoint is None:
        position_residual = None
        orientation_residual = None
    else:
        target = state.task_waypoint.target_tcp_pose
        position_residual = position_distance(target.position, tcp_pose.position)
        orientation_residual = quaternion_angular_residual(
            target.orientation, tcp_pose.orientation
        )
    return StateReplay(
        route_index=state.route_index,
        name=state.name,
        link_pose=link_pose,
        tcp_pose=tcp_pose,
        position_residual_m=position_residual,
        orientation_residual_rad=orientation_residual,
    )


def run_fk_replays(
    route: tuple[PlanState, ...],
    expected_limits: tuple[JointLimit, ...],
    data_root: Path,
) -> tuple[ReplayTrial, ...]:
    trials: list[ReplayTrial] = []
    for trial_index in range(REPLAY_TRIAL_COUNT):
        client_id = pb.connect(pb.DIRECT)
        if client_id < 0:
            raise InfrastructureError("PyBullet DIRECT connection failed")
        try:
            pb.resetSimulation(physicsClientId=client_id)
            pb.setAdditionalSearchPath(str(data_root), physicsClientId=client_id)
            body_id = pb.loadURDF(
                ROBOT_URDF_RELATIVE.as_posix(),
                basePosition=BASE_POSITION,
                baseOrientation=(0.0, 0.0, 0.0, 1.0),
                useFixedBase=True,
                physicsClientId=client_id,
            )
            _validate_loaded_robot(body_id, client_id, expected_limits)
            states = tuple(
                _state_replay(state, body_id, client_id) for state in route
            )
            trials.append(ReplayTrial(trial_index, states))
        finally:
            pb.disconnect(physicsClientId=client_id)
    return tuple(trials)


def reproducibility_summary(
    trials: tuple[ReplayTrial, ...],
) -> ReproducibilitySummary:
    if len(trials) != REPLAY_TRIAL_COUNT:
        raise KinematicContractError(
            f"Expected {REPLAY_TRIAL_COUNT} replay trials; found {len(trials)}"
        )
    expected_indices = tuple(range(8))
    for trial in trials:
        if tuple(state.route_index for state in trial.states) != expected_indices:
            raise KinematicContractError("Replay trial state structure is invalid")

    def maximum_spread(
        pose_selector: str,
        orientation: bool,
    ) -> tuple[float, str]:
        maximum = -1.0
        responsible = ""
        for route_index in expected_indices:
            poses = [
                getattr(trial.states[route_index], pose_selector) for trial in trials
            ]
            for left_index, left in enumerate(poses):
                for right in poses[left_index + 1 :]:
                    if orientation:
                        spread = quaternion_angular_residual(
                            left.orientation, right.orientation
                        )
                    else:
                        spread = position_distance(left.position, right.position)
                    if not math.isfinite(spread):
                        raise NumericalContractError("Non-finite reproducibility spread")
                    if spread > maximum:
                        maximum = spread
                        responsible = (
                            f"{trials[0].states[route_index].name}"
                            f"[{route_index}]"
                        )
        return maximum, responsible

    link_position, link_position_state = maximum_spread("link_pose", False)
    tcp_position, tcp_position_state = maximum_spread("tcp_pose", False)
    link_orientation, link_orientation_state = maximum_spread("link_pose", True)
    tcp_orientation, tcp_orientation_state = maximum_spread("tcp_pose", True)
    summary = ReproducibilitySummary(
        link_position,
        link_position_state,
        tcp_position,
        tcp_position_state,
        link_orientation,
        link_orientation_state,
        tcp_orientation,
        tcp_orientation_state,
    )
    if max(link_position, tcp_position) > REPRODUCIBILITY_POSITION_TOLERANCE_M:
        raise KinematicContractError("B2_HOLD_REPRODUCIBILITY: position spread")
    if (
        max(link_orientation, tcp_orientation)
        > REPRODUCIBILITY_ORIENTATION_TOLERANCE_RAD
    ):
        raise KinematicContractError("B2_HOLD_REPRODUCIBILITY: orientation spread")
    return summary


def _pose_json(pose: Pose) -> JsonObject:
    return {
        "position": list(pose.position),
        "quaternion_xyzw": list(pose.orientation),
    }


def _joint_value_json(value: JointValueEvidence) -> JsonObject:
    return {
        "joint_index": value.index,
        "joint_name": value.name,
        "value_rad": value.value_rad,
        "lower_limit_rad": value.lower_rad,
        "upper_limit_rad": value.upper_rad,
        "margin_to_lower_rad": value.lower_margin_rad,
        "margin_to_upper_rad": value.upper_margin_rad,
        "nearest_limit_margin_rad": value.nearest_margin_rad,
    }


def _leg_json(leg: LegEvidence) -> JsonObject:
    return {
        "from": leg.start,
        "to": leg.end,
        "signed_joint_delta_rad": list(leg.signed_delta_rad),
        "absolute_joint_delta_rad": list(leg.absolute_delta_rad),
        "max_abs_endpoint_joint_delta_rad": leg.max_abs_delta_rad,
        "responsible_joint_index": leg.responsible_joint_index,
        "responsible_joint_name": leg.responsible_joint_name,
        "responsible_signed_delta_rad": leg.responsible_signed_delta_rad,
        "endpoint_joint_delta_exceeded": leg.endpoint_joint_delta_exceeded,
        "threshold_rad": MAX_ENDPOINT_JOINT_DELTA_RAD,
        "threshold_comparison": "strict_greater_than",
    }


def _home_json(evaluation: HomeEvaluation) -> JsonObject:
    return {
        "candidate": evaluation.candidate,
        "joint_vector": list(evaluation.joint_vector),
        "joint_limit_evidence": [
            _joint_value_json(value) for value in evaluation.joint_values
        ],
        "minimum_joint_margin_rad": evaluation.minimum_margin_rad,
        "outgoing_leg": _leg_json(evaluation.outgoing_leg),
        "incoming_leg": _leg_json(evaluation.incoming_leg),
        "accepted": evaluation.accepted,
        "rejection_reasons": list(evaluation.rejection_reasons),
    }


def _state_replay_json(replay: StateReplay) -> JsonObject:
    return {
        "route_index": replay.route_index,
        "state": replay.name,
        "world_link_frame_pose": _pose_json(replay.link_pose),
        "virtual_tcp_pose": _pose_json(replay.tcp_pose),
        "position_residual_m": replay.position_residual_m,
        "orientation_residual_rad": replay.orientation_residual_rad,
    }


def _task_waypoint_json(waypoint: TaskWaypoint) -> JsonObject:
    return {
        "state": waypoint.name,
        "predecessor_waypoint_name": waypoint.predecessor_name,
        "joint_vector": list(waypoint.joint_vector),
        "predecessor_target_link_pose": _pose_json(
            waypoint.predecessor_target_link_pose
        ),
        "target_virtual_tcp_pose": _pose_json(waypoint.target_tcp_pose),
        "target_virtual_tcp_derivation": (
            "compose predecessor target link pose with local "
            "(0,0,0.080 m), identity rotation exactly once"
        ),
        "predecessor_actual_world_link_frame_pose": _pose_json(
            waypoint.predecessor_actual_link_pose
        ),
        "predecessor_joint_margin_rad": waypoint.predecessor_joint_margin_rad,
        "predecessor_position_residual_m": waypoint.predecessor_position_residual_m,
        "predecessor_orientation_residual_rad": (
            waypoint.predecessor_orientation_residual_rad
        ),
    }


def _run_git(repository_root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=repository_root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise InfrastructureError(
            f"git {' '.join(arguments)} failed: {completed.stderr.strip()}"
        )
    return completed.stdout.strip()


def verify_repository_for_generation(repository_root: Path) -> JsonObject:
    top_level = Path(_run_git(repository_root, "rev-parse", "--show-toplevel"))
    if top_level.resolve() != repository_root.resolve():
        raise InfrastructureError(f"Unexpected repository root: {top_level}")
    branch = _run_git(repository_root, "branch", "--show-current")
    head = _run_git(repository_root, "rev-parse", "HEAD")
    if branch != EXPECTED_BRANCH or head != CALIBRATION_FREEZE_COMMIT:
        raise InfrastructureError("B2_HARD_BLOCKER_WORKSPACE_DRIFT")
    if _run_git(repository_root, "diff", "--cached", "--name-only"):
        raise InfrastructureError("Staged files exist during B2 generation")
    _run_git(repository_root, "diff", "--check")
    status = _run_git(repository_root, "status", "--short")
    allowed = {
        "?? scripts/prototype5/run_scene_kinematic_plan_b2.py",
        "?? src/prototype5/scene_kinematic_plan_b2.py",
        "?? tests/prototype5/test_scene_kinematic_plan_b2.py",
        "?? results/prototype5/scene_calibration/failed_attempts/",
    }
    observed = set(status.splitlines()) if status else set()
    if not observed <= allowed:
        raise InfrastructureError(f"Unexpected B2 generation status: {status}")
    return {
        "repository_root": str(repository_root.resolve()),
        "branch": branch,
        "head": head,
        "status_short_before_generation": status,
        "staged_files": [],
        "git_diff_check": "clean",
    }


def _runtime_provenance(repository_root: Path) -> JsonObject:
    binary_path = Path(pb.__file__).resolve()
    data_root = Path(pybullet_data.getDataPath()).resolve()
    urdf_path = data_root / ROBOT_URDF_RELATIVE
    if importlib.metadata.version("pybullet") != PYBULLET_PACKAGE_VERSION:
        raise InfrastructureError("Unexpected PyBullet package version")
    if pb.getAPIVersion() != PYBULLET_API_VERSION:
        raise InfrastructureError("Unexpected PyBullet API version")
    if sha256_file(binary_path) != PYBULLET_BINARY_SHA256:
        raise InfrastructureError("Unexpected PyBullet binary hash")
    if sha256_file(urdf_path) != ROBOT_URDF_SHA256:
        raise InfrastructureError("Unexpected KUKA URDF hash")
    source = repository_root / "src/prototype5/scene_kinematic_plan_b2.py"
    runner = repository_root / "scripts/prototype5/run_scene_kinematic_plan_b2.py"
    tests = repository_root / "tests/prototype5/test_scene_kinematic_plan_b2.py"
    for path in (source, runner, tests):
        if not path.is_file():
            raise InfrastructureError(f"Required B2 file is missing: {path}")
    return {
        "python_executable": str(Path(sys.executable).resolve()),
        "python_version": sys.version,
        "platform": platform.platform(),
        "pybullet_package_version": PYBULLET_PACKAGE_VERSION,
        "pybullet_api_version": pb.getAPIVersion(),
        "pybullet_binary_path": str(binary_path),
        "pybullet_binary_sha256": sha256_file(binary_path),
        "pybullet_data_path": str(data_root),
        "urdf_path": str(urdf_path),
        "urdf_sha256": sha256_file(urdf_path),
        "generator_module_sha256": sha256_file(source),
        "runner_sha256": sha256_file(runner),
        "tests_sha256": sha256_file(tests),
    }


def _plan_state_json(
    state: PlanState,
    limits: tuple[JointLimit, ...],
    replay: StateReplay,
) -> JsonObject:
    joint_values = joint_value_evidence(state.joint_vector, limits)
    value: JsonObject = {
        "route_index": state.route_index,
        "state": state.name,
        "joint_vector": list(state.joint_vector),
        "joint_limit_evidence": [
            _joint_value_json(item) for item in joint_values
        ],
        "minimum_joint_margin_rad": min(
            item.nearest_margin_rad for item in joint_values
        ),
        "replay": _state_replay_json(replay),
    }
    if state.task_waypoint is None:
        value["cartesian_target_evaluated"] = False
        value["task_waypoint"] = None
    else:
        value["cartesian_target_evaluated"] = True
        value["task_waypoint"] = _task_waypoint_json(state.task_waypoint)
    return value


def build_b2_artifact(repository_root: Path) -> JsonObject:
    repository_root = repository_root.resolve()
    repository = verify_repository_for_generation(repository_root)
    runtime = _runtime_provenance(repository_root)
    calibration = load_calibration_input(repository_root)
    task_by_name = {waypoint.name: waypoint for waypoint in calibration.task_waypoints}
    home = select_home(
        task_by_name["SOURCE_HIGH"].joint_vector,
        task_by_name["DESTINATION_HIGH_RETURN"].joint_vector,
        calibration.joint_limits,
    )
    route = build_route(home.selected_joint_vector, calibration.task_waypoints)
    legs = build_route_legs(route, calibration.joint_limits)
    all_joint_values = [
        (state, value)
        for state in route[:-1]
        for value in joint_value_evidence(state.joint_vector, calibration.joint_limits)
    ]
    route_min_state, route_min_value = min(
        all_joint_values, key=lambda pair: pair[1].nearest_margin_rad
    )
    if route_min_value.nearest_margin_rad < MIN_JOINT_MARGIN_RAD:
        raise KinematicContractError("B2 route joint-margin screen failed")
    max_leg = max(legs, key=lambda leg: leg.max_abs_delta_rad)

    data_root = Path(pybullet_data.getDataPath()).resolve()
    trials = run_fk_replays(route, calibration.joint_limits, data_root)
    first_replay = trials[0]
    task_replays = [
        state for state in first_replay.states if state.name != "HOME"
    ]
    if len(task_replays) != 6:
        raise KinematicContractError("Replay did not contain six task states")
    for state in task_replays:
        if state.position_residual_m is None or state.orientation_residual_rad is None:
            raise KinematicContractError(f"Missing residual for {state.name}")
        if state.position_residual_m > MAX_WAYPOINT_POSITION_ERROR_M:
            raise KinematicContractError(
                "B2_HARD_BLOCKER_CALIBRATION_CONTRADICTION: position residual"
            )
        if state.orientation_residual_rad > MAX_WAYPOINT_ORIENTATION_ERROR_RAD:
            raise KinematicContractError(
                "B2_HARD_BLOCKER_CALIBRATION_CONTRADICTION: orientation residual"
            )
    reproducibility = reproducibility_summary(trials)

    home_roundtrip_delta = joint_vector(
        [end - start for start, end in zip(route[0].joint_vector, route[-1].joint_vector)],
        "home_roundtrip_definition_delta",
    )
    if max(abs(value) for value in home_roundtrip_delta) != 0.0:
        raise KinematicContractError("HOME round-trip definition is not exact")

    h1_value: JsonObject = (
        {"evaluated": False, "evidence": None}
        if home.h1 is None
        else {"evaluated": True, "evidence": _home_json(home.h1)}
    )
    return {
        "schema_identifier": SCHEMA_IDENTIFIER,
        "schema_version": SCHEMA_VERSION,
        "gate_identifier": GATE_IDENTIFIER,
        "provenance": {
            **repository,
            **runtime,
            "calibration_freeze_commit": CALIBRATION_FREEZE_COMMIT,
            "b1_2_artifact_path": str((repository_root / B1_2_RELATIVE_PATH).resolve()),
            "b1_2_artifact_sha256": B1_2_SHA256,
            "b1_2_digest_file_sha256": B1_2_DIGEST_SHA256,
            "task_waypoint_source": (
                "exact committed B1.2 joint vectors; no B2 inverse-kinematics solve"
            ),
        },
        "semantic_execution_tuple": {
            "scene_id": "manufacturing_demo_scene",
            "scene_state_version": "1.0.0",
            "operation": "MOVE",
            "object": "blue_component",
            "source": "input_tray_a",
            "destination": "assembly_fixture_b",
        },
        "robot": {
            "urdf": ROBOT_URDF_RELATIVE.as_posix(),
            "base_position": list(BASE_POSITION),
            "use_fixed_base": True,
            "controlled_joints": list(CONTROLLED_JOINTS),
            "ee_link": EE_LINK,
            "joint_limits": [
                {
                    "joint_index": limit.index,
                    "joint_name": limit.name,
                    "lower_limit_rad": limit.lower_rad,
                    "upper_limit_rad": limit.upper_rad,
                }
                for limit in calibration.joint_limits
            ],
            "urdf_velocity_fields_used_as_execution_policy": False,
        },
        "frozen_calibration": {
            "layout": LAYOUT_NAME,
            "source_xy_m": list(SOURCE_XY_M),
            "destination_xy_m": list(DESTINATION_XY_M),
            "orientation": ORIENTATION_NAME,
            "orientation_euler_rad": [math.pi, 0.0, 0.0],
            "virtual_tcp_m": VIRTUAL_TCP_M,
            "virtual_tcp_local_pose": _pose_json(VIRTUAL_TCP_LOCAL_POSE),
            "lift_m": LIFT_M,
            "selected_b1_2_candidate_id": calibration.candidate_id,
        },
        "screens": {
            "minimum_joint_margin_rad": MIN_JOINT_MARGIN_RAD,
            "maximum_task_position_residual_m": MAX_WAYPOINT_POSITION_ERROR_M,
            "maximum_task_orientation_residual_rad": (
                MAX_WAYPOINT_ORIENTATION_ERROR_RAD
            ),
            "maximum_endpoint_joint_delta_rad": MAX_ENDPOINT_JOINT_DELTA_RAD,
            "endpoint_joint_delta_comparison": "strict_greater_than_is_exceeded",
            "reproducibility_position_tolerance_m": (
                REPRODUCIBILITY_POSITION_TOLERANCE_M
            ),
            "reproducibility_orientation_tolerance_rad": (
                REPRODUCIBILITY_ORIENTATION_TOLERANCE_RAD
            ),
        },
        "home_selection": {
            "policy": (
                "evaluate H0=[0]*7; only if rejected evaluate H1 midpoint of "
                "SOURCE_HIGH and DESTINATION_HIGH_RETURN; no H2"
            ),
            "h0": {"evaluated": True, "evidence": _home_json(home.h0)},
            "h1": h1_value,
            "selected_candidate": home.selected_candidate,
            "simulation_home_joint_state": list(home.selected_joint_vector),
        },
        "ordered_plan": [
            _plan_state_json(state, calibration.joint_limits, replay)
            for state, replay in zip(route, first_replay.states)
        ],
        "route_legs": [_leg_json(leg) for leg in legs],
        "plan_metrics": {
            "state_count": len(route),
            "leg_count": len(legs),
            "minimum_route_joint_margin_rad": route_min_value.nearest_margin_rad,
            "minimum_margin_state": route_min_state.name,
            "minimum_margin_joint_index": route_min_value.index,
            "minimum_margin_joint_name": route_min_value.name,
            "maximum_route_endpoint_joint_delta_rad": max_leg.max_abs_delta_rad,
            "maximum_delta_leg": f"{max_leg.start}->{max_leg.end}",
            "maximum_delta_joint_index": max_leg.responsible_joint_index,
            "maximum_delta_joint_name": max_leg.responsible_joint_name,
            "maximum_delta_signed_rad": max_leg.responsible_signed_delta_rad,
        },
        "round_trip_definition": {
            "initial_home_joint_vector": list(route[0].joint_vector),
            "final_home_joint_vector": list(route[-1].joint_vector),
            "home_roundtrip_definition_delta": list(home_roundtrip_delta),
            "maximum_absolute_difference_rad": max(
                abs(value) for value in home_roundtrip_delta
            ),
            "claim": "route-definition equality; not dynamic controller accuracy",
        },
        "reproducibility": {
            "trial_count": len(trials),
            "fresh_direct_session_per_trial": True,
            "physics_steps_per_trial": 0,
            "trials": [
                {
                    "trial_index": trial.trial_index,
                    "states": [_state_replay_json(state) for state in trial.states],
                }
                for trial in trials
            ],
            "summary": {
                "maximum_link_position_spread_m": (
                    reproducibility.maximum_link_position_spread_m
                ),
                "link_position_responsible_state": reproducibility.link_position_state,
                "maximum_tcp_position_spread_m": (
                    reproducibility.maximum_tcp_position_spread_m
                ),
                "tcp_position_responsible_state": reproducibility.tcp_position_state,
                "maximum_link_orientation_spread_rad": (
                    reproducibility.maximum_link_orientation_spread_rad
                ),
                "link_orientation_responsible_state": (
                    reproducibility.link_orientation_state
                ),
                "maximum_tcp_orientation_spread_rad": (
                    reproducibility.maximum_tcp_orientation_spread_rad
                ),
                "tcp_orientation_responsible_state": (
                    reproducibility.tcp_orientation_state
                ),
            },
        },
        "claim_boundaries": {
            "establishes": (
                "deterministic joint-limit-qualified FK-verified ordered static "
                "joint-state plan under the pinned PyBullet environment"
            ),
            "does_not_establish": [
                "collision freedom",
                "continuous path safety",
                "dynamic executability",
                "velocity or acceleration safety",
                "controller stability",
                "physical grasp validity",
                "settled placement accuracy",
                "real-robot validity",
                "industrial safety",
            ],
        },
    }


def deterministic_json_bytes(value: object) -> bytes:
    try:
        text = json.dumps(
            value,
            sort_keys=True,
            indent=2,
            allow_nan=False,
            ensure_ascii=False,
        )
    except (TypeError, ValueError) as error:
        raise NumericalContractError(f"Artifact is not strict JSON: {error}") from error
    return (text + "\n").encode("utf-8")


def _write_new_file(path: Path, content: bytes) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite existing artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=path.parent, delete=False, prefix=f".{path.name}."
        ) as stream:
            temporary_path = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def write_b2_artifact(output_path: Path, artifact: JsonObject) -> tuple[str, Path]:
    digest_path = output_path.with_suffix(output_path.suffix + ".sha256")
    if output_path.exists() or digest_path.exists():
        raise FileExistsError(
            f"Refusing to overwrite B2 artifact or digest: {output_path}"
        )
    content = deterministic_json_bytes(artifact)
    digest = hashlib.sha256(content).hexdigest()
    _write_new_file(output_path, content)
    try:
        _write_new_file(
            digest_path,
            f"{digest}  {output_path.name}\n".encode("ascii"),
        )
    except BaseException:
        # The generated artifact is retained as failed-run evidence.  It is not
        # deleted or silently overwritten by this writer.
        raise
    return digest, digest_path


def verify_companion_digest(output_path: Path, digest_path: Path) -> str:
    digest = sha256_file(output_path)
    expected = f"{digest}  {output_path.name}\n"
    if digest_path.read_text(encoding="ascii") != expected:
        raise InfrastructureError("B2 companion digest does not match artifact")
    return digest
