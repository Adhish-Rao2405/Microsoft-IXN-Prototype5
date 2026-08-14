"""Single-owner PyBullet adapter for deterministic frozen evidence replay."""

from __future__ import annotations

import hashlib
import importlib.metadata
import math
import threading
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Final, cast

import pybullet as pb
import pybullet_data

from src.prototype5 import scene_collision_qualification_b3_1 as b31
from src.prototype5.frozen_evidence_replay import (
    CONTROLLED_JOINT_INDICES,
    FrozenEvidenceReplayPlan,
    FrozenReplayFrame,
    FrozenReplaySnapshot,
    ReplayDomainError,
    load_registered_frozen_evidence_replay,
)


class PyBulletEvidenceReplayError(RuntimeError):
    """Base failure for static PyBullet evidence reconstruction."""


class ReplayRuntimeIntegrityError(PyBulletEvidenceReplayError):
    """Installed PyBullet/KUKA bytes differ from frozen provenance."""


class ReplaySessionStateError(PyBulletEvidenceReplayError):
    """Replay session lifecycle or navigation was invalid."""


class ReplaySceneError(PyBulletEvidenceReplayError):
    """The deterministic replay scene could not be constructed or applied."""


class _ReplaySessionState(Enum):
    NEW = "NEW"
    OPEN = "OPEN"
    CLEANUP_PENDING = "CLEANUP_PENDING"
    CLOSED = "CLOSED"


@dataclass(frozen=True, slots=True)
class ReplayRuntimeAttestation:
    pybullet_package_version: str
    pybullet_api_version: int
    pybullet_binary_sha256: str
    kuka_urdf_sha256: str
    kuka_asset_manifest_sha256: str


@dataclass(frozen=True, slots=True)
class ReplaySnapshotReadback:
    snapshot: FrozenReplaySnapshot
    joint_positions: tuple[float, ...]
    component_position_m: tuple[float, float, float]
    component_quaternion_xyzw: tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class ReplayFrameReadback:
    frame: FrozenReplayFrame
    joint_positions: tuple[float, ...]
    component_position_m: tuple[float, float, float]
    component_quaternion_xyzw: tuple[float, float, float, float]


_VISUAL_COLOURS: Final[tuple[tuple[str, tuple[float, float, float, float]], ...]] = (
    ("source_platform", (0.25, 0.45, 0.75, 1.0)),
    ("destination_floor", (0.35, 0.65, 0.35, 1.0)),
    ("destination_wall_x_minus", (0.45, 0.55, 0.45, 1.0)),
    ("destination_wall_x_plus", (0.45, 0.55, 0.45, 1.0)),
    ("destination_wall_y_minus", (0.45, 0.55, 0.45, 1.0)),
    ("destination_wall_y_plus", (0.45, 0.55, 0.45, 1.0)),
    ("blue_component", (0.05, 0.25, 0.95, 1.0)),
)
POSE_ABS_TOLERANCE: Final[float] = 1.0e-15
REPLAY_CAMERA_DISTANCE: Final[float] = 1.6
REPLAY_CAMERA_YAW: Final[float] = 45.0
REPLAY_CAMERA_PITCH: Final[float] = -30.0
REPLAY_CAMERA_TARGET: Final[tuple[float, float, float]] = (0.25, 0.0, 0.35)


def _position_matches(
    actual: tuple[float, float, float],
    expected: tuple[float, float, float],
) -> bool:
    return all(
        math.isclose(
            observed,
            frozen,
            rel_tol=0.0,
            abs_tol=POSE_ABS_TOLERANCE,
        )
        for observed, frozen in zip(actual, expected, strict=True)
    )


def _quaternion_matches_rotation(
    actual: tuple[float, float, float, float],
    expected: tuple[float, float, float, float],
) -> bool:
    """Compare rotations without requiring identical quaternion signs."""

    direct_error = max(
        abs(observed - frozen)
        for observed, frozen in zip(actual, expected, strict=True)
    )
    negated_error = max(
        abs(observed + frozen)
        for observed, frozen in zip(actual, expected, strict=True)
    )
    return min(direct_error, negated_error) <= POSE_ABS_TOLERANCE


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise ReplayRuntimeIntegrityError(f"runtime file cannot be read: {path.name}") from exc
    return digest.hexdigest()


def attest_replay_runtime(plan: FrozenEvidenceReplayPlan) -> ReplayRuntimeAttestation:
    """Verify the installed renderer and KUKA assets against the D0 binding."""

    if not isinstance(plan, FrozenEvidenceReplayPlan):
        raise TypeError("plan must be FrozenEvidenceReplayPlan")
    expected = plan.runtime_provenance
    try:
        package_version = importlib.metadata.version("pybullet")
        api_version = int(pb.getAPIVersion())
        binary_path = Path(cast(str, pb.__file__)).resolve(strict=True)
        data_root = Path(pybullet_data.getDataPath()).resolve(strict=True)
        urdf_path = (data_root / b31.KUKA_URDF_RELATIVE).resolve(strict=True)
        observed = ReplayRuntimeAttestation(
            pybullet_package_version=package_version,
            pybullet_api_version=api_version,
            pybullet_binary_sha256=_sha256_file(binary_path),
            kuka_urdf_sha256=_sha256_file(urdf_path),
            kuka_asset_manifest_sha256=b31.directory_manifest_sha256(urdf_path.parent),
        )
    except ReplayRuntimeIntegrityError:
        raise
    except Exception as exc:
        raise ReplayRuntimeIntegrityError("PyBullet runtime provenance is unavailable") from exc
    required = ReplayRuntimeAttestation(
        pybullet_package_version=expected.pybullet_package_version,
        pybullet_api_version=expected.pybullet_api_version,
        pybullet_binary_sha256=expected.pybullet_binary_sha256,
        kuka_urdf_sha256=expected.kuka_urdf_sha256,
        kuka_asset_manifest_sha256=expected.kuka_asset_manifest_sha256,
    )
    if observed != required:
        raise ReplayRuntimeIntegrityError(
            f"PyBullet/KUKA runtime identity changed: {observed!r} != {required!r}"
        )
    return observed


def _colour_for(semantic_id: str) -> tuple[float, float, float, float]:
    for registered_id, colour in _VISUAL_COLOURS:
        if semantic_id == registered_id:
            return colour
    raise ReplaySceneError(f"unregistered replay visual body: {semantic_id}")


def _create_replay_box(definition: b31.BoxDefinition, client_id: int) -> int:
    collision_shape = pb.createCollisionShape(
        pb.GEOM_BOX,
        halfExtents=definition.half_extents_m,
        physicsClientId=client_id,
    )
    visual_shape = pb.createVisualShape(
        pb.GEOM_BOX,
        halfExtents=definition.half_extents_m,
        rgbaColor=_colour_for(definition.semantic_id),
        physicsClientId=client_id,
    )
    if collision_shape < 0 or visual_shape < 0:
        raise ReplaySceneError(f"failed to create replay shape: {definition.semantic_id}")
    body = pb.createMultiBody(
        baseMass=0.0,
        baseCollisionShapeIndex=collision_shape,
        baseVisualShapeIndex=visual_shape,
        basePosition=definition.center_m,
        baseOrientation=b31.BASE_ORIENTATION,
        physicsClientId=client_id,
    )
    if body < 0:
        raise ReplaySceneError(f"failed to create replay body: {definition.semantic_id}")
    return body


class PyBulletEvidenceReplaySession:
    """Own one explicit PyBullet client and apply registered snapshots only."""

    def __init__(
        self,
        *,
        connection_mode: int = pb.DIRECT,
    ) -> None:
        self._initialize(
            load_registered_frozen_evidence_replay(),
            connection_mode=connection_mode,
        )

    @classmethod
    def _from_attested_plan(
        cls,
        plan: FrozenEvidenceReplayPlan,
        *,
        connection_mode: int = pb.DIRECT,
    ) -> PyBulletEvidenceReplaySession:
        """Construct from an attested plan for isolated tests only."""

        instance = cls.__new__(cls)
        instance._initialize(plan, connection_mode=connection_mode)
        return instance

    def _initialize(
        self,
        plan: FrozenEvidenceReplayPlan,
        *,
        connection_mode: int,
    ) -> None:
        if not isinstance(plan, FrozenEvidenceReplayPlan):
            raise TypeError("plan must be FrozenEvidenceReplayPlan")
        if isinstance(connection_mode, bool) or connection_mode not in {pb.DIRECT, pb.GUI}:
            raise ValueError("connection_mode must be pybullet.DIRECT or pybullet.GUI")
        self._plan = plan
        self._connection_mode = connection_mode
        self._client_id: int | None = None
        self._robot_body: int | None = None
        self._component_body: int | None = None
        self._environment_bodies: tuple[tuple[str, int], ...] = ()
        self._current_replay_index: int | None = None
        self._current_frame_index: int | None = None
        self._owner_thread_id = threading.get_ident()
        self._state = _ReplaySessionState.NEW

    def _require_owner_thread(self) -> None:
        if threading.get_ident() != self._owner_thread_id:
            raise ReplaySessionStateError("PyBullet replay access is owner-thread only")

    @property
    def plan(self) -> FrozenEvidenceReplayPlan:
        return self._plan

    @property
    def is_open(self) -> bool:
        self._require_owner_thread()
        return (
            self._state is _ReplaySessionState.OPEN
            and self._client_id is not None
            and bool(pb.isConnected(physicsClientId=self._client_id))
        )

    @property
    def lifecycle_state(self) -> str:
        self._require_owner_thread()
        return self._state.value

    @property
    def cleanup_pending(self) -> bool:
        self._require_owner_thread()
        return self._state is _ReplaySessionState.CLEANUP_PENDING

    @property
    def client_id(self) -> int:
        return self._require_open_client()

    @property
    def robot_body(self) -> int:
        self._require_open_client()
        if self._robot_body is None:
            raise ReplaySessionStateError("replay robot is unavailable")
        return self._robot_body

    @property
    def current_snapshot(self) -> FrozenReplaySnapshot:
        self._require_open_client()
        if self._current_replay_index is None:
            raise ReplaySessionStateError("no replay snapshot has been applied")
        return self._plan.snapshot_at(self._current_replay_index)

    @property
    def current_frame(self) -> FrozenReplayFrame:
        self._require_open_client()
        if self._current_frame_index is None:
            raise ReplaySessionStateError("no replay frame has been applied")
        return self._plan.frame_at(self._current_frame_index)

    def _require_open_client(self) -> int:
        self._require_owner_thread()
        if self._state is _ReplaySessionState.CLEANUP_PENDING:
            raise ReplaySessionStateError("replay session cleanup is pending")
        if self._state is not _ReplaySessionState.OPEN or self._client_id is None:
            raise ReplaySessionStateError("replay session is not open")
        if not pb.isConnected(physicsClientId=self._client_id):
            self._mark_closed()
            raise ReplaySessionStateError("PyBullet replay client disconnected unexpectedly")
        return self._client_id

    def _mark_closed(self) -> None:
        self._client_id = None
        self._robot_body = None
        self._component_body = None
        self._environment_bodies = ()
        self._current_replay_index = None
        self._current_frame_index = None
        self._state = _ReplaySessionState.CLOSED

    def _disconnect_owned_client(self, client_id: int) -> None:
        if self._client_id != client_id:
            raise ReplaySessionStateError("PyBullet replay client ownership changed")
        if not pb.isConnected(physicsClientId=client_id):
            self._mark_closed()
            return
        pb.disconnect(physicsClientId=client_id)
        if pb.isConnected(physicsClientId=client_id):
            raise RuntimeError("PyBullet replay client remained connected")
        self._mark_closed()

    def _disconnect_after_failure(
        self,
        client_id: int,
        original: BaseException,
    ) -> None:
        try:
            self._disconnect_owned_client(client_id)
        except BaseException as cleanup_error:
            self._state = _ReplaySessionState.CLEANUP_PENDING
            if isinstance(original, Exception) and isinstance(
                cleanup_error,
                Exception,
            ):
                raise ReplaySceneError(
                    "replay scene failed and PyBullet cleanup also failed"
                ) from ExceptionGroup(
                    "replay construction and cleanup failures",
                    [original, cleanup_error],
                )
            raise BaseExceptionGroup(
                "replay operation and cleanup failures",
                [original, cleanup_error],
            ) from None

    def open(self) -> PyBulletEvidenceReplaySession:
        self._require_owner_thread()
        if self._state is _ReplaySessionState.CLOSED:
            raise ReplaySessionStateError("closed replay session cannot be reopened")
        if self._state is _ReplaySessionState.CLEANUP_PENDING:
            raise ReplaySessionStateError("replay session cleanup is pending")
        if self._state is _ReplaySessionState.OPEN or self._client_id is not None:
            raise ReplaySessionStateError("replay session is already open")
        attest_replay_runtime(self._plan)
        client_id = pb.connect(self._connection_mode)
        if isinstance(client_id, bool) or not isinstance(client_id, int) or client_id < 0:
            self._mark_closed()
            raise ReplaySceneError("PyBullet replay connection failed")
        self._client_id = client_id
        self._state = _ReplaySessionState.OPEN
        try:
            pb.resetSimulation(physicsClientId=client_id)
            data_root = Path(pybullet_data.getDataPath()).resolve(strict=True)
            robot = b31.load_kuka(client_id, data_root, b31.SELF_COLLISION_FLAGS)
            if isinstance(robot, bool) or not isinstance(robot, int) or robot < 0:
                raise ReplaySceneError("frozen KUKA body identity is invalid")
            inventory = b31.kuka_link_inventory(robot, client_id)
            b31.verify_kuka_urdf_topology(
                inventory,
                data_root / b31.KUKA_URDF_RELATIVE,
            )
            definitions = b31.frozen_box_definitions()
            b31.validate_frozen_box_definitions(definitions)
            bodies = tuple(
                (definition.semantic_id, _create_replay_box(definition, client_id))
                for definition in definitions
            )
            if (
                len(bodies) != 7
                or len({semantic_id for semantic_id, _ in bodies}) != 7
                or pb.getNumBodies(physicsClientId=client_id) != 8
            ):
                raise ReplaySceneError("frozen replay body inventory changed")
            component_body = dict(bodies).get("blue_component")
            if component_body is None:
                raise ReplaySceneError("frozen component body is unavailable")
            self._robot_body = robot
            self._component_body = component_body
            self._environment_bodies = tuple(
                (semantic_id, body)
                for semantic_id, body in bodies
                if semantic_id != "blue_component"
            )
            return self
        except BaseException as exc:
            self._disconnect_after_failure(client_id, exc)
            if not isinstance(exc, Exception):
                raise
            if isinstance(exc, PyBulletEvidenceReplayError):
                raise
            raise ReplaySceneError("failed to construct frozen replay scene") from exc

    def _apply_frozen_state(
        self,
        frame: FrozenReplayFrame,
    ) -> tuple[
        tuple[float, ...],
        tuple[float, float, float],
        tuple[float, float, float, float],
    ]:
        client_id = self._require_open_client()
        robot = self.robot_body
        if self._component_body is None:
            raise ReplaySessionStateError("replay component is unavailable")
        try:
            for joint_index, position in zip(
                CONTROLLED_JOINT_INDICES,
                frame.joint_positions,
                strict=True,
            ):
                pb.resetJointState(
                    bodyUniqueId=robot,
                    jointIndex=joint_index,
                    targetValue=position,
                    physicsClientId=client_id,
                )
            pb.resetBasePositionAndOrientation(
                self._component_body,
                frame.component_position_m,
                frame.component_quaternion_xyzw,
                physicsClientId=client_id,
            )
            joints = tuple(
                float(
                    pb.getJointState(
                        robot,
                        joint_index,
                        physicsClientId=client_id,
                    )[0]
                )
                for joint_index in CONTROLLED_JOINT_INDICES
            )
            raw_position, raw_orientation = pb.getBasePositionAndOrientation(
                self._component_body,
                physicsClientId=client_id,
            )
            position = cast(tuple[float, float, float], tuple(float(v) for v in raw_position))
            orientation = cast(
                tuple[float, float, float, float],
                tuple(float(v) for v in raw_orientation),
            )
            if any(not math.isfinite(value) for value in (*joints, *position, *orientation)):
                raise ReplaySceneError("PyBullet replay readback is non-finite")
            if joints != frame.joint_positions:
                raise ReplaySceneError("PyBullet joint readback differs from frozen frame")
            if not _position_matches(position, frame.component_position_m):
                raise ReplaySceneError(
                    "PyBullet component position differs from frozen frame"
                )
            if not _quaternion_matches_rotation(
                orientation,
                frame.component_quaternion_xyzw,
            ):
                raise ReplaySceneError(
                    "PyBullet component orientation differs from frozen frame"
                )
        except BaseException as exc:
            self._disconnect_after_failure(client_id, exc)
            if not isinstance(exc, Exception):
                raise
            if isinstance(exc, PyBulletEvidenceReplayError):
                raise
            raise ReplaySceneError("failed to apply frozen replay frame") from exc
        return joints, position, orientation

    def apply_frame(self, frame_index: int) -> ReplayFrameReadback:
        frame = self._plan.frame_at(frame_index)
        joints, position, orientation = self._apply_frozen_state(frame)
        self._current_frame_index = frame_index
        self._current_replay_index = None
        return ReplayFrameReadback(frame, joints, position, orientation)

    def apply_snapshot(self, replay_index: int) -> ReplaySnapshotReadback:
        snapshot = self._plan.snapshot_at(replay_index)
        frame = self._plan.frame_at(snapshot.semantic_snapshot_index)
        joints, position, orientation = self._apply_frozen_state(frame)
        self._current_replay_index = replay_index
        self._current_frame_index = snapshot.semantic_snapshot_index
        return ReplaySnapshotReadback(snapshot, joints, position, orientation)

    def next_snapshot(self) -> ReplaySnapshotReadback:
        self._require_open_client()
        target = 0 if self._current_replay_index is None else self._current_replay_index + 1
        return self.apply_snapshot(target)

    def previous_snapshot(self) -> ReplaySnapshotReadback:
        self._require_open_client()
        if self._current_replay_index is None:
            raise ReplaySessionStateError("no current snapshot for previous navigation")
        return self.apply_snapshot(self._current_replay_index - 1)

    def probe_connection(self) -> bool:
        """Probe the exact owned client; callable only by the owner thread."""

        self._require_owner_thread()
        if self._state is not _ReplaySessionState.OPEN or self._client_id is None:
            raise ReplaySessionStateError("replay session is not open")
        if pb.isConnected(physicsClientId=self._client_id):
            return True
        self._mark_closed()
        return False

    def reset_view(self) -> None:
        client_id = self._require_open_client()
        if self._connection_mode == pb.DIRECT:
            return
        try:
            pb.resetDebugVisualizerCamera(
                cameraDistance=REPLAY_CAMERA_DISTANCE,
                cameraYaw=REPLAY_CAMERA_YAW,
                cameraPitch=REPLAY_CAMERA_PITCH,
                cameraTargetPosition=REPLAY_CAMERA_TARGET,
                physicsClientId=client_id,
            )
        except BaseException as exc:
            self._disconnect_after_failure(client_id, exc)
            if not isinstance(exc, Exception):
                raise
            raise ReplaySceneError("failed to reset replay presentation view") from exc

    def close(self) -> None:
        self._require_owner_thread()
        if self._state is _ReplaySessionState.CLOSED:
            return
        if self._state is _ReplaySessionState.NEW:
            self._mark_closed()
            return
        client_id = self._client_id
        if client_id is None:
            self._state = _ReplaySessionState.CLEANUP_PENDING
            raise ReplaySessionStateError("cleanup-pending session lost client ownership")
        try:
            self._disconnect_owned_client(client_id)
        except BaseException as exc:
            self._state = _ReplaySessionState.CLEANUP_PENDING
            if isinstance(exc, Exception):
                raise ReplaySessionStateError("PyBullet replay disconnect failed") from exc
            raise

    def __enter__(self) -> PyBulletEvidenceReplaySession:
        return self.open()

    def __exit__(
        self,
        exc_type: object,
        exc: BaseException | None,
        traceback: object,
    ) -> None:
        try:
            self.close()
        except BaseException as cleanup_error:
            if exc is None:
                raise
            raise BaseExceptionGroup(
                "replay body and cleanup failures",
                [exc, cleanup_error],
            ) from None


__all__ = (
    "PyBulletEvidenceReplayError",
    "PyBulletEvidenceReplaySession",
    "ReplayFrameReadback",
    "ReplayRuntimeAttestation",
    "ReplayRuntimeIntegrityError",
    "ReplaySceneError",
    "ReplaySessionStateError",
    "ReplaySnapshotReadback",
    "attest_replay_runtime",
)
