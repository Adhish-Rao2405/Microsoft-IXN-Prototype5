from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import os
import platform
from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys
from typing import Any, Iterable, Mapping, Sequence

import pybullet as pb
import pybullet_data


EVIDENCE_SCHEMA_NAME = "prototype5.scene_calibration.b1_1"
EVIDENCE_SCHEMA_VERSION = "1.0.0"
EXPECTED_BRANCH = "feature/s1-pybullet-governed-simulation"
EXPECTED_HEAD = "4cb6c66c375639088ea552a18d7e30d08ee00491"
EXPECTED_PYTHON_VERSION = (3, 12, 10)
EXPECTED_PYBULLET_VERSION = "3.2.7"
EXPECTED_PYBULLET_SHA256 = (
    "e8a99694353e508f9e934a57494c177d"
    "db9317cde94781da8bb68670c2334e40"
)
EXPECTED_KUKA_URDF_SHA256 = (
    "5c13c5b4bb88b5265223e0ec9a7706c"
    "bf81e9bb21cc0e18534273755a041788c"
)
EXPECTED_KUKA_MANIFEST_SHA256 = (
    "cee6f5a30f860c1302cb7ef69f0da2c"
    "0736a283fe87b87504f0141438c544fb3"
)

MIN_JOINT_MARGIN_RAD = 0.20
BRANCH_DISCONTINUITY_RAD = math.pi / 2.0
MAX_WAYPOINT_POSITION_ERROR_M = 0.010
MAX_WAYPOINT_ORIENTATION_ERROR_RAD = 0.010
INTERPOLATION_SAMPLES_PER_LEG = 51
QUATERNION_MIN_NORM = 1.0e-12

COMPONENT_HALF_EXTENTS_M = (0.025, 0.025, 0.025)
SOURCE_PLATFORM_HALF_EXTENTS_M = (0.060, 0.060, 0.010)
SOURCE_PLATFORM_CENTER_Z_M = 0.010
SOURCE_PLATFORM_TOP_Z_M = 0.020
DESTINATION_OUTER_HALF_EXTENTS_M = (0.070, 0.070, 0.010)
DESTINATION_FLOOR_CENTER_Z_M = 0.010
DESTINATION_FLOOR_TOP_Z_M = 0.020
DESTINATION_INTERIOR_HALF_EXTENTS_M = (0.050, 0.050)
DESTINATION_RIM_TOP_Z_M = 0.040
DESTINATION_RESERVED_WALL_MARGIN_M = 0.005
TRANSFER_CLEARANCE_MARGIN_M = 0.010

VIRTUAL_TOOL_OFFSETS_Z_M = (0.080, 0.100)
LIFT_OFFSETS_M = (0.140, 0.180)
ORIENTATION_NAMES = ("down_x_pi", "down_y_pi")

Vector3 = tuple[float, float, float]
Quaternion = tuple[float, float, float, float]
JointVector = list[float]
JsonRecord = dict[str, Any]


@dataclass(frozen=True)
class Layout:
    name: str
    source_xy: tuple[float, float]
    destination_xy: tuple[float, float]


LAYOUTS = (
    Layout("A", (0.45, -0.20), (0.45, 0.20)),
    Layout("B", (0.45, -0.25), (0.45, 0.25)),
    Layout("C", (0.50, -0.20), (0.50, 0.20)),
    Layout("D", (0.50, -0.25), (0.50, 0.25)),
)


@dataclass(frozen=True)
class CandidateSpec:
    layout: Layout
    orientation_name: str
    virtual_tool_offset_z_m: float
    lift_offset_m: float

    @property
    def candidate_id(self) -> str:
        tcp = f"{self.virtual_tool_offset_z_m:.3f}".replace(".", "p")
        lift = f"{self.lift_offset_m:.3f}".replace(".", "p")
        return (
            f"b1_1-{self.layout.name}-{self.orientation_name}"
            f"-tcp_{tcp}-lift_{lift}"
        )


@dataclass(frozen=True)
class WaypointTarget:
    name: str
    position: Vector3


@dataclass(frozen=True)
class RobotModel:
    body_id: int
    controlled_joints: tuple[int, ...]
    lower_limits: tuple[float, ...]
    upper_limits: tuple[float, ...]
    joint_ranges: tuple[float, ...]
    joint_names: tuple[str, ...]
    joint_metadata: tuple[JsonRecord, ...]
    ee_link: int
    ee_local_inertial_position: Vector3
    ee_local_inertial_orientation: Quaternion


@dataclass(frozen=True)
class ParetoObjective:
    field: str
    direction: str

    def __post_init__(self) -> None:
        if self.direction not in {"maximize", "minimize"}:
            raise ValueError(f"Unsupported objective direction: {self.direction}")


PARETO_OBJECTIVES = (
    ParetoObjective("min_waypoint_joint_margin_rad", "maximize"),
    ParetoObjective("min_transfer_clearance_m", "maximize"),
    ParetoObjective("max_leg_delta_rad", "minimize"),
    ParetoObjective("max_waypoint_position_error_m", "minimize"),
    ParetoObjective("predicted_release_center_error_m", "minimize"),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def directory_manifest_sha256(root: Path) -> str:
    if not root.is_dir():
        raise FileNotFoundError(f"Asset directory does not exist: {root}")
    digest = hashlib.sha256()
    files = sorted(path for path in root.rglob("*") if path.is_file())
    if not files:
        raise ValueError(f"Asset directory is empty: {root}")
    for path in files:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, byteorder="big"))
        digest.update(relative)
        digest.update(bytes.fromhex(sha256_file(path)))
    return digest.hexdigest()


def repository_root() -> Path:
    root = Path(__file__).resolve().parents[2]
    if not (root / ".git").exists():
        raise RuntimeError(f"Generator is not inside the expected repository: {root}")
    return root


def run_git(
    root: Path,
    *arguments: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={root.as_posix()}",
            "-C",
            str(root),
            *arguments,
        ],
        check=check,
        capture_output=True,
        text=True,
    )


def verify_repository_identity(root: Path) -> JsonRecord:
    branch = run_git(root, "branch", "--show-current").stdout.strip()
    head = run_git(root, "rev-parse", "HEAD").stdout.strip()
    status = run_git(root, "status", "--short").stdout.strip()
    if branch != EXPECTED_BRANCH:
        raise RuntimeError(f"Unexpected branch: {branch!r}")
    if head != EXPECTED_HEAD:
        raise RuntimeError(f"Unexpected HEAD: {head!r}")
    return {"branch": branch, "head": head, "status_short": status}


def _finite_float_tuple(
    values: Sequence[float],
    expected_length: int,
    label: str,
) -> tuple[float, ...]:
    if len(values) != expected_length:
        raise ValueError(f"{label} must contain {expected_length} values")
    converted = tuple(float(value) for value in values)
    if not all(math.isfinite(value) for value in converted):
        raise ValueError(f"{label} must contain only finite values")
    return converted


def normalize_quaternion(values: Sequence[float]) -> Quaternion:
    quaternion = _finite_float_tuple(values, 4, "quaternion")
    norm = math.sqrt(math.fsum(value * value for value in quaternion))
    if norm <= QUATERNION_MIN_NORM:
        raise ValueError(
            f"Quaternion norm must exceed {QUATERNION_MIN_NORM}; received {norm}"
        )
    return (
        quaternion[0] / norm,
        quaternion[1] / norm,
        quaternion[2] / norm,
        quaternion[3] / norm,
    )


def quaternion_multiply(
    left: Sequence[float],
    right: Sequence[float],
) -> Quaternion:
    lx, ly, lz, lw = _finite_float_tuple(left, 4, "left quaternion")
    rx, ry, rz, rw = _finite_float_tuple(right, 4, "right quaternion")
    return (
        lw * rx + lx * rw + ly * rz - lz * ry,
        lw * ry - lx * rz + ly * rw + lz * rx,
        lw * rz + lx * ry - ly * rx + lz * rw,
        lw * rw - lx * rx - ly * ry - lz * rz,
    )


def quaternion_angular_distance(
    left: Sequence[float],
    right: Sequence[float],
) -> float:
    """Return the shortest rotational distance in [0, pi]."""
    lx, ly, lz, lw = normalize_quaternion(left)
    normalized_right = normalize_quaternion(right)
    relative = quaternion_multiply(
        (-lx, -ly, -lz, lw),
        normalized_right,
    )
    vector_norm = math.sqrt(
        math.fsum(component * component for component in relative[:3])
    )
    angle = 2.0 * math.atan2(vector_norm, abs(relative[3]))
    if not 0.0 <= angle <= math.pi:
        raise ArithmeticError(f"Quaternion distance escaped [0, pi]: {angle}")
    return angle


def euclidean_distance(
    left: Sequence[float],
    right: Sequence[float],
) -> float:
    if len(left) != len(right):
        raise ValueError("Distance vectors must have equal length")
    return math.sqrt(
        math.fsum((float(a) - float(b)) ** 2 for a, b in zip(left, right))
    )


def projected_half_extents_world(
    orientation: Sequence[float],
    local_half_extents: Sequence[float],
) -> Vector3:
    x, y, z, w = normalize_quaternion(orientation)
    hx, hy, hz = _finite_float_tuple(local_half_extents, 3, "half extents")
    matrix = (
        (
            1.0 - 2.0 * (y * y + z * z),
            2.0 * (x * y - z * w),
            2.0 * (x * z + y * w),
        ),
        (
            2.0 * (x * y + z * w),
            1.0 - 2.0 * (x * x + z * z),
            2.0 * (y * z - x * w),
        ),
        (
            2.0 * (x * z - y * w),
            2.0 * (y * z + x * w),
            1.0 - 2.0 * (x * x + y * y),
        ),
    )
    extents = (hx, hy, hz)
    projected = tuple(
        math.fsum(
            abs(matrix[row][column]) * extents[column]
            for column in range(3)
        )
        for row in range(3)
    )
    return projected[0], projected[1], projected[2]


def search_space() -> tuple[CandidateSpec, ...]:
    return tuple(
        CandidateSpec(layout, orientation, tool_offset, lift_offset)
        for layout in LAYOUTS
        for orientation in ORIENTATION_NAMES
        for tool_offset in VIRTUAL_TOOL_OFFSETS_Z_M
        for lift_offset in LIFT_OFFSETS_M
    )


def _candidate_identity(spec: CandidateSpec) -> JsonRecord:
    return {
        "candidate_id": spec.candidate_id,
        "layout": spec.layout.name,
        "orientation": spec.orientation_name,
        "virtual_tool_offset_z_m": spec.virtual_tool_offset_z_m,
        "lift_offset_m": spec.lift_offset_m,
    }


def _orientation(name: str) -> Quaternion:
    if name == "down_x_pi":
        euler = (math.pi, 0.0, 0.0)
    elif name == "down_y_pi":
        euler = (0.0, math.pi, 0.0)
    else:
        raise ValueError(f"Unknown orientation: {name}")
    return normalize_quaternion(pb.getQuaternionFromEuler(euler))


def make_waypoints(
    spec: CandidateSpec,
) -> tuple[Vector3, Vector3, tuple[WaypointTarget, ...]]:
    source_component_center = (
        spec.layout.source_xy[0],
        spec.layout.source_xy[1],
        SOURCE_PLATFORM_TOP_Z_M + COMPONENT_HALF_EXTENTS_M[2],
    )
    destination_component_center = (
        spec.layout.destination_xy[0],
        spec.layout.destination_xy[1],
        DESTINATION_FLOOR_TOP_Z_M + COMPONENT_HALF_EXTENTS_M[2],
    )
    source_tool = (
        source_component_center[0],
        source_component_center[1],
        source_component_center[2] + spec.virtual_tool_offset_z_m,
    )
    destination_tool = (
        destination_component_center[0],
        destination_component_center[1],
        destination_component_center[2] + spec.virtual_tool_offset_z_m,
    )
    source_high = (
        source_tool[0],
        source_tool[1],
        source_tool[2] + spec.lift_offset_m,
    )
    destination_high = (
        destination_tool[0],
        destination_tool[1],
        destination_tool[2] + spec.lift_offset_m,
    )
    sequence = (
        WaypointTarget("source_high", source_high),
        WaypointTarget("source_tool", source_tool),
        WaypointTarget("source_high_return", source_high),
        WaypointTarget("destination_high", destination_high),
        WaypointTarget("destination_tool", destination_tool),
        WaypointTarget("destination_high_return", destination_high),
    )
    return source_component_center, destination_component_center, sequence


def _regions_overlap_xy(layout: Layout) -> bool:
    overlap_x = abs(layout.source_xy[0] - layout.destination_xy[0]) < (
        SOURCE_PLATFORM_HALF_EXTENTS_M[0]
        + DESTINATION_OUTER_HALF_EXTENTS_M[0]
    )
    overlap_y = abs(layout.source_xy[1] - layout.destination_xy[1]) < (
        SOURCE_PLATFORM_HALF_EXTENTS_M[1]
        + DESTINATION_OUTER_HALF_EXTENTS_M[1]
    )
    return overlap_x and overlap_y


def load_robot(client_id: int, data_root: Path) -> RobotModel:
    pb.resetSimulation(physicsClientId=client_id)
    pb.setAdditionalSearchPath(str(data_root), physicsClientId=client_id)
    body_id = pb.loadURDF(
        "kuka_iiwa/model.urdf",
        basePosition=(0.0, 0.0, 0.0),
        baseOrientation=(0.0, 0.0, 0.0, 1.0),
        useFixedBase=True,
        physicsClientId=client_id,
    )
    controlled: list[int] = []
    metadata: list[JsonRecord] = []
    for joint_index in range(
        pb.getNumJoints(body_id, physicsClientId=client_id)
    ):
        info = pb.getJointInfo(
            body_id,
            joint_index,
            physicsClientId=client_id,
        )
        record = {
            "index": joint_index,
            "joint_name": info[1].decode("utf-8"),
            "joint_type": int(info[2]),
            "lower_limit_rad": float(info[8]),
            "upper_limit_rad": float(info[9]),
            "max_force": float(info[10]),
            "max_velocity": float(info[11]),
            "link_name": info[12].decode("utf-8"),
        }
        metadata.append(record)
        if info[2] == pb.JOINT_REVOLUTE:
            controlled.append(joint_index)
    if controlled != list(range(7)):
        raise RuntimeError(f"Unexpected controlled joints: {controlled}")
    lower = tuple(
        float(metadata[index]["lower_limit_rad"])
        for index in controlled
    )
    upper = tuple(
        float(metadata[index]["upper_limit_rad"])
        for index in controlled
    )
    ranges = tuple(high - low for low, high in zip(lower, upper))
    joint_names = tuple(
        str(metadata[index]["joint_name"])
        for index in controlled
    )
    ee_link = 6
    dynamics = pb.getDynamicsInfo(
        body_id,
        ee_link,
        physicsClientId=client_id,
    )
    inertial_position = _finite_float_tuple(
        dynamics[3],
        3,
        "EE local inertial position",
    )
    return RobotModel(
        body_id=body_id,
        controlled_joints=tuple(controlled),
        lower_limits=lower,
        upper_limits=upper,
        joint_ranges=ranges,
        joint_names=joint_names,
        joint_metadata=tuple(metadata),
        ee_link=ee_link,
        ee_local_inertial_position=(
            inertial_position[0],
            inertial_position[1],
            inertial_position[2],
        ),
        ee_local_inertial_orientation=normalize_quaternion(dynamics[4]),
    )


def set_joint_configuration(
    robot: RobotModel,
    values: Sequence[float],
    client_id: int,
) -> None:
    if len(values) != len(robot.controlled_joints):
        raise ValueError("Joint vector has the wrong cardinality")
    for joint, value in zip(robot.controlled_joints, values):
        pb.resetJointState(
            robot.body_id,
            joint,
            targetValue=float(value),
            targetVelocity=0.0,
            physicsClientId=client_id,
        )


def _link_frame_pose(
    robot: RobotModel,
    client_id: int,
) -> tuple[Vector3, Quaternion]:
    state = pb.getLinkState(
        robot.body_id,
        robot.ee_link,
        computeForwardKinematics=True,
        physicsClientId=client_id,
    )
    position_values = _finite_float_tuple(
        state[4],
        3,
        "link-frame position",
    )
    position = (
        position_values[0],
        position_values[1],
        position_values[2],
    )
    return position, normalize_quaternion(state[5])


def _plain_ik(
    robot: RobotModel,
    target: WaypointTarget,
    orientation: Quaternion,
    client_id: int,
) -> JointVector:
    solution = pb.calculateInverseKinematics(
        robot.body_id,
        robot.ee_link,
        targetPosition=target.position,
        targetOrientation=orientation,
        maxNumIterations=300,
        residualThreshold=1.0e-8,
        physicsClientId=client_id,
    )
    return [
        float(solution[index])
        for index in range(len(robot.controlled_joints))
    ]


def _seeded_nullspace_ik(
    robot: RobotModel,
    target: WaypointTarget,
    orientation: Quaternion,
    seed: Sequence[float],
    client_id: int,
) -> JointVector:
    solution = pb.calculateInverseKinematics(
        robot.body_id,
        robot.ee_link,
        targetPosition=target.position,
        targetOrientation=orientation,
        lowerLimits=robot.lower_limits,
        upperLimits=robot.upper_limits,
        jointRanges=robot.joint_ranges,
        restPoses=seed,
        maxNumIterations=300,
        residualThreshold=1.0e-8,
        physicsClientId=client_id,
    )
    return [
        float(solution[index])
        for index in range(len(robot.controlled_joints))
    ]


def joint_limit_violations(
    values: Sequence[float],
    robot: RobotModel,
) -> list[JsonRecord]:
    if len(values) != len(robot.controlled_joints):
        raise ValueError("Joint vector has the wrong cardinality")
    violations: list[JsonRecord] = []
    for offset, value in enumerate(values):
        numeric_value = float(value)
        if not math.isfinite(numeric_value):
            raise ValueError("Joint vector contains a non-finite value")
        lower = robot.lower_limits[offset]
        upper = robot.upper_limits[offset]
        if numeric_value < lower:
            excess = numeric_value - lower
            side = "lower"
        elif numeric_value > upper:
            excess = numeric_value - upper
            side = "upper"
        else:
            continue
        violations.append(
            {
                "joint_index": robot.controlled_joints[offset],
                "joint_name": robot.joint_names[offset],
                "value_rad": numeric_value,
                "lower_limit_rad": lower,
                "upper_limit_rad": upper,
                "limit_side": side,
                "signed_excess_rad": excess,
            }
        )
    return violations


def _joint_margin(
    values: Sequence[float],
    robot: RobotModel,
) -> float:
    if len(values) != len(robot.controlled_joints):
        raise ValueError("Joint vector has the wrong cardinality")
    return min(
        min(value - lower, upper - value)
        for value, lower, upper in zip(
            values,
            robot.lower_limits,
            robot.upper_limits,
        )
    )


def _waypoint_record(
    target: WaypointTarget,
    values: JointVector,
    target_orientation: Quaternion,
    robot: RobotModel,
    client_id: int,
    solver_mode: str,
) -> JsonRecord:
    set_joint_configuration(robot, values, client_id)
    actual_position, actual_orientation = _link_frame_pose(
        robot,
        client_id,
    )
    return {
        "name": target.name,
        "solver_mode": solver_mode,
        "target_position": list(target.position),
        "target_orientation": list(target_orientation),
        "joint_vector": list(values),
        "joint_margin_rad": _joint_margin(values, robot),
        "position_error_m": euclidean_distance(
            target.position,
            actual_position,
        ),
        "orientation_error_rad": quaternion_angular_distance(
            target_orientation,
            actual_orientation,
        ),
        "actual_link_frame_position": list(actual_position),
        "actual_link_frame_orientation": list(actual_orientation),
    }


def _failure_records(
    spec: CandidateSpec,
    sequence: Sequence[WaypointTarget],
    reached_waypoints: Sequence[JsonRecord],
    failed_waypoint: str,
    failure_stage: str,
    failure_reason: str,
    solver_mode: str,
    raw_joint_vector: Sequence[float] | None,
    violations: Sequence[JsonRecord],
    exception: BaseException | None = None,
) -> tuple[JsonRecord, JsonRecord]:
    raw = (
        None
        if raw_joint_vector is None
        else [float(value) for value in raw_joint_vector]
    )
    failure: JsonRecord = {
        "failure_stage": failure_stage,
        "failure_reason": failure_reason,
        "failed_waypoint": failed_waypoint,
        "solver_mode": solver_mode,
        "raw_joint_vector": raw,
        "violations": list(violations),
    }
    if exception is not None:
        failure["exception_type"] = type(exception).__name__
        failure["exception_message"] = str(exception)
    common = {
        **_candidate_identity(spec),
        "status": "rejected",
        "survives": False,
        "pareto_nondominated": False,
        "selection_policy_rank": None,
        **failure,
    }
    reached_names = {
        str(record["name"])
        for record in reached_waypoints
    }
    detail = {
        **common,
        "metrics_evaluated": False,
        "trajectory_evaluated": False,
        "transfer_clearance_evaluated": False,
        "release_evaluated": False,
        "reached_waypoints": list(reached_waypoints),
        "unreached_waypoints": [
            target.name
            for target in sequence
            if target.name not in reached_names
        ],
    }
    summary = {
        **common,
        "metrics_evaluated": False,
    }
    return summary, detail


def _transform_record(
    position: Sequence[float],
    orientation: Sequence[float],
) -> JsonRecord:
    return {
        "position": [float(value) for value in position],
        "orientation": list(normalize_quaternion(orientation)),
    }


def solve_candidate(
    spec: CandidateSpec,
    robot: RobotModel,
    client_id: int,
) -> tuple[JsonRecord, JsonRecord]:
    if _regions_overlap_xy(spec.layout):
        raise RuntimeError(
            f"Primitive regions overlap for layout {spec.layout.name}"
        )
    (
        source_component_center,
        destination_component_center,
        sequence,
    ) = make_waypoints(spec)
    target_orientation = _orientation(spec.orientation_name)
    zero_configuration = [0.0] * len(robot.controlled_joints)
    set_joint_configuration(robot, zero_configuration, client_id)
    first_target = sequence[0]
    try:
        first_values = _plain_ik(
            robot,
            first_target,
            target_orientation,
            client_id,
        )
    except Exception as exc:
        return _failure_records(
            spec,
            sequence,
            (),
            first_target.name,
            "first_waypoint_ik",
            "first_waypoint_ik_exception",
            "plain_ik_neutral_state",
            None,
            (),
            exc,
        )
    if not all(math.isfinite(value) for value in first_values):
        return _failure_records(
            spec,
            sequence,
            (),
            first_target.name,
            "first_waypoint_ik",
            "first_waypoint_nonfinite",
            "plain_ik_neutral_state",
            first_values,
            (),
        )
    violations = joint_limit_violations(first_values, robot)
    if violations:
        return _failure_records(
            spec,
            sequence,
            (),
            first_target.name,
            "first_waypoint_ik",
            "first_waypoint_out_of_limits",
            "plain_ik_neutral_state",
            first_values,
            violations,
        )

    waypoints = [
        _waypoint_record(
            first_target,
            first_values,
            target_orientation,
            robot,
            client_id,
            "plain_ik_neutral_state",
        )
    ]
    seed = list(first_values)
    for target in sequence[1:]:
        set_joint_configuration(robot, seed, client_id)
        try:
            values = _seeded_nullspace_ik(
                robot,
                target,
                target_orientation,
                seed,
                client_id,
            )
        except Exception as exc:
            return _failure_records(
                spec,
                sequence,
                waypoints,
                target.name,
                "waypoint_ik",
                "waypoint_ik_exception",
                "seeded_nullspace_ik_previous_waypoint",
                None,
                (),
                exc,
            )
        if not all(math.isfinite(value) for value in values):
            return _failure_records(
                spec,
                sequence,
                waypoints,
                target.name,
                "waypoint_ik",
                "waypoint_nonfinite",
                "seeded_nullspace_ik_previous_waypoint",
                values,
                (),
            )
        violations = joint_limit_violations(values, robot)
        if violations:
            return _failure_records(
                spec,
                sequence,
                waypoints,
                target.name,
                "waypoint_ik",
                "waypoint_out_of_limits",
                "seeded_nullspace_ik_previous_waypoint",
                values,
                violations,
            )
        record = _waypoint_record(
            target,
            values,
            target_orientation,
            robot,
            client_id,
            "seeded_nullspace_ik_previous_waypoint",
        )
        waypoints.append(record)
        seed = list(values)

    source_tool = next(
        record
        for record in waypoints
        if record["name"] == "source_tool"
    )
    inverse_position, inverse_orientation = pb.invertTransform(
        source_tool["actual_link_frame_position"],
        source_tool["actual_link_frame_orientation"],
    )
    (
        component_local_position,
        component_local_orientation_raw,
    ) = pb.multiplyTransforms(
        inverse_position,
        inverse_orientation,
        source_component_center,
        (0.0, 0.0, 0.0, 1.0),
    )
    component_local_orientation = normalize_quaternion(
        component_local_orientation_raw
    )

    legs: list[JsonRecord] = []
    transfer_minimum: JsonRecord | None = None
    max_leg_delta = 0.0
    branch_discontinuity = False
    for start, end in zip(waypoints, waypoints[1:]):
        delta = [
            float(end_value) - float(start_value)
            for start_value, end_value in zip(
                start["joint_vector"],
                end["joint_vector"],
            )
        ]
        responsible_offset = max(
            range(len(delta)),
            key=lambda index: abs(delta[index]),
        )
        leg_max_delta = abs(delta[responsible_offset])
        max_leg_delta = max(max_leg_delta, leg_max_delta)
        leg_discontinuity = any(
            abs(value) > BRANCH_DISCONTINUITY_RAD
            for value in delta
        )
        branch_discontinuity = (
            branch_discontinuity
            or leg_discontinuity
        )
        is_transfer = (
            start["name"] == "source_high_return"
            and end["name"] == "destination_high"
        )
        leg_minimum: JsonRecord | None = None
        if is_transfer:
            for sample_index in range(
                INTERPOLATION_SAMPLES_PER_LEG
            ):
                alpha = sample_index / (
                    INTERPOLATION_SAMPLES_PER_LEG - 1
                )
                sample_values = [
                    float(start_value) + alpha * change
                    for start_value, change in zip(
                        start["joint_vector"],
                        delta,
                    )
                ]
                set_joint_configuration(
                    robot,
                    sample_values,
                    client_id,
                )
                ee_position, ee_orientation = _link_frame_pose(
                    robot,
                    client_id,
                )
                (
                    component_position,
                    component_orientation_raw,
                ) = pb.multiplyTransforms(
                    ee_position,
                    ee_orientation,
                    component_local_position,
                    component_local_orientation,
                )
                component_orientation = normalize_quaternion(
                    component_orientation_raw
                )
                projected_extents = projected_half_extents_world(
                    component_orientation,
                    COMPONENT_HALF_EXTENTS_M,
                )
                component_bottom = (
                    float(component_position[2])
                    - projected_extents[2]
                )
                required_bottom = (
                    DESTINATION_RIM_TOP_Z_M
                    + TRANSFER_CLEARANCE_MARGIN_M
                )
                clearance = component_bottom - required_bottom
                attribution = {
                    "trajectory_leg": {
                        "from": start["name"],
                        "to": end["name"],
                    },
                    "sample_index": sample_index,
                    "sample_count": (
                        INTERPOLATION_SAMPLES_PER_LEG
                    ),
                    "sample_alpha": alpha,
                    "joint_vector": sample_values,
                    "ee_link_frame_pose": _transform_record(
                        ee_position,
                        ee_orientation,
                    ),
                    "carried_component_pose": _transform_record(
                        component_position,
                        component_orientation,
                    ),
                    "carried_component_projected_half_extents_m": list(
                        projected_extents
                    ),
                    "component_bottom_z_m": component_bottom,
                    "required_component_bottom_z_m": required_bottom,
                    "clearance_m": clearance,
                }
                if (
                    leg_minimum is None
                    or clearance < float(leg_minimum["clearance_m"])
                ):
                    leg_minimum = attribution
                if (
                    transfer_minimum is None
                    or clearance
                    < float(transfer_minimum["clearance_m"])
                ):
                    transfer_minimum = attribution
        legs.append(
            {
                "from": start["name"],
                "to": end["name"],
                "joint_delta_rad": delta,
                "max_abs_joint_delta_rad": leg_max_delta,
                "responsible_joint_index": (
                    robot.controlled_joints[responsible_offset]
                ),
                "responsible_joint_name": (
                    robot.joint_names[responsible_offset]
                ),
                "responsible_joint_signed_delta_rad": (
                    delta[responsible_offset]
                ),
                "branch_discontinuity": leg_discontinuity,
                "min_endpoint_joint_margin_rad": min(
                    float(start["joint_margin_rad"]),
                    float(end["joint_margin_rad"]),
                ),
                "transfer_clearance_evaluated": is_transfer,
                "transfer_minimum": leg_minimum,
            }
        )
    if transfer_minimum is None:
        raise RuntimeError(
            f"Transfer leg was not evaluated for {spec.candidate_id}"
        )

    destination_tool = next(
        record
        for record in waypoints
        if record["name"] == "destination_tool"
    )
    (
        release_position,
        release_orientation_raw,
    ) = pb.multiplyTransforms(
        destination_tool["actual_link_frame_position"],
        destination_tool["actual_link_frame_orientation"],
        component_local_position,
        component_local_orientation,
    )
    release_orientation = normalize_quaternion(
        release_orientation_raw
    )
    release_extents = projected_half_extents_world(
        release_orientation,
        COMPONENT_HALF_EXTENTS_M,
    )
    dx = (
        float(release_position[0])
        - destination_component_center[0]
    )
    dy = (
        float(release_position[1])
        - destination_component_center[1]
    )
    dz = (
        float(release_position[2])
        - destination_component_center[2]
    )
    usable_x = (
        DESTINATION_INTERIOR_HALF_EXTENTS_M[0]
        - release_extents[0]
        - DESTINATION_RESERVED_WALL_MARGIN_M
    )
    usable_y = (
        DESTINATION_INTERIOR_HALF_EXTENTS_M[1]
        - release_extents[1]
        - DESTINATION_RESERVED_WALL_MARGIN_M
    )
    fixture_geometry_valid = usable_x >= 0.0 and usable_y >= 0.0
    footprint_contained = (
        fixture_geometry_valid
        and abs(dx) <= usable_x
        and abs(dy) <= usable_y
    )

    min_margin = min(
        float(record["joint_margin_rad"])
        for record in waypoints
    )
    max_position_error = max(
        float(record["position_error_m"])
        for record in waypoints
    )
    max_orientation_error = max(
        float(record["orientation_error_rad"])
        for record in waypoints
    )
    release_center_error = euclidean_distance(
        release_position,
        destination_component_center,
    )
    rejection_reasons: list[str] = []
    if min_margin < MIN_JOINT_MARGIN_RAD:
        rejection_reasons.append("JOINT_MARGIN")
    if max_position_error > MAX_WAYPOINT_POSITION_ERROR_M:
        rejection_reasons.append("IK_POSITION_ERROR")
    if max_orientation_error > MAX_WAYPOINT_ORIENTATION_ERROR_RAD:
        rejection_reasons.append("IK_ORIENTATION_ERROR")
    if float(transfer_minimum["clearance_m"]) < 0.0:
        rejection_reasons.append("TRANSFER_CLEARANCE")
    if branch_discontinuity:
        rejection_reasons.append("BRANCH_DISCONTINUITY")
    if not fixture_geometry_valid:
        rejection_reasons.append("FIXTURE_GEOMETRY")
    if fixture_geometry_valid and not footprint_contained:
        rejection_reasons.append("RELEASE_FOOTPRINT")
    survives = not rejection_reasons
    status = "survivor" if survives else "rejected"

    metrics = {
        "min_waypoint_joint_margin_rad": min_margin,
        "min_transfer_clearance_m": float(
            transfer_minimum["clearance_m"]
        ),
        "max_leg_delta_rad": max_leg_delta,
        "max_waypoint_position_error_m": max_position_error,
        "max_waypoint_orientation_error_rad": (
            max_orientation_error
        ),
        "predicted_release_center_error_m": (
            release_center_error
        ),
        "release_footprint_contained": footprint_contained,
        "branch_discontinuity": branch_discontinuity,
    }
    common = {
        **_candidate_identity(spec),
        "status": status,
        "survives": survives,
        "metrics_evaluated": True,
        "failure_stage": None,
        "failure_reason": None,
        "rejection_reasons": rejection_reasons,
        "pareto_nondominated": False,
        "selection_policy_rank": None,
        **metrics,
    }
    detail = {
        **common,
        "source_xy": list(spec.layout.source_xy),
        "destination_xy": list(spec.layout.destination_xy),
        "target_orientation": list(target_orientation),
        "source_component_center": list(
            source_component_center
        ),
        "destination_component_center": list(
            destination_component_center
        ),
        "trajectory_evaluated": True,
        "transfer_clearance_evaluated": True,
        "release_evaluated": True,
        "waypoints": waypoints,
        "legs": legs,
        "virtual_component_local_transform": {
            **_transform_record(
                component_local_position,
                component_local_orientation,
            ),
            "frame_semantics": (
                "terminal URDF link-frame kinematic transform only; "
                "not createConstraint evidence"
            ),
        },
        "transfer_clearance_attribution": transfer_minimum,
        "predicted_release_pose": _transform_record(
            release_position,
            release_orientation,
        ),
        "predicted_release_projected_half_extents_m": list(
            release_extents
        ),
        "release_offset_m": {
            "x": dx,
            "y": dy,
            "z": dz,
        },
        "usable_center_half_extent_m": {
            "x": usable_x,
            "y": usable_y,
        },
        "fixture_geometry_valid": fixture_geometry_valid,
        "release_floor_relation": {
            "component_bottom_z_m": (
                float(release_position[2])
                - release_extents[2]
            ),
            "destination_floor_top_z_m": (
                DESTINATION_FLOOR_TOP_Z_M
            ),
            "bottom_minus_floor_top_m": (
                float(release_position[2])
                - release_extents[2]
                - DESTINATION_FLOOR_TOP_Z_M
            ),
            "screening_effect": (
                "measured_not_a_b1_rejection_criterion"
            ),
        },
    }
    return dict(common), detail


def dominates(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    objectives: Sequence[ParetoObjective] = PARETO_OBJECTIVES,
) -> bool:
    weakly_better = True
    strictly_better = False
    for objective in objectives:
        left_value = float(left[objective.field])
        right_value = float(right[objective.field])
        if objective.direction == "maximize":
            weakly_better = (
                weakly_better
                and left_value >= right_value
            )
            strictly_better = (
                strictly_better
                or left_value > right_value
            )
        else:
            weakly_better = (
                weakly_better
                and left_value <= right_value
            )
            strictly_better = (
                strictly_better
                or left_value < right_value
            )
    return weakly_better and strictly_better


def apply_decision_metadata(
    summaries: list[JsonRecord],
    details: list[JsonRecord],
) -> tuple[JsonRecord, JsonRecord]:
    detail_by_id = {
        str(detail["candidate_id"]): detail
        for detail in details
    }
    if set(detail_by_id) != {
        str(summary["candidate_id"])
        for summary in summaries
    }:
        raise ValueError(
            "Summary/detail candidate identities do not match"
        )
    survivors = [
        summary
        for summary in summaries
        if summary["survives"]
    ]
    frontier = [
        candidate
        for candidate in survivors
        if not any(
            dominates(other, candidate)
            for other in survivors
            if other is not candidate
        )
    ]
    frontier_ids = {
        str(candidate["candidate_id"])
        for candidate in frontier
    }
    for summary in summaries:
        candidate_id = str(summary["candidate_id"])
        nondominated = candidate_id in frontier_ids
        summary["pareto_nondominated"] = nondominated
        detail_by_id[candidate_id][
            "pareto_nondominated"
        ] = nondominated

    ranked = sorted(
        survivors,
        key=lambda item: (
            -float(item[
                "min_waypoint_joint_margin_rad"
            ]),
            -float(item[
                "min_transfer_clearance_m"
            ]),
            float(item["max_leg_delta_rad"]),
            float(item[
                "max_waypoint_position_error_m"
            ]),
            float(item[
                "predicted_release_center_error_m"
            ]),
            str(item["candidate_id"]),
        ),
    )
    for rank, summary in enumerate(ranked, start=1):
        candidate_id = str(summary["candidate_id"])
        summary["selection_policy_rank"] = rank
        detail_by_id[candidate_id][
            "selection_policy_rank"
        ] = rank

    pareto_record = {
        "record_type": "pareto_analysis",
        "population": "surviving_candidates",
        "objectives": [
            {
                "field": objective.field,
                "direction": objective.direction,
            }
            for objective in PARETO_OBJECTIVES
        ],
        "nondominated_candidate_ids": sorted(frontier_ids),
        "nondominated_count": len(frontier_ids),
    }
    policy_record = {
        "record_type": "selection_policy",
        "name": "b1_lexicographic_screening_policy_v1",
        "classification": "ENGINEERING_POLICY",
        "physical_superiority_claimed": False,
        "priority_order": [
            {
                "field": objective.field,
                "direction": objective.direction,
            }
            for objective in PARETO_OBJECTIVES
        ],
        "tie_breaker": {
            "field": "candidate_id",
            "direction": "ascending",
        },
        "ranked_candidate_ids": [
            str(candidate["candidate_id"])
            for candidate in ranked
        ],
    }
    return pareto_record, policy_record


def _search_space_record() -> JsonRecord:
    return {
        "record_type": "search_space",
        "candidate_count": len(search_space()),
        "layouts": [
            {
                "name": layout.name,
                "source_xy_m": list(layout.source_xy),
                "destination_xy_m": list(
                    layout.destination_xy
                ),
            }
            for layout in LAYOUTS
        ],
        "orientations": list(ORIENTATION_NAMES),
        "virtual_tool_offsets_z_m": list(
            VIRTUAL_TOOL_OFFSETS_Z_M
        ),
        "lift_offsets_m": list(LIFT_OFFSETS_M),
        "thresholds": {
            "min_joint_margin_rad": MIN_JOINT_MARGIN_RAD,
            "branch_discontinuity_rad": (
                BRANCH_DISCONTINUITY_RAD
            ),
            "max_waypoint_position_error_m": (
                MAX_WAYPOINT_POSITION_ERROR_M
            ),
            "max_waypoint_orientation_error_rad": (
                MAX_WAYPOINT_ORIENTATION_ERROR_RAD
            ),
            "interpolation_samples_per_leg": (
                INTERPOLATION_SAMPLES_PER_LEG
            ),
        },
        "geometry": {
            "component_half_extents_m": list(
                COMPONENT_HALF_EXTENTS_M
            ),
            "source_platform_half_extents_m": list(
                SOURCE_PLATFORM_HALF_EXTENTS_M
            ),
            "source_platform_center_z_m": (
                SOURCE_PLATFORM_CENTER_Z_M
            ),
            "source_platform_top_z_m": (
                SOURCE_PLATFORM_TOP_Z_M
            ),
            "destination_outer_half_extents_m": list(
                DESTINATION_OUTER_HALF_EXTENTS_M
            ),
            "destination_floor_center_z_m": (
                DESTINATION_FLOOR_CENTER_Z_M
            ),
            "destination_floor_top_z_m": (
                DESTINATION_FLOOR_TOP_Z_M
            ),
            "destination_interior_half_extents_m": list(
                DESTINATION_INTERIOR_HALF_EXTENTS_M
            ),
            "destination_rim_top_z_m": (
                DESTINATION_RIM_TOP_Z_M
            ),
            "destination_reserved_wall_margin_m": (
                DESTINATION_RESERVED_WALL_MARGIN_M
            ),
            "transfer_clearance_margin_m": (
                TRANSFER_CLEARANCE_MARGIN_M
            ),
        },
        "scope": (
            "static kinematic engineering screen; not dynamic execution, "
            "continuous collision proof, industrial safety validation, "
            "or grasp validation"
        ),
    }


def _robot_metadata_record(robot: RobotModel) -> JsonRecord:
    return {
        "record_type": "robot_metadata",
        "controlled_joints": list(robot.controlled_joints),
        "joint_metadata": list(robot.joint_metadata),
        "lower_limits_rad": list(robot.lower_limits),
        "upper_limits_rad": list(robot.upper_limits),
        "joint_ranges_rad": list(robot.joint_ranges),
        "ee_link": robot.ee_link,
        "ee_local_inertial_position": list(
            robot.ee_local_inertial_position
        ),
        "ee_local_inertial_orientation": list(
            robot.ee_local_inertial_orientation
        ),
        "world_base_mount_position": [0.0, 0.0, 0.0],
        "base_position_semantics": (
            "URDF base-link world mounting position"
        ),
    }


def _verify_runtime_environment(
) -> tuple[Path, JsonRecord]:
    if sys.version_info[:3] != EXPECTED_PYTHON_VERSION:
        raise RuntimeError(
            f"Unexpected Python version: {sys.version_info[:3]!r}; "
            f"expected {EXPECTED_PYTHON_VERSION!r}"
        )
    package_version = importlib.metadata.version("pybullet")
    if package_version != EXPECTED_PYBULLET_VERSION:
        raise RuntimeError(
            f"Unexpected PyBullet version: {package_version}"
        )
    binary_path = Path(pb.__file__).resolve()
    binary_sha256 = sha256_file(binary_path)
    if binary_sha256 != EXPECTED_PYBULLET_SHA256:
        raise RuntimeError(
            "Unexpected PyBullet binary SHA-256: "
            f"{binary_sha256}"
        )
    data_root = Path(pybullet_data.getDataPath()).resolve()
    kuka_root = data_root / "kuka_iiwa"
    urdf_path = kuka_root / "model.urdf"
    urdf_sha256 = sha256_file(urdf_path)
    if urdf_sha256 != EXPECTED_KUKA_URDF_SHA256:
        raise RuntimeError(
            f"Unexpected KUKA URDF SHA-256: {urdf_sha256}"
        )
    manifest_sha256 = directory_manifest_sha256(kuka_root)
    if manifest_sha256 != EXPECTED_KUKA_MANIFEST_SHA256:
        raise RuntimeError(
            "Unexpected KUKA asset manifest SHA-256: "
            f"{manifest_sha256}"
        )
    runtime = {
        "python_executable": sys.executable,
        "python_version": sys.version.replace("\n", " "),
        "platform": platform.platform(),
        "pybullet_package_version": package_version,
        "pybullet_api_version": pb.getAPIVersion(),
        "pybullet_binary": str(binary_path),
        "pybullet_binary_sha256": binary_sha256,
        "pybullet_data": str(data_root),
        "kuka_urdf": str(urdf_path),
        "kuka_urdf_sha256": urdf_sha256,
        "kuka_directory_manifest_sha256": manifest_sha256,
    }
    return data_root, runtime


def generate_evidence_records(
    probe_script: Path,
    historical_b1_script: Path,
    historical_b1_results: Path,
) -> list[JsonRecord]:
    root = repository_root()
    repository_state = verify_repository_identity(root)
    data_root, runtime = _verify_runtime_environment()
    for required_path in (
        probe_script,
        historical_b1_script,
        historical_b1_results,
    ):
        if not required_path.is_file():
            raise FileNotFoundError(
                "Required evidence input does not exist: "
                f"{required_path}"
            )
    provenance = {
        "record_type": "provenance",
        "evidence_schema": EVIDENCE_SCHEMA_NAME,
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "repository_root": str(root),
        **repository_state,
        "probe_script": str(probe_script.resolve()),
        "probe_script_sha256": sha256_file(probe_script),
        "generator_module": str(Path(__file__).resolve()),
        "generator_module_sha256": sha256_file(
            Path(__file__).resolve()
        ),
        "historical_b1_script": str(
            historical_b1_script.resolve()
        ),
        "historical_b1_script_sha256": sha256_file(
            historical_b1_script
        ),
        "historical_b1_results": str(
            historical_b1_results.resolve()
        ),
        "historical_b1_results_sha256": sha256_file(
            historical_b1_results
        ),
        **runtime,
    }
    records: list[JsonRecord] = [
        provenance,
        _search_space_record(),
    ]
    client_id = pb.connect(pb.DIRECT)
    if client_id < 0:
        raise RuntimeError("PyBullet DIRECT connection failed")
    try:
        robot = load_robot(client_id, data_root)
        summaries: list[JsonRecord] = []
        details: list[JsonRecord] = []
        for spec in search_space():
            summary, detail = solve_candidate(
                spec,
                robot,
                client_id,
            )
            summaries.append(summary)
            details.append(detail)
        pareto_record, policy_record = apply_decision_metadata(
            summaries,
            details,
        )
        down_x_survivors = sum(
            bool(record["survives"])
            and record["orientation"] == "down_x_pi"
            for record in summaries
        )
        down_y_protocol_rejections = sum(
            not bool(record["survives"])
            and record["orientation"] == "down_y_pi"
            and record["failure_reason"]
            == "first_waypoint_out_of_limits"
            for record in summaries
        )
        topology_matches = (
            len(summaries) == 32
            and len(details) == 32
            and down_x_survivors == 16
            and down_y_protocol_rejections == 16
        )
        records.extend(
            (
                _robot_metadata_record(robot),
                policy_record,
            )
        )
        for summary, detail in zip(summaries, details):
            records.append(
                {
                    "record_type": "candidate_summary",
                    **summary,
                }
            )
            records.append(
                {
                    "record_type": "candidate_detail",
                    **detail,
                }
            )
        records.extend(
            (
                pareto_record,
                {
                    "record_type": "runtime_summary",
                    "total_candidates": len(summaries),
                    "candidate_summary_count": len(summaries),
                    "candidate_detail_count": len(details),
                    "survivor_count": sum(
                        bool(record["survives"])
                        for record in summaries
                    ),
                    "down_x_survivor_count": (
                        down_x_survivors
                    ),
                    "down_y_protocol_rejection_count": (
                        down_y_protocol_rejections
                    ),
                    "expected_topology_matches": (
                        topology_matches
                    ),
                },
            )
        )
    finally:
        pb.disconnect(physicsClientId=client_id)

    ending_state = verify_repository_identity(root)
    diff_check = run_git(
        root,
        "diff",
        "--check",
        check=False,
    )
    records.append(
        {
            "record_type": "repository_integrity",
            **ending_state,
            "diff_check_exit_code": diff_check.returncode,
            "diff_check_stdout": diff_check.stdout,
            "diff_check_stderr": diff_check.stderr,
        }
    )
    return records


def write_evidence(
    records: Iterable[Mapping[str, Any]],
    output_path: Path,
) -> str:
    output_path = output_path.resolve()
    digest_path = Path(f"{output_path}.sha256")
    temporary_path = output_path.with_name(
        f"{output_path.name}.tmp"
    )
    for forbidden_existing in (
        output_path,
        digest_path,
        temporary_path,
    ):
        if forbidden_existing.exists():
            raise FileExistsError(
                "Refusing to overwrite B1.1 evidence: "
                f"{forbidden_existing}"
            )
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    try:
        with temporary_path.open(
            "x",
            encoding="utf-8",
            newline="\n",
        ) as handle:
            for record in records:
                handle.write(
                    json.dumps(
                        dict(record),
                        sort_keys=True,
                        allow_nan=False,
                        separators=(",", ":"),
                    )
                )
                handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary_path.rename(output_path)
        evidence_sha256 = sha256_file(output_path)
        with digest_path.open(
            "x",
            encoding="ascii",
            newline="\n",
        ) as digest_handle:
            digest_handle.write(
                f"{evidence_sha256}  {output_path.name}\n"
            )
            digest_handle.flush()
            os.fsync(digest_handle.fileno())
    except BaseException:
        if temporary_path.exists():
            temporary_path.unlink()
        raise
    return evidence_sha256


def evidence_record_counts(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        record_type = str(
            record.get("record_type", "<missing>")
        )
        counts[record_type] = (
            counts.get(record_type, 0) + 1
        )
    return counts
