"""B3.1 collision-detector and frozen-scene foundation qualification.

This gate characterises the pinned PyBullet closest-point kernel, reconstructs
the frozen B1 scene geometry, verifies KUKA collision topology, and validates
component/contact-policy primitives.  It deliberately does not evaluate the
frozen B2 route or claim continuous collision freedom.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import re
import subprocess
import tempfile
from typing import Any, NoReturn, Sequence
import xml.etree.ElementTree as ET

import pybullet as pb
import pybullet_data


SCHEMA_IDENTIFIER = "prototype5.scene_collision_qualification.b3_1"
SCHEMA_VERSION = "1.0.0"
GATE_IDENTIFIER = "B3_1_COLLISION_DETECTOR_AND_FROZEN_SCENE_QUALIFICATION"
PASS_RESULT = "B3_1_PASS_DETECTOR_FOUNDATION"

STARTING_HEAD = "f0967b746afa2e027b4fe7eb524138473cb6db8b"
B1_2_ARTIFACT_SHA256 = (
    "b852fcdba89a89e0a83abc83c80cdf6eceb6b5a33babaf0558fce6d479b80f2c"
)
B2_ARTIFACT_SHA256 = (
    "a5a468145aea5aa21a649cccd1de3d6d2f8f15349d4b326db9380a6ad1256554"
)
B1_2_ARTIFACT = Path(
    "results/prototype5/scene_calibration/phase_b1_2_results.jsonl"
)
B2_ARTIFACT = Path(
    "results/prototype5/scene_calibration/phase_b2_kinematic_plan.json"
)
SELECTED_CANDIDATE_ID = "b1_1-C-down_x_pi-tcp_0p080-lift_0p140"

PYBULLET_PACKAGE_VERSION = "3.2.7"
PYBULLET_API_VERSION = 202010061
PYBULLET_BINARY_SHA256 = (
    "e8a99694353e508f9e934a57494c177ddb9317cde94781da8bb68670c2334e40"
)
KUKA_URDF_RELATIVE = Path("kuka_iiwa/model.urdf")
KUKA_URDF_SHA256 = "5c13c5b4bb88b5265223e0ec9a7706cbf81e9bb21cc0e18534273755a041788c"
KUKA_ASSET_MANIFEST_SHA256 = (
    "cee6f5a30f860c1302cb7ef69f0da2c0736a283fe87b87504f0141438c544fb3"
)

BASE_POSITION = (0.0, 0.0, 0.0)
BASE_ORIENTATION = (0.0, 0.0, 0.0, 1.0)
ROBOT_LINK_INDICES = (-1, 0, 1, 2, 3, 4, 5, 6)
EE_LINK_INDEX = 6
SELF_COLLISION_FLAGS = (
    pb.URDF_USE_SELF_COLLISION | pb.URDF_USE_SELF_COLLISION_EXCLUDE_PARENT
)

SOURCE_XY_M = (0.50, -0.20)
DESTINATION_XY_M = (0.50, 0.20)
COMPONENT_HALF_EXTENTS_M = (0.025, 0.025, 0.025)
SOURCE_PLATFORM_HALF_EXTENTS_M = (0.060, 0.060, 0.010)
SOURCE_PLATFORM_CENTER_M = (0.50, -0.20, 0.010)
DESTINATION_FLOOR_HALF_EXTENTS_M = (0.070, 0.070, 0.010)
DESTINATION_FLOOR_CENTER_M = (0.50, 0.20, 0.010)
DESTINATION_INTERIOR_HALF_EXTENTS_M = (0.050, 0.050)
DESTINATION_FLOOR_TOP_Z_M = 0.020
DESTINATION_RIM_TOP_Z_M = 0.040
SOURCE_COMPONENT_POSE = ((0.50, -0.20, 0.045), BASE_ORIENTATION)

CLOSEST_POINT_QUERY_HORIZON_M = 0.050
SYNTHETIC_SEPARATIONS_M = (
    1e-3,
    1e-4,
    1e-5,
    1e-6,
    0.0,
    -1e-6,
    -1e-5,
    -1e-4,
    -1e-3,
)
SYNTHETIC_REPEAT_COUNT = 10
SELF_COLLISION_PROBE_REPEAT_COUNT = 5
PREDECESSOR_POSITION_SCREEN_M = 0.010

_WINDOWS_ABSOLUTE_PATH = re.compile(r"(?i)\b[A-Z]:\\")
_FORBIDDEN_PATH_MARKERS = (
    "\\Users\\",
    "/Users/",
    "\\AppData\\",
    "/AppData/",
    "\\Temp\\",
    "/Temp/",
)

FROZEN_MANIFEST = {
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
    "src/prototype5/scene_calibration_b1_2.py": (
        "47ea195a07fc1255fb04d14a59f989b1122e24e29372c8148e612006dda769ea"
    ),
    "scripts/prototype5/run_scene_calibration_b1_2.py": (
        "70a933148c900c96087922ff7339d0f62ba24d066ae27706984b8358d1cf6028"
    ),
    "tests/prototype5/test_scene_calibration_b1_2.py": (
        "1176f6852b32d4780aef61a3367a996484fffcf255efd27aebf525c2fc898598"
    ),
    "results/prototype5/scene_calibration/phase_b1_2_results.jsonl": B1_2_ARTIFACT_SHA256,
    "results/prototype5/scene_calibration/phase_b1_2_results.jsonl.sha256": (
        "c81946e7e4f06bf51617d2e72ca84275e35abd2ee345f0dd993a1d8639b62781"
    ),
    "src/prototype5/scene_kinematic_plan_b2.py": (
        "e1355e070d2c4fd354a5c3657979857db11225ea87faa99a353449a13ef8d75a"
    ),
    "scripts/prototype5/run_scene_kinematic_plan_b2.py": (
        "5ef8ee06337f8b77a42afee8900f2f4e02641f2d1dabe8fa1b96b6314c531b41"
    ),
    "tests/prototype5/test_scene_kinematic_plan_b2.py": (
        "e1c4d3ae5dfcd1a026a70098ad38388c85a864c4dfec0122e026b5a4c14016cc"
    ),
    "results/prototype5/scene_calibration/phase_b2_kinematic_plan.json": (
        B2_ARTIFACT_SHA256
    ),
    "results/prototype5/scene_calibration/phase_b2_kinematic_plan.json.sha256": (
        "eec7218da6a2449ae9b1d836046f6cc97318e6f0c04da8bc2a5a57777c2b839c"
    ),
}

Vector3 = tuple[float, float, float]
Quaternion = tuple[float, float, float, float]
JsonObject = dict[str, object]


class B3QualificationError(RuntimeError):
    """Base class for fail-closed B3.1 failures."""


class FrozenEvidenceError(B3QualificationError):
    """A frozen predecessor or runtime identity has drifted."""


class NumericalInputError(B3QualificationError):
    """A malformed or non-finite numerical input was supplied."""


class DetectorQualificationError(B3QualificationError):
    """The pinned collision detector did not meet the B3.1 contract."""


class ComponentPhase(str, Enum):
    SOURCE_SUPPORTED = "SOURCE_SUPPORTED"
    ATTACHMENT_BOUNDARY = "ATTACHMENT_BOUNDARY"
    CARRIED = "CARRIED"
    RELEASE_BOUNDARY = "RELEASE_BOUNDARY"
    DESTINATION_SUPPORTED = "DESTINATION_SUPPORTED"


class SemanticGroup(str, Enum):
    COMPONENT = "COMPONENT"
    SOURCE_PLATFORM = "SOURCE_PLATFORM"
    DESTINATION_FLOOR = "DESTINATION_FLOOR"
    DESTINATION_WALL = "DESTINATION_WALL"
    ROBOT = "ROBOT"


class ContactPermission(str, Enum):
    FORBIDDEN = "FORBIDDEN"
    SUPPORT_CONTACT_PENDING_B3_2_NUMERIC_BAND = (
        "SUPPORT_CONTACT_PENDING_B3_2_NUMERIC_BAND"
    )


COMPONENT_ROBOT_CONTACT_POLICY = ContactPermission.FORBIDDEN


@dataclass(frozen=True)
class Pose:
    position: Vector3
    orientation: Quaternion


@dataclass(frozen=True)
class BoxDefinition:
    semantic_id: str
    group: SemanticGroup
    center_m: Vector3
    half_extents_m: Vector3

    @property
    def minimum_m(self) -> Vector3:
        return tuple(
            center - half for center, half in zip(self.center_m, self.half_extents_m)
        )  # type: ignore[return-value]

    @property
    def maximum_m(self) -> Vector3:
        return tuple(
            center + half for center, half in zip(self.center_m, self.half_extents_m)
        )  # type: ignore[return-value]


@dataclass(frozen=True, order=True)
class LinkPair:
    first: int
    second: int

    def __post_init__(self) -> None:
        if self.first >= self.second:
            raise NumericalInputError("LinkPair must be strictly ordered")


@dataclass(frozen=True)
class LinkInventory:
    index: int
    name: str
    parent_index: int | None
    parent_name: str | None
    collision_shapes: tuple[JsonObject, ...]
    collision_margin_m: float


@dataclass(frozen=True)
class PredecessorEvidence:
    virtual_component_local_pose: Pose
    source_component_pose: Pose
    predicted_release_pose: Pose
    predicted_release_floor_relation: JsonObject
    source_pick_link_pose: Pose
    destination_place_link_pose: Pose
    carried_endpoint_joint_vectors: tuple[tuple[str, tuple[float, ...]], ...]


@dataclass(frozen=True)
class ClosestPointResult:
    found: bool
    signed_distance_m: float | None
    separation_lower_bound_m: float | None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def directory_manifest_sha256(root: Path) -> str:
    if not root.is_dir():
        raise FrozenEvidenceError(f"Missing asset directory: {root}")
    digest = hashlib.sha256()
    files = sorted(path for path in root.rglob("*") if path.is_file())
    if not files:
        raise FrozenEvidenceError(f"Empty asset directory: {root}")
    for path in files:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, byteorder="big"))
        digest.update(relative)
        digest.update(bytes.fromhex(sha256_file(path)))
    return digest.hexdigest()


def _logical_artifact_path(
    path: Path,
    *,
    repository_root: Path,
    pybullet_data_root: Path,
) -> str:
    resolved = path.resolve()
    approved_roots = (
        ("pybullet_data", pybullet_data_root.resolve()),
        ("repository", repository_root.resolve()),
    )
    for label, root in approved_roots:
        try:
            relative = resolved.relative_to(root)
        except ValueError:
            continue
        suffix = "" if relative == Path(".") else relative.as_posix()
        return f"{label}/{suffix}"
    raise FrozenEvidenceError(
        "Evidence path is outside approved reproducible roots"
    )


def _python_environment_binary_identity(binary_path: Path) -> str:
    filename = binary_path.resolve().name
    if not filename:
        raise FrozenEvidenceError("PyBullet binary identity has no filename")
    return f"python_environment/{filename}"


def assert_portable_evidence(raw_text: str) -> None:
    if not isinstance(raw_text, str):
        raise FrozenEvidenceError("Raw evidence must be text")
    if _WINDOWS_ABSOLUTE_PATH.search(raw_text):
        raise FrozenEvidenceError(
            "Evidence contains a drive-qualified Windows path"
        )
    lowered = raw_text.casefold()
    for marker in _FORBIDDEN_PATH_MARKERS:
        if marker.casefold() in lowered:
            raise FrozenEvidenceError(
                f"Evidence contains machine-specific path marker: {marker!r}"
            )


def _finite_float(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise NumericalInputError(f"{field} must be numeric")
    converted = float(value)
    if not math.isfinite(converted):
        raise NumericalInputError(f"{field} must be finite")
    return converted


def _sequence(value: object, field: str, length: int) -> Sequence[object]:
    if not isinstance(value, (list, tuple)) or len(value) != length:
        raise NumericalInputError(f"{field} must contain {length} values")
    return value


def vector3(value: object, field: str) -> Vector3:
    values = _sequence(value, field, 3)
    return (
        _finite_float(values[0], f"{field}[0]"),
        _finite_float(values[1], f"{field}[1]"),
        _finite_float(values[2], f"{field}[2]"),
    )


def normalize_quaternion(
    value: Sequence[float] | None,
    field: str,
    *,
    norm_epsilon: float = 1e-12,
) -> Quaternion:
    if value is None:
        raise NumericalInputError(f"{field} must not be null")
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise NumericalInputError(f"{field} must be a numerical sequence")
    if len(value) != 4:
        raise NumericalInputError(
            f"{field} must contain exactly four components; got {len(value)}"
        )
    values = value
    converted = tuple(
        _finite_float(component, f"{field}[{index}]")
        for index, component in enumerate(values)
    )
    norm = math.sqrt(math.fsum(component * component for component in converted))
    epsilon = _finite_float(norm_epsilon, "quaternion norm epsilon")
    if epsilon <= 0.0:
        raise NumericalInputError("Quaternion norm epsilon must be positive")
    if not math.isfinite(norm) or norm <= epsilon:
        raise NumericalInputError(
            f"{field} norm is invalid or too small: {norm!r}"
        )
    return (
        converted[0] / norm,
        converted[1] / norm,
        converted[2] / norm,
        converted[3] / norm,
    )


def quaternion_angular_distance(
    left: Sequence[float] | None,
    right: Sequence[float] | None,
) -> float:
    q_left = normalize_quaternion(left, "left quaternion")
    q_right = normalize_quaternion(right, "right quaternion")
    dot = math.fsum(
        lhs * rhs for lhs, rhs in zip(q_left, q_right, strict=True)
    )
    dot = min(1.0, max(-1.0, abs(dot)))
    return 2.0 * math.acos(dot)


def position_distance(left: Vector3, right: Vector3) -> float:
    return math.sqrt(math.fsum((a - b) ** 2 for a, b in zip(left, right)))


def compose_pose_pybullet(parent: Pose, local: Pose) -> Pose:
    position, orientation = pb.multiplyTransforms(
        parent.position,
        parent.orientation,
        local.position,
        local.orientation,
    )
    return Pose(
        vector3(position, "composed position"),
        normalize_quaternion(orientation, "composed orientation"),
    )


def _reject_json_constant(token: str) -> NoReturn:
    raise FrozenEvidenceError(f"Non-finite JSON constant: {token}")


def _strict_json(path: Path) -> dict[str, Any]:
    value = json.loads(
        path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant
    )
    if not isinstance(value, dict):
        raise FrozenEvidenceError(f"Expected JSON object: {path}")
    return value


def _strict_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        value = json.loads(line, parse_constant=_reject_json_constant)
        if not isinstance(value, dict):
            raise FrozenEvidenceError(f"Record {line_number} is not an object")
        records.append(value)
    return records


def _pose_from_mapping(
    value: object,
    field: str,
    position_key: str = "position",
    orientation_key: str = "orientation",
) -> Pose:
    if not isinstance(value, dict):
        raise FrozenEvidenceError(f"{field} must be an object")
    return Pose(
        vector3(value.get(position_key), f"{field}.{position_key}"),
        normalize_quaternion(
            value.get(orientation_key), f"{field}.{orientation_key}"
        ),
    )


def verify_frozen_manifest(repository_root: Path) -> JsonObject:
    observed: JsonObject = {}
    for relative, expected in FROZEN_MANIFEST.items():
        path = repository_root / relative
        if not path.is_file():
            raise FrozenEvidenceError(f"Missing frozen file: {relative}")
        actual = sha256_file(path)
        if actual != expected:
            raise FrozenEvidenceError(
                f"Frozen predecessor drift: {relative}: {actual} != {expected}"
            )
        observed[relative] = actual
    for relative in (B1_2_ARTIFACT, B2_ARTIFACT):
        artifact = repository_root / relative
        digest_path = artifact.with_suffix(artifact.suffix + ".sha256")
        expected_content = f"{sha256_file(artifact)}  {artifact.name}\n"
        if digest_path.read_text(encoding="ascii") != expected_content:
            raise FrozenEvidenceError(f"Companion digest mismatch: {relative}")
    return observed


def load_predecessor_evidence(repository_root: Path) -> PredecessorEvidence:
    b1_records = _strict_jsonl(repository_root / B1_2_ARTIFACT)
    if len(b1_records) != 71:
        raise FrozenEvidenceError("B1.2 record count changed")
    details = [
        record
        for record in b1_records
        if record.get("record_type") == "candidate_detail"
        and record.get("candidate_id") == SELECTED_CANDIDATE_ID
    ]
    if len(details) != 1:
        raise FrozenEvidenceError("Selected B1.2 candidate is not unique")
    detail = details[0]
    expected_candidate = {
        "layout": "C",
        "orientation": "down_x_pi",
        "virtual_tool_offset_z_m": 0.08,
        "lift_offset_m": 0.14,
        "survives": True,
    }
    for key, expected in expected_candidate.items():
        if detail.get(key) != expected:
            raise FrozenEvidenceError(f"Selected candidate field changed: {key}")
    if tuple(detail.get("source_xy", ())) != SOURCE_XY_M:
        raise FrozenEvidenceError("Frozen source coordinates changed")
    if tuple(detail.get("destination_xy", ())) != DESTINATION_XY_M:
        raise FrozenEvidenceError("Frozen destination coordinates changed")
    local = _pose_from_mapping(
        detail.get("virtual_component_local_transform"),
        "virtual_component_local_transform",
    )
    source = Pose(
        vector3(detail.get("source_component_center"), "source_component_center"),
        BASE_ORIENTATION,
    )
    release = _pose_from_mapping(detail.get("predicted_release_pose"), "release")
    floor_relation = detail.get("release_floor_relation")
    if not isinstance(floor_relation, dict):
        raise FrozenEvidenceError("Missing B1.2 release-floor relation")

    b2 = _strict_json(repository_root / B2_ARTIFACT)
    if b2.get("schema_identifier") != "prototype5.scene_kinematic_plan.b2":
        raise FrozenEvidenceError("Unexpected B2 schema")
    ordered_plan = b2.get("ordered_plan")
    if not isinstance(ordered_plan, list) or len(ordered_plan) != 8:
        raise FrozenEvidenceError("Unexpected B2 route")
    by_name = {
        state.get("state"): state
        for state in ordered_plan
        if isinstance(state, dict) and state.get("state") != "HOME"
    }
    if set(by_name) != {
        "SOURCE_HIGH",
        "SOURCE_PICK",
        "SOURCE_HIGH_RETURN",
        "DESTINATION_HIGH",
        "DESTINATION_PLACE",
        "DESTINATION_HIGH_RETURN",
    }:
        raise FrozenEvidenceError("Unexpected B2 task states")

    def link_pose(state_name: str) -> Pose:
        replay = by_name[state_name].get("replay")
        if not isinstance(replay, dict):
            raise FrozenEvidenceError(f"Missing B2 replay: {state_name}")
        return _pose_from_mapping(
            replay.get("world_link_frame_pose"),
            f"{state_name}.world_link_frame_pose",
            orientation_key="quaternion_xyzw",
        )

    carried_state_names = (
        "SOURCE_PICK",
        "SOURCE_HIGH_RETURN",
        "DESTINATION_HIGH",
        "DESTINATION_PLACE",
    )
    carried_endpoint_joint_vectors: list[tuple[str, tuple[float, ...]]] = []
    for state_name in carried_state_names:
        raw_vector = by_name[state_name].get("joint_vector")
        values = _sequence(raw_vector, f"{state_name}.joint_vector", 7)
        vector = tuple(
            _finite_float(value, f"{state_name}.joint_vector[{index}]")
            for index, value in enumerate(values)
        )
        carried_endpoint_joint_vectors.append((state_name, vector))

    return PredecessorEvidence(
        virtual_component_local_pose=local,
        source_component_pose=source,
        predicted_release_pose=release,
        predicted_release_floor_relation=dict(floor_relation),
        source_pick_link_pose=link_pose("SOURCE_PICK"),
        destination_place_link_pose=link_pose("DESTINATION_PLACE"),
        carried_endpoint_joint_vectors=tuple(carried_endpoint_joint_vectors),
    )


def frozen_box_definitions() -> tuple[BoxDefinition, ...]:
    return (
        BoxDefinition(
            "source_platform",
            SemanticGroup.SOURCE_PLATFORM,
            SOURCE_PLATFORM_CENTER_M,
            SOURCE_PLATFORM_HALF_EXTENTS_M,
        ),
        BoxDefinition(
            "destination_floor",
            SemanticGroup.DESTINATION_FLOOR,
            DESTINATION_FLOOR_CENTER_M,
            DESTINATION_FLOOR_HALF_EXTENTS_M,
        ),
        BoxDefinition(
            "destination_wall_x_minus",
            SemanticGroup.DESTINATION_WALL,
            (0.44, 0.20, 0.030),
            (0.010, 0.070, 0.010),
        ),
        BoxDefinition(
            "destination_wall_x_plus",
            SemanticGroup.DESTINATION_WALL,
            (0.56, 0.20, 0.030),
            (0.010, 0.070, 0.010),
        ),
        BoxDefinition(
            "destination_wall_y_minus",
            SemanticGroup.DESTINATION_WALL,
            (0.50, 0.14, 0.030),
            (0.050, 0.010, 0.010),
        ),
        BoxDefinition(
            "destination_wall_y_plus",
            SemanticGroup.DESTINATION_WALL,
            (0.50, 0.26, 0.030),
            (0.050, 0.010, 0.010),
        ),
        BoxDefinition(
            "blue_component",
            SemanticGroup.COMPONENT,
            SOURCE_COMPONENT_POSE[0],
            COMPONENT_HALF_EXTENTS_M,
        ),
    )


def validate_frozen_box_definitions(
    definitions: tuple[BoxDefinition, ...],
) -> None:
    expected = {
        "source_platform": ((0.44, -0.26, 0.0), (0.56, -0.14, 0.02)),
        "destination_floor": ((0.43, 0.13, 0.0), (0.57, 0.27, 0.02)),
        "destination_wall_x_minus": ((0.43, 0.13, 0.02), (0.45, 0.27, 0.04)),
        "destination_wall_x_plus": ((0.55, 0.13, 0.02), (0.57, 0.27, 0.04)),
        "destination_wall_y_minus": ((0.45, 0.13, 0.02), (0.55, 0.15, 0.04)),
        "destination_wall_y_plus": ((0.45, 0.25, 0.02), (0.55, 0.27, 0.04)),
        "blue_component": ((0.475, -0.225, 0.02), (0.525, -0.175, 0.07)),
    }
    if len(definitions) != 7 or len({item.semantic_id for item in definitions}) != 7:
        raise FrozenEvidenceError("Frozen scene must contain seven unique boxes")
    for definition in definitions:
        if not all(value > 0.0 for value in definition.half_extents_m):
            raise NumericalInputError(f"Invalid half extents: {definition.semantic_id}")
        if definition.semantic_id not in expected:
            raise FrozenEvidenceError(f"Unexpected scene body: {definition.semantic_id}")
        expected_minimum, expected_maximum = expected[definition.semantic_id]
        if any(
            not math.isclose(actual, expected_value, rel_tol=0.0, abs_tol=1e-15)
            for actual, expected_value in zip(definition.minimum_m, expected_minimum)
        ):
            raise FrozenEvidenceError(f"Minimum bounds changed: {definition.semantic_id}")
        if any(
            not math.isclose(actual, expected_value, rel_tol=0.0, abs_tol=1e-15)
            for actual, expected_value in zip(definition.maximum_m, expected_maximum)
        ):
            raise FrozenEvidenceError(f"Maximum bounds changed: {definition.semantic_id}")


def contact_permission(
    first: SemanticGroup,
    second: SemanticGroup,
    phase: ComponentPhase,
) -> ContactPermission:
    pair = frozenset((first, second))
    source_support = frozenset(
        (SemanticGroup.COMPONENT, SemanticGroup.SOURCE_PLATFORM)
    )
    destination_support = frozenset(
        (SemanticGroup.COMPONENT, SemanticGroup.DESTINATION_FLOOR)
    )
    component_robot = frozenset(
        (SemanticGroup.COMPONENT, SemanticGroup.ROBOT)
    )
    if pair == component_robot:
        return COMPONENT_ROBOT_CONTACT_POLICY
    if pair == source_support and phase in {
        ComponentPhase.SOURCE_SUPPORTED,
        ComponentPhase.ATTACHMENT_BOUNDARY,
    }:
        return ContactPermission.SUPPORT_CONTACT_PENDING_B3_2_NUMERIC_BAND
    if pair == destination_support and phase in {
        ComponentPhase.RELEASE_BOUNDARY,
        ComponentPhase.DESTINATION_SUPPORTED,
    }:
        return ContactPermission.SUPPORT_CONTACT_PENDING_B3_2_NUMERIC_BAND
    return ContactPermission.FORBIDDEN


def analytical_axis_aligned_x_separation(
    center_a_x: float,
    half_extent_a_x: float,
    center_b_x: float,
    half_extent_b_x: float,
) -> float:
    values = (
        _finite_float(center_a_x, "center_a_x"),
        _finite_float(half_extent_a_x, "half_extent_a_x"),
        _finite_float(center_b_x, "center_b_x"),
        _finite_float(half_extent_b_x, "half_extent_b_x"),
    )
    if values[1] <= 0.0 or values[3] <= 0.0:
        raise NumericalInputError("Half extents must be positive")
    return abs(values[2] - values[0]) - (values[1] + values[3])


def _validate_collision_identity(
    body_id: int | None,
    link_index: int | None,
    *,
    physics_client_id: int,
) -> None:
    if body_id is None or isinstance(body_id, bool) or not isinstance(body_id, int):
        raise DetectorQualificationError(
            "body_id must be a valid integer body identifier"
        )
    if (
        link_index is None
        or isinstance(link_index, bool)
        or not isinstance(link_index, int)
    ):
        raise DetectorQualificationError(
            "link_index must be a valid integer link identifier"
        )
    body_ids = {
        int(pb.getBodyUniqueId(index, physicsClientId=physics_client_id))
        for index in range(pb.getNumBodies(physicsClientId=physics_client_id))
    }
    if body_id not in body_ids:
        raise DetectorQualificationError(
            f"Unknown Bullet body identifier: {body_id}"
        )
    joint_count = int(
        pb.getNumJoints(body_id, physicsClientId=physics_client_id)
    )
    if joint_count == 0:
        if link_index != -1:
            raise DetectorQualificationError(
                f"Static/base-only body {body_id} permits only link -1; "
                f"received {link_index}"
            )
    elif link_index < -1 or link_index >= joint_count:
        raise DetectorQualificationError(
            f"Invalid link {link_index} for body {body_id}; "
            f"valid range is -1..{joint_count - 1}"
        )
    collision_shapes = pb.getCollisionShapeData(
        body_id,
        link_index,
        physicsClientId=physics_client_id,
    )
    if not collision_shapes:
        raise DetectorQualificationError(
            f"Body {body_id} link {link_index} has no collision geometry"
        )


def _validate_physics_client_id(client_id: int | None) -> int:
    if (
        client_id is None
        or isinstance(client_id, bool)
        or not isinstance(client_id, int)
        or client_id < 0
    ):
        raise DetectorQualificationError(
            "physics_client_id must be a non-negative integer"
        )
    try:
        info = pb.getConnectionInfo(physicsClientId=client_id)
    except pb.error as exc:
        raise DetectorQualificationError(
            f"Invalid Bullet physics client: {client_id}"
        ) from exc
    if not info or not bool(info.get("isConnected", 0)):
        raise DetectorQualificationError(
            f"Bullet physics client is not connected: {client_id}"
        )
    return client_id


def closest_point_query(
    body_a: int | None,
    body_b: int | None,
    client_id: int | None,
    *,
    link_a: int | None = -1,
    link_b: int | None = -1,
    horizon_m: float = CLOSEST_POINT_QUERY_HORIZON_M,
) -> ClosestPointResult:
    validated_client_id = _validate_physics_client_id(client_id)
    horizon = _finite_float(horizon_m, "horizon_m")
    if horizon <= 0.0:
        raise NumericalInputError("Closest-point horizon must be positive")
    _validate_collision_identity(
        body_a,
        link_a,
        physics_client_id=validated_client_id,
    )
    _validate_collision_identity(
        body_b,
        link_b,
        physics_client_id=validated_client_id,
    )
    assert body_a is not None and body_b is not None
    assert link_a is not None and link_b is not None
    points = pb.getClosestPoints(
        bodyA=body_a,
        bodyB=body_b,
        distance=horizon,
        linkIndexA=link_a,
        linkIndexB=link_b,
        physicsClientId=validated_client_id,
    )
    if not points:
        return ClosestPointResult(False, None, horizon)
    distances = tuple(_finite_float(point[8], "contactDistance") for point in points)
    return ClosestPointResult(True, min(distances), None)


def _create_static_box(
    definition: BoxDefinition,
    client_id: int,
) -> int:
    shape = pb.createCollisionShape(
        pb.GEOM_BOX,
        halfExtents=definition.half_extents_m,
        physicsClientId=client_id,
    )
    if shape < 0:
        raise DetectorQualificationError(
            f"Failed to create collision shape: {definition.semantic_id}"
        )
    body = pb.createMultiBody(
        baseMass=0.0,
        baseCollisionShapeIndex=shape,
        basePosition=definition.center_m,
        baseOrientation=BASE_ORIENTATION,
        physicsClientId=client_id,
    )
    if body < 0:
        raise DetectorQualificationError(
            f"Failed to create collision body: {definition.semantic_id}"
        )
    return body


def _collision_shape_json(
    shape: Sequence[object],
    *,
    repository_root: Path | None = None,
    pybullet_data_root: Path | None = None,
) -> JsonObject:
    resolved_repository_root = (
        Path(__file__).resolve().parents[2]
        if repository_root is None
        else repository_root.resolve()
    )
    resolved_data_root = (
        Path(pybullet_data.getDataPath()).resolve()
        if pybullet_data_root is None
        else pybullet_data_root.resolve()
    )
    filename = shape[4]
    if isinstance(filename, bytes):
        filename_value = filename.decode("utf-8")
    else:
        filename_value = str(filename)
    file_path = Path(filename_value) if filename_value else None
    file_identity = (
        None
        if file_path is None
        else _logical_artifact_path(
            file_path,
            repository_root=resolved_repository_root,
            pybullet_data_root=resolved_data_root,
        )
    )
    file_sha256 = (
        None
        if file_path is None
        else sha256_file(file_path.resolve())
    )
    dimensions = tuple(float(value) for value in shape[3])
    if not all(math.isfinite(value) for value in dimensions):
        raise NumericalInputError("Collision shape dimensions must be finite")
    return {
        "object_unique_id": int(shape[0]),
        "link_index": int(shape[1]),
        "geometry_type": int(shape[2]),
        "dimensions": list(dimensions),
        "file_backed": file_path is not None,
        "file_identity": file_identity,
        "file_sha256": file_sha256,
        "local_frame_position": list(vector3(shape[5], "collision frame position")),
        "local_frame_orientation": list(
            normalize_quaternion(shape[6], "collision frame orientation")
        ),
    }


def _collision_margin(body: int, link: int, client_id: int) -> float:
    dynamics = pb.getDynamicsInfo(body, link, physicsClientId=client_id)
    if len(dynamics) <= 11:
        raise DetectorQualificationError("PyBullet did not expose collision margin")
    return _finite_float(dynamics[11], "collision margin")


def load_kuka(client_id: int, data_root: Path, flags: int) -> int:
    pb.setAdditionalSearchPath(str(data_root), physicsClientId=client_id)
    body = pb.loadURDF(
        KUKA_URDF_RELATIVE.as_posix(),
        basePosition=BASE_POSITION,
        baseOrientation=BASE_ORIENTATION,
        useFixedBase=True,
        flags=flags,
        physicsClientId=client_id,
    )
    if body < 0:
        raise DetectorQualificationError("Failed to load frozen KUKA URDF")
    if pb.getNumJoints(body, physicsClientId=client_id) != 7:
        raise DetectorQualificationError("KUKA joint count changed")
    return body


def kuka_link_inventory(
    body: int,
    client_id: int,
) -> tuple[LinkInventory, ...]:
    body_info = pb.getBodyInfo(body, physicsClientId=client_id)
    base_name = body_info[0].decode("utf-8")
    names = {-1: base_name}
    parents: dict[int, int | None] = {-1: None}
    for index in range(7):
        info = pb.getJointInfo(body, index, physicsClientId=client_id)
        names[index] = info[12].decode("utf-8")
        parents[index] = int(info[16])
    inventory: list[LinkInventory] = []
    for index in ROBOT_LINK_INDICES:
        shapes = pb.getCollisionShapeData(body, index, physicsClientId=client_id)
        if len(shapes) != 1:
            raise DetectorQualificationError(
                f"Expected one collision shape for KUKA link {index}; found {len(shapes)}"
            )
        parent = parents[index]
        inventory.append(
            LinkInventory(
                index=index,
                name=names[index],
                parent_index=parent,
                parent_name=None if parent is None else names[parent],
                collision_shapes=tuple(_collision_shape_json(shape) for shape in shapes),
                collision_margin_m=_collision_margin(body, index, client_id),
            )
        )
    if tuple(item.index for item in inventory) != ROBOT_LINK_INDICES:
        raise DetectorQualificationError("KUKA collision-body inventory changed")
    return tuple(inventory)


def derive_self_collision_pairs(
    inventory: tuple[LinkInventory, ...],
) -> tuple[tuple[LinkPair, ...], tuple[LinkPair, ...], tuple[LinkPair, ...]]:
    indices = tuple(item.index for item in inventory)
    all_pairs = tuple(
        LinkPair(indices[first], indices[second])
        for first in range(len(indices))
        for second in range(first + 1, len(indices))
    )
    direct_pairs = tuple(
        sorted(
            LinkPair(min(item.index, item.parent_index), max(item.index, item.parent_index))
            for item in inventory
            if item.parent_index is not None
        )
    )
    direct_set = set(direct_pairs)
    nonadjacent = tuple(pair for pair in all_pairs if pair not in direct_set)
    if len(all_pairs) != 28 or len(direct_pairs) != 7 or len(nonadjacent) != 21:
        raise DetectorQualificationError(
            "KUKA topology did not derive 28 total, 7 direct, 21 non-adjacent pairs"
        )
    if len(set(nonadjacent)) != len(nonadjacent):
        raise DetectorQualificationError(
            "Duplicate KUKA self-collision pair detected"
        )
    return all_pairs, direct_pairs, nonadjacent


def verify_kuka_urdf_topology(
    inventory: tuple[LinkInventory, ...],
    urdf_path: Path,
) -> None:
    root = ET.parse(urdf_path).getroot()
    urdf_links = {element.attrib["name"] for element in root.findall("link")}
    runtime_links = {item.name for item in inventory}
    if runtime_links != urdf_links:
        raise DetectorQualificationError("Runtime and URDF KUKA link sets differ")
    runtime_edges = {
        (item.parent_name, item.name)
        for item in inventory
        if item.parent_name is not None
    }
    urdf_edges = {
        (
            joint.find("parent").attrib["link"],
            joint.find("child").attrib["link"],
        )
        for joint in root.findall("joint")
    }
    if runtime_edges != urdf_edges:
        raise DetectorQualificationError("Runtime and URDF KUKA parent topology differ")


def _link_inventory_json(item: LinkInventory) -> JsonObject:
    return {
        "link_index": item.index,
        "link_name": item.name,
        "parent_index": item.parent_index,
        "parent_name": item.parent_name,
        "collision_shapes": list(item.collision_shapes),
        "collision_margin_m": item.collision_margin_m,
    }


def _pair_json(pair: LinkPair, names: dict[int, str]) -> JsonObject:
    return {
        "first_link_index": pair.first,
        "first_link_name": names[pair.first],
        "second_link_index": pair.second,
        "second_link_name": names[pair.second],
    }


def reconstruct_frozen_scene(data_root: Path | None = None) -> JsonObject:
    definitions = frozen_box_definitions()
    validate_frozen_box_definitions(definitions)
    resolved_data_root = (
        Path(pybullet_data.getDataPath()).resolve()
        if data_root is None
        else data_root.resolve()
    )
    client_id = pb.connect(pb.DIRECT)
    if client_id < 0:
        raise DetectorQualificationError("PyBullet DIRECT connection failed")
    try:
        pb.resetSimulation(physicsClientId=client_id)
        robot = load_kuka(client_id, resolved_data_root, SELF_COLLISION_FLAGS)
        inventory = kuka_link_inventory(robot, client_id)
        verify_kuka_urdf_topology(
            inventory, resolved_data_root / KUKA_URDF_RELATIVE
        )
        bodies: list[JsonObject] = []
        for definition in definitions:
            body = _create_static_box(definition, client_id)
            shapes = pb.getCollisionShapeData(body, -1, physicsClientId=client_id)
            if len(shapes) != 1 or int(shapes[0][2]) != pb.GEOM_BOX:
                raise DetectorQualificationError(
                    f"Scene body is not one GEOM_BOX: {definition.semantic_id}"
                )
            bodies.append(
                {
                    "semantic_id": definition.semantic_id,
                    "semantic_group": definition.group.value,
                    "body_id": body,
                    "base_mass": 0.0,
                    "center_m": list(definition.center_m),
                    "half_extents_m": list(definition.half_extents_m),
                    "minimum_m": list(definition.minimum_m),
                    "maximum_m": list(definition.maximum_m),
                    "collision_shape": _collision_shape_json(shapes[0]),
                    "collision_margin_m": _collision_margin(body, -1, client_id),
                }
            )
        total_bodies = pb.getNumBodies(physicsClientId=client_id)
        if total_bodies != 8:
            raise DetectorQualificationError(
                f"Frozen B3.1 scene must contain robot plus seven boxes; found {total_bodies}"
            )
        all_pairs, direct_pairs, nonadjacent = derive_self_collision_pairs(inventory)
        names = {item.index: item.name for item in inventory}
        return {
            "direct_client": True,
            "physics_steps": 0,
            "global_plane_loaded": False,
            "body_count": total_bodies,
            "robot": {
                "body_id": robot,
                "load_flags": SELF_COLLISION_FLAGS,
                "use_fixed_base": True,
                "base_position": list(BASE_POSITION),
                "base_orientation": list(BASE_ORIENTATION),
                "collision_inventory": [
                    _link_inventory_json(item) for item in inventory
                ],
                "all_self_pairs": [_pair_json(pair, names) for pair in all_pairs],
                "direct_parent_pairs": [
                    _pair_json(pair, names) for pair in direct_pairs
                ],
                "queried_nonadjacent_pairs": [
                    _pair_json(pair, names) for pair in nonadjacent
                ],
            },
            "static_boxes": bodies,
            "fixture_representation": (
                "one floor box plus four non-overlapping rim-wall boxes; cavity unfilled"
            ),
        }
    finally:
        pb.disconnect(physicsClientId=client_id)


def _distance_observation(
    requested_separation_m: float,
    repetition: int,
) -> JsonObject:
    requested = _finite_float(requested_separation_m, "requested separation")
    client_id = pb.connect(pb.DIRECT)
    if client_id < 0:
        raise DetectorQualificationError("PyBullet DIRECT connection failed")
    try:
        pb.resetSimulation(physicsClientId=client_id)
        half_extents = (0.1, 0.1, 0.1)
        definition_a = BoxDefinition(
            "synthetic_box_a", SemanticGroup.SOURCE_PLATFORM, (0.0, 0.0, 0.0), half_extents
        )
        definition_b = BoxDefinition(
            "synthetic_box_b",
            SemanticGroup.DESTINATION_FLOOR,
            (0.2 + requested, 0.0, 0.0),
            half_extents,
        )
        body_a = _create_static_box(definition_a, client_id)
        body_b = _create_static_box(definition_b, client_id)
        analytical = analytical_axis_aligned_x_separation(
            definition_a.center_m[0],
            half_extents[0],
            definition_b.center_m[0],
            half_extents[0],
        )
        query = closest_point_query(body_a, body_b, client_id)
        if not query.found or query.signed_distance_m is None:
            raise DetectorQualificationError(
                f"Synthetic calibration point not found: {requested}"
            )
        error = query.signed_distance_m - analytical
        return {
            "repetition": repetition,
            "requested_signed_separation_m": requested,
            "analytical_signed_separation_m": analytical,
            "closest_point_found": True,
            "pybullet_contact_distance_m": query.signed_distance_m,
            "signed_error_m": error,
            "absolute_error_m": abs(error),
            "box_a_collision_margin_m": _collision_margin(body_a, -1, client_id),
            "box_b_collision_margin_m": _collision_margin(body_b, -1, client_id),
            "physics_steps": 0,
        }
    finally:
        pb.disconnect(physicsClientId=client_id)


def _no_result_horizon_control() -> JsonObject:
    requested = 0.051
    client_id = pb.connect(pb.DIRECT)
    if client_id < 0:
        raise DetectorQualificationError("PyBullet DIRECT connection failed")
    try:
        pb.resetSimulation(physicsClientId=client_id)
        half_extents = (0.1, 0.1, 0.1)
        body_a = _create_static_box(
            BoxDefinition(
                "horizon_a", SemanticGroup.SOURCE_PLATFORM, (0.0, 0.0, 0.0), half_extents
            ),
            client_id,
        )
        body_b = _create_static_box(
            BoxDefinition(
                "horizon_b",
                SemanticGroup.DESTINATION_FLOOR,
                (0.2 + requested, 0.0, 0.0),
                half_extents,
            ),
            client_id,
        )
        query = closest_point_query(body_a, body_b, client_id)
        if query.found or query.signed_distance_m is not None:
            raise DetectorQualificationError("Query-horizon control unexpectedly found a point")
        return {
            "analytical_signed_separation_m": requested,
            "query_horizon_m": CLOSEST_POINT_QUERY_HORIZON_M,
            "closest_point_found": False,
            "signed_distance_m": None,
            "separation_lower_bound_m": query.separation_lower_bound_m,
        }
    finally:
        pb.disconnect(physicsClientId=client_id)


def qualify_distance_kernel() -> JsonObject:
    observations = tuple(
        _distance_observation(separation, repetition)
        for repetition in range(SYNTHETIC_REPEAT_COUNT)
        for separation in SYNTHETIC_SEPARATIONS_M
    )
    for repetition in range(SYNTHETIC_REPEAT_COUNT):
        ordered = sorted(
            (
                record
                for record in observations
                if record["repetition"] == repetition
            ),
            key=lambda record: float(record["analytical_signed_separation_m"]),
        )
        distances = [float(record["pybullet_contact_distance_m"]) for record in ordered]
        if any(right < left for left, right in zip(distances, distances[1:])):
            raise DetectorQualificationError(
                f"Synthetic closest-point distances are non-monotonic: repetition {repetition}"
            )
    grouped: list[JsonObject] = []
    maximum_spread = 0.0
    for requested in SYNTHETIC_SEPARATIONS_M:
        values = [
            float(record["pybullet_contact_distance_m"])
            for record in observations
            if record["requested_signed_separation_m"] == requested
        ]
        spread = max(values) - min(values)
        maximum_spread = max(maximum_spread, spread)
        grouped.append(
            {
                "requested_signed_separation_m": requested,
                "minimum_observed_m": min(values),
                "maximum_observed_m": max(values),
                "spread_m": spread,
                "sample_count": len(values),
            }
        )
    maximum_error = max(float(record["absolute_error_m"]) for record in observations)
    margins = {
        float(record["box_a_collision_margin_m"]) for record in observations
    } | {float(record["box_b_collision_margin_m"]) for record in observations}
    if len(margins) != 1:
        raise DetectorQualificationError("Synthetic box margins were inconsistent")
    return {
        "query_primitive": "getClosestPoints",
        "query_semantics": {
            "positive": "separation",
            "negative": "penetration",
            "no_result": "separation exceeds bounded query horizon",
        },
        "query_horizon_m": CLOSEST_POINT_QUERY_HORIZON_M,
        "fresh_direct_session_per_observation": True,
        "repeat_count_per_requested_distance": SYNTHETIC_REPEAT_COUNT,
        "observations": list(observations),
        "repeatability_by_requested_distance": grouped,
        "maximum_absolute_analytical_error_m": maximum_error,
        "maximum_run_to_run_spread_m": maximum_spread,
        "observed_kernel_uncertainty_envelope_m": maximum_error + maximum_spread,
        "uncertainty_envelope_status": "PROPOSED_FOR_B3_2_REVIEW_NOT_CONTACT_EPSILON",
        "final_contact_epsilon_frozen": False,
        "synthetic_collision_margin_m": next(iter(margins)),
        "collision_margins_modified": False,
        "horizon_no_result_control": _no_result_horizon_control(),
    }


_SYNTHETIC_ARTICULATED_URDF = """<?xml version="1.0"?>
<robot name="b3_1_self_collision_probe">
  <link name="probe_base">
    <inertial><origin xyz="0 0 0"/><mass value="1"/><inertia ixx="0.01" ixy="0" ixz="0" iyy="0.01" iyz="0" izz="0.01"/></inertial>
    <collision><geometry><box size="0.2 0.2 0.2"/></geometry></collision>
  </link>
  <link name="probe_link_0">
    <inertial><origin xyz="0 0 0"/><mass value="1"/><inertia ixx="0.01" ixy="0" ixz="0" iyy="0.01" iyz="0" izz="0.01"/></inertial>
    <collision><geometry><box size="0.2 0.2 0.2"/></geometry></collision>
  </link>
  <link name="probe_link_1">
    <inertial><origin xyz="0 0 0"/><mass value="1"/><inertia ixx="0.01" ixy="0" ixz="0" iyy="0.01" iyz="0" izz="0.01"/></inertial>
    <collision><geometry><box size="0.1 0.1 0.1"/></geometry></collision>
  </link>
  <link name="probe_link_2">
    <inertial><origin xyz="0 0 0"/><mass value="1"/><inertia ixx="0.01" ixy="0" ixz="0" iyy="0.01" iyz="0" izz="0.01"/></inertial>
    <collision><geometry><box size="0.2 0.2 0.2"/></geometry></collision>
  </link>
  <joint name="probe_joint_0" type="revolute">
    <parent link="probe_base"/><child link="probe_link_0"/><origin xyz="0 0 0"/><axis xyz="0 0 1"/><limit lower="-3.14" upper="3.14" effort="1" velocity="1"/>
  </joint>
  <joint name="probe_joint_1" type="revolute">
    <parent link="probe_link_0"/><child link="probe_link_1"/><origin xyz="0.5 0 0"/><axis xyz="0 0 1"/><limit lower="-3.14" upper="3.14" effort="1" velocity="1"/>
  </joint>
  <joint name="probe_joint_2" type="revolute">
    <parent link="probe_link_1"/><child link="probe_link_2"/><origin xyz="-0.5 0 0"/><axis xyz="0 0 1"/><limit lower="-3.14" upper="3.14" effort="1" velocity="1"/>
  </joint>
</robot>
"""


def _contact_pair_set(body: int, client_id: int) -> tuple[LinkPair, ...]:
    pb.performCollisionDetection(physicsClientId=client_id)
    pairs: set[LinkPair] = set()
    for point in pb.getContactPoints(
        bodyA=body, bodyB=body, physicsClientId=client_id
    ):
        first = int(point[3])
        second = int(point[4])
        if first != second:
            pairs.add(LinkPair(min(first, second), max(first, second)))
    return tuple(sorted(pairs))


def _pair_query_json(body: int, pair: LinkPair, client_id: int) -> JsonObject:
    result = closest_point_query(
        body,
        body,
        client_id,
        link_a=pair.first,
        link_b=pair.second,
    )
    return {
        "pair": [pair.first, pair.second],
        "closest_point_found": result.found,
        "signed_distance_m": result.signed_distance_m,
        "separation_lower_bound_m": result.separation_lower_bound_m,
    }


def _synthetic_self_collision_observation(
    urdf_path: Path,
    variant: str,
    flags: int,
    repetition: int,
) -> JsonObject:
    client_id = pb.connect(pb.DIRECT)
    if client_id < 0:
        raise DetectorQualificationError("PyBullet DIRECT connection failed")
    try:
        pb.resetSimulation(physicsClientId=client_id)
        body = pb.loadURDF(
            str(urdf_path),
            useFixedBase=True,
            flags=flags,
            physicsClientId=client_id,
        )
        if body < 0:
            raise DetectorQualificationError("Synthetic articulated URDF failed to load")
        controls = (
            LinkPair(-1, 0),
            LinkPair(-1, 1),
            LinkPair(-1, 2),
            LinkPair(0, 2),
        )
        return {
            "variant": variant,
            "flags": flags,
            "repetition": repetition,
            "contact_pairs_after_perform_collision_detection": [
                [pair.first, pair.second]
                for pair in _contact_pair_set(body, client_id)
            ],
            "explicit_get_closest_points_controls": [
                _pair_query_json(body, pair, client_id) for pair in controls
            ],
            "physics_steps": 0,
        }
    finally:
        pb.disconnect(physicsClientId=client_id)


def _kuka_flag_observation(
    variant: str,
    flags: int,
    repetition: int,
) -> JsonObject:
    client_id = pb.connect(pb.DIRECT)
    if client_id < 0:
        raise DetectorQualificationError("PyBullet DIRECT connection failed")
    try:
        pb.resetSimulation(physicsClientId=client_id)
        body = load_kuka(
            client_id, Path(pybullet_data.getDataPath()).resolve(), flags
        )
        inventory = kuka_link_inventory(body, client_id)
        all_pairs, direct_pairs, non_adjacent_pairs = derive_self_collision_pairs(
            inventory
        )
        return {
            "variant": variant,
            "flags": flags,
            "repetition": repetition,
            "contact_pairs_after_perform_collision_detection": [
                [pair.first, pair.second]
                for pair in _contact_pair_set(body, client_id)
            ],
            "explicit_get_closest_points_all_28_pairs": [
                _pair_query_json(body, pair, client_id) for pair in all_pairs
            ],
            "direct_parent_pairs": [
                [pair.first, pair.second] for pair in direct_pairs
            ],
            "authoritative_non_adjacent_pairs": [
                [pair.first, pair.second] for pair in non_adjacent_pairs
            ],
            "physics_steps": 0,
        }
    finally:
        pb.disconnect(physicsClientId=client_id)


def _explicit_query_signature(observation: JsonObject) -> tuple[tuple[object, ...], ...]:
    controls = observation.get("explicit_get_closest_points_controls")
    if controls is None:
        controls = observation.get("explicit_get_closest_points_all_28_pairs")
    if not isinstance(controls, list):
        raise DetectorQualificationError("Missing explicit closest-point controls")
    signature: list[tuple[object, ...]] = []
    for control in controls:
        if not isinstance(control, dict):
            raise DetectorQualificationError("Malformed closest-point control")
        distance = control.get("signed_distance_m")
        rounded = (
            None
            if distance is None
            else round(_finite_float(distance, "distance"), 12)
        )
        pair = control.get("pair")
        if not isinstance(pair, list) or len(pair) != 2:
            raise DetectorQualificationError("Malformed pair identity")
        signature.append(
            (
                int(pair[0]),
                int(pair[1]),
                bool(control.get("closest_point_found")),
                rounded,
            )
        )
    return tuple(signature)


def qualify_self_collision_semantics() -> JsonObject:
    variants = (
        ("DEFAULT", 0),
        ("URDF_USE_SELF_COLLISION", pb.URDF_USE_SELF_COLLISION),
        (
            "URDF_USE_SELF_COLLISION_EXCLUDE_PARENT",
            pb.URDF_USE_SELF_COLLISION | pb.URDF_USE_SELF_COLLISION_EXCLUDE_PARENT,
        ),
        (
            "URDF_USE_SELF_COLLISION_EXCLUDE_ALL_PARENTS",
            pb.URDF_USE_SELF_COLLISION
            | pb.URDF_USE_SELF_COLLISION_EXCLUDE_ALL_PARENTS,
        ),
    )
    with tempfile.TemporaryDirectory(prefix="prototype5-b3-1-self-collision-") as raw:
        urdf_path = Path(raw) / "self_collision_probe.urdf"
        urdf_path.write_text(
            _SYNTHETIC_ARTICULATED_URDF, encoding="utf-8", newline="\n"
        )
        synthetic = [
            _synthetic_self_collision_observation(
                urdf_path, variant, flags, repetition
            )
            for variant, flags in variants
            for repetition in range(SELF_COLLISION_PROBE_REPEAT_COUNT)
        ]

    expected_contact_pairs = {
        "DEFAULT": (),
        "URDF_USE_SELF_COLLISION": ((-1, 2), (0, 2)),
        "URDF_USE_SELF_COLLISION_EXCLUDE_PARENT": ((-1, 2), (0, 2)),
        "URDF_USE_SELF_COLLISION_EXCLUDE_ALL_PARENTS": (),
    }
    for variant, expected in expected_contact_pairs.items():
        selected = [record for record in synthetic if record["variant"] == variant]
        observed = {
            tuple(
                tuple(int(value) for value in pair)
                for pair in record[
                    "contact_pairs_after_perform_collision_detection"
                ]
            )
            for record in selected
        }
        if observed != {expected}:
            raise DetectorQualificationError(
                f"Unexpected self-collision filter result for {variant}: {observed}"
            )
        signatures = {_explicit_query_signature(record) for record in selected}
        if len(signatures) != 1:
            raise DetectorQualificationError(
                f"Explicit synthetic queries were not repeatable: {variant}"
            )
    reference_signature = _explicit_query_signature(synthetic[0])
    if any(
        _explicit_query_signature(record) != reference_signature
        for record in synthetic
    ):
        raise DetectorQualificationError(
            "Explicit synthetic pair queries changed with self-collision flags"
        )
    control_map = {
        (int(record[0]), int(record[1])): (bool(record[2]), record[3])
        for record in reference_signature
    }
    if not control_map[(-1, 0)][0] or control_map[(-1, 1)][0]:
        raise DetectorQualificationError("Synthetic parent/separated controls failed")
    if not control_map[(-1, 2)][0] or not control_map[(0, 2)][0]:
        raise DetectorQualificationError("Synthetic non-adjacent positive control failed")

    kuka_variants = variants[:3]
    kuka = [
        _kuka_flag_observation(variant, flags, repetition)
        for variant, flags in kuka_variants
        for repetition in range(SELF_COLLISION_PROBE_REPEAT_COUNT)
    ]
    kuka_reference = _explicit_query_signature(kuka[0])
    if any(_explicit_query_signature(record) != kuka_reference for record in kuka):
        raise DetectorQualificationError(
            "Explicit KUKA pair queries changed with self-collision flags"
        )
    if any(
        record["contact_pairs_after_perform_collision_detection"] for record in kuka
    ):
        raise DetectorQualificationError(
            "Neutral KUKA unexpectedly produced contact-manifold self-collisions"
        )
    return {
        "synthetic_articulated_control": {
            "description": (
                "Four-body serial chain with direct-parent overlap, separated control, "
                "and two non-adjacent overlap controls"
            ),
            "repeat_count_per_flag_variant": SELF_COLLISION_PROBE_REPEAT_COUNT,
            "observations": synthetic,
            "expected_contact_pairs_by_flag": {
                key: [list(pair) for pair in value]
                for key, value in expected_contact_pairs.items()
            },
        },
        "kuka_neutral_state_probe": {
            "route_evaluated": False,
            "repeat_count_per_flag_variant": SELF_COLLISION_PROBE_REPEAT_COUNT,
            "observations": kuka,
        },
        "empirical_conclusions": {
            "contact_manifold_generation_respects_self_collision_flags": True,
            "explicit_pair_get_closest_points_ignores_self_collision_flags": True,
            "exclude_all_parents_adopted": False,
            "authoritative_b3_pair_policy": (
                "explicit getClosestPoints over derived non-adjacent pair inventory"
            ),
            "direct_parent_pairs_excluded_only": True,
        },
    }


def _pose_json(pose: Pose) -> JsonObject:
    return {
        "position_m": list(pose.position),
        "quaternion_xyzw": list(pose.orientation),
    }


def qualify_component_transform(predecessor: PredecessorEvidence) -> JsonObject:
    reconstructed_source = compose_pose_pybullet(
        predecessor.source_pick_link_pose,
        predecessor.virtual_component_local_pose,
    )
    source_position_residual = position_distance(
        reconstructed_source.position, predecessor.source_component_pose.position
    )
    source_orientation_residual = quaternion_angular_distance(
        reconstructed_source.orientation, predecessor.source_component_pose.orientation
    )
    if source_position_residual > PREDECESSOR_POSITION_SCREEN_M:
        raise DetectorQualificationError(
            "Frozen component attachment transform produces a source discontinuity"
        )
    reconstructed_release = compose_pose_pybullet(
        predecessor.destination_place_link_pose,
        predecessor.virtual_component_local_pose,
    )
    release_position_residual = position_distance(
        reconstructed_release.position, predecessor.predicted_release_pose.position
    )
    release_orientation_residual = quaternion_angular_distance(
        reconstructed_release.orientation,
        predecessor.predicted_release_pose.orientation,
    )
    if release_position_residual > 1e-12 or release_orientation_residual > 1e-12:
        raise DetectorQualificationError("Frozen predicted release pose did not replay")
    floor_relation = predecessor.predicted_release_floor_relation
    bottom_minus_floor = _finite_float(
        floor_relation.get("bottom_minus_floor_top_m"),
        "release floor relation",
    )
    return {
        "attachment_model": (
            "terminal URDF link-frame kinematic transform only; no gripper, "
            "createConstraint, or grasp-physics evidence"
        ),
        "component_robot_contact_permission": "FORBIDDEN_FOR_ALL_ROBOT_LINKS",
        "virtual_component_local_pose": _pose_json(
            predecessor.virtual_component_local_pose
        ),
        "source_supported_pose": _pose_json(predecessor.source_component_pose),
        "source_pick_reconstructed_attached_pose": _pose_json(reconstructed_source),
        "attachment_boundary_position_discontinuity_m": source_position_residual,
        "attachment_boundary_orientation_discontinuity_rad": source_orientation_residual,
        "attachment_reconstruction_screen_m": PREDECESSOR_POSITION_SCREEN_M,
        "predicted_release_pose_from_b1_2": _pose_json(
            predecessor.predicted_release_pose
        ),
        "destination_place_reconstructed_release_pose": _pose_json(
            reconstructed_release
        ),
        "release_reconstruction_position_residual_m": release_position_residual,
        "release_reconstruction_orientation_residual_rad": release_orientation_residual,
        "release_pose_snapped_to_nominal_destination": False,
        "post_release_pose_policy": "fixed_at_actual_predicted_release_pose",
        "predicted_release_floor_relation": dict(floor_relation),
        "bottom_minus_destination_floor_top_m": bottom_minus_floor,
        "floor_relation_rounded_to_zero": False,
        "route_collision_verdict_produced": False,
    }


def qualify_component_robot_endpoint_clearance(
    predecessor: PredecessorEvidence,
) -> JsonObject:
    client_id = pb.connect(pb.DIRECT)
    if client_id < 0:
        raise DetectorQualificationError("PyBullet DIRECT connection failed")
    try:
        pb.resetSimulation(physicsClientId=client_id)
        robot = load_kuka(
            client_id,
            Path(pybullet_data.getDataPath()).resolve(),
            SELF_COLLISION_FLAGS,
        )
        inventory = kuka_link_inventory(robot, client_id)
        component = _create_static_box(
            BoxDefinition(
                "blue_component_endpoint_policy_probe",
                SemanticGroup.COMPONENT,
                predecessor.source_component_pose.position,
                COMPONENT_HALF_EXTENTS_M,
            ),
            client_id,
        )
        endpoint_records: list[JsonObject] = []
        global_minimum: JsonObject | None = None
        for state_name, joint_vector in predecessor.carried_endpoint_joint_vectors:
            for joint_index, value in enumerate(joint_vector):
                pb.resetJointState(
                    robot,
                    joint_index,
                    value,
                    physicsClientId=client_id,
                )
            link_state = pb.getLinkState(
                robot,
                EE_LINK_INDEX,
                computeForwardKinematics=True,
                physicsClientId=client_id,
            )
            terminal_pose = Pose(
                vector3(link_state[4], f"{state_name}.terminal_position"),
                normalize_quaternion(
                    link_state[5], f"{state_name}.terminal_orientation"
                ),
            )
            component_pose = compose_pose_pybullet(
                terminal_pose,
                predecessor.virtual_component_local_pose,
            )
            pb.resetBasePositionAndOrientation(
                component,
                component_pose.position,
                component_pose.orientation,
                physicsClientId=client_id,
            )
            pair_records: list[JsonObject] = []
            for item in inventory:
                query = closest_point_query(
                    robot,
                    component,
                    client_id,
                    link_a=item.index,
                    link_b=-1,
                    horizon_m=1.0,
                )
                if not query.found or query.signed_distance_m is None:
                    raise DetectorQualificationError(
                        f"Component/robot endpoint query incomplete: "
                        f"{state_name} link {item.index}"
                    )
                record: JsonObject = {
                    "robot_link_index": item.index,
                    "robot_link_name": item.name,
                    "signed_distance_m": query.signed_distance_m,
                }
                pair_records.append(record)
                if global_minimum is None or query.signed_distance_m < float(
                    global_minimum["signed_distance_m"]
                ):
                    global_minimum = {
                        "state": state_name,
                        **record,
                    }
            terminal = next(
                record
                for record in pair_records
                if record["robot_link_index"] == EE_LINK_INDEX
            )
            minimum = min(
                pair_records,
                key=lambda record: float(record["signed_distance_m"]),
            )
            if float(minimum["signed_distance_m"]) <= 0.0:
                raise DetectorQualificationError(
                    f"Component/robot endpoint contact detected: {state_name}"
                )
            if float(terminal["signed_distance_m"]) <= 0.0:
                raise DetectorQualificationError(
                    f"Component/terminal-link endpoint contact detected: {state_name}"
                )
            endpoint_records.append(
                {
                    "state": state_name,
                    "component_pose": _pose_json(component_pose),
                    "pair_distances": pair_records,
                    "minimum_pair": minimum,
                    "terminal_link_6_signed_distance_m": terminal[
                        "signed_distance_m"
                    ],
                }
            )
        if global_minimum is None:
            raise DetectorQualificationError(
                "Missing component/robot endpoint evidence"
            )
        return {
            "contact_policy": COMPONENT_ROBOT_CONTACT_POLICY.value,
            "audited_endpoint_states": endpoint_records,
            "minimum_component_robot_distance": global_minimum,
            "all_endpoint_distances_positive": True,
            "route_interpolation_evaluated": False,
            "intermediate_route_clearance_claimed": False,
            "physics_steps": 0,
        }
    finally:
        pb.disconnect(physicsClientId=client_id)


def _policy_table() -> list[JsonObject]:
    rows: list[JsonObject] = []
    tested_pairs = (
        (SemanticGroup.COMPONENT, SemanticGroup.SOURCE_PLATFORM),
        (SemanticGroup.COMPONENT, SemanticGroup.DESTINATION_FLOOR),
        (SemanticGroup.COMPONENT, SemanticGroup.DESTINATION_WALL),
        (SemanticGroup.ROBOT, SemanticGroup.SOURCE_PLATFORM),
        (SemanticGroup.ROBOT, SemanticGroup.DESTINATION_FLOOR),
        (SemanticGroup.ROBOT, SemanticGroup.DESTINATION_WALL),
        (SemanticGroup.COMPONENT, SemanticGroup.ROBOT),
    )
    for phase in ComponentPhase:
        for first, second in tested_pairs:
            rows.append(
                {
                    "phase": phase.value,
                    "first_group": first.value,
                    "second_group": second.value,
                    "permission": contact_permission(first, second, phase).value,
                }
            )
    return rows


def qualify_contact_policy_controls() -> JsonObject:
    client_id = pb.connect(pb.DIRECT)
    if client_id < 0:
        raise DetectorQualificationError("PyBullet DIRECT connection failed")
    try:
        pb.resetSimulation(physicsClientId=client_id)
        source = _create_static_box(frozen_box_definitions()[0], client_id)
        component_definition = frozen_box_definitions()[-1]
        component = _create_static_box(component_definition, client_id)
        support_query = closest_point_query(source, component, client_id)
        if not support_query.found or support_query.signed_distance_m is None:
            raise DetectorQualificationError("Source support control was not detected")

        wall_definition = next(
            definition
            for definition in frozen_box_definitions()
            if definition.semantic_id == "destination_wall_x_plus"
        )
        wall = _create_static_box(wall_definition, client_id)
        pb.resetBasePositionAndOrientation(
            component,
            (0.55, 0.20, 0.045),
            BASE_ORIENTATION,
            physicsClientId=client_id,
        )
        wall_query = closest_point_query(component, wall, client_id)
        if (
            not wall_query.found
            or wall_query.signed_distance_m is None
            or wall_query.signed_distance_m >= 0.0
        ):
            raise DetectorQualificationError(
                "Intentional destination-wall penetration control failed"
            )
        if contact_permission(
            SemanticGroup.COMPONENT,
            SemanticGroup.SOURCE_PLATFORM,
            ComponentPhase.SOURCE_SUPPORTED,
        ) is ContactPermission.FORBIDDEN:
            raise DetectorQualificationError("Source support policy control failed")
        if contact_permission(
            SemanticGroup.COMPONENT,
            SemanticGroup.SOURCE_PLATFORM,
            ComponentPhase.CARRIED,
        ) is not ContactPermission.FORBIDDEN:
            raise DetectorQualificationError("Carried source-contact policy control failed")
        if any(
            contact_permission(
                SemanticGroup.COMPONENT,
                SemanticGroup.DESTINATION_WALL,
                phase,
            ) is not ContactPermission.FORBIDDEN
            for phase in ComponentPhase
        ):
            raise DetectorQualificationError("Destination-wall policy control failed")
        return {
            "policy_table": _policy_table(),
            "source_support_geometric_control": {
                "signed_distance_m": support_query.signed_distance_m,
                "source_supported_permission": contact_permission(
                    SemanticGroup.COMPONENT,
                    SemanticGroup.SOURCE_PLATFORM,
                    ComponentPhase.SOURCE_SUPPORTED,
                ).value,
                "carried_permission": contact_permission(
                    SemanticGroup.COMPONENT,
                    SemanticGroup.SOURCE_PLATFORM,
                    ComponentPhase.CARRIED,
                ).value,
            },
            "destination_wall_intentional_penetration_control": {
                "component_center_m": [0.55, 0.20, 0.045],
                "wall_semantic_id": wall_definition.semantic_id,
                "signed_distance_m": wall_query.signed_distance_m,
                "permission_all_phases": "FORBIDDEN",
            },
            "material_penetration_permitted_for_support_pairs": False,
            "final_numeric_contact_band_frozen": False,
            "physics_steps": 0,
        }
    finally:
        pb.disconnect(physicsClientId=client_id)


def _run_git(repository_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def _git_commit_is_ancestor(
    repository_root: Path,
    ancestor: str,
    descendant: str,
) -> bool:
    completed = subprocess.run(
        ("git", "merge-base", "--is-ancestor", ancestor, descendant),
        cwd=repository_root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode not in (0, 1):
        raise FrozenEvidenceError(
            "Unable to verify predecessor commit ancestry"
        )
    return completed.returncode == 0


def verify_repository_and_runtime(repository_root: Path) -> JsonObject:
    root = Path(_run_git(repository_root, "rev-parse", "--show-toplevel")).resolve()
    if root != repository_root.resolve():
        raise FrozenEvidenceError(f"Wrong repository root: {root}")
    head = _run_git(repository_root, "rev-parse", "HEAD")
    if not _git_commit_is_ancestor(
        repository_root,
        STARTING_HEAD,
        head,
    ):
        raise FrozenEvidenceError(
            f"Frozen predecessor {STARTING_HEAD} "
            f"is not an ancestor of HEAD {head}"
        )
    package_version = importlib.metadata.version("pybullet")
    api_version = int(pb.getAPIVersion())
    binary_path = Path(str(pb.__file__)).resolve()
    binary_sha = sha256_file(binary_path)
    data_root = Path(pybullet_data.getDataPath()).resolve()
    urdf_path = data_root / KUKA_URDF_RELATIVE
    asset_root = urdf_path.parent
    observed: JsonObject = {
        "package_version": package_version,
        "api_version": api_version,
        "binary_identity": _python_environment_binary_identity(binary_path),
        "binary_sha256": binary_sha,
        "urdf_identity": _logical_artifact_path(
            urdf_path,
            repository_root=repository_root,
            pybullet_data_root=data_root,
        ),
        "urdf_sha256": sha256_file(urdf_path),
        "kuka_asset_manifest_sha256": directory_manifest_sha256(asset_root),
    }
    expected = {
        "package_version": PYBULLET_PACKAGE_VERSION,
        "api_version": PYBULLET_API_VERSION,
        "binary_sha256": PYBULLET_BINARY_SHA256,
        "urdf_sha256": KUKA_URDF_SHA256,
        "kuka_asset_manifest_sha256": KUKA_ASSET_MANIFEST_SHA256,
    }
    for key, value in expected.items():
        if observed[key] != value:
            raise FrozenEvidenceError(
                f"Pinned PyBullet/KUKA identity changed: {key}: {observed[key]} != {value}"
            )
    return {
        "repository_root": "repository/",
        "predecessor_baseline_commit": STARTING_HEAD,
        "lineage_contract": "CURRENT_HEAD_DESCENDS_FROM_PREDECESSOR_BASELINE",
        "python": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
        },
        "pybullet": observed,
    }


def build_b3_1_artifact(repository_root: Path) -> JsonObject:
    repository_root = repository_root.resolve()
    runtime = verify_repository_and_runtime(repository_root)
    predecessor_hashes = verify_frozen_manifest(repository_root)
    predecessor = load_predecessor_evidence(repository_root)
    scene = reconstruct_frozen_scene()
    distance_kernel = qualify_distance_kernel()
    self_collision = qualify_self_collision_semantics()
    component = qualify_component_transform(predecessor)
    component_robot = qualify_component_robot_endpoint_clearance(predecessor)
    contact_policy = qualify_contact_policy_controls()
    source_path = Path(__file__).resolve()
    runner_path = (
        repository_root
        / "scripts/prototype5/run_scene_collision_qualification_b3_1.py"
    )
    test_path = (
        repository_root
        / "tests/prototype5/test_scene_collision_qualification_b3_1.py"
    )
    for path in (source_path, runner_path, test_path):
        if not path.is_file():
            raise FrozenEvidenceError(f"Missing B3.1 implementation file: {path}")
    return {
        "schema_identifier": SCHEMA_IDENTIFIER,
        "schema_version": SCHEMA_VERSION,
        "gate_identifier": GATE_IDENTIFIER,
        "result": PASS_RESULT,
        "provenance": {
            **runtime,
            "predecessor_artifact_sha256": {
                "b1_2": B1_2_ARTIFACT_SHA256,
                "b2": B2_ARTIFACT_SHA256,
            },
            "frozen_predecessor_manifest": predecessor_hashes,
            "source_sha256": sha256_file(source_path),
            "runner_sha256": sha256_file(runner_path),
            "tests_sha256": sha256_file(test_path),
        },
        "scope_contract": {
            "b2_route_collision_evaluated": False,
            "b2_route_collision_verdict": None,
            "route_interpolation_policy_frozen": False,
            "final_contact_epsilon_frozen": False,
            "collision_margins_modified": False,
            "physics_steps": 0,
            "global_plane_present": False,
        },
        "frozen_scene_reconstruction": scene,
        "collision_kernel_calibration": distance_kernel,
        "self_collision_semantics": self_collision,
        "component_transform_qualification": component,
        "component_robot_endpoint_clearance": component_robot,
        "contact_policy_foundation": contact_policy,
        "explicit_non_claims": [
            "The frozen B2 route has not been collision-qualified by B3.1.",
            "Continuous collision freedom has not been established.",
            "Dynamic executability and controller behaviour have not been established.",
            "The virtual component transform is not grasp-physics evidence.",
            "Placement accuracy has not been measured dynamically.",
            "No real-robot or industrial-safety claim is supported.",
        ],
        "pass_meaning": (
            "The pinned PyBullet collision-query kernel, frozen scene reconstruction, "
            "pair topology, and B3 contact-policy foundation were qualified sufficiently "
            "to proceed to a separately reviewed B3.2 frozen-route collision evaluation."
        ),
        "issues_before_b3_2": [
            "Independently review and freeze a numerical contact ambiguity band.",
            "Independently review and freeze the discrete route interpolation contract.",
            "Do not infer a continuous collision proof from discrete sampling.",
        ],
    }


def serialize_artifact(artifact: JsonObject) -> bytes:
    raw_text = (
        json.dumps(
            artifact,
            sort_keys=True,
            indent=2,
            allow_nan=False,
            ensure_ascii=False,
        )
        + "\n"
    )
    assert_portable_evidence(raw_text)
    return raw_text.encode("utf-8")


def write_artifact(artifact: JsonObject, output_path: Path) -> str:
    digest_path = output_path.with_suffix(output_path.suffix + ".sha256")
    if output_path.exists() or digest_path.exists():
        raise FileExistsError(
            f"Refusing to overwrite B3.1 evidence: {output_path} or {digest_path}"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = serialize_artifact(artifact)
    digest = hashlib.sha256(payload).hexdigest()
    with output_path.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        with digest_path.open("xb") as stream:
            stream.write(f"{digest}  {output_path.name}\n".encode("ascii"))
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        output_path.unlink(missing_ok=True)
        raise
    return digest


def verify_artifact_digest(output_path: Path) -> str:
    digest = sha256_file(output_path)
    expected = f"{digest}  {output_path.name}\n"
    digest_path = output_path.with_suffix(output_path.suffix + ".sha256")
    if digest_path.read_text(encoding="ascii") != expected:
        raise FrozenEvidenceError(f"B3.1 companion digest mismatch: {digest_path}")
    return digest
