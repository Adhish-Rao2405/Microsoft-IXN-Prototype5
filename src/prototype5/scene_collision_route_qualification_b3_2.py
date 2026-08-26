"""Deterministic discrete collision qualification for the frozen B2 route.

B3.2 is a static, zero-step PyBullet qualification gate.  It samples the
immutable B2 joint route, applies the frozen B3.1 collision-query semantics,
and preserves a complete scientific FAIL result instead of mutating inputs.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import subprocess
from typing import Any, NoReturn, Sequence

import pybullet as pb
import pybullet_data

from . import scene_collision_qualification_b3_1 as b31


SCHEMA_IDENTIFIER = "prototype5.scene_collision_route_qualification.b3_2"
SCHEMA_VERSION = "1.0.0"
GATE_IDENTIFIER = "B3_2_DISCRETE_ROUTE_COLLISION_QUALIFICATION"
PASS_RESULT = "B3_2_PASS_DISCRETE_ROUTE_QUALIFICATION"
FAIL_RESULT = "B3_2_FAIL_DISCRETE_ROUTE_QUALIFICATION"
MAXIMUM_PASS_CLAIM = (
    "No forbidden collision/contact was observed at any configuration sampled "
    "along the frozen B2 route under the declared deterministic discrete B3.2 "
    "protocol."
)
SCIENTIFIC_FAIL_CLAIM = (
    "Only the recorded discrete geometric failures under the frozen B3.2 protocol "
    "are established."
)
DISCRETE_SAMPLING_LIMITATION = (
    "Discrete sampling cannot prove the absence of collision between evaluated "
    "configurations."
)

SPECIFICATION_FREEZE_COMMIT = "a7ca2243c33097c4dd2b4a6afa3c79b1da7e41f2"
B3_1_COMMIT = "4953197e9e4fcb6a1e2d92e49e975fee257fc093"
R1_1_COMMIT = "8d0ef61262396b55782f492a0010a0e0c59af9ed"
SPECIFICATION_PATH = Path(
    "docs/prototype5/phase_b3_2_discrete_route_collision_qualification_spec.md"
)
SPECIFICATION_SHA256 = (
    "ffdcf517d56e32ae5b5a175bef89e015489a3d23ab7c1a4856c9987da7e4344a"
)
SPECIFICATION_GIT_BLOB = "5b63ae433315ea94cd58c734bcf379367dafcd71"

B1_2_ARTIFACT = b31.B1_2_ARTIFACT
B2_ARTIFACT = b31.B2_ARTIFACT
B3_1_ARTIFACT = Path(
    "results/prototype5/scene_calibration/phase_b3_1_collision_qualification.json"
)
B1_2_ARTIFACT_SHA256 = b31.B1_2_ARTIFACT_SHA256
B2_ARTIFACT_SHA256 = b31.B2_ARTIFACT_SHA256
B3_1_ARTIFACT_SHA256 = (
    "004783320d3af4d1de45aaeee3f6da09829d6ad395d49221bac054452fa5af02"
)
CI_WHEEL_PATH = Path("ci/wheels/pybullet-3.2.7-cp312-cp312-win_amd64.whl")
CI_WHEEL_SHA256 = (
    "de6f71be9d8b78f4413a2bc958971725d2b061c4bf2d733e62488683c384726b"
)

NUMERICAL_CONTACT_EPSILON_M = 1.0e-12
CLOSEST_POINT_QUERY_HORIZON_M = 0.050
BASE_MAX_JOINT_STEP_RAD = 0.010
ROUTE_REPRODUCIBILITY_REPEAT_COUNT = 2

EXPECTED_ROUTE_STATES = (
    "HOME",
    "SOURCE_HIGH",
    "SOURCE_PICK",
    "SOURCE_HIGH_RETURN",
    "DESTINATION_HIGH",
    "DESTINATION_PLACE",
    "DESTINATION_HIGH_RETURN",
    "HOME",
)
EXPECTED_HOME_JOINT_VECTOR = (
    0.7993234719552273,
    1.3696794627951159,
    -1.3444968999751499,
    -1.708611091255202,
    -1.744593730435666,
    -1.3230449060760399,
    -0.8646425864747171,
)
EXPECTED_COARSE_INTERVALS = (39, 20, 19, 77, 20, 19, 39)
EXPECTED_FINE_INTERVALS = (78, 40, 38, 154, 40, 38, 78)
EXPECTED_COARSE_ROUTE_CONFIGURATIONS = 234
EXPECTED_FINE_ROUTE_CONFIGURATIONS = 467
EXPECTED_COARSE_SEMANTIC_SNAPSHOTS = 236
EXPECTED_FINE_SEMANTIC_SNAPSHOTS = 469
EXPECTED_PAIR_QUERIES_PER_SEMANTIC_SNAPSHOT = 83
EXPECTED_COARSE_QUERY_COUNT = 19_588
EXPECTED_FINE_QUERY_COUNT = 38_927
EXPECTED_TOTAL_QUERY_COUNT = 97_442

MAX_ROUTE_SEGMENTS = 7
MAX_FINE_ROUTE_CONFIGURATIONS = 1024
MAX_FINE_SEMANTIC_SNAPSHOTS = 1024
MAX_PAIR_QUERIES_PER_SEMANTIC_SNAPSHOT = 83
MAX_TOTAL_COLLISION_QUERIES = 150_000

ROBOT_LINK_INDICES = b31.ROBOT_LINK_INDICES
ENVIRONMENT_SEMANTIC_IDS = (
    "source_platform",
    "destination_floor",
    "destination_wall_x_minus",
    "destination_wall_x_plus",
    "destination_wall_y_minus",
    "destination_wall_y_plus",
)
SCIENTIFIC_FAILURE_CODES = (
    "B3_2_FAIL_FORBIDDEN_CONTACT",
    "B3_2_FAIL_SUPPORT_MATERIAL_PENETRATION",
    "B3_2_FAIL_REQUIRED_SUPPORT_MISSING",
)
REQUIRED_ARTIFACT_SECTIONS = (
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
)
REQUIRED_OBSERVATION_FIELDS = (
    "pair_index",
    "pair_id",
    "found",
    "signed_distance_m",
    "separation_lower_bound_m",
    "classification",
    "permission",
    "decision",
)
REQUIRED_SEMANTIC_SNAPSHOT_FIELDS = (
    "route_configuration_index",
    "semantic_snapshot_index",
    "segment_index",
    "segment_sample_index",
    "segment_interval_count",
    "alpha",
    "route_state",
    "phase",
    "boundary_snapshot",
    "joint_vector",
    "component_pose",
    "observations",
)
AGGREGATE_CLEARANCE_FIELDS = (
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
)
AGGREGATE_FAILURE_FIELDS = (
    ("forbidden_failure_count", SCIENTIFIC_FAILURE_CODES[0]),
    ("support_material_penetration_count", SCIENTIFIC_FAILURE_CODES[1]),
    ("required_support_missing_count", SCIENTIFIC_FAILURE_CODES[2]),
)

JsonObject = dict[str, object]
JointVector = tuple[float, ...]


class B3_2_InfrastructureError(RuntimeError):
    """Fail-closed infrastructure, provenance, or contract failure."""


class DistanceClassification(str, Enum):
    MATERIAL_PENETRATION = "MATERIAL_PENETRATION"
    NUMERICAL_CONTACT_BAND = "NUMERICAL_CONTACT_BAND"
    SEPARATED = "SEPARATED"
    SEPARATED_BEYOND_QUERY_HORIZON = "SEPARATED_BEYOND_QUERY_HORIZON"


class PairPolicy(str, Enum):
    FORBIDDEN = "FORBIDDEN"
    PERMITTED_SUPPORT = "PERMITTED_SUPPORT"
    REQUIRED_SUPPORT = "REQUIRED_SUPPORT"


class BoundarySnapshot(str, Enum):
    NONE = "NONE"
    PRE = "PRE"
    POST = "POST"


class ComponentPhase(str, Enum):
    SOURCE_SUPPORTED = "SOURCE_SUPPORTED"
    ATTACHMENT_BOUNDARY = "ATTACHMENT_BOUNDARY"
    CARRIED = "CARRIED"
    RELEASE_BOUNDARY = "RELEASE_BOUNDARY"
    DESTINATION_SUPPORTED = "DESTINATION_SUPPORTED"


class PairCategory(str, Enum):
    ROBOT_SELF = "ROBOT_SELF"
    ROBOT_ENVIRONMENT = "ROBOT_ENVIRONMENT"
    COMPONENT_ROBOT = "COMPONENT_ROBOT"
    COMPONENT_ENVIRONMENT = "COMPONENT_ENVIRONMENT"


class PassName(str, Enum):
    COARSE = "COARSE"
    FINE_PASS_1 = "FINE_PASS_1"
    FINE_PASS_2 = "FINE_PASS_2"


@dataclass(frozen=True)
class RouteState:
    state: str
    joint_vector: JointVector
    lower_limits: JointVector
    upper_limits: JointVector


@dataclass(frozen=True)
class RouteConfiguration:
    route_configuration_index: int
    segment_index: int
    segment_sample_index: int
    segment_interval_count: int
    alpha: float
    route_state: str
    joint_vector: JointVector


@dataclass(frozen=True)
class SemanticSnapshot:
    route_configuration_index: int
    semantic_snapshot_index: int
    segment_index: int
    segment_sample_index: int
    segment_interval_count: int
    alpha: float
    route_state: str
    phase: ComponentPhase
    boundary_snapshot: BoundarySnapshot
    joint_vector: JointVector


@dataclass(frozen=True)
class CollisionPair:
    pair_index: int
    pair_id: str
    category: PairCategory
    first_robot_link: int | None = None
    second_robot_link: int | None = None
    robot_link: int | None = None
    environment_semantic_id: str | None = None


@dataclass(frozen=True)
class FrozenInputs:
    route: tuple[RouteState, ...]
    predecessor: b31.PredecessorEvidence
    self_collision_pairs: tuple[b31.LinkPair, ...]
    input_hashes: dict[str, str]


@dataclass(frozen=True)
class RuntimeScene:
    client_id: int
    robot_body: int
    component_body: int
    environment_bodies: dict[str, int]


@dataclass(frozen=True)
class PassEvidence:
    name: PassName
    interval_counts: tuple[int, ...]
    route_configuration_count: int
    semantic_snapshots: tuple[JsonObject, ...]
    scientific_failures: tuple[JsonObject, ...]
    query_count: int
    overall_result: str


def _reject_json_constant(token: str) -> NoReturn:
    raise B3_2_InfrastructureError(f"Non-finite JSON constant: {token}")


def _strict_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=_reject_json_constant,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise B3_2_InfrastructureError(f"Invalid JSON artifact: {path}") from exc
    if not isinstance(value, dict):
        raise B3_2_InfrastructureError(f"Expected JSON object: {path}")
    return value


def _required(mapping: dict[str, Any], key: str, field: str) -> Any:
    if key not in mapping:
        raise B3_2_InfrastructureError(f"Missing required field: {field}.{key}")
    value = mapping[key]
    if value is None:
        raise B3_2_InfrastructureError(f"Required field is null: {field}.{key}")
    return value


def finite_float(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise B3_2_InfrastructureError(f"{field} must be numeric")
    converted = float(value)
    if not math.isfinite(converted):
        raise B3_2_InfrastructureError(f"{field} must be finite")
    return converted


def _integer(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise B3_2_InfrastructureError(f"{field} must be an integer")
    return value


def _sequence(value: object, field: str, length: int) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise B3_2_InfrastructureError(f"{field} must be a sequence")
    if len(value) != length:
        raise B3_2_InfrastructureError(
            f"{field} must contain exactly {length} values"
        )
    return value


def _joint_vector(value: object, field: str) -> JointVector:
    values = _sequence(value, field, 7)
    return tuple(
        finite_float(item, f"{field}[{index}]")
        for index, item in enumerate(values)
    )


def _run_git(repository_root: Path, *arguments: str) -> str:
    try:
        completed = subprocess.run(
            ("git", *arguments),
            cwd=repository_root,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise B3_2_InfrastructureError(
            f"Git verification failed: {' '.join(arguments)}"
        ) from exc
    return completed.stdout.strip()


def _commit_is_ancestor(repository_root: Path, ancestor: str, head: str) -> bool:
    try:
        completed = subprocess.run(
            ("git", "merge-base", "--is-ancestor", ancestor, head),
            cwd=repository_root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise B3_2_InfrastructureError("Git ancestry verification failed") from exc
    if completed.returncode not in (0, 1):
        raise B3_2_InfrastructureError("Git ancestry verification was indeterminate")
    return completed.returncode == 0


def _verify_digest(artifact: Path, expected_sha256: str) -> None:
    if not artifact.is_file():
        raise B3_2_InfrastructureError(f"Missing frozen artifact: {artifact}")
    actual = b31.sha256_file(artifact)
    if actual != expected_sha256:
        raise B3_2_InfrastructureError(
            f"Frozen artifact drift: {artifact}: {actual} != {expected_sha256}"
        )
    digest_path = artifact.with_suffix(artifact.suffix + ".sha256")
    expected = f"{expected_sha256}  {artifact.name}\n"
    try:
        digest_text = digest_path.read_text(encoding="ascii")
    except (OSError, UnicodeError) as exc:
        raise B3_2_InfrastructureError(
            f"Missing or invalid companion digest: {digest_path}"
        ) from exc
    if digest_text != expected:
        raise B3_2_InfrastructureError(
            f"Companion digest mismatch: {digest_path}"
        )


def verify_repository_and_runtime(repository_root: Path) -> JsonObject:
    root = Path(_run_git(repository_root, "rev-parse", "--show-toplevel")).resolve()
    if root != repository_root.resolve():
        raise B3_2_InfrastructureError(f"Wrong repository root: {root}")
    head = _run_git(repository_root, "rev-parse", "HEAD")
    for required_commit in (B3_1_COMMIT, R1_1_COMMIT, SPECIFICATION_FREEZE_COMMIT):
        if not _commit_is_ancestor(repository_root, required_commit, head):
            raise B3_2_InfrastructureError(
                f"Required commit is not an ancestor of HEAD: {required_commit}"
            )
    specification = repository_root / SPECIFICATION_PATH
    if b31.sha256_file(specification) != SPECIFICATION_SHA256:
        raise B3_2_InfrastructureError("Frozen B3.2 specification bytes changed")
    if _run_git(repository_root, "rev-parse", f"HEAD:{SPECIFICATION_PATH.as_posix()}") != SPECIFICATION_GIT_BLOB:
        raise B3_2_InfrastructureError("Frozen B3.2 specification Git blob changed")
    eol = _run_git(repository_root, "check-attr", "eol", "--", SPECIFICATION_PATH.as_posix())
    if not eol.endswith("eol: lf"):
        raise B3_2_InfrastructureError("Frozen B3.2 specification EOL policy changed")

    _verify_digest(repository_root / B1_2_ARTIFACT, B1_2_ARTIFACT_SHA256)
    _verify_digest(repository_root / B2_ARTIFACT, B2_ARTIFACT_SHA256)
    _verify_digest(repository_root / B3_1_ARTIFACT, B3_1_ARTIFACT_SHA256)
    wheel = repository_root / CI_WHEEL_PATH
    if b31.sha256_file(wheel) != CI_WHEEL_SHA256:
        raise B3_2_InfrastructureError("Qualified CI PyBullet wheel changed")
    wheel_digest = wheel.with_suffix(wheel.suffix + ".sha256")
    if wheel_digest.read_text(encoding="ascii") != f"{CI_WHEEL_SHA256}  {wheel.name}\n":
        raise B3_2_InfrastructureError("Qualified CI wheel digest changed")

    package_version = importlib.metadata.version("pybullet")
    api_version = int(pb.getAPIVersion())
    binary_path = Path(str(pb.__file__)).resolve()
    data_root = Path(pybullet_data.getDataPath()).resolve()
    urdf_path = data_root / b31.KUKA_URDF_RELATIVE
    observed = {
        "package_version": package_version,
        "api_version": api_version,
        "binary_identity": f"python_environment/{binary_path.name}",
        "binary_sha256": b31.sha256_file(binary_path),
        "urdf_identity": f"pybullet_data/{b31.KUKA_URDF_RELATIVE.as_posix()}",
        "urdf_sha256": b31.sha256_file(urdf_path),
        "kuka_asset_manifest_sha256": b31.directory_manifest_sha256(urdf_path.parent),
    }
    expected = {
        "package_version": b31.PYBULLET_PACKAGE_VERSION,
        "api_version": b31.PYBULLET_API_VERSION,
        "binary_sha256": b31.PYBULLET_BINARY_SHA256,
        "urdf_sha256": b31.KUKA_URDF_SHA256,
        "kuka_asset_manifest_sha256": b31.KUKA_ASSET_MANIFEST_SHA256,
    }
    for key, value in expected.items():
        if observed[key] != value:
            raise B3_2_InfrastructureError(
                f"Pinned PyBullet/KUKA identity changed: {key}"
            )
    return {
        "repository_root": "repository/",
        "lineage_contract": "CURRENT_HEAD_DESCENDS_FROM_ALL_FROZEN_PREDECESSORS",
        "required_ancestor_commits": [
            B3_1_COMMIT,
            R1_1_COMMIT,
            SPECIFICATION_FREEZE_COMMIT,
        ],
        "python": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
        },
        "pybullet": observed,
        "qualified_ci_wheel": {
            "identity": f"repository/{CI_WHEEL_PATH.as_posix()}",
            "sha256": CI_WHEEL_SHA256,
        },
    }


def load_frozen_inputs(repository_root: Path) -> FrozenInputs:
    _verify_digest(repository_root / B1_2_ARTIFACT, B1_2_ARTIFACT_SHA256)
    _verify_digest(repository_root / B2_ARTIFACT, B2_ARTIFACT_SHA256)
    _verify_digest(repository_root / B3_1_ARTIFACT, B3_1_ARTIFACT_SHA256)
    predecessor = b31.load_predecessor_evidence(repository_root)

    b2 = _strict_json(repository_root / B2_ARTIFACT)
    if _required(b2, "schema_identifier", "b2") != "prototype5.scene_kinematic_plan.b2":
        raise B3_2_InfrastructureError("Unexpected B2 schema")
    ordered_plan = _required(b2, "ordered_plan", "b2")
    if not isinstance(ordered_plan, list) or len(ordered_plan) != 8:
        raise B3_2_InfrastructureError("B2 route must contain exactly eight states")
    route: list[RouteState] = []
    for index, raw_state in enumerate(ordered_plan):
        if not isinstance(raw_state, dict):
            raise B3_2_InfrastructureError(f"B2 route state {index} is not an object")
        state = _required(raw_state, "state", f"b2.ordered_plan[{index}]")
        if state != EXPECTED_ROUTE_STATES[index]:
            raise B3_2_InfrastructureError(f"Frozen B2 route state changed at {index}")
        if _integer(
            _required(raw_state, "route_index", f"b2.ordered_plan[{index}]"),
            f"b2.ordered_plan[{index}].route_index",
        ) != index:
            raise B3_2_InfrastructureError("B2 route indexes are not contiguous")
        vector = _joint_vector(
            _required(raw_state, "joint_vector", f"b2.ordered_plan[{index}]"),
            f"b2.ordered_plan[{index}].joint_vector",
        )
        limits = _required(
            raw_state,
            "joint_limit_evidence",
            f"b2.ordered_plan[{index}]",
        )
        if not isinstance(limits, list) or len(limits) != 7:
            raise B3_2_InfrastructureError("B2 joint-limit evidence must contain seven entries")
        lower: list[float] = []
        upper: list[float] = []
        for joint_index, item in enumerate(limits):
            if not isinstance(item, dict):
                raise B3_2_InfrastructureError("Malformed B2 joint-limit evidence")
            if _integer(_required(item, "joint_index", "joint_limit"), "joint_index") != joint_index:
                raise B3_2_InfrastructureError("B2 joint-limit order changed")
            low = finite_float(_required(item, "lower_limit_rad", "joint_limit"), "lower_limit_rad")
            high = finite_float(_required(item, "upper_limit_rad", "joint_limit"), "upper_limit_rad")
            if low >= high or not low <= vector[joint_index] <= high:
                raise B3_2_InfrastructureError("B2 route vector violates frozen joint limits")
            lower.append(low)
            upper.append(high)
        route.append(RouteState(str(state), vector, tuple(lower), tuple(upper)))
    if route[0].joint_vector != route[-1].joint_vector:
        raise B3_2_InfrastructureError("Frozen HOME round trip changed")
    reference_limits = (route[0].lower_limits, route[0].upper_limits)
    if any((item.lower_limits, item.upper_limits) != reference_limits for item in route):
        raise B3_2_InfrastructureError("Frozen B2 joint limits vary by route state")

    b3_1 = _strict_json(repository_root / B3_1_ARTIFACT)
    if _required(b3_1, "schema_identifier", "b3_1") != b31.SCHEMA_IDENTIFIER:
        raise B3_2_InfrastructureError("Unexpected B3.1 schema")
    scene = _required(b3_1, "frozen_scene_reconstruction", "b3_1")
    if not isinstance(scene, dict):
        raise B3_2_InfrastructureError("Missing B3.1 frozen scene")
    robot = _required(scene, "robot", "b3_1.frozen_scene_reconstruction")
    if not isinstance(robot, dict):
        raise B3_2_InfrastructureError("Missing B3.1 robot evidence")
    raw_pairs = _required(robot, "queried_nonadjacent_pairs", "b3_1.robot")
    if not isinstance(raw_pairs, list) or len(raw_pairs) != 21:
        raise B3_2_InfrastructureError("B3.1 authoritative pair inventory changed")
    pairs: list[b31.LinkPair] = []
    for index, item in enumerate(raw_pairs):
        if not isinstance(item, dict):
            raise B3_2_InfrastructureError(f"Malformed B3.1 pair {index}")
        first = _integer(_required(item, "first_link_index", "b3_1.pair"), "first_link_index")
        second = _integer(_required(item, "second_link_index", "b3_1.pair"), "second_link_index")
        pairs.append(b31.LinkPair(first, second))
    if len(set(pairs)) != 21:
        raise B3_2_InfrastructureError("B3.1 authoritative pair inventory has duplicates")

    intervals = interval_counts(tuple(route), refinement_factor=1)
    if intervals != EXPECTED_COARSE_INTERVALS:
        raise B3_2_InfrastructureError("Frozen B2 route interval vector changed")
    return FrozenInputs(
        route=tuple(route),
        predecessor=predecessor,
        self_collision_pairs=tuple(pairs),
        input_hashes={
            B1_2_ARTIFACT.as_posix(): B1_2_ARTIFACT_SHA256,
            B2_ARTIFACT.as_posix(): B2_ARTIFACT_SHA256,
            B3_1_ARTIFACT.as_posix(): B3_1_ARTIFACT_SHA256,
        },
    )


def classify_signed_distance(distance_m: object) -> DistanceClassification:
    distance = finite_float(distance_m, "signed_distance_m")
    if distance < -NUMERICAL_CONTACT_EPSILON_M:
        return DistanceClassification.MATERIAL_PENETRATION
    if distance <= NUMERICAL_CONTACT_EPSILON_M:
        return DistanceClassification.NUMERICAL_CONTACT_BAND
    return DistanceClassification.SEPARATED


def classify_closest_point(
    result: b31.ClosestPointResult,
) -> DistanceClassification:
    if not isinstance(result, b31.ClosestPointResult):
        raise B3_2_InfrastructureError("Malformed closest-point result")
    if result.found:
        if result.signed_distance_m is None or result.separation_lower_bound_m is not None:
            raise B3_2_InfrastructureError("Malformed found closest-point result")
        return classify_signed_distance(result.signed_distance_m)
    if result.signed_distance_m is not None:
        raise B3_2_InfrastructureError("No-result observation contains a signed distance")
    lower = finite_float(result.separation_lower_bound_m, "separation_lower_bound_m")
    if lower != CLOSEST_POINT_QUERY_HORIZON_M:
        raise B3_2_InfrastructureError("No-result lower bound changed")
    return DistanceClassification.SEPARATED_BEYOND_QUERY_HORIZON


def decide_contact(
    policy: PairPolicy,
    classification: DistanceClassification,
) -> str:
    if not isinstance(policy, PairPolicy) or not isinstance(
        classification, DistanceClassification
    ):
        raise B3_2_InfrastructureError("Unknown contact policy or classification")
    if policy is PairPolicy.FORBIDDEN:
        if classification in {
            DistanceClassification.MATERIAL_PENETRATION,
            DistanceClassification.NUMERICAL_CONTACT_BAND,
        }:
            return SCIENTIFIC_FAILURE_CODES[0]
        return "PASS"
    if classification is DistanceClassification.MATERIAL_PENETRATION:
        return SCIENTIFIC_FAILURE_CODES[1]
    if policy is PairPolicy.REQUIRED_SUPPORT and classification in {
        DistanceClassification.SEPARATED,
        DistanceClassification.SEPARATED_BEYOND_QUERY_HORIZON,
    }:
        return SCIENTIFIC_FAILURE_CODES[2]
    return "PASS"


def interval_counts(
    route: tuple[RouteState, ...],
    *,
    refinement_factor: int,
) -> tuple[int, ...]:
    if isinstance(refinement_factor, bool) or refinement_factor not in (1, 2):
        raise B3_2_InfrastructureError("Refinement factor must be exactly 1 or 2")
    if len(route) != 8:
        raise B3_2_InfrastructureError("Route must contain eight states")
    if len(route) - 1 > MAX_ROUTE_SEGMENTS:
        raise B3_2_InfrastructureError("Route segment cap exceeded")
    for state_index, state in enumerate(route):
        if not isinstance(state, RouteState):
            raise B3_2_InfrastructureError("Route entries must be RouteState values")
        if (
            len(state.joint_vector) != 7
            or len(state.lower_limits) != 7
            or len(state.upper_limits) != 7
        ):
            raise B3_2_InfrastructureError("Route vectors and limits must contain seven joints")
        for joint_index, (value, lower, upper) in enumerate(
            zip(
                state.joint_vector,
                state.lower_limits,
                state.upper_limits,
                strict=True,
            )
        ):
            checked_value = finite_float(
                value,
                f"route[{state_index}].joint_vector[{joint_index}]",
            )
            checked_lower = finite_float(
                lower,
                f"route[{state_index}].lower_limits[{joint_index}]",
            )
            checked_upper = finite_float(
                upper,
                f"route[{state_index}].upper_limits[{joint_index}]",
            )
            if checked_lower >= checked_upper or not checked_lower <= checked_value <= checked_upper:
                raise B3_2_InfrastructureError("Route joint value violates declared limits")
    counts: list[int] = []
    for start, end in zip(route[:-1], route[1:], strict=True):
        if len(start.joint_vector) != 7 or len(end.joint_vector) != 7:
            raise B3_2_InfrastructureError("Route vectors must have seven joints")
        maximum_delta = max(
            abs(right - left)
            for left, right in zip(start.joint_vector, end.joint_vector, strict=True)
        )
        coarse = max(1, math.ceil(maximum_delta / BASE_MAX_JOINT_STEP_RAD))
        counts.append(refinement_factor * coarse)
    return tuple(counts)


def enforce_protocol_caps(
    *,
    route_segments: int,
    fine_route_configurations: int,
    fine_semantic_snapshots: int,
    pairs_per_snapshot: int,
    total_queries: int,
) -> None:
    values = {
        "route_segments": (route_segments, MAX_ROUTE_SEGMENTS),
        "fine_route_configurations": (
            fine_route_configurations,
            MAX_FINE_ROUTE_CONFIGURATIONS,
        ),
        "fine_semantic_snapshots": (
            fine_semantic_snapshots,
            MAX_FINE_SEMANTIC_SNAPSHOTS,
        ),
        "pairs_per_snapshot": (
            pairs_per_snapshot,
            MAX_PAIR_QUERIES_PER_SEMANTIC_SNAPSHOT,
        ),
        "total_queries": (total_queries, MAX_TOTAL_COLLISION_QUERIES),
    }
    for field, (value, cap) in values.items():
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise B3_2_InfrastructureError(f"{field} must be a non-negative integer")
        if value > cap:
            raise B3_2_InfrastructureError(f"{field} cap exceeded")


def sample_route(
    route: tuple[RouteState, ...],
    *,
    refinement_factor: int,
) -> tuple[RouteConfiguration, ...]:
    intervals = interval_counts(route, refinement_factor=refinement_factor)
    expected = (
        EXPECTED_COARSE_INTERVALS
        if refinement_factor == 1
        else EXPECTED_FINE_INTERVALS
    )
    if intervals != expected:
        raise B3_2_InfrastructureError("Route interval cardinality changed")
    configurations: list[RouteConfiguration] = []
    for segment_index, (start, end, count) in enumerate(
        zip(route[:-1], route[1:], intervals, strict=True)
    ):
        first_sample = 0 if segment_index == 0 else 1
        for sample_index in range(first_sample, count + 1):
            ratio = Fraction(sample_index, count)
            if sample_index == 0:
                vector = start.joint_vector
                route_state = start.state
            elif sample_index == count:
                vector = end.joint_vector
                route_state = end.state
            else:
                alpha = float(ratio)
                vector = tuple(
                    left + alpha * (right - left)
                    for left, right in zip(
                        start.joint_vector,
                        end.joint_vector,
                        strict=True,
                    )
                )
                route_state = "INTERPOLATED"
            for joint_index, value in enumerate(vector):
                if not math.isfinite(value):
                    raise B3_2_InfrastructureError("Interpolated joint value is non-finite")
                if not route[0].lower_limits[joint_index] <= value <= route[0].upper_limits[joint_index]:
                    raise B3_2_InfrastructureError("Interpolated joint value exceeds frozen limits")
            configurations.append(
                RouteConfiguration(
                    route_configuration_index=len(configurations),
                    segment_index=segment_index,
                    segment_sample_index=sample_index,
                    segment_interval_count=count,
                    alpha=float(ratio),
                    route_state=route_state,
                    joint_vector=vector,
                )
            )
    expected_count = (
        EXPECTED_COARSE_ROUTE_CONFIGURATIONS
        if refinement_factor == 1
        else EXPECTED_FINE_ROUTE_CONFIGURATIONS
    )
    if len(configurations) != expected_count:
        raise B3_2_InfrastructureError("Route configuration count changed")
    if refinement_factor == 2 and len(configurations) > MAX_FINE_ROUTE_CONFIGURATIONS:
        raise B3_2_InfrastructureError("Fine route configuration cap exceeded")
    return tuple(configurations)


def semantic_snapshots(
    route: tuple[RouteState, ...],
    *,
    refinement_factor: int,
) -> tuple[SemanticSnapshot, ...]:
    snapshots: list[SemanticSnapshot] = []
    for configuration in sample_route(route, refinement_factor=refinement_factor):
        if configuration.route_state == "SOURCE_PICK":
            phase_boundaries = (
                (ComponentPhase.ATTACHMENT_BOUNDARY, BoundarySnapshot.PRE),
                (ComponentPhase.ATTACHMENT_BOUNDARY, BoundarySnapshot.POST),
            )
        elif configuration.route_state == "DESTINATION_PLACE":
            phase_boundaries = (
                (ComponentPhase.RELEASE_BOUNDARY, BoundarySnapshot.PRE),
                (ComponentPhase.RELEASE_BOUNDARY, BoundarySnapshot.POST),
            )
        elif configuration.segment_index <= 1:
            phase_boundaries = ((ComponentPhase.SOURCE_SUPPORTED, BoundarySnapshot.NONE),)
        elif configuration.segment_index <= 4:
            phase_boundaries = ((ComponentPhase.CARRIED, BoundarySnapshot.NONE),)
        else:
            phase_boundaries = ((ComponentPhase.DESTINATION_SUPPORTED, BoundarySnapshot.NONE),)
        for phase, boundary in phase_boundaries:
            snapshots.append(
                SemanticSnapshot(
                    route_configuration_index=configuration.route_configuration_index,
                    semantic_snapshot_index=len(snapshots),
                    segment_index=configuration.segment_index,
                    segment_sample_index=configuration.segment_sample_index,
                    segment_interval_count=configuration.segment_interval_count,
                    alpha=configuration.alpha,
                    route_state=configuration.route_state,
                    phase=phase,
                    boundary_snapshot=boundary,
                    joint_vector=configuration.joint_vector,
                )
            )
    expected = (
        EXPECTED_COARSE_SEMANTIC_SNAPSHOTS
        if refinement_factor == 1
        else EXPECTED_FINE_SEMANTIC_SNAPSHOTS
    )
    if len(snapshots) != expected:
        raise B3_2_InfrastructureError("Semantic snapshot count changed")
    if refinement_factor == 2 and len(snapshots) > MAX_FINE_SEMANTIC_SNAPSHOTS:
        raise B3_2_InfrastructureError("Fine semantic snapshot cap exceeded")
    return tuple(snapshots)


def build_collision_pair_inventory(
    self_collision_pairs: tuple[b31.LinkPair, ...],
) -> tuple[CollisionPair, ...]:
    if len(self_collision_pairs) != 21 or len(set(self_collision_pairs)) != 21:
        raise B3_2_InfrastructureError("Authoritative self-collision inventory must contain 21 unique pairs")
    pairs: list[CollisionPair] = []
    for pair in self_collision_pairs:
        pairs.append(
            CollisionPair(
                len(pairs),
                f"robot_self:{pair.first}:{pair.second}",
                PairCategory.ROBOT_SELF,
                first_robot_link=pair.first,
                second_robot_link=pair.second,
            )
        )
    for robot_link in ROBOT_LINK_INDICES:
        for environment in ENVIRONMENT_SEMANTIC_IDS:
            pairs.append(
                CollisionPair(
                    len(pairs),
                    f"robot_environment:{robot_link}:{environment}",
                    PairCategory.ROBOT_ENVIRONMENT,
                    robot_link=robot_link,
                    environment_semantic_id=environment,
                )
            )
    for robot_link in ROBOT_LINK_INDICES:
        pairs.append(
            CollisionPair(
                len(pairs),
                f"component_robot:{robot_link}",
                PairCategory.COMPONENT_ROBOT,
                robot_link=robot_link,
            )
        )
    for environment in ENVIRONMENT_SEMANTIC_IDS:
        pairs.append(
            CollisionPair(
                len(pairs),
                f"component_environment:{environment}",
                PairCategory.COMPONENT_ENVIRONMENT,
                environment_semantic_id=environment,
            )
        )
    if len(pairs) != EXPECTED_PAIR_QUERIES_PER_SEMANTIC_SNAPSHOT:
        raise B3_2_InfrastructureError("Collision-pair inventory count changed")
    if len(pairs) > MAX_PAIR_QUERIES_PER_SEMANTIC_SNAPSHOT:
        raise B3_2_InfrastructureError("Collision-pair cap exceeded")
    if tuple(item.pair_index for item in pairs) != tuple(range(83)):
        raise B3_2_InfrastructureError("Collision-pair indexes are not canonical")
    if len({item.pair_id for item in pairs}) != 83:
        raise B3_2_InfrastructureError("Collision-pair IDs are not unique")
    return tuple(pairs)


def component_environment_policy(
    environment_semantic_id: str,
    phase: ComponentPhase,
    boundary: BoundarySnapshot,
) -> PairPolicy:
    if environment_semantic_id not in ENVIRONMENT_SEMANTIC_IDS:
        raise B3_2_InfrastructureError("Unknown environment semantic ID")
    if environment_semantic_id == "source_platform":
        if (phase, boundary) in {
            (ComponentPhase.SOURCE_SUPPORTED, BoundarySnapshot.NONE),
            (ComponentPhase.ATTACHMENT_BOUNDARY, BoundarySnapshot.PRE),
        }:
            return PairPolicy.REQUIRED_SUPPORT
        if (phase, boundary) == (
            ComponentPhase.ATTACHMENT_BOUNDARY,
            BoundarySnapshot.POST,
        ):
            return PairPolicy.PERMITTED_SUPPORT
    elif environment_semantic_id == "destination_floor":
        if (phase, boundary) == (
            ComponentPhase.RELEASE_BOUNDARY,
            BoundarySnapshot.PRE,
        ):
            return PairPolicy.PERMITTED_SUPPORT
        if (phase, boundary) in {
            (ComponentPhase.RELEASE_BOUNDARY, BoundarySnapshot.POST),
            (ComponentPhase.DESTINATION_SUPPORTED, BoundarySnapshot.NONE),
        }:
            return PairPolicy.REQUIRED_SUPPORT
    return PairPolicy.FORBIDDEN


def pair_policy(
    pair: CollisionPair,
    phase: ComponentPhase,
    boundary: BoundarySnapshot,
) -> PairPolicy:
    if pair.category is PairCategory.COMPONENT_ENVIRONMENT:
        if pair.environment_semantic_id is None:
            raise B3_2_InfrastructureError("Component/environment pair lacks semantic ID")
        return component_environment_policy(
            pair.environment_semantic_id,
            phase,
            boundary,
        )
    return PairPolicy.FORBIDDEN


def carried_pose_from_link_state(
    link_state: Sequence[object],
    terminal_link_to_component: b31.Pose,
) -> b31.Pose:
    if (
        isinstance(link_state, (str, bytes))
        or not isinstance(link_state, Sequence)
        or len(link_state) <= 5
    ):
        raise B3_2_InfrastructureError("Malformed PyBullet link state")
    world_link_pose = b31.Pose(
        b31.vector3(link_state[4], "world link-frame position"),
        b31.normalize_quaternion(link_state[5], "world link-frame orientation"),
    )
    return b31.compose_pose_pybullet(world_link_pose, terminal_link_to_component)


def _component_pose(
    scene: RuntimeScene,
    snapshot: SemanticSnapshot,
    predecessor: b31.PredecessorEvidence,
) -> b31.Pose:
    state = (snapshot.phase, snapshot.boundary_snapshot)
    if state in {
        (ComponentPhase.SOURCE_SUPPORTED, BoundarySnapshot.NONE),
        (ComponentPhase.ATTACHMENT_BOUNDARY, BoundarySnapshot.PRE),
    }:
        return predecessor.source_component_pose
    if state in {
        (ComponentPhase.ATTACHMENT_BOUNDARY, BoundarySnapshot.POST),
        (ComponentPhase.CARRIED, BoundarySnapshot.NONE),
        (ComponentPhase.RELEASE_BOUNDARY, BoundarySnapshot.PRE),
    }:
        link_state = pb.getLinkState(
            scene.robot_body,
            b31.EE_LINK_INDEX,
            computeForwardKinematics=True,
            physicsClientId=scene.client_id,
        )
        return carried_pose_from_link_state(
            link_state,
            predecessor.virtual_component_local_pose,
        )
    if state in {
        (ComponentPhase.RELEASE_BOUNDARY, BoundarySnapshot.POST),
        (ComponentPhase.DESTINATION_SUPPORTED, BoundarySnapshot.NONE),
    }:
        return predecessor.predicted_release_pose
    raise B3_2_InfrastructureError("Unsupported component phase/boundary state")


def _open_runtime_scene(inputs: FrozenInputs) -> RuntimeScene:
    client_id = pb.connect(pb.DIRECT)
    if client_id < 0:
        raise B3_2_InfrastructureError("PyBullet DIRECT connection failed")
    try:
        pb.resetSimulation(physicsClientId=client_id)
        data_root = Path(pybullet_data.getDataPath()).resolve()
        robot = b31.load_kuka(client_id, data_root, b31.SELF_COLLISION_FLAGS)
        inventory = b31.kuka_link_inventory(robot, client_id)
        b31.verify_kuka_urdf_topology(
            inventory,
            data_root / b31.KUKA_URDF_RELATIVE,
        )
        _, direct_pairs, derived_pairs = b31.derive_self_collision_pairs(inventory)
        if len(direct_pairs) != 7 or derived_pairs != inputs.self_collision_pairs:
            raise B3_2_InfrastructureError(
                "Runtime KUKA topology differs from authoritative B3.1 pairs"
            )
        definitions = b31.frozen_box_definitions()
        b31.validate_frozen_box_definitions(definitions)
        bodies: dict[str, int] = {}
        for definition in definitions:
            bodies[definition.semantic_id] = b31._create_static_box(
                definition,
                client_id,
            )
        if set(bodies) != {*ENVIRONMENT_SEMANTIC_IDS, "blue_component"}:
            raise B3_2_InfrastructureError("Frozen scene body inventory changed")
        if pb.getNumBodies(physicsClientId=client_id) != 8:
            raise B3_2_InfrastructureError("Frozen scene must contain exactly eight bodies")
        return RuntimeScene(
            client_id=client_id,
            robot_body=robot,
            component_body=bodies.pop("blue_component"),
            environment_bodies=bodies,
        )
    except BaseException:
        pb.disconnect(physicsClientId=client_id)
        raise


def _query_pair(
    scene: RuntimeScene,
    pair: CollisionPair,
) -> b31.ClosestPointResult:
    if pair.category is PairCategory.ROBOT_SELF:
        return b31.closest_point_query(
            scene.robot_body,
            scene.robot_body,
            scene.client_id,
            link_a=pair.first_robot_link,
            link_b=pair.second_robot_link,
            horizon_m=CLOSEST_POINT_QUERY_HORIZON_M,
        )
    if pair.category is PairCategory.ROBOT_ENVIRONMENT:
        if pair.environment_semantic_id is None:
            raise B3_2_InfrastructureError("Robot/environment pair lacks semantic ID")
        return b31.closest_point_query(
            scene.robot_body,
            scene.environment_bodies[pair.environment_semantic_id],
            scene.client_id,
            link_a=pair.robot_link,
            link_b=-1,
            horizon_m=CLOSEST_POINT_QUERY_HORIZON_M,
        )
    if pair.category is PairCategory.COMPONENT_ROBOT:
        return b31.closest_point_query(
            scene.component_body,
            scene.robot_body,
            scene.client_id,
            link_a=-1,
            link_b=pair.robot_link,
            horizon_m=CLOSEST_POINT_QUERY_HORIZON_M,
        )
    if pair.category is PairCategory.COMPONENT_ENVIRONMENT:
        if pair.environment_semantic_id is None:
            raise B3_2_InfrastructureError("Component/environment pair lacks semantic ID")
        return b31.closest_point_query(
            scene.component_body,
            scene.environment_bodies[pair.environment_semantic_id],
            scene.client_id,
            link_a=-1,
            link_b=-1,
            horizon_m=CLOSEST_POINT_QUERY_HORIZON_M,
        )
    raise B3_2_InfrastructureError("Unknown collision-pair category")


def _snapshot_json(snapshot: SemanticSnapshot) -> JsonObject:
    return {
        "route_configuration_index": snapshot.route_configuration_index,
        "semantic_snapshot_index": snapshot.semantic_snapshot_index,
        "segment_index": snapshot.segment_index,
        "segment_sample_index": snapshot.segment_sample_index,
        "segment_interval_count": snapshot.segment_interval_count,
        "alpha": snapshot.alpha,
        "route_state": snapshot.route_state,
        "phase": snapshot.phase.value,
        "boundary_snapshot": snapshot.boundary_snapshot.value,
        "joint_vector": list(snapshot.joint_vector),
    }


def _failure_summary(failures: Sequence[JsonObject]) -> JsonObject:
    summary: JsonObject = {code: 0 for code in SCIENTIFIC_FAILURE_CODES}
    for failure in failures:
        code = failure.get("failure_code")
        if code not in SCIENTIFIC_FAILURE_CODES:
            raise B3_2_InfrastructureError("Unknown scientific failure code")
        summary[str(code)] = int(summary[str(code)]) + 1
    return summary


def overall_result(scientific_failures: Sequence[JsonObject]) -> str:
    _failure_summary(scientific_failures)
    return PASS_RESULT if not scientific_failures else FAIL_RESULT


def _result_json(scientific_failures: Sequence[JsonObject]) -> JsonObject:
    failures = list(scientific_failures)
    failure_summary = _failure_summary(failures)
    failure_codes_present: list[str] = []
    for failure in failures:
        code = str(failure["failure_code"])
        if code not in failure_codes_present:
            failure_codes_present.append(code)
    return {
        "overall_result": overall_result(failures),
        "scientific_failures": failures,
        "scientific_failure_count": len(failures),
        "failure_summary": failure_summary,
        "failure_codes_present": failure_codes_present,
        "primary_failure": None if not failures else failures[0],
    }


def run_qualification_pass(
    inputs: FrozenInputs,
    pairs: tuple[CollisionPair, ...],
    *,
    pass_name: PassName,
    refinement_factor: int,
) -> PassEvidence:
    if len(pairs) != 83:
        raise B3_2_InfrastructureError("Pass received a non-canonical pair inventory")
    snapshots = semantic_snapshots(inputs.route, refinement_factor=refinement_factor)
    expected_queries = len(snapshots) * len(pairs)
    if expected_queries > MAX_TOTAL_COLLISION_QUERIES:
        raise B3_2_InfrastructureError("Per-pass collision-query cap exceeded")
    scene = _open_runtime_scene(inputs)
    evidence: list[JsonObject] = []
    failures: list[JsonObject] = []
    query_count = 0
    try:
        for snapshot in snapshots:
            for joint_index, value in enumerate(snapshot.joint_vector):
                pb.resetJointState(
                    scene.robot_body,
                    joint_index,
                    value,
                    physicsClientId=scene.client_id,
                )
            pose = _component_pose(scene, snapshot, inputs.predecessor)
            pb.resetBasePositionAndOrientation(
                scene.component_body,
                pose.position,
                pose.orientation,
                physicsClientId=scene.client_id,
            )
            observations: list[JsonObject] = []
            for pair in pairs:
                result = _query_pair(scene, pair)
                classification = classify_closest_point(result)
                policy = pair_policy(
                    pair,
                    snapshot.phase,
                    snapshot.boundary_snapshot,
                )
                decision = decide_contact(policy, classification)
                observation: JsonObject = {
                    "pair_index": pair.pair_index,
                    "pair_id": pair.pair_id,
                    "found": result.found,
                    "signed_distance_m": result.signed_distance_m,
                    "separation_lower_bound_m": result.separation_lower_bound_m,
                    "classification": classification.value,
                    "permission": policy.value,
                    "decision": decision,
                }
                observations.append(observation)
                query_count += 1
                if decision != "PASS":
                    failures.append(
                        {
                            "semantic_snapshot_index": snapshot.semantic_snapshot_index,
                            "pair_index": pair.pair_index,
                            "pair_id": pair.pair_id,
                            "failure_code": decision,
                            "route_state": snapshot.route_state,
                            "phase": snapshot.phase.value,
                            "boundary_snapshot": snapshot.boundary_snapshot.value,
                        }
                    )
            if len(observations) != EXPECTED_PAIR_QUERIES_PER_SEMANTIC_SNAPSHOT:
                raise B3_2_InfrastructureError("Snapshot query count changed")
            item = _snapshot_json(snapshot)
            item["component_pose"] = {
                "position_m": list(pose.position),
                "quaternion_xyzw": list(pose.orientation),
            }
            item["observations"] = observations
            evidence.append(item)
    finally:
        pb.disconnect(physicsClientId=scene.client_id)
    if query_count != expected_queries:
        raise B3_2_InfrastructureError("Pass query count changed")
    ordered_failures = tuple(
        sorted(
            failures,
            key=lambda item: (
                int(item["semantic_snapshot_index"]),
                int(item["pair_index"]),
                str(item["failure_code"]),
            ),
        )
    )
    result = overall_result(ordered_failures)
    return PassEvidence(
        name=pass_name,
        interval_counts=interval_counts(
            inputs.route,
            refinement_factor=refinement_factor,
        ),
        route_configuration_count=len(
            sample_route(inputs.route, refinement_factor=refinement_factor)
        ),
        semantic_snapshots=tuple(evidence),
        scientific_failures=ordered_failures,
        query_count=query_count,
        overall_result=result,
    )


def _observation_signature(observation: JsonObject) -> tuple[object, ...]:
    required_fields = (
        "pair_index",
        "pair_id",
        "found",
        "signed_distance_m",
        "separation_lower_bound_m",
        "classification",
        "permission",
        "decision",
    )
    for field in required_fields:
        if field not in observation:
            raise B3_2_InfrastructureError(
                f"Observation is missing required field: {field}"
            )
    return tuple(observation[field] for field in required_fields)


def compare_fine_passes(
    first: PassEvidence,
    second: PassEvidence,
) -> JsonObject:
    if first.name is not PassName.FINE_PASS_1 or second.name is not PassName.FINE_PASS_2:
        raise B3_2_InfrastructureError("Reproducibility requires fine pass 1 and fine pass 2")
    if first.route_configuration_count != second.route_configuration_count:
        raise B3_2_InfrastructureError("Fine route configuration counts differ")
    if len(first.semantic_snapshots) != len(second.semantic_snapshots):
        raise B3_2_InfrastructureError("Fine semantic snapshot counts differ")
    if first.query_count != second.query_count:
        raise B3_2_InfrastructureError("Fine query counts differ")

    maximum_spread = 0.0
    found_state_mismatches = 0
    distance_tolerance_violations = 0
    decision_mismatches = 0
    classification_mismatches = 0
    lower_bound_mismatches = 0
    compared_found_distances = 0
    compared_observations = 0
    metadata_fields = (
        "route_configuration_index",
        "semantic_snapshot_index",
        "segment_index",
        "segment_sample_index",
        "segment_interval_count",
        "alpha",
        "route_state",
        "phase",
        "boundary_snapshot",
        "joint_vector",
        "component_pose",
    )
    for first_snapshot, second_snapshot in zip(
        first.semantic_snapshots,
        second.semantic_snapshots,
        strict=True,
    ):
        if any(
            first_snapshot.get(field) != second_snapshot.get(field)
            for field in metadata_fields
        ):
            raise B3_2_InfrastructureError("Fine semantic snapshot metadata differs")
        first_observations = first_snapshot.get("observations")
        second_observations = second_snapshot.get("observations")
        if not isinstance(first_observations, list) or not isinstance(second_observations, list):
            raise B3_2_InfrastructureError("Fine snapshot observations are malformed")
        if len(first_observations) != 83 or len(second_observations) != 83:
            raise B3_2_InfrastructureError("Fine snapshot observation count changed")
        for first_observation, second_observation in zip(
            first_observations,
            second_observations,
            strict=True,
        ):
            if not isinstance(first_observation, dict) or not isinstance(second_observation, dict):
                raise B3_2_InfrastructureError("Fine observation is not an object")
            _observation_signature(first_observation)
            _observation_signature(second_observation)
            compared_observations += 1
            if first_observation["pair_index"] != second_observation["pair_index"] or first_observation["pair_id"] != second_observation["pair_id"]:
                raise B3_2_InfrastructureError("Fine pair identity/order differs")
            first_found = first_observation["found"]
            second_found = second_observation["found"]
            if not isinstance(first_found, bool) or not isinstance(second_found, bool):
                raise B3_2_InfrastructureError("Fine found flag is not boolean")
            if first_found != second_found:
                found_state_mismatches += 1
                continue
            if first_observation["classification"] != second_observation["classification"]:
                classification_mismatches += 1
            if first_observation["permission"] != second_observation["permission"] or first_observation["decision"] != second_observation["decision"]:
                decision_mismatches += 1
            if first_found:
                first_distance = finite_float(
                    first_observation["signed_distance_m"],
                    "fine pass 1 signed distance",
                )
                second_distance = finite_float(
                    second_observation["signed_distance_m"],
                    "fine pass 2 signed distance",
                )
                spread = abs(first_distance - second_distance)
                maximum_spread = max(maximum_spread, spread)
                compared_found_distances += 1
                if spread > NUMERICAL_CONTACT_EPSILON_M:
                    distance_tolerance_violations += 1
            elif (
                first_observation["signed_distance_m"] is not None
                or second_observation["signed_distance_m"] is not None
                or first_observation["separation_lower_bound_m"]
                != CLOSEST_POINT_QUERY_HORIZON_M
                or second_observation["separation_lower_bound_m"]
                != CLOSEST_POINT_QUERY_HORIZON_M
            ):
                lower_bound_mismatches += 1
    failure_mismatch = first.scientific_failures != second.scientific_failures
    result_mismatch = first.overall_result != second.overall_result
    if any(
        (
            found_state_mismatches,
            distance_tolerance_violations,
            decision_mismatches,
            classification_mismatches,
            lower_bound_mismatches,
            int(failure_mismatch),
            int(result_mismatch),
        )
    ):
        raise B3_2_InfrastructureError("Fine-pass reproducibility contract failed")
    if compared_observations != EXPECTED_FINE_QUERY_COUNT:
        raise B3_2_InfrastructureError("Fine comparison count changed")
    return {
        "repeat_count": ROUTE_REPRODUCIBILITY_REPEAT_COUNT,
        "fresh_independent_direct_sessions": True,
        "semantic_snapshot_count": len(first.semantic_snapshots),
        "compared_observation_count": compared_observations,
        "compared_found_distance_count": compared_found_distances,
        "maximum_found_distance_spread_m": maximum_spread,
        "distance_tolerance_m": NUMERICAL_CONTACT_EPSILON_M,
        "found_state_mismatch_count": found_state_mismatches,
        "distance_tolerance_violation_count": distance_tolerance_violations,
        "classification_mismatch_count": classification_mismatches,
        "decision_mismatch_count": decision_mismatches,
        "lower_bound_mismatch_count": lower_bound_mismatches,
        "scientific_failure_mismatch": failure_mismatch,
        "overall_result_mismatch": result_mismatch,
        "fine_pass_2_query_count": second.query_count,
        "fine_pass_2_result": second.overall_result,
    }


def compare_coarse_to_fine(
    coarse: PassEvidence,
    fine: PassEvidence,
) -> JsonObject:
    if coarse.name is not PassName.COARSE or fine.name is not PassName.FINE_PASS_1:
        raise B3_2_InfrastructureError("Nested comparison requires coarse and authoritative fine passes")
    fine_index: dict[tuple[int, Fraction, str], JsonObject] = {}
    for snapshot in fine.semantic_snapshots:
        segment_index = _integer(snapshot.get("segment_index"), "fine.segment_index")
        sample_index = _integer(snapshot.get("segment_sample_index"), "fine.segment_sample_index")
        interval_count = _integer(snapshot.get("segment_interval_count"), "fine.segment_interval_count")
        boundary = snapshot.get("boundary_snapshot")
        if not isinstance(boundary, str):
            raise B3_2_InfrastructureError("Fine boundary snapshot is malformed")
        key = (segment_index, Fraction(sample_index, interval_count), boundary)
        if key in fine_index:
            raise B3_2_InfrastructureError("Duplicate authoritative fine semantic key")
        fine_index[key] = snapshot

    semantic_comparisons = 0
    decision_comparisons = 0
    decision_disagreements = 0
    for coarse_snapshot in coarse.semantic_snapshots:
        segment_index = _integer(coarse_snapshot.get("segment_index"), "coarse.segment_index")
        sample_index = _integer(coarse_snapshot.get("segment_sample_index"), "coarse.segment_sample_index")
        interval_count = _integer(coarse_snapshot.get("segment_interval_count"), "coarse.segment_interval_count")
        boundary = coarse_snapshot.get("boundary_snapshot")
        if not isinstance(boundary, str):
            raise B3_2_InfrastructureError("Coarse boundary snapshot is malformed")
        key = (segment_index, Fraction(sample_index, interval_count), boundary)
        fine_snapshot = fine_index.get(key)
        if fine_snapshot is None:
            raise B3_2_InfrastructureError("Coarse configuration is not nested in fine grid")
        for field in ("route_state", "phase", "boundary_snapshot", "joint_vector", "component_pose"):
            if coarse_snapshot.get(field) != fine_snapshot.get(field):
                raise B3_2_InfrastructureError("Nested coarse/fine semantic metadata differs")
        coarse_observations = coarse_snapshot.get("observations")
        fine_observations = fine_snapshot.get("observations")
        if not isinstance(coarse_observations, list) or not isinstance(fine_observations, list):
            raise B3_2_InfrastructureError("Nested observations are malformed")
        for coarse_observation, fine_observation in zip(
            coarse_observations,
            fine_observations,
            strict=True,
        ):
            if not isinstance(coarse_observation, dict) or not isinstance(fine_observation, dict):
                raise B3_2_InfrastructureError("Nested observation is not an object")
            if coarse_observation.get("pair_id") != fine_observation.get("pair_id"):
                raise B3_2_InfrastructureError("Nested pair order differs")
            decision_comparisons += 1
            if coarse_observation.get("decision") != fine_observation.get("decision"):
                decision_disagreements += 1
        semantic_comparisons += 1
    if semantic_comparisons != EXPECTED_COARSE_SEMANTIC_SNAPSHOTS:
        raise B3_2_InfrastructureError("Nested semantic comparison count changed")
    if decision_comparisons != EXPECTED_COARSE_QUERY_COUNT or decision_disagreements:
        raise B3_2_InfrastructureError("Coarse/fine nested decision agreement failed")
    return {
        "nested_semantic_snapshot_comparison_count": semantic_comparisons,
        "nested_decision_comparison_count": decision_comparisons,
        "decision_disagreement_count": decision_disagreements,
        "coarse_grid_exactly_nested": True,
    }


def aggregate_authoritative_fine(first: PassEvidence) -> JsonObject:
    if first.name is not PassName.FINE_PASS_1:
        raise B3_2_InfrastructureError("Aggregate scope must be authoritative fine pass 1")
    found_count = 0
    censored_count = 0
    contact_band_count = 0
    material_penetration_count = 0
    forbidden_failure_count = 0
    support_penetration_count = 0
    required_support_missing_count = 0
    minimum: JsonObject | None = None
    minimum_forbidden: JsonObject | None = None
    total = 0
    for snapshot in first.semantic_snapshots:
        semantic_index = _integer(
            snapshot.get("semantic_snapshot_index"),
            "semantic_snapshot_index",
        )
        observations = snapshot.get("observations")
        if not isinstance(observations, list) or len(observations) != 83:
            raise B3_2_InfrastructureError("Authoritative observations are malformed")
        for observation in observations:
            if not isinstance(observation, dict):
                raise B3_2_InfrastructureError("Authoritative observation is not an object")
            _observation_signature(observation)
            total += 1
            found = observation["found"]
            if not isinstance(found, bool):
                raise B3_2_InfrastructureError("Authoritative found flag is malformed")
            classification = observation["classification"]
            permission = observation["permission"]
            decision = observation["decision"]
            if found:
                found_count += 1
                distance = finite_float(
                    observation["signed_distance_m"],
                    "authoritative signed distance",
                )
                item = {
                    "signed_distance_m": distance,
                    "semantic_snapshot_index": semantic_index,
                    "pair_index": _integer(observation["pair_index"], "pair_index"),
                    "pair_id": str(observation["pair_id"]),
                }
                if minimum is None or distance < float(minimum["signed_distance_m"]):
                    minimum = item
                if permission == PairPolicy.FORBIDDEN.value and (
                    minimum_forbidden is None
                    or distance < float(minimum_forbidden["signed_distance_m"])
                ):
                    minimum_forbidden = item
            else:
                censored_count += 1
                if observation["signed_distance_m"] is not None or observation["separation_lower_bound_m"] != CLOSEST_POINT_QUERY_HORIZON_M:
                    raise B3_2_InfrastructureError("Malformed authoritative censored observation")
            if classification == DistanceClassification.NUMERICAL_CONTACT_BAND.value:
                contact_band_count += 1
            elif classification == DistanceClassification.MATERIAL_PENETRATION.value:
                material_penetration_count += 1
            if decision == SCIENTIFIC_FAILURE_CODES[0]:
                forbidden_failure_count += 1
            elif decision == SCIENTIFIC_FAILURE_CODES[1]:
                support_penetration_count += 1
            elif decision == SCIENTIFIC_FAILURE_CODES[2]:
                required_support_missing_count += 1
            elif decision != "PASS":
                raise B3_2_InfrastructureError("Unknown authoritative decision")
    if total != EXPECTED_FINE_QUERY_COUNT or found_count + censored_count != total:
        raise B3_2_InfrastructureError("Authoritative aggregate accounting failed")
    if (found_count == 0) != (minimum is None):
        raise B3_2_InfrastructureError("Authoritative observed minimum is inconsistent")
    return {
        "total_query_count": total,
        "found_query_count": found_count,
        "censored_no_result_count": censored_count,
        "minimum_observed_signed_distance": minimum,
        "minimum_forbidden_observed_signed_distance": minimum_forbidden,
        "contact_band_event_count": contact_band_count,
        "material_penetration_event_count": material_penetration_count,
        "forbidden_failure_count": forbidden_failure_count,
        "support_material_penetration_count": support_penetration_count,
        "required_support_missing_count": required_support_missing_count,
    }


def _pair_inventory_json(pairs: tuple[CollisionPair, ...]) -> JsonObject:
    counts = {category.value: 0 for category in PairCategory}
    entries: list[JsonObject] = []
    for pair in pairs:
        counts[pair.category.value] += 1
        if pair.category is PairCategory.ROBOT_SELF:
            query_signature: JsonObject = {
                "bodyA": "robot",
                "bodyB": "robot",
                "linkIndexA": pair.first_robot_link,
                "linkIndexB": pair.second_robot_link,
            }
        elif pair.category is PairCategory.ROBOT_ENVIRONMENT:
            query_signature = {
                "bodyA": "robot",
                "bodyB": pair.environment_semantic_id,
                "linkIndexA": pair.robot_link,
                "linkIndexB": -1,
            }
        elif pair.category is PairCategory.COMPONENT_ROBOT:
            query_signature = {
                "bodyA": "component",
                "bodyB": "robot",
                "linkIndexA": -1,
                "linkIndexB": pair.robot_link,
            }
        else:
            query_signature = {
                "bodyA": "component",
                "bodyB": pair.environment_semantic_id,
                "linkIndexA": -1,
                "linkIndexB": -1,
            }
        query_signature["distance_m"] = CLOSEST_POINT_QUERY_HORIZON_M
        query_signature["physics_client_id"] = "EXPLICIT_PASS_LOCAL"
        entries.append(
            {
                "pair_index": pair.pair_index,
                "pair_id": pair.pair_id,
                "category": pair.category.value,
                "query_signature": query_signature,
            }
        )
    expected_counts = {
        PairCategory.ROBOT_SELF.value: 21,
        PairCategory.ROBOT_ENVIRONMENT.value: 48,
        PairCategory.COMPONENT_ROBOT.value: 8,
        PairCategory.COMPONENT_ENVIRONMENT.value: 6,
    }
    if counts != expected_counts:
        raise B3_2_InfrastructureError("Collision-pair category counts changed")
    return {
        "category_order": [category.value for category in PairCategory],
        "robot_body_order": list(ROBOT_LINK_INDICES),
        "environment_order": list(ENVIRONMENT_SEMANTIC_IDS),
        "category_counts": counts,
        "total_pair_count": len(pairs),
        "pairs": entries,
    }


def _component_phase_contract_json() -> JsonObject:
    rows: list[JsonObject] = []
    for environment in ENVIRONMENT_SEMANTIC_IDS:
        for phase, boundary in (
            (ComponentPhase.SOURCE_SUPPORTED, BoundarySnapshot.NONE),
            (ComponentPhase.ATTACHMENT_BOUNDARY, BoundarySnapshot.PRE),
            (ComponentPhase.ATTACHMENT_BOUNDARY, BoundarySnapshot.POST),
            (ComponentPhase.CARRIED, BoundarySnapshot.NONE),
            (ComponentPhase.RELEASE_BOUNDARY, BoundarySnapshot.PRE),
            (ComponentPhase.RELEASE_BOUNDARY, BoundarySnapshot.POST),
            (ComponentPhase.DESTINATION_SUPPORTED, BoundarySnapshot.NONE),
        ):
            rows.append(
                {
                    "environment_semantic_id": environment,
                    "phase": phase.value,
                    "boundary_snapshot": boundary.value,
                    "policy": component_environment_policy(
                        environment,
                        phase,
                        boundary,
                    ).value,
                }
            )
    return {
        "component_robot_policy": PairPolicy.FORBIDDEN.value,
        "destination_wall_policy": PairPolicy.FORBIDDEN.value,
        "carried_pose_formula": "world_T_component = world_T_terminal_link * terminal_link_T_component",
        "terminal_link_pose_fields": [4, 5],
        "boundary_snapshot_enum": [item.value for item in BoundarySnapshot],
        "attachment_constraint_created": False,
        "grasp_or_release_physics_executed": False,
        "policy_rows": rows,
    }


def _pass_summary(pass_evidence: PassEvidence) -> JsonObject:
    return {
        "pass_name": pass_evidence.name.value,
        "fresh_direct_session": True,
        "physics_steps": 0,
        "interval_counts": list(pass_evidence.interval_counts),
        "total_interval_count": sum(pass_evidence.interval_counts),
        "route_configuration_count": pass_evidence.route_configuration_count,
        "semantic_snapshot_count": len(pass_evidence.semantic_snapshots),
        "query_count": pass_evidence.query_count,
        "scientific_failure_count": len(pass_evidence.scientific_failures),
        "failure_summary": _failure_summary(pass_evidence.scientific_failures),
        "overall_result": pass_evidence.overall_result,
    }


def build_b3_2_artifact(repository_root: Path) -> JsonObject:
    repository_root = repository_root.resolve()
    runtime = verify_repository_and_runtime(repository_root)
    inputs = load_frozen_inputs(repository_root)
    pairs = build_collision_pair_inventory(inputs.self_collision_pairs)
    projected_total = (
        EXPECTED_COARSE_QUERY_COUNT
        + EXPECTED_FINE_QUERY_COUNT
        + EXPECTED_FINE_QUERY_COUNT
    )
    enforce_protocol_caps(
        route_segments=7,
        fine_route_configurations=EXPECTED_FINE_ROUTE_CONFIGURATIONS,
        fine_semantic_snapshots=EXPECTED_FINE_SEMANTIC_SNAPSHOTS,
        pairs_per_snapshot=len(pairs),
        total_queries=projected_total,
    )
    if projected_total != EXPECTED_TOTAL_QUERY_COUNT or projected_total > MAX_TOTAL_COLLISION_QUERIES:
        raise B3_2_InfrastructureError("Complete protocol query accounting failed")

    coarse = run_qualification_pass(
        inputs,
        pairs,
        pass_name=PassName.COARSE,
        refinement_factor=1,
    )
    fine_first = run_qualification_pass(
        inputs,
        pairs,
        pass_name=PassName.FINE_PASS_1,
        refinement_factor=2,
    )
    fine_second = run_qualification_pass(
        inputs,
        pairs,
        pass_name=PassName.FINE_PASS_2,
        refinement_factor=2,
    )
    if (
        coarse.query_count,
        fine_first.query_count,
        fine_second.query_count,
    ) != (
        EXPECTED_COARSE_QUERY_COUNT,
        EXPECTED_FINE_QUERY_COUNT,
        EXPECTED_FINE_QUERY_COUNT,
    ):
        raise B3_2_InfrastructureError("Exact pass query counts changed")
    reproducibility = compare_fine_passes(fine_first, fine_second)
    nested = compare_coarse_to_fine(coarse, fine_first)
    aggregate = aggregate_authoritative_fine(fine_first)

    source_path = Path(__file__).resolve()
    runner_path = repository_root / "scripts/prototype5/run_scene_collision_route_qualification_b3_2.py"
    test_path = repository_root / "tests/prototype5/test_scene_collision_route_qualification_b3_2.py"
    for path in (source_path, runner_path, test_path):
        if not path.is_file():
            raise B3_2_InfrastructureError(f"Missing B3.2 implementation file: {path.name}")

    result = _result_json(fine_first.scientific_failures)
    if result["overall_result"] != fine_first.overall_result:
        raise B3_2_InfrastructureError("Overall result vocabulary changed")
    artifact: JsonObject = {
        "schema_identifier": SCHEMA_IDENTIFIER,
        "schema_version": SCHEMA_VERSION,
        "gate_identifier": GATE_IDENTIFIER,
        "provenance": {
            **runtime,
            "specification": {
                "identity": f"repository/{SPECIFICATION_PATH.as_posix()}",
                "freeze_commit": SPECIFICATION_FREEZE_COMMIT,
                "git_blob": SPECIFICATION_GIT_BLOB,
                "sha256": SPECIFICATION_SHA256,
            },
            "source_sha256": b31.sha256_file(source_path),
            "runner_sha256": b31.sha256_file(runner_path),
            "tests_sha256": b31.sha256_file(test_path),
        },
        "frozen_input_contract": {
            "artifact_sha256": inputs.input_hashes,
            "route_state_order": list(EXPECTED_ROUTE_STATES),
            "home_joint_vector": list(inputs.route[0].joint_vector),
            "route_inputs_modified": False,
            "predecessor_evidence_regenerated": False,
        },
        "numeric_contact_contract": {
            "numerical_contact_epsilon_m": NUMERICAL_CONTACT_EPSILON_M,
            "closest_point_query_horizon_m": CLOSEST_POINT_QUERY_HORIZON_M,
            "epsilon_meaning": "NUMERICAL_ZERO_CLASSIFIER_ONLY",
            "classifications": [item.value for item in DistanceClassification],
            "decision_matrix": {
                policy.value: {
                    classification.value: decide_contact(policy, classification)
                    for classification in DistanceClassification
                }
                for policy in PairPolicy
            },
        },
        "interpolation_contract": {
            "formula": "q(t) = q0 + t * (q1 - q0)",
            "base_max_joint_step_rad": BASE_MAX_JOINT_STEP_RAD,
            "coarse_interval_counts": list(EXPECTED_COARSE_INTERVALS),
            "fine_interval_counts": list(EXPECTED_FINE_INTERVALS),
            "coarse_total_intervals": sum(EXPECTED_COARSE_INTERVALS),
            "fine_total_intervals": sum(EXPECTED_FINE_INTERVALS),
            "coarse_route_configuration_count": coarse.route_configuration_count,
            "fine_route_configuration_count": fine_first.route_configuration_count,
            "coarse_semantic_snapshot_count": len(coarse.semantic_snapshots),
            "fine_semantic_snapshot_count": len(fine_first.semantic_snapshots),
            "fine_grid_nests_coarse_grid_exactly": True,
        },
        "collision_pair_inventory": _pair_inventory_json(pairs),
        "component_phase_contract": _component_phase_contract_json(),
        "coarse_sensitivity_summary": {
            **_pass_summary(coarse),
            "nested_authoritative_comparison": nested,
        },
        "authoritative_fine_route": {
            **_pass_summary(fine_first),
            "semantic_snapshots": list(fine_first.semantic_snapshots),
        },
        "reproducibility_summary": reproducibility,
        "aggregate_clearance_summary": aggregate,
        "result": result,
        "claim_boundaries": {
            "maximum_pass_claim": MAXIMUM_PASS_CLAIM,
            "scientific_fail_claim": SCIENTIFIC_FAIL_CLAIM,
            "discrete_sampling_limitation": DISCRETE_SAMPLING_LIMITATION,
            "continuous_collision_freedom_claimed": False,
            "dynamic_executability_claimed": False,
            "physical_robot_safety_claimed": False,
            "industrial_certification_claimed": False,
            "sim_to_real_validity_claimed": False,
        },
    }
    validate_canonical_artifact(artifact)
    return artifact


def _canonical_mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise B3_2_InfrastructureError(f"{field} must be a mapping")
    return value


def _canonical_integer(
    mapping: Mapping[str, object],
    key: str,
    field: str,
) -> int:
    if key not in mapping:
        raise B3_2_InfrastructureError(f"Missing required field: {field}.{key}")
    return _integer(mapping[key], f"{field}.{key}")


def _validate_aggregate_minimum(
    value: object,
    field: str,
    *,
    required: bool,
) -> None:
    if value is None:
        if required:
            raise B3_2_InfrastructureError(f"{field} cannot be null")
        return
    minimum = _canonical_mapping(value, field)
    expected_fields = {
        "signed_distance_m",
        "semantic_snapshot_index",
        "pair_index",
        "pair_id",
    }
    if set(minimum) != expected_fields:
        raise B3_2_InfrastructureError(f"{field} schema changed")
    finite_float(minimum["signed_distance_m"], f"{field}.signed_distance_m")
    semantic_index = _integer(
        minimum["semantic_snapshot_index"],
        f"{field}.semantic_snapshot_index",
    )
    pair_index = _integer(minimum["pair_index"], f"{field}.pair_index")
    pair_id = minimum["pair_id"]
    if not 0 <= semantic_index < EXPECTED_FINE_SEMANTIC_SNAPSHOTS:
        raise B3_2_InfrastructureError(f"{field} semantic index is invalid")
    if not 0 <= pair_index < EXPECTED_PAIR_QUERIES_PER_SEMANTIC_SNAPSHOT:
        raise B3_2_InfrastructureError(f"{field} pair index is invalid")
    if not isinstance(pair_id, str) or not pair_id:
        raise B3_2_InfrastructureError(f"{field} pair ID is invalid")


def _canonical_sha256(value: object, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise B3_2_InfrastructureError(f"{field} must be a lowercase SHA-256")
    return value


def _validate_provenance(provenance: Mapping[str, object]) -> None:
    specification = _canonical_mapping(
        provenance.get("specification"),
        "provenance.specification",
    )
    expected_specification = {
        "identity": f"repository/{SPECIFICATION_PATH.as_posix()}",
        "freeze_commit": SPECIFICATION_FREEZE_COMMIT,
        "git_blob": SPECIFICATION_GIT_BLOB,
        "sha256": SPECIFICATION_SHA256,
    }
    if dict(specification) != expected_specification:
        raise B3_2_InfrastructureError("Canonical specification provenance changed")
    for field in ("source_sha256", "runner_sha256", "tests_sha256"):
        if field not in provenance:
            raise B3_2_InfrastructureError(f"Missing required field: provenance.{field}")
        _canonical_sha256(provenance[field], f"provenance.{field}")
    if provenance.get("repository_root") != "repository/":
        raise B3_2_InfrastructureError("Canonical repository identity changed")
    if provenance.get("lineage_contract") != (
        "CURRENT_HEAD_DESCENDS_FROM_ALL_FROZEN_PREDECESSORS"
    ):
        raise B3_2_InfrastructureError("Canonical lineage contract changed")
    if provenance.get("required_ancestor_commits") != [
        B3_1_COMMIT,
        R1_1_COMMIT,
        SPECIFICATION_FREEZE_COMMIT,
    ]:
        raise B3_2_InfrastructureError("Canonical lineage commits changed")

    python_provenance = _canonical_mapping(
        provenance.get("python"),
        "provenance.python",
    )
    if set(python_provenance) != {"implementation", "version"} or not all(
        isinstance(python_provenance[field], str) and python_provenance[field]
        for field in ("implementation", "version")
    ):
        raise B3_2_InfrastructureError("Canonical Python provenance is malformed")
    pybullet_provenance = _canonical_mapping(
        provenance.get("pybullet"),
        "provenance.pybullet",
    )
    expected_pybullet = {
        "package_version": b31.PYBULLET_PACKAGE_VERSION,
        "api_version": b31.PYBULLET_API_VERSION,
        "binary_sha256": b31.PYBULLET_BINARY_SHA256,
        "urdf_identity": f"pybullet_data/{b31.KUKA_URDF_RELATIVE.as_posix()}",
        "urdf_sha256": b31.KUKA_URDF_SHA256,
        "kuka_asset_manifest_sha256": b31.KUKA_ASSET_MANIFEST_SHA256,
    }
    for field, expected in expected_pybullet.items():
        if pybullet_provenance.get(field) != expected:
            raise B3_2_InfrastructureError(
                f"Canonical PyBullet provenance changed: {field}"
            )
    binary_identity = pybullet_provenance.get("binary_identity")
    if (
        set(pybullet_provenance) != {*expected_pybullet, "binary_identity"}
        or not isinstance(binary_identity, str)
        or not binary_identity.startswith("python_environment/")
        or len(binary_identity) == len("python_environment/")
    ):
        raise B3_2_InfrastructureError("Canonical PyBullet binary identity is malformed")
    qualified_wheel = _canonical_mapping(
        provenance.get("qualified_ci_wheel"),
        "provenance.qualified_ci_wheel",
    )
    if dict(qualified_wheel) != {
        "identity": f"repository/{CI_WHEEL_PATH.as_posix()}",
        "sha256": CI_WHEEL_SHA256,
    }:
        raise B3_2_InfrastructureError("Canonical CI wheel provenance changed")


def _validate_frozen_contract_sections(
    frozen_inputs: Mapping[str, object],
    numeric: Mapping[str, object],
    interpolation: Mapping[str, object],
) -> None:
    artifact_hashes = _canonical_mapping(
        frozen_inputs.get("artifact_sha256"),
        "frozen_input_contract.artifact_sha256",
    )
    if dict(artifact_hashes) != {
        B1_2_ARTIFACT.as_posix(): B1_2_ARTIFACT_SHA256,
        B2_ARTIFACT.as_posix(): B2_ARTIFACT_SHA256,
        B3_1_ARTIFACT.as_posix(): B3_1_ARTIFACT_SHA256,
    }:
        raise B3_2_InfrastructureError("Canonical frozen-input hashes changed")
    home = frozen_inputs.get("home_joint_vector")
    if not isinstance(home, list) or tuple(home) != EXPECTED_HOME_JOINT_VECTOR:
        raise B3_2_InfrastructureError("Canonical frozen HOME changed")
    if frozen_inputs.get("route_state_order") != list(EXPECTED_ROUTE_STATES):
        raise B3_2_InfrastructureError("Canonical frozen route order changed")
    if frozen_inputs.get("route_inputs_modified") is not False:
        raise B3_2_InfrastructureError("Canonical route mutation flag changed")
    if frozen_inputs.get("predecessor_evidence_regenerated") is not False:
        raise B3_2_InfrastructureError("Canonical predecessor mutation flag changed")

    expected_numeric = {
        "numerical_contact_epsilon_m": NUMERICAL_CONTACT_EPSILON_M,
        "closest_point_query_horizon_m": CLOSEST_POINT_QUERY_HORIZON_M,
        "epsilon_meaning": "NUMERICAL_ZERO_CLASSIFIER_ONLY",
        "classifications": [item.value for item in DistanceClassification],
        "decision_matrix": {
            policy.value: {
                classification.value: decide_contact(policy, classification)
                for classification in DistanceClassification
            }
            for policy in PairPolicy
        },
    }
    if dict(numeric) != expected_numeric:
        raise B3_2_InfrastructureError("Canonical numerical contact contract changed")

    expected_interpolation = {
        "formula": "q(t) = q0 + t * (q1 - q0)",
        "base_max_joint_step_rad": BASE_MAX_JOINT_STEP_RAD,
        "coarse_interval_counts": list(EXPECTED_COARSE_INTERVALS),
        "fine_interval_counts": list(EXPECTED_FINE_INTERVALS),
        "coarse_total_intervals": sum(EXPECTED_COARSE_INTERVALS),
        "fine_total_intervals": sum(EXPECTED_FINE_INTERVALS),
        "coarse_route_configuration_count": EXPECTED_COARSE_ROUTE_CONFIGURATIONS,
        "fine_route_configuration_count": EXPECTED_FINE_ROUTE_CONFIGURATIONS,
        "coarse_semantic_snapshot_count": EXPECTED_COARSE_SEMANTIC_SNAPSHOTS,
        "fine_semantic_snapshot_count": EXPECTED_FINE_SEMANTIC_SNAPSHOTS,
        "fine_grid_nests_coarse_grid_exactly": True,
    }
    if dict(interpolation) != expected_interpolation:
        raise B3_2_InfrastructureError("Canonical interpolation contract changed")


def _validate_failure_count_summary(
    value: object,
    field: str,
) -> tuple[JsonObject, int]:
    summary = _canonical_mapping(value, field)
    if set(summary) != set(SCIENTIFIC_FAILURE_CODES):
        raise B3_2_InfrastructureError(f"{field} schema changed")
    normalized: JsonObject = {}
    total = 0
    for code in SCIENTIFIC_FAILURE_CODES:
        count = _integer(summary[code], f"{field}.{code}")
        if count < 0:
            raise B3_2_InfrastructureError(f"{field}.{code} is negative")
        normalized[code] = count
        total += count
    return normalized, total


def _validate_coarse_summary(coarse: Mapping[str, object]) -> None:
    expected = {
        "pass_name": PassName.COARSE.value,
        "fresh_direct_session": True,
        "physics_steps": 0,
        "interval_counts": list(EXPECTED_COARSE_INTERVALS),
        "total_interval_count": sum(EXPECTED_COARSE_INTERVALS),
        "route_configuration_count": EXPECTED_COARSE_ROUTE_CONFIGURATIONS,
        "semantic_snapshot_count": EXPECTED_COARSE_SEMANTIC_SNAPSHOTS,
        "query_count": EXPECTED_COARSE_QUERY_COUNT,
    }
    for field, expected_value in expected.items():
        if coarse.get(field) != expected_value:
            raise B3_2_InfrastructureError(f"coarse_sensitivity_summary.{field} changed")
    summary, total = _validate_failure_count_summary(
        coarse.get("failure_summary"),
        "coarse_sensitivity_summary.failure_summary",
    )
    failure_count = _canonical_integer(
        coarse,
        "scientific_failure_count",
        "coarse_sensitivity_summary",
    )
    if failure_count != total or dict(coarse.get("failure_summary", {})) != summary:
        raise B3_2_InfrastructureError("Coarse scientific failure accounting changed")
    expected_result = PASS_RESULT if failure_count == 0 else FAIL_RESULT
    if coarse.get("overall_result") != expected_result:
        raise B3_2_InfrastructureError("Coarse scientific result is inconsistent")
    nested = _canonical_mapping(
        coarse.get("nested_authoritative_comparison"),
        "coarse_sensitivity_summary.nested_authoritative_comparison",
    )
    if dict(nested) != {
        "nested_semantic_snapshot_comparison_count": EXPECTED_COARSE_SEMANTIC_SNAPSHOTS,
        "nested_decision_comparison_count": EXPECTED_COARSE_QUERY_COUNT,
        "decision_disagreement_count": 0,
        "coarse_grid_exactly_nested": True,
    }:
        raise B3_2_InfrastructureError("Canonical coarse/fine sensitivity changed")


def _validate_reproducibility_summary(
    reproducibility: Mapping[str, object],
    expected_result: str,
) -> None:
    exact_fields = {
        "repeat_count": ROUTE_REPRODUCIBILITY_REPEAT_COUNT,
        "semantic_snapshot_count": EXPECTED_FINE_SEMANTIC_SNAPSHOTS,
        "compared_observation_count": EXPECTED_FINE_QUERY_COUNT,
        "fine_pass_2_query_count": EXPECTED_FINE_QUERY_COUNT,
        "distance_tolerance_m": NUMERICAL_CONTACT_EPSILON_M,
        "found_state_mismatch_count": 0,
        "classification_mismatch_count": 0,
        "decision_mismatch_count": 0,
        "lower_bound_mismatch_count": 0,
        "distance_tolerance_violation_count": 0,
        "scientific_failure_mismatch": False,
        "overall_result_mismatch": False,
        "fresh_independent_direct_sessions": True,
        "fine_pass_2_result": expected_result,
    }
    for field, expected_value in exact_fields.items():
        if reproducibility.get(field) != expected_value:
            raise B3_2_InfrastructureError(
                f"reproducibility_summary.{field} changed"
            )
    compared_found = _canonical_integer(
        reproducibility,
        "compared_found_distance_count",
        "reproducibility_summary",
    )
    if not 0 <= compared_found <= EXPECTED_FINE_QUERY_COUNT:
        raise B3_2_InfrastructureError("Reproducibility found count is invalid")
    spread = finite_float(
        reproducibility.get("maximum_found_distance_spread_m"),
        "reproducibility_summary.maximum_found_distance_spread_m",
    )
    if not 0.0 <= spread <= NUMERICAL_CONTACT_EPSILON_M:
        raise B3_2_InfrastructureError("Reproducibility distance spread is invalid")


def _validate_component_phase_contract(contract: Mapping[str, object]) -> None:
    if dict(contract) != _component_phase_contract_json():
        raise B3_2_InfrastructureError("Canonical component phase contract changed")


def _validate_claim_boundaries(claims: Mapping[str, object]) -> None:
    expected = {
        "maximum_pass_claim": MAXIMUM_PASS_CLAIM,
        "scientific_fail_claim": SCIENTIFIC_FAIL_CLAIM,
        "discrete_sampling_limitation": DISCRETE_SAMPLING_LIMITATION,
        "continuous_collision_freedom_claimed": False,
        "dynamic_executability_claimed": False,
        "physical_robot_safety_claimed": False,
        "industrial_certification_claimed": False,
        "sim_to_real_validity_claimed": False,
    }
    if dict(claims) != expected:
        raise B3_2_InfrastructureError("Canonical claim boundaries changed")


def _validate_collision_pair_inventory(
    inventory: Mapping[str, object],
) -> tuple[tuple[str, PairCategory, str | None], ...]:
    if set(inventory) != {
        "category_order",
        "robot_body_order",
        "environment_order",
        "category_counts",
        "total_pair_count",
        "pairs",
    }:
        raise B3_2_InfrastructureError("Collision-pair inventory schema changed")
    if inventory.get("category_order") != [item.value for item in PairCategory]:
        raise B3_2_InfrastructureError("Collision-pair category order changed")
    if inventory.get("robot_body_order") != list(ROBOT_LINK_INDICES):
        raise B3_2_InfrastructureError("Collision-pair robot order changed")
    if inventory.get("environment_order") != list(ENVIRONMENT_SEMANTIC_IDS):
        raise B3_2_InfrastructureError("Collision-pair environment order changed")
    expected_counts = {
        PairCategory.ROBOT_SELF.value: 21,
        PairCategory.ROBOT_ENVIRONMENT.value: 48,
        PairCategory.COMPONENT_ROBOT.value: 8,
        PairCategory.COMPONENT_ENVIRONMENT.value: 6,
    }
    counts = _canonical_mapping(
        inventory.get("category_counts"),
        "collision_pair_inventory.category_counts",
    )
    if dict(counts) != expected_counts or inventory.get("total_pair_count") != 83:
        raise B3_2_InfrastructureError("Collision-pair inventory counts changed")
    raw_pairs = inventory.get("pairs")
    if not isinstance(raw_pairs, list) or len(raw_pairs) != 83:
        raise B3_2_InfrastructureError("Collision-pair inventory cardinality changed")

    validated: list[tuple[str, PairCategory, str | None]] = []
    pair_ids: set[str] = set()
    category_counts = {category: 0 for category in PairCategory}
    for expected_index, raw_pair in enumerate(raw_pairs):
        pair = _canonical_mapping(
            raw_pair,
            f"collision_pair_inventory.pairs[{expected_index}]",
        )
        if set(pair) != {"pair_index", "pair_id", "category", "query_signature"}:
            raise B3_2_InfrastructureError("Collision-pair record schema changed")
        if _canonical_integer(
            pair,
            "pair_index",
            f"collision_pair_inventory.pairs[{expected_index}]",
        ) != expected_index:
            raise B3_2_InfrastructureError("Collision-pair indexes are not canonical")
        pair_id = pair.get("pair_id")
        if not isinstance(pair_id, str) or not pair_id or pair_id in pair_ids:
            raise B3_2_InfrastructureError("Collision-pair ID is empty or duplicated")
        pair_ids.add(pair_id)
        try:
            category = PairCategory(str(pair.get("category")))
        except ValueError as exc:
            raise B3_2_InfrastructureError("Collision-pair category is invalid") from exc
        if expected_index < 21:
            expected_category = PairCategory.ROBOT_SELF
        elif expected_index < 69:
            expected_category = PairCategory.ROBOT_ENVIRONMENT
        elif expected_index < 77:
            expected_category = PairCategory.COMPONENT_ROBOT
        else:
            expected_category = PairCategory.COMPONENT_ENVIRONMENT
        if category is not expected_category:
            raise B3_2_InfrastructureError("Collision-pair category sequence changed")
        category_counts[category] += 1
        parts = pair_id.split(":")
        environment: str | None = None
        try:
            if category is PairCategory.ROBOT_SELF:
                if len(parts) != 3 or parts[0] != "robot_self":
                    raise ValueError
                first_link, second_link = int(parts[1]), int(parts[2])
                if (
                    pair_id != f"robot_self:{first_link}:{second_link}"
                    or first_link not in ROBOT_LINK_INDICES
                    or second_link not in ROBOT_LINK_INDICES
                    or first_link >= second_link
                ):
                    raise ValueError
                signature = {
                    "bodyA": "robot",
                    "bodyB": "robot",
                    "linkIndexA": first_link,
                    "linkIndexB": second_link,
                }
            elif category is PairCategory.ROBOT_ENVIRONMENT:
                offset = expected_index - 21
                robot_link = ROBOT_LINK_INDICES[offset // len(ENVIRONMENT_SEMANTIC_IDS)]
                environment = ENVIRONMENT_SEMANTIC_IDS[
                    offset % len(ENVIRONMENT_SEMANTIC_IDS)
                ]
                if pair_id != f"robot_environment:{robot_link}:{environment}":
                    raise ValueError
                signature = {
                    "bodyA": "robot",
                    "bodyB": environment,
                    "linkIndexA": robot_link,
                    "linkIndexB": -1,
                }
            elif category is PairCategory.COMPONENT_ROBOT:
                robot_link = ROBOT_LINK_INDICES[expected_index - 69]
                if pair_id != f"component_robot:{robot_link}":
                    raise ValueError
                signature = {
                    "bodyA": "component",
                    "bodyB": "robot",
                    "linkIndexA": -1,
                    "linkIndexB": robot_link,
                }
            else:
                environment = ENVIRONMENT_SEMANTIC_IDS[expected_index - 77]
                if pair_id != f"component_environment:{environment}":
                    raise ValueError
                signature = {
                    "bodyA": "component",
                    "bodyB": environment,
                    "linkIndexA": -1,
                    "linkIndexB": -1,
                }
        except (ValueError, IndexError) as exc:
            raise B3_2_InfrastructureError(
                f"Collision-pair identity is invalid at index {expected_index}"
            ) from exc
        signature.update(
            {
                "distance_m": CLOSEST_POINT_QUERY_HORIZON_M,
                "physics_client_id": "EXPLICIT_PASS_LOCAL",
            }
        )
        stored_signature = _canonical_mapping(
            pair.get("query_signature"),
            f"collision_pair_inventory.pairs[{expected_index}].query_signature",
        )
        if dict(stored_signature) != signature:
            raise B3_2_InfrastructureError(
                f"Collision-pair query signature changed at index {expected_index}"
            )
        validated.append((pair_id, category, environment))
    if {category.value: count for category, count in category_counts.items()} != expected_counts:
        raise B3_2_InfrastructureError("Collision-pair derived counts changed")
    return tuple(validated)


def _expected_fine_semantic_sequence() -> tuple[
    tuple[int, int, int, int, str, ComponentPhase, BoundarySnapshot],
    ...,
]:
    sequence: list[
        tuple[int, int, int, int, str, ComponentPhase, BoundarySnapshot]
    ] = []
    route_configuration_index = 0
    for segment_index, interval_count in enumerate(EXPECTED_FINE_INTERVALS):
        first_sample = 0 if segment_index == 0 else 1
        for sample_index in range(first_sample, interval_count + 1):
            if sample_index == 0:
                route_state = EXPECTED_ROUTE_STATES[segment_index]
            elif sample_index == interval_count:
                route_state = EXPECTED_ROUTE_STATES[segment_index + 1]
            else:
                route_state = "INTERPOLATED"
            if route_state == "SOURCE_PICK":
                phase_boundaries = (
                    (ComponentPhase.ATTACHMENT_BOUNDARY, BoundarySnapshot.PRE),
                    (ComponentPhase.ATTACHMENT_BOUNDARY, BoundarySnapshot.POST),
                )
            elif route_state == "DESTINATION_PLACE":
                phase_boundaries = (
                    (ComponentPhase.RELEASE_BOUNDARY, BoundarySnapshot.PRE),
                    (ComponentPhase.RELEASE_BOUNDARY, BoundarySnapshot.POST),
                )
            elif segment_index <= 1:
                phase_boundaries = (
                    (ComponentPhase.SOURCE_SUPPORTED, BoundarySnapshot.NONE),
                )
            elif segment_index <= 4:
                phase_boundaries = ((ComponentPhase.CARRIED, BoundarySnapshot.NONE),)
            else:
                phase_boundaries = (
                    (ComponentPhase.DESTINATION_SUPPORTED, BoundarySnapshot.NONE),
                )
            for phase, boundary in phase_boundaries:
                sequence.append(
                    (
                        route_configuration_index,
                        segment_index,
                        sample_index,
                        interval_count,
                        route_state,
                        phase,
                        boundary,
                    )
                )
            route_configuration_index += 1
    if (
        route_configuration_index != EXPECTED_FINE_ROUTE_CONFIGURATIONS
        or len(sequence) != EXPECTED_FINE_SEMANTIC_SNAPSHOTS
    ):
        raise B3_2_InfrastructureError(
            "Frozen fine semantic-sequence construction changed"
        )
    return tuple(sequence)


def validate_canonical_artifact(artifact: Mapping[str, object]) -> None:
    """Validate canonical evidence structure without reevaluating its physics."""

    artifact = _canonical_mapping(artifact, "artifact")
    identities = (
        ("schema_identifier", SCHEMA_IDENTIFIER),
        ("schema_version", SCHEMA_VERSION),
        ("gate_identifier", GATE_IDENTIFIER),
    )
    for field, expected in identities:
        if artifact.get(field) != expected:
            raise B3_2_InfrastructureError(f"Canonical artifact {field} mismatch")
    sections = {
        field: _canonical_mapping(artifact.get(field), field)
        for field in REQUIRED_ARTIFACT_SECTIONS
        if field in artifact
    }
    if tuple(sections) != REQUIRED_ARTIFACT_SECTIONS:
        missing = [field for field in REQUIRED_ARTIFACT_SECTIONS if field not in artifact]
        raise B3_2_InfrastructureError(
            f"Canonical artifact required sections are incomplete: {missing}"
        )
    _validate_provenance(sections["provenance"])
    _validate_frozen_contract_sections(
        sections["frozen_input_contract"],
        sections["numeric_contact_contract"],
        sections["interpolation_contract"],
    )
    canonical_pairs = _validate_collision_pair_inventory(
        sections["collision_pair_inventory"]
    )
    _validate_component_phase_contract(sections["component_phase_contract"])
    _validate_coarse_summary(sections["coarse_sensitivity_summary"])
    _validate_claim_boundaries(sections["claim_boundaries"])

    fine = sections["authoritative_fine_route"]
    expected_fine_fields = (
        ("pass_name", PassName.FINE_PASS_1.value),
        ("route_configuration_count", EXPECTED_FINE_ROUTE_CONFIGURATIONS),
        ("semantic_snapshot_count", EXPECTED_FINE_SEMANTIC_SNAPSHOTS),
        ("query_count", EXPECTED_FINE_QUERY_COUNT),
    )
    for field, expected in expected_fine_fields:
        if fine.get(field) != expected:
            raise B3_2_InfrastructureError(
                f"authoritative_fine_route.{field} mismatch"
            )
    snapshots = fine.get("semantic_snapshots")
    if not isinstance(snapshots, list) or len(snapshots) != EXPECTED_FINE_SEMANTIC_SNAPSHOTS:
        raise B3_2_InfrastructureError(
            "authoritative_fine_route.semantic_snapshots cardinality changed"
        )
    valid_classifications = {item.value for item in DistanceClassification}
    valid_permissions = {item.value for item in PairPolicy}
    valid_decisions = {"PASS", *SCIENTIFIC_FAILURE_CODES}
    derived_failures: list[JsonObject] = []
    aggregate_total = 0
    aggregate_found = 0
    aggregate_censored = 0
    aggregate_contact_band = 0
    aggregate_material_penetration = 0
    aggregate_failure_counts = {code: 0 for code in SCIENTIFIC_FAILURE_CODES}
    aggregate_minimum: JsonObject | None = None
    aggregate_forbidden_minimum: JsonObject | None = None
    aggregate_forbidden_found = 0
    expected_semantic_sequence = _expected_fine_semantic_sequence()
    for expected_semantic_index, raw_snapshot in enumerate(snapshots):
        snapshot = _canonical_mapping(
            raw_snapshot,
            f"authoritative_fine_route.semantic_snapshots[{expected_semantic_index}]",
        )
        missing_snapshot_fields = [
            field
            for field in REQUIRED_SEMANTIC_SNAPSHOT_FIELDS
            if field not in snapshot
        ]
        if missing_snapshot_fields:
            raise B3_2_InfrastructureError(
                f"Canonical semantic snapshot fields are incomplete: {missing_snapshot_fields}"
            )
        snapshot_field = (
            f"authoritative_fine_route.semantic_snapshots[{expected_semantic_index}]"
        )
        route_configuration_index = _canonical_integer(
            snapshot,
            "route_configuration_index",
            snapshot_field,
        )
        segment_index = _canonical_integer(snapshot, "segment_index", snapshot_field)
        segment_sample_index = _canonical_integer(
            snapshot,
            "segment_sample_index",
            snapshot_field,
        )
        segment_interval_count = _canonical_integer(
            snapshot,
            "segment_interval_count",
            snapshot_field,
        )
        if not 0 <= route_configuration_index < EXPECTED_FINE_ROUTE_CONFIGURATIONS:
            raise B3_2_InfrastructureError(
                "Authoritative route configuration index is invalid"
            )
        if not 0 <= segment_index < len(EXPECTED_FINE_INTERVALS):
            raise B3_2_InfrastructureError("Authoritative segment index is invalid")
        if segment_interval_count != EXPECTED_FINE_INTERVALS[segment_index]:
            raise B3_2_InfrastructureError(
                "Authoritative segment interval count changed"
            )
        if not 0 <= segment_sample_index <= segment_interval_count:
            raise B3_2_InfrastructureError(
                "Authoritative segment sample index is invalid"
            )
        alpha = finite_float(snapshot["alpha"], f"{snapshot_field}.alpha")
        if alpha != float(Fraction(segment_sample_index, segment_interval_count)):
            raise B3_2_InfrastructureError("Authoritative interpolation alpha is invalid")
        route_state = snapshot["route_state"]
        if not isinstance(route_state, str) or route_state not in {
            *EXPECTED_ROUTE_STATES,
            "INTERPOLATED",
        }:
            raise B3_2_InfrastructureError("Authoritative route state is invalid")
        try:
            snapshot_phase = ComponentPhase(str(snapshot["phase"]))
            snapshot_boundary = BoundarySnapshot(str(snapshot["boundary_snapshot"]))
        except ValueError as exc:
            raise B3_2_InfrastructureError(
                "Authoritative phase/boundary state is invalid"
            ) from exc
        if (snapshot_phase, snapshot_boundary) not in {
            (ComponentPhase.SOURCE_SUPPORTED, BoundarySnapshot.NONE),
            (ComponentPhase.ATTACHMENT_BOUNDARY, BoundarySnapshot.PRE),
            (ComponentPhase.ATTACHMENT_BOUNDARY, BoundarySnapshot.POST),
            (ComponentPhase.CARRIED, BoundarySnapshot.NONE),
            (ComponentPhase.RELEASE_BOUNDARY, BoundarySnapshot.PRE),
            (ComponentPhase.RELEASE_BOUNDARY, BoundarySnapshot.POST),
            (ComponentPhase.DESTINATION_SUPPORTED, BoundarySnapshot.NONE),
        }:
            raise B3_2_InfrastructureError(
                "Authoritative phase/boundary combination is invalid"
            )
        (
            expected_route_configuration_index,
            expected_segment_index,
            expected_segment_sample_index,
            expected_segment_interval_count,
            expected_route_state,
            expected_phase,
            expected_boundary,
        ) = expected_semantic_sequence[expected_semantic_index]
        if (
            route_configuration_index,
            segment_index,
            segment_sample_index,
            segment_interval_count,
            route_state,
            snapshot_phase,
            snapshot_boundary,
        ) != (
            expected_route_configuration_index,
            expected_segment_index,
            expected_segment_sample_index,
            expected_segment_interval_count,
            expected_route_state,
            expected_phase,
            expected_boundary,
        ):
            raise B3_2_InfrastructureError(
                "Authoritative semantic phase sequence changed"
            )
        joint_vector = snapshot["joint_vector"]
        if not isinstance(joint_vector, list) or len(joint_vector) != 7:
            raise B3_2_InfrastructureError("Authoritative joint vector is malformed")
        for joint_index, value in enumerate(joint_vector):
            finite_float(value, f"{snapshot_field}.joint_vector[{joint_index}]")
        if expected_boundary is BoundarySnapshot.POST:
            previous_snapshot = _canonical_mapping(
                snapshots[expected_semantic_index - 1],
                f"authoritative_fine_route.semantic_snapshots[{expected_semantic_index - 1}]",
            )
            if (
                previous_snapshot.get("route_configuration_index")
                != route_configuration_index
                or previous_snapshot.get("joint_vector") != joint_vector
            ):
                raise B3_2_InfrastructureError(
                    "Boundary PRE/POST snapshots do not preserve identical robot q"
                )
        component_pose = _canonical_mapping(
            snapshot["component_pose"],
            f"{snapshot_field}.component_pose",
        )
        if set(component_pose) != {"position_m", "quaternion_xyzw"}:
            raise B3_2_InfrastructureError("Authoritative component pose schema changed")
        for field, length in (("position_m", 3), ("quaternion_xyzw", 4)):
            values = component_pose[field]
            if not isinstance(values, list) or len(values) != length:
                raise B3_2_InfrastructureError(
                    f"Authoritative component pose {field} is malformed"
                )
            for value_index, value in enumerate(values):
                finite_float(
                    value,
                    f"{snapshot_field}.component_pose.{field}[{value_index}]",
                )
        semantic_index = _canonical_integer(
            snapshot,
            "semantic_snapshot_index",
            f"authoritative_fine_route.semantic_snapshots[{expected_semantic_index}]",
        )
        if semantic_index != expected_semantic_index:
            raise B3_2_InfrastructureError(
                "Authoritative semantic snapshot indexes are not canonical"
            )
        observations = snapshot.get("observations")
        if not isinstance(observations, list) or len(observations) != EXPECTED_PAIR_QUERIES_PER_SEMANTIC_SNAPSHOT:
            raise B3_2_InfrastructureError(
                f"Authoritative snapshot {expected_semantic_index} observation count changed"
            )
        for expected_pair_index, raw_observation in enumerate(observations):
            observation = _canonical_mapping(
                raw_observation,
                f"authoritative snapshot {expected_semantic_index} observation {expected_pair_index}",
            )
            missing_fields = [
                field for field in REQUIRED_OBSERVATION_FIELDS if field not in observation
            ]
            if missing_fields:
                raise B3_2_InfrastructureError(
                    f"Canonical observation fields are incomplete: {missing_fields}"
                )
            pair_index = _integer(
                observation["pair_index"],
                f"authoritative snapshot {expected_semantic_index} pair_index",
            )
            if pair_index != expected_pair_index:
                raise B3_2_InfrastructureError(
                    "Authoritative observation pair indexes are not canonical"
                )
            pair_id = observation["pair_id"]
            found = observation["found"]
            if not isinstance(pair_id, str) or not pair_id:
                raise B3_2_InfrastructureError("Canonical observation pair ID is invalid")
            if not isinstance(found, bool):
                raise B3_2_InfrastructureError("Canonical observation found flag is invalid")
            canonical_pair_id, pair_category, environment = canonical_pairs[pair_index]
            if pair_id != canonical_pair_id:
                raise B3_2_InfrastructureError(
                    "Canonical observation pair ID does not match its inventory index"
                )
            if found:
                signed_distance = finite_float(
                    observation["signed_distance_m"],
                    "canonical observation signed distance",
                )
                if observation["separation_lower_bound_m"] is not None:
                    raise B3_2_InfrastructureError(
                        "Found canonical observation has a separation lower bound"
                    )
                expected_classification = classify_signed_distance(signed_distance)
                aggregate_found += 1
                minimum_item: JsonObject = {
                    "signed_distance_m": signed_distance,
                    "semantic_snapshot_index": semantic_index,
                    "pair_index": pair_index,
                    "pair_id": pair_id,
                }
                if (
                    aggregate_minimum is None
                    or signed_distance < float(aggregate_minimum["signed_distance_m"])
                ):
                    aggregate_minimum = minimum_item
            else:
                if (
                    observation["signed_distance_m"] is not None
                    or observation["separation_lower_bound_m"]
                    != CLOSEST_POINT_QUERY_HORIZON_M
                ):
                    raise B3_2_InfrastructureError(
                        "Censored canonical observation representation is invalid"
                    )
                signed_distance = None
                expected_classification = (
                    DistanceClassification.SEPARATED_BEYOND_QUERY_HORIZON
                )
                aggregate_censored += 1
            classification_value = observation["classification"]
            if (
                classification_value not in valid_classifications
                or classification_value != expected_classification.value
            ):
                raise B3_2_InfrastructureError(
                    "Canonical observation classification contradicts its distance"
                )
            if pair_category is PairCategory.COMPONENT_ENVIRONMENT:
                if environment is None:
                    raise B3_2_InfrastructureError(
                        "Canonical component/environment pair lacks environment identity"
                    )
                expected_permission = component_environment_policy(
                    environment,
                    snapshot_phase,
                    snapshot_boundary,
                )
            else:
                expected_permission = PairPolicy.FORBIDDEN
            permission_value = observation["permission"]
            if (
                permission_value not in valid_permissions
                or permission_value != expected_permission.value
            ):
                raise B3_2_InfrastructureError(
                    "Canonical observation permission contradicts phase policy"
                )
            expected_decision = decide_contact(
                expected_permission,
                expected_classification,
            )
            decision_value = observation["decision"]
            if (
                decision_value not in valid_decisions
                or decision_value != expected_decision
            ):
                raise B3_2_InfrastructureError(
                    "Canonical observation decision contradicts contact policy"
                )

            aggregate_total += 1
            if expected_classification is DistanceClassification.NUMERICAL_CONTACT_BAND:
                aggregate_contact_band += 1
            elif expected_classification is DistanceClassification.MATERIAL_PENETRATION:
                aggregate_material_penetration += 1
            if found and expected_permission is PairPolicy.FORBIDDEN:
                aggregate_forbidden_found += 1
                if (
                    aggregate_forbidden_minimum is None
                    or signed_distance
                    < float(aggregate_forbidden_minimum["signed_distance_m"])
                ):
                    aggregate_forbidden_minimum = minimum_item
            if expected_decision != "PASS":
                aggregate_failure_counts[expected_decision] += 1
                derived_failures.append(
                    {
                        "semantic_snapshot_index": semantic_index,
                        "pair_index": pair_index,
                        "pair_id": pair_id,
                        "failure_code": expected_decision,
                        "route_state": route_state,
                        "phase": snapshot_phase.value,
                        "boundary_snapshot": snapshot_boundary.value,
                    }
                )

    if (
        aggregate_total != EXPECTED_FINE_QUERY_COUNT
        or aggregate_found + aggregate_censored != EXPECTED_FINE_QUERY_COUNT
    ):
        raise B3_2_InfrastructureError(
            "Derived authoritative aggregate query accounting failed"
        )
    derived_failures = sorted(
        derived_failures,
        key=lambda failure: (
            int(failure["semantic_snapshot_index"]),
            int(failure["pair_index"]),
            str(failure["failure_code"]),
        ),
    )
    derived_summary = _failure_summary(derived_failures)
    derived_result = PASS_RESULT if not derived_failures else FAIL_RESULT
    expected_fine_summary_fields = {
        "fresh_direct_session": True,
        "physics_steps": 0,
        "interval_counts": list(EXPECTED_FINE_INTERVALS),
        "total_interval_count": sum(EXPECTED_FINE_INTERVALS),
        "scientific_failure_count": len(derived_failures),
        "overall_result": derived_result,
    }
    for field, expected_value in expected_fine_summary_fields.items():
        if fine.get(field) != expected_value:
            raise B3_2_InfrastructureError(
                f"authoritative_fine_route.{field} is inconsistent"
            )
    fine_failure_summary = _canonical_mapping(
        fine.get("failure_summary"),
        "authoritative_fine_route.failure_summary",
    )
    if dict(fine_failure_summary) != derived_summary:
        raise B3_2_InfrastructureError(
            "authoritative_fine_route.failure_summary is inconsistent"
        )
    _validate_reproducibility_summary(
        sections["reproducibility_summary"],
        derived_result,
    )
    derived_aggregate: JsonObject = {
        "total_query_count": aggregate_total,
        "found_query_count": aggregate_found,
        "censored_no_result_count": aggregate_censored,
        "minimum_observed_signed_distance": aggregate_minimum,
        "minimum_forbidden_observed_signed_distance": aggregate_forbidden_minimum,
        "contact_band_event_count": aggregate_contact_band,
        "material_penetration_event_count": aggregate_material_penetration,
        "forbidden_failure_count": aggregate_failure_counts[
            SCIENTIFIC_FAILURE_CODES[0]
        ],
        "support_material_penetration_count": aggregate_failure_counts[
            SCIENTIFIC_FAILURE_CODES[1]
        ],
        "required_support_missing_count": aggregate_failure_counts[
            SCIENTIFIC_FAILURE_CODES[2]
        ],
    }

    result = sections["result"]
    raw_failures = result.get("scientific_failures")
    if not isinstance(raw_failures, list):
        raise B3_2_InfrastructureError("result.scientific_failures must be a list")
    failures: list[JsonObject] = []
    ordering_keys: list[tuple[int, int, str]] = []
    first_appearance: list[str] = []
    for index, raw_failure in enumerate(raw_failures):
        failure_mapping = _canonical_mapping(
            raw_failure,
            f"result.scientific_failures[{index}]",
        )
        failure = dict(failure_mapping)
        semantic_index = _canonical_integer(
            failure_mapping,
            "semantic_snapshot_index",
            f"result.scientific_failures[{index}]",
        )
        pair_index = _canonical_integer(
            failure_mapping,
            "pair_index",
            f"result.scientific_failures[{index}]",
        )
        failure_code = failure_mapping.get("failure_code")
        if not 0 <= semantic_index < EXPECTED_FINE_SEMANTIC_SNAPSHOTS:
            raise B3_2_InfrastructureError("Scientific failure semantic index is invalid")
        if not 0 <= pair_index < EXPECTED_PAIR_QUERIES_PER_SEMANTIC_SNAPSHOT:
            raise B3_2_InfrastructureError("Scientific failure pair index is invalid")
        if failure_code not in SCIENTIFIC_FAILURE_CODES:
            raise B3_2_InfrastructureError("Scientific failure code is invalid")
        ordering_keys.append((semantic_index, pair_index, str(failure_code)))
        if failure_code not in first_appearance:
            first_appearance.append(str(failure_code))
        failures.append(failure)
    if ordering_keys != sorted(ordering_keys):
        raise B3_2_InfrastructureError("Scientific failures are not canonically ordered")
    if failures != derived_failures:
        raise B3_2_InfrastructureError(
            "Recorded scientific failures do not match authoritative observations"
        )

    first_appearance = []
    for failure in derived_failures:
        code = str(failure["failure_code"])
        if code not in first_appearance:
            first_appearance.append(code)
    failure_summary = _canonical_mapping(
        result.get("failure_summary"),
        "result.failure_summary",
    )
    if set(failure_summary) != set(SCIENTIFIC_FAILURE_CODES):
        raise B3_2_InfrastructureError("result.failure_summary schema changed")
    for code in SCIENTIFIC_FAILURE_CODES:
        count = _integer(
            failure_summary[code],
            f"result.failure_summary.{code}",
        )
        if count < 0:
            raise B3_2_InfrastructureError("Scientific failure count is negative")
    if dict(failure_summary) != derived_summary:
        raise B3_2_InfrastructureError("result.failure_summary is inconsistent")
    if result.get("failure_codes_present") != first_appearance:
        raise B3_2_InfrastructureError(
            "result.failure_codes_present does not preserve first appearance"
        )
    if "scientific_failure_count" not in result or _integer(
        result["scientific_failure_count"],
        "result.scientific_failure_count",
    ) != len(derived_failures):
        raise B3_2_InfrastructureError("result.scientific_failure_count is inconsistent")
    if result.get("overall_result") != derived_result:
        raise B3_2_InfrastructureError("result.overall_result is inconsistent")
    expected_primary = None if not derived_failures else derived_failures[0]
    if "primary_failure" not in result or result["primary_failure"] != expected_primary:
        raise B3_2_InfrastructureError("result.primary_failure is inconsistent")

    aggregate = sections["aggregate_clearance_summary"]
    if set(aggregate) != set(AGGREGATE_CLEARANCE_FIELDS):
        raise B3_2_InfrastructureError("aggregate_clearance_summary schema changed")
    aggregate_counts: dict[str, int] = {}
    for field in (
        "total_query_count",
        "found_query_count",
        "censored_no_result_count",
        "contact_band_event_count",
        "material_penetration_event_count",
        "forbidden_failure_count",
        "support_material_penetration_count",
        "required_support_missing_count",
    ):
        count = _canonical_integer(aggregate, field, "aggregate_clearance_summary")
        if count < 0:
            raise B3_2_InfrastructureError(
                f"aggregate_clearance_summary.{field} is negative"
            )
        aggregate_counts[field] = count
    if aggregate_counts["total_query_count"] != EXPECTED_FINE_QUERY_COUNT:
        raise B3_2_InfrastructureError("Authoritative aggregate query count changed")
    if (
        aggregate_counts["found_query_count"]
        + aggregate_counts["censored_no_result_count"]
        != EXPECTED_FINE_QUERY_COUNT
    ):
        raise B3_2_InfrastructureError("Authoritative aggregate accounting failed")
    _validate_aggregate_minimum(
        aggregate["minimum_observed_signed_distance"],
        "aggregate_clearance_summary.minimum_observed_signed_distance",
        required=aggregate_counts["found_query_count"] > 0,
    )
    _validate_aggregate_minimum(
        aggregate["minimum_forbidden_observed_signed_distance"],
        "aggregate_clearance_summary.minimum_forbidden_observed_signed_distance",
        required=aggregate_forbidden_found > 0,
    )
    for aggregate_field, failure_code in AGGREGATE_FAILURE_FIELDS:
        if aggregate_counts[aggregate_field] != derived_summary[failure_code]:
            raise B3_2_InfrastructureError(
                "Aggregate and result scientific failure counts differ"
            )
    if dict(aggregate) != derived_aggregate:
        raise B3_2_InfrastructureError(
            "Aggregate clearance summary does not match authoritative observations"
        )


def serialize_artifact(artifact: JsonObject) -> bytes:
    try:
        text = (
            json.dumps(
                artifact,
                sort_keys=True,
                indent=2,
                allow_nan=False,
                ensure_ascii=False,
            )
            + "\n"
        )
    except (TypeError, ValueError) as exc:
        raise B3_2_InfrastructureError("Artifact is not finite canonical JSON") from exc
    try:
        b31.assert_portable_evidence(text)
    except b31.FrozenEvidenceError as exc:
        raise B3_2_InfrastructureError(
            "Artifact contains non-portable evidence"
        ) from exc
    payload = text.encode("utf-8")
    if payload.startswith(b"\xef\xbb\xbf") or b"\r" in payload or not payload.endswith(b"\n") or payload.endswith(b"\n\n"):
        raise B3_2_InfrastructureError("Artifact byte serialization contract failed")
    return payload


def _write_exclusive_fsync(path: Path, payload: bytes) -> None:
    created = False
    try:
        stream = path.open("xb")
        created = True
        with stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        if created:
            path.unlink(missing_ok=True)
        raise


def ensure_output_available(output_path: Path) -> None:
    digest_path = output_path.with_suffix(output_path.suffix + ".sha256")
    if output_path.exists() or digest_path.exists():
        raise FileExistsError(
            f"Refusing to overwrite B3.2 evidence: {output_path.name} or {digest_path.name}"
        )


def write_artifact(artifact: JsonObject, output_path: Path) -> str:
    validate_canonical_artifact(artifact)
    ensure_output_available(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = serialize_artifact(artifact)
    digest = hashlib.sha256(payload).hexdigest()
    digest_path = output_path.with_suffix(output_path.suffix + ".sha256")
    json_created = False
    digest_created = False
    _write_exclusive_fsync(output_path, payload)
    json_created = True
    try:
        _write_exclusive_fsync(
            digest_path,
            f"{digest}  {output_path.name}\n".encode("ascii"),
        )
        digest_created = True
    except BaseException:
        if json_created:
            output_path.unlink(missing_ok=True)
        raise
    try:
        verified = verify_artifact_digest(output_path)
    except BaseException:
        if json_created:
            output_path.unlink(missing_ok=True)
        if digest_created:
            digest_path.unlink(missing_ok=True)
        raise
    if verified != digest:
        if json_created:
            output_path.unlink(missing_ok=True)
        if digest_created:
            digest_path.unlink(missing_ok=True)
        raise B3_2_InfrastructureError("Post-write B3.2 digest verification failed")
    return digest


def verify_artifact_digest(output_path: Path) -> str:
    digest_path = output_path.with_suffix(output_path.suffix + ".sha256")
    if not output_path.is_file() or not digest_path.is_file():
        raise B3_2_InfrastructureError("B3.2 evidence pair is incomplete")
    digest = b31.sha256_file(output_path)
    try:
        digest_text = digest_path.read_text(encoding="ascii")
    except (OSError, UnicodeError) as exc:
        raise B3_2_InfrastructureError("B3.2 digest sidecar is invalid") from exc
    if digest_text != f"{digest}  {output_path.name}\n":
        raise B3_2_InfrastructureError("B3.2 digest sidecar mismatch")
    payload = output_path.read_bytes()
    if payload.startswith(b"\xef\xbb\xbf") or b"\r" in payload or not payload.endswith(b"\n") or payload.endswith(b"\n\n"):
        raise B3_2_InfrastructureError("Stored B3.2 artifact byte contract failed")
    parsed = _strict_json(output_path)
    validate_canonical_artifact(parsed)
    canonical_payload = serialize_artifact(parsed)
    if payload != canonical_payload:
        raise B3_2_InfrastructureError(
            "Stored B3.2 artifact bytes are not canonical serialization"
        )
    return digest
