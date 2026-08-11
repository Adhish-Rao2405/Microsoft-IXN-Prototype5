"""Immutable, attested replay model for the frozen B2/B3.2 evidence.

This module reads only server-registered repository artifacts.  It does not run
IK, plan motion, query collisions, step physics, or grant execution authority.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final, Mapping, Sequence, cast

from src.prototype5.final_demo_contract import (
    FinalDemoContract,
    FrozenReplayContext,
    RecordedFailureReference,
    ReplayClaimBoundary,
    RuntimeProvenance,
    Scenario,
    SceneIdentity,
    load_final_demo_contract,
)


REPOSITORY_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
REPLAY_SCENARIO_ID: Final[str] = "FROZEN_B2_PICK_PLACE_EVIDENCE_REPLAY"
REPLAY_BINDING_ID: Final[str] = "FROZEN_B2_B3_2_EVIDENCE_V1"
CONTROLLED_JOINT_INDICES: Final[tuple[int, ...]] = tuple(range(7))
EXPECTED_B2_ROUTE_STATES: Final[tuple[str, ...]] = (
    "HOME",
    "SOURCE_HIGH",
    "SOURCE_PICK",
    "SOURCE_HIGH_RETURN",
    "DESTINATION_HIGH",
    "DESTINATION_PLACE",
    "DESTINATION_HIGH_RETURN",
    "HOME",
)
EXPECTED_B3_2_RESULT: Final[str] = "B3_2_FAIL_DISCRETE_ROUTE_QUALIFICATION"
EXPECTED_FAILURE_CODE: Final[str] = "B3_2_FAIL_SUPPORT_MATERIAL_PENETRATION"
EXPECTED_ARTIFACT_PATHS: Final[tuple[str, ...]] = (
    "results/prototype5/scene_calibration/phase_b2_kinematic_plan.json",
    "results/prototype5/scene_calibration/phase_b3_1_collision_qualification.json",
    "results/prototype5/scene_calibration/phase_b3_2_discrete_route_collision_qualification.json",
    "docs/prototype5/phase_b3_2_discrete_route_collision_qualification_spec.md",
)
EXPECTED_REPLAY_CLAIM_LABELS: Final[tuple[str, str]] = (
    "EVIDENCE REPLAY",
    "NOT PHYSICAL EXECUTION",
)
EXPECTED_DISCRETE_SAMPLING_LIMITATION: Final[str] = (
    "Discrete sampling cannot prove the absence of collision between evaluated "
    "configurations."
)


class FrozenEvidenceReplayError(RuntimeError):
    """Base failure for constructing frozen replay state."""


class ReplayArtifactAccessError(FrozenEvidenceReplayError):
    """A registered repository artifact could not be read."""


class ReplayArtifactIntegrityError(FrozenEvidenceReplayError):
    """Artifact bytes or identities differed from the registered binding."""


class ReplayArtifactFormatError(FrozenEvidenceReplayError):
    """Attested JSON did not satisfy the replay structural contract."""


class ReplayDomainError(FrozenEvidenceReplayError):
    """Validated replay domain state violated a frozen invariant."""


@dataclass(frozen=True, slots=True)
class FrozenReplayClaimBoundary:
    required_labels: tuple[str, ...]
    reconstructs_frozen_states: bool
    consumes_immutable_evidence: bool
    performs_new_ik: bool
    optimises_trajectory: bool
    generates_new_collision_result: bool
    proves_dynamic_feasibility: bool
    proves_physical_robot_safety: bool
    authorises_physical_execution: bool
    replay_is_fresh_execution: bool
    generated_by_current_model_output: bool
    discrete_sampling_limitation: str

    def __post_init__(self) -> None:
        if self.required_labels != EXPECTED_REPLAY_CLAIM_LABELS:
            raise ReplayDomainError("frozen replay claim labels changed")
        if not (
            self.reconstructs_frozen_states is True
            and self.consumes_immutable_evidence is True
            and self.performs_new_ik is False
            and self.optimises_trajectory is False
            and self.generates_new_collision_result is False
            and self.proves_dynamic_feasibility is False
            and self.proves_physical_robot_safety is False
            and self.authorises_physical_execution is False
            and self.replay_is_fresh_execution is False
            and self.generated_by_current_model_output is False
        ):
            raise ReplayDomainError("frozen replay claim semantics changed")
        if self.discrete_sampling_limitation != EXPECTED_DISCRETE_SAMPLING_LIMITATION:
            raise ReplayDomainError("frozen discrete-sampling limitation changed")

    @classmethod
    def from_contract(
        cls,
        claim_boundary: ReplayClaimBoundary,
    ) -> FrozenReplayClaimBoundary:
        if not isinstance(claim_boundary, ReplayClaimBoundary):
            raise TypeError("claim_boundary must be ReplayClaimBoundary")
        return cls(
            required_labels=tuple(claim_boundary.required_labels),
            reconstructs_frozen_states=claim_boundary.reconstructs_frozen_states,
            consumes_immutable_evidence=claim_boundary.consumes_immutable_evidence,
            performs_new_ik=claim_boundary.performs_new_ik,
            optimises_trajectory=claim_boundary.optimises_trajectory,
            generates_new_collision_result=(
                claim_boundary.generates_new_collision_result
            ),
            proves_dynamic_feasibility=claim_boundary.proves_dynamic_feasibility,
            proves_physical_robot_safety=(
                claim_boundary.proves_physical_robot_safety
            ),
            authorises_physical_execution=(
                claim_boundary.authorises_physical_execution
            ),
            replay_is_fresh_execution=claim_boundary.replay_is_fresh_execution,
            generated_by_current_model_output=(
                claim_boundary.generated_by_current_model_output
            ),
            discrete_sampling_limitation=(
                claim_boundary.discrete_sampling_limitation
            ),
        )


class _NonCanonicalJSONError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class _ExpectedReplayPoint:
    semantic_snapshot_index: int
    route_configuration_index: int
    b2_route_index: int
    route_state: str
    phase: str
    boundary_snapshot: str


EXPECTED_REPLAY_POINTS: Final[tuple[_ExpectedReplayPoint, ...]] = (
    _ExpectedReplayPoint(0, 0, 0, "HOME", "SOURCE_SUPPORTED", "NONE"),
    _ExpectedReplayPoint(78, 78, 1, "SOURCE_HIGH", "SOURCE_SUPPORTED", "NONE"),
    _ExpectedReplayPoint(
        118, 118, 2, "SOURCE_PICK", "ATTACHMENT_BOUNDARY", "PRE"
    ),
    _ExpectedReplayPoint(
        119, 118, 2, "SOURCE_PICK", "ATTACHMENT_BOUNDARY", "POST"
    ),
    _ExpectedReplayPoint(
        157, 156, 3, "SOURCE_HIGH_RETURN", "CARRIED", "NONE"
    ),
    _ExpectedReplayPoint(311, 310, 4, "DESTINATION_HIGH", "CARRIED", "NONE"),
    _ExpectedReplayPoint(
        351, 350, 5, "DESTINATION_PLACE", "RELEASE_BOUNDARY", "PRE"
    ),
    _ExpectedReplayPoint(
        352, 350, 5, "DESTINATION_PLACE", "RELEASE_BOUNDARY", "POST"
    ),
    _ExpectedReplayPoint(
        390, 388, 6, "DESTINATION_HIGH_RETURN", "DESTINATION_SUPPORTED", "NONE"
    ),
    _ExpectedReplayPoint(468, 466, 7, "HOME", "DESTINATION_SUPPORTED", "NONE"),
)


@dataclass(frozen=True, slots=True)
class ArtifactAttestation:
    logical_path: str
    sha256: str
    byte_count: int

    def __post_init__(self) -> None:
        logical = PurePosixPath(self.logical_path)
        if (
            not self.logical_path
            or logical.is_absolute()
            or ".." in logical.parts
        ):
            raise ReplayDomainError("artifact attestation path must be repository-relative")
        if len(self.sha256) != 64 or any(
            character not in "0123456789abcdef" for character in self.sha256
        ):
            raise ReplayDomainError("artifact attestation SHA-256 is malformed")
        if (
            isinstance(self.byte_count, bool)
            or not isinstance(self.byte_count, int)
            or self.byte_count <= 0
        ):
            raise ReplayDomainError("artifact attestation byte count must be positive")


@dataclass(frozen=True, slots=True)
class FrozenReplaySnapshot:
    replay_index: int
    semantic_snapshot_index: int
    route_configuration_index: int
    b2_route_index: int
    route_state: str
    phase: str
    boundary_snapshot: str
    joint_positions: tuple[float, ...]
    component_position_m: tuple[float, float, float]
    component_quaternion_xyzw: tuple[float, float, float, float]

    def __post_init__(self) -> None:
        for field_name in (
            "replay_index",
            "semantic_snapshot_index",
            "route_configuration_index",
            "b2_route_index",
        ):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ReplayDomainError(f"{field_name} must be a non-negative integer")
        if self.b2_route_index >= len(EXPECTED_B2_ROUTE_STATES):
            raise ReplayDomainError("b2_route_index outside frozen domain")
        if self.route_state not in set(EXPECTED_B2_ROUTE_STATES):
            raise ReplayDomainError(f"unknown frozen route state: {self.route_state}")
        if self.phase not in {
            "SOURCE_SUPPORTED",
            "ATTACHMENT_BOUNDARY",
            "CARRIED",
            "RELEASE_BOUNDARY",
            "DESTINATION_SUPPORTED",
        }:
            raise ReplayDomainError(f"unknown frozen component phase: {self.phase}")
        if self.boundary_snapshot not in {"NONE", "PRE", "POST"}:
            raise ReplayDomainError("unknown frozen boundary snapshot")
        _validate_float_tuple(self.joint_positions, 7, "joint_positions")
        _validate_float_tuple(self.component_position_m, 3, "component_position_m")
        _validate_float_tuple(
            self.component_quaternion_xyzw,
            4,
            "component_quaternion_xyzw",
        )
        norm = math.sqrt(
            sum(value * value for value in self.component_quaternion_xyzw)
        )
        if not math.isclose(norm, 1.0, rel_tol=0.0, abs_tol=1.0e-9):
            raise ReplayDomainError("component quaternion must be normalized")


@dataclass(frozen=True, slots=True)
class FrozenQualificationMetadata:
    overall_result: str
    scientific_failure_count: int
    failure_codes_present: tuple[str, ...]
    forbidden_contact_failure_count: int
    support_material_penetration_failure_count: int
    required_support_missing_failure_count: int
    recorded_failure: RecordedFailureReference

    def __post_init__(self) -> None:
        for field_name in (
            "scientific_failure_count",
            "forbidden_contact_failure_count",
            "support_material_penetration_failure_count",
            "required_support_missing_failure_count",
        ):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ReplayDomainError(f"{field_name} must be a non-negative integer")
        if self.overall_result != EXPECTED_B3_2_RESULT:
            raise ReplayDomainError("B3.2 terminal result changed")
        if self.scientific_failure_count != 118:
            raise ReplayDomainError("B3.2 scientific failure count changed")
        if self.failure_codes_present != (EXPECTED_FAILURE_CODE,):
            raise ReplayDomainError("B3.2 failure-code set changed")
        if (
            self.forbidden_contact_failure_count,
            self.support_material_penetration_failure_count,
            self.required_support_missing_failure_count,
        ) != (0, 118, 0):
            raise ReplayDomainError("B3.2 failure summary changed")


@dataclass(frozen=True, slots=True)
class FrozenEvidenceReplayPlan:
    scenario_id: str
    binding_id: str
    scene_identity: SceneIdentity
    runtime_provenance: RuntimeProvenance
    claim_boundary: FrozenReplayClaimBoundary
    artifacts: tuple[ArtifactAttestation, ...]
    snapshots: tuple[FrozenReplaySnapshot, ...]
    qualification: FrozenQualificationMetadata

    def __post_init__(self) -> None:
        if not isinstance(self.claim_boundary, FrozenReplayClaimBoundary):
            raise ReplayDomainError("replay claim boundary is not deeply immutable")
        if self.scenario_id != REPLAY_SCENARIO_ID:
            raise ReplayDomainError("replay scenario identity changed")
        if self.binding_id != REPLAY_BINDING_ID:
            raise ReplayDomainError("replay binding identity changed")
        if len(self.artifacts) != 4 or len(
            {artifact.logical_path for artifact in self.artifacts}
        ) != 4:
            raise ReplayDomainError("exactly four unique artifacts must be attested")
        if tuple(artifact.logical_path for artifact in self.artifacts) != (
            EXPECTED_ARTIFACT_PATHS
        ):
            raise ReplayDomainError("frozen artifact attestation order changed")
        if len(self.snapshots) != len(EXPECTED_REPLAY_POINTS):
            raise ReplayDomainError("frozen replay point count changed")
        for index, (snapshot, expected) in enumerate(
            zip(self.snapshots, EXPECTED_REPLAY_POINTS, strict=True)
        ):
            actual = (
                snapshot.replay_index,
                snapshot.semantic_snapshot_index,
                snapshot.route_configuration_index,
                snapshot.b2_route_index,
                snapshot.route_state,
                snapshot.phase,
                snapshot.boundary_snapshot,
            )
            required = (
                index,
                expected.semantic_snapshot_index,
                expected.route_configuration_index,
                expected.b2_route_index,
                expected.route_state,
                expected.phase,
                expected.boundary_snapshot,
            )
            if actual != required:
                raise ReplayDomainError("frozen replay sequence changed")

    def snapshot_at(self, replay_index: int) -> FrozenReplaySnapshot:
        if isinstance(replay_index, bool) or not isinstance(replay_index, int):
            raise ReplayDomainError("replay index must be an integer")
        if not 0 <= replay_index < len(self.snapshots):
            raise ReplayDomainError("replay index outside frozen domain")
        return self.snapshots[replay_index]


def _validate_float_tuple(
    values: tuple[float, ...],
    expected_length: int,
    field: str,
) -> None:
    if not isinstance(values, tuple) or len(values) != expected_length:
        raise ReplayDomainError(f"{field} must contain {expected_length} values")
    if any(
        isinstance(value, bool)
        or not isinstance(value, float)
        or not math.isfinite(value)
        for value in values
    ):
        raise ReplayDomainError(f"{field} must contain finite floats")


def _reject_json_constant(token: str) -> object:
    raise _NonCanonicalJSONError(f"non-standard JSON constant forbidden: {token}")


def _reject_duplicate_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _NonCanonicalJSONError(f"duplicate JSON key forbidden: {key}")
        result[key] = value
    return result


def _strict_json_bytes(payload: bytes, logical_path: str) -> Mapping[str, object]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ReplayArtifactFormatError(
            f"artifact is not valid UTF-8: {logical_path}"
        ) from exc
    if not text or text.startswith("\ufeff"):
        raise ReplayArtifactFormatError(
            f"artifact is empty or has a UTF-8 BOM: {logical_path}"
        )
    try:
        decoded = json.loads(
            text,
            parse_constant=_reject_json_constant,
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (json.JSONDecodeError, _NonCanonicalJSONError) as exc:
        raise ReplayArtifactFormatError(
            f"artifact is invalid or non-canonical JSON: {logical_path}"
        ) from exc
    if not isinstance(decoded, dict) or not decoded:
        raise ReplayArtifactFormatError(
            f"artifact root must be a non-empty JSON object: {logical_path}"
        )
    return cast(Mapping[str, object], decoded)


def _resolve_registered_path(repository_root: Path, logical_path: str) -> Path:
    if not isinstance(repository_root, Path):
        raise TypeError("repository_root must be pathlib.Path")
    logical = PurePosixPath(logical_path)
    if logical.is_absolute() or ".." in logical.parts:
        raise ReplayArtifactAccessError("registered artifact path is not bounded")
    try:
        root = repository_root.resolve(strict=True)
        candidate = root.joinpath(*logical.parts).resolve(strict=True)
        candidate.relative_to(root)
    except (OSError, ValueError) as exc:
        raise ReplayArtifactAccessError(
            f"registered artifact is unavailable: {logical_path}"
        ) from exc
    if not candidate.is_file():
        raise ReplayArtifactAccessError(
            f"registered artifact is not a file: {logical_path}"
        )
    return candidate


def _read_attested_bytes(
    repository_root: Path,
    logical_path: str,
    expected_sha256: str,
) -> tuple[bytes, ArtifactAttestation]:
    path = _resolve_registered_path(repository_root, logical_path)
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise ReplayArtifactAccessError(
            f"registered artifact cannot be read: {logical_path}"
        ) from exc
    if not payload:
        raise ReplayArtifactIntegrityError(f"registered artifact is empty: {logical_path}")
    actual_sha256 = hashlib.sha256(payload).hexdigest()
    if actual_sha256 != expected_sha256:
        raise ReplayArtifactIntegrityError(
            f"registered artifact SHA-256 mismatch: {logical_path}"
        )
    return payload, ArtifactAttestation(logical_path, actual_sha256, len(payload))


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ReplayArtifactFormatError(f"{field} must be an object")
    return cast(Mapping[str, object], value)


def _sequence(value: object, field: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, list):
        raise ReplayArtifactFormatError(f"{field} must be an array")
    return cast(Sequence[object], value)


def _required(mapping: Mapping[str, object], key: str, field: str) -> object:
    if key not in mapping:
        raise ReplayArtifactFormatError(f"{field}.{key} is required")
    return mapping[key]


def _strict_integer(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ReplayArtifactFormatError(f"{field} must be an integer")
    return value


def _require_exact_typed_value(
    value: object,
    expected: object,
    field: str,
) -> None:
    if isinstance(expected, bool):
        if not isinstance(value, bool) or value is not expected:
            raise ReplayArtifactFormatError(f"{field} changed")
        return
    if isinstance(expected, int):
        if isinstance(value, bool) or not isinstance(value, int) or value != expected:
            raise ReplayArtifactFormatError(f"{field} changed")
        return
    if isinstance(expected, str):
        if not isinstance(value, str) or value != expected:
            raise ReplayArtifactFormatError(f"{field} changed")
        return
    raise TypeError(
        f"unsupported frozen comparison type for {field}: "
        f"{type(expected).__name__}"
    )


def _finite_float(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ReplayArtifactFormatError(f"{field} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ReplayArtifactFormatError(f"{field} must be finite")
    return result


def _float_tuple(value: object, length: int, field: str) -> tuple[float, ...]:
    items = _sequence(value, field)
    if len(items) != length:
        raise ReplayArtifactFormatError(f"{field} must contain {length} values")
    return tuple(_finite_float(item, f"{field}[{index}]") for index, item in enumerate(items))


def _parse_b2(payload: Mapping[str, object], scene: SceneIdentity) -> tuple[tuple[float, ...], ...]:
    if (
        payload.get("schema_identifier") != "prototype5.scene_kinematic_plan.b2"
        or payload.get("schema_version") != "1.0.0"
        or payload.get("gate_identifier") != "B2_HOME_AND_KINEMATIC_PLAN"
    ):
        raise ReplayArtifactFormatError("B2 schema identity changed")
    semantic = _mapping(payload.get("semantic_execution_tuple"), "B2 semantic tuple")
    if dict(semantic) != scene.model_dump():
        raise ReplayArtifactFormatError("B2 scene identity differs from D0 binding")
    robot = _mapping(payload.get("robot"), "B2 robot")
    controlled_joints = _sequence(
        robot.get("controlled_joints"),
        "B2 controlled joints",
    )
    if (
        tuple(
            _strict_integer(value, f"B2 controlled joints[{index}]")
            for index, value in enumerate(controlled_joints)
        )
        != CONTROLLED_JOINT_INDICES
        or _strict_integer(robot.get("ee_link"), "B2 ee_link") != 6
        or robot.get("urdf") != "kuka_iiwa/model.urdf"
        or robot.get("use_fixed_base") is not True
        or tuple(_float_tuple(robot.get("base_position"), 3, "B2 base position"))
        != (0.0, 0.0, 0.0)
    ):
        raise ReplayArtifactFormatError("B2 robot identity changed")
    ordered_plan = _sequence(payload.get("ordered_plan"), "B2 ordered plan")
    if len(ordered_plan) != len(EXPECTED_B2_ROUTE_STATES):
        raise ReplayArtifactFormatError("B2 ordered plan cardinality changed")
    vectors: list[tuple[float, ...]] = []
    for route_index, (raw_state, expected_state) in enumerate(
        zip(ordered_plan, EXPECTED_B2_ROUTE_STATES, strict=True)
    ):
        state = _mapping(raw_state, f"B2 ordered_plan[{route_index}]")
        if (
            _strict_integer(state.get("route_index"), "B2 route_index") != route_index
            or state.get("state") != expected_state
        ):
            raise ReplayArtifactFormatError("B2 route order changed")
        replay = _mapping(state.get("replay"), "B2 replay")
        if (
            _strict_integer(replay.get("route_index"), "B2 replay route_index")
            != route_index
            or replay.get("state") != expected_state
        ):
            raise ReplayArtifactFormatError("B2 replay identity contradicts plan state")
        vectors.append(
            _float_tuple(state.get("joint_vector"), 7, f"B2 state {route_index} joints")
        )
    if vectors[0] != vectors[-1]:
        raise ReplayArtifactFormatError("B2 final HOME differs from initial HOME")
    return tuple(vectors)


def _parse_b3_1(payload: Mapping[str, object]) -> None:
    if (
        payload.get("schema_identifier")
        != "prototype5.scene_collision_qualification.b3_1"
        or payload.get("schema_version") != "1.0.0"
        or payload.get("gate_identifier")
        != "B3_1_COLLISION_DETECTOR_AND_FROZEN_SCENE_QUALIFICATION"
    ):
        raise ReplayArtifactFormatError("B3.1 schema identity changed")


def _parse_snapshot(
    raw_snapshot: object,
    expected: _ExpectedReplayPoint,
    replay_index: int,
    b2_joint_positions: tuple[float, ...],
) -> FrozenReplaySnapshot:
    snapshot = _mapping(raw_snapshot, f"B3.2 snapshot {expected.semantic_snapshot_index}")
    exact_fields: dict[str, int | str] = {
        "semantic_snapshot_index": expected.semantic_snapshot_index,
        "route_configuration_index": expected.route_configuration_index,
        "route_state": expected.route_state,
        "phase": expected.phase,
        "boundary_snapshot": expected.boundary_snapshot,
    }
    for field, value in exact_fields.items():
        _require_exact_typed_value(
            snapshot.get(field),
            value,
            f"B3.2 replay snapshot {field}",
        )
    joints = _float_tuple(snapshot.get("joint_vector"), 7, "B3.2 joint vector")
    if joints != b2_joint_positions:
        raise ReplayArtifactFormatError("B3.2 endpoint joints differ from frozen B2")
    pose = _mapping(snapshot.get("component_pose"), "B3.2 component pose")
    observations = _sequence(snapshot.get("observations"), "B3.2 observations")
    if len(observations) != 83:
        raise ReplayArtifactFormatError("B3.2 observation cardinality changed")
    return FrozenReplaySnapshot(
        replay_index=replay_index,
        semantic_snapshot_index=expected.semantic_snapshot_index,
        route_configuration_index=expected.route_configuration_index,
        b2_route_index=expected.b2_route_index,
        route_state=expected.route_state,
        phase=expected.phase,
        boundary_snapshot=expected.boundary_snapshot,
        joint_positions=joints,
        component_position_m=cast(
            tuple[float, float, float],
            _float_tuple(pose.get("position_m"), 3, "B3.2 component position"),
        ),
        component_quaternion_xyzw=cast(
            tuple[float, float, float, float],
            _float_tuple(
                pose.get("quaternion_xyzw"),
                4,
                "B3.2 component orientation",
            ),
        ),
    )


def _parse_b3_2(
    payload: Mapping[str, object],
    b2_vectors: tuple[tuple[float, ...], ...],
    contract: FinalDemoContract,
) -> tuple[tuple[FrozenReplaySnapshot, ...], FrozenQualificationMetadata]:
    if (
        payload.get("schema_identifier")
        != "prototype5.scene_collision_route_qualification.b3_2"
        or payload.get("schema_version") != "1.0.0"
        or payload.get("gate_identifier")
        != "B3_2_DISCRETE_ROUTE_COLLISION_QUALIFICATION"
    ):
        raise ReplayArtifactFormatError("B3.2 schema identity changed")
    result = _mapping(payload.get("result"), "B3.2 result")
    binding = contract.frozen_evidence_bindings.b3_2
    try:
        _require_exact_typed_value(
            result.get("overall_result"),
            binding.expected_terminal_status,
            "B3.2 result overall_result",
        )
        _require_exact_typed_value(
            result.get("scientific_failure_count"),
            binding.expected_scientific_failure_count,
            "B3.2 result scientific_failure_count",
        )
    except ReplayArtifactFormatError as exc:
        raise ReplayArtifactFormatError("B3.2 result differs from D0 binding") from exc
    if tuple(_sequence(result.get("failure_codes_present"), "failure codes")) != tuple(
        binding.expected_failure_codes_present
    ):
        raise ReplayArtifactFormatError("B3.2 result differs from D0 binding")
    failures = _sequence(result.get("scientific_failures"), "scientific failures")
    if len(failures) != 118:
        raise ReplayArtifactFormatError("B3.2 scientific failure list changed")
    failure_summary = _mapping(result.get("failure_summary"), "failure summary")
    expected_summary = {
        "B3_2_FAIL_FORBIDDEN_CONTACT": 0,
        "B3_2_FAIL_SUPPORT_MATERIAL_PENETRATION": 118,
        "B3_2_FAIL_REQUIRED_SUPPORT_MISSING": 0,
    }
    if set(failure_summary) != set(expected_summary):
        raise ReplayArtifactFormatError("B3.2 failure summary changed")
    for key, expected_count in expected_summary.items():
        actual_count = _strict_integer(
            failure_summary.get(key),
            f"B3.2 failure summary {key}",
        )
        if actual_count != expected_count:
            raise ReplayArtifactFormatError("B3.2 failure summary changed")
    fine = _mapping(payload.get("authoritative_fine_route"), "authoritative fine route")
    expected_fine = {
        "pass_name": "FINE_PASS_1",
        "route_configuration_count": 467,
        "semantic_snapshot_count": 469,
        "query_count": 38927,
        "physics_steps": 0,
        "fresh_direct_session": True,
        "overall_result": EXPECTED_B3_2_RESULT,
        "scientific_failure_count": 118,
    }
    for key, value in expected_fine.items():
        try:
            _require_exact_typed_value(
                fine.get(key),
                value,
                f"B3.2 authoritative fine route {key}",
            )
        except ReplayArtifactFormatError as exc:
            raise ReplayArtifactFormatError(
                "B3.2 authoritative pass identity changed"
            ) from exc
    raw_snapshots = _sequence(fine.get("semantic_snapshots"), "semantic snapshots")
    if len(raw_snapshots) != 469:
        raise ReplayArtifactFormatError("B3.2 semantic snapshot count changed")
    snapshots = tuple(
        _parse_snapshot(
            raw_snapshots[expected.semantic_snapshot_index],
            expected,
            replay_index,
            b2_vectors[expected.b2_route_index],
        )
        for replay_index, expected in enumerate(EXPECTED_REPLAY_POINTS)
    )
    recorded = contract.frozen_evidence_bindings.recorded_failure_reference
    recorded_snapshot = _mapping(
        raw_snapshots[recorded.semantic_snapshot_index],
        "recorded failure snapshot",
    )
    observation = _mapping(
        _sequence(recorded_snapshot.get("observations"), "recorded observations")[
            recorded.pair_index
        ],
        "recorded failure observation",
    )
    _require_exact_typed_value(
        observation.get("pair_index"),
        recorded.pair_index,
        "recorded B3.2 failure observation pair_index",
    )
    exact_observation = {
        "pair_id": recorded.pair_id,
        "signed_distance_m": recorded.signed_distance_m,
        "classification": recorded.classification,
        "permission": recorded.permission,
        "decision": recorded.decision,
    }
    if any(observation.get(key) != value for key, value in exact_observation.items()):
        raise ReplayArtifactFormatError("recorded B3.2 failure observation changed")
    qualification = FrozenQualificationMetadata(
        overall_result=cast(str, result["overall_result"]),
        scientific_failure_count=cast(int, result["scientific_failure_count"]),
        failure_codes_present=tuple(cast(Sequence[str], result["failure_codes_present"])),
        forbidden_contact_failure_count=cast(
            int, failure_summary["B3_2_FAIL_FORBIDDEN_CONTACT"]
        ),
        support_material_penetration_failure_count=cast(
            int, failure_summary["B3_2_FAIL_SUPPORT_MATERIAL_PENETRATION"]
        ),
        required_support_missing_failure_count=cast(
            int, failure_summary["B3_2_FAIL_REQUIRED_SUPPORT_MISSING"]
        ),
        recorded_failure=recorded,
    )
    return snapshots, qualification


def _registered_replay_scenario(contract: FinalDemoContract) -> Scenario:
    replay_scenarios = tuple(
        scenario
        for scenario in contract.scenario_contract.scenarios
        if scenario.replay_capability.classification == "FROZEN_B2_REPLAY_COMPATIBLE"
    )
    if len(replay_scenarios) != 1:
        raise ReplayDomainError("exactly one server-registered replay scenario is required")
    scenario = replay_scenarios[0]
    if (
        scenario.scenario_id != REPLAY_SCENARIO_ID
        or scenario.replay_capability.qualification_replay_access
        != "SERVER_REGISTERED_ONLY"
        or not isinstance(scenario.authoritative_context, FrozenReplayContext)
        or scenario.authoritative_context.binding_id != REPLAY_BINDING_ID
        or scenario.model_input_enabled
        or scenario.client_overridable_context_fields
    ):
        raise ReplayDomainError("dedicated replay scenario binding changed")
    return scenario


def _load_registered_frozen_evidence_replay_from_root(
    repository_root: Path,
    contract: FinalDemoContract,
) -> FrozenEvidenceReplayPlan:
    scenario = _registered_replay_scenario(contract)
    bindings = contract.frozen_evidence_bindings
    if bindings.binding_id != REPLAY_BINDING_ID:
        raise ReplayDomainError("frozen evidence binding changed")

    b2_bytes, b2_attestation = _read_attested_bytes(
        repository_root, bindings.b2.path, bindings.b2.sha256
    )
    b31_bytes, b31_attestation = _read_attested_bytes(
        repository_root, bindings.b3_1.path, bindings.b3_1.sha256
    )
    b32_bytes, b32_attestation = _read_attested_bytes(
        repository_root, bindings.b3_2.path, bindings.b3_2.sha256
    )
    _, specification_attestation = _read_attested_bytes(
        repository_root,
        bindings.b3_2.specification_path,
        bindings.b3_2.specification_sha256,
    )

    b2 = _strict_json_bytes(b2_bytes, bindings.b2.path)
    b31 = _strict_json_bytes(b31_bytes, bindings.b3_1.path)
    b32 = _strict_json_bytes(b32_bytes, bindings.b3_2.path)
    b2_vectors = _parse_b2(b2, bindings.scene_identity)
    _parse_b3_1(b31)
    snapshots, qualification = _parse_b3_2(b32, b2_vectors, contract)
    return FrozenEvidenceReplayPlan(
        scenario_id=scenario.scenario_id,
        binding_id=bindings.binding_id,
        scene_identity=bindings.scene_identity,
        runtime_provenance=bindings.runtime_provenance,
        claim_boundary=FrozenReplayClaimBoundary.from_contract(
            contract.replay_claim_boundary
        ),
        artifacts=(
            b2_attestation,
            b31_attestation,
            b32_attestation,
            specification_attestation,
        ),
        snapshots=snapshots,
        qualification=qualification,
    )


def load_registered_frozen_evidence_replay() -> FrozenEvidenceReplayPlan:
    """Load the sole server-registered replay from immutable repository bindings."""

    return _load_registered_frozen_evidence_replay_from_root(
        REPOSITORY_ROOT,
        load_final_demo_contract(),
    )


__all__ = (
    "ArtifactAttestation",
    "CONTROLLED_JOINT_INDICES",
    "EXPECTED_B2_ROUTE_STATES",
    "EXPECTED_B3_2_RESULT",
    "FrozenEvidenceReplayError",
    "FrozenEvidenceReplayPlan",
    "FrozenQualificationMetadata",
    "FrozenReplayClaimBoundary",
    "FrozenReplaySnapshot",
    "ReplayArtifactAccessError",
    "ReplayArtifactFormatError",
    "ReplayArtifactIntegrityError",
    "ReplayDomainError",
    "load_registered_frozen_evidence_replay",
)
