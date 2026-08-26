"""Single-owner coordinator for frozen PyBullet evidence replay.

The coordinator serializes presentation mutations. It never computes robotics
evidence and never exposes the owned PyBullet session to request workers.
"""

from __future__ import annotations

import secrets
import threading
import time
from concurrent.futures import Future, TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Callable, Final, Protocol

from src.prototype5.frozen_evidence_replay import (
    EXPECTED_B3_2_RESULT,
    EXPECTED_FAILURE_CODE,
    EXPECTED_FRAME_COUNT,
    REPLAY_BINDING_ID,
    REPLAY_SCENARIO_ID,
    FrozenEvidenceReplayError,
    FrozenReplayFrame,
)
from src.prototype5.pybullet_evidence_replay import (
    PyBulletEvidenceReplaySession,
    ReplayClientDisconnectedError,
    ReplayFrameReadback,
    ReplayRuntimeIntegrityError,
    ReplaySceneError,
    ReplaySessionStateError,
)


MAX_SAFE_INTEGER: Final[int] = 9_007_199_254_740_991
REPLAY_FRAME_COUNT: Final[int] = EXPECTED_FRAME_COUNT
KEY_SNAPSHOT_INDICES: Final[tuple[int, ...]] = (
    0,
    78,
    118,
    119,
    157,
    311,
    351,
    352,
    390,
    468,
)
ALLOWED_CONTROLS: Final[tuple[str, ...]] = (
    "START",
    "PAUSE",
    "RESUME",
    "NEXT_SNAPSHOT",
    "PREVIOUS_SNAPSHOT",
    "STOP",
    "RESET_VIEW",
)
B2_SHA256: Final[str] = (
    "a5a468145aea5aa21a649cccd1de3d6d2f8f15349d4b326db9380a6ad1256554"
)
B3_2_SHA256: Final[str] = (
    "11c8b83f8c4d0545c9a8df604046a335acb00121a51bf6e1d5b39504991c1798"
)
PRESENTATION_LABELS: Final[tuple[str, ...]] = (
    "EVIDENCE REPLAY",
    "NOT PHYSICAL EXECUTION",
    "DISCRETE SAMPLED STATES — NO DYNAMIC TIMING",
)


class ReplayLifecycle(StrEnum):
    IDLE = "IDLE"
    STARTING = "STARTING"
    PAUSED = "PAUSED"
    PLAYING = "PLAYING"
    COMPLETED = "COMPLETED"
    STOPPING = "STOPPING"
    FAILED = "FAILED"
    CLEANUP_FAILED = "CLEANUP_FAILED"


class ReplayControl(StrEnum):
    START = "START"
    PAUSE = "PAUSE"
    RESUME = "RESUME"
    NEXT_SNAPSHOT = "NEXT_SNAPSHOT"
    PREVIOUS_SNAPSHOT = "PREVIOUS_SNAPSHOT"
    STOP = "STOP"
    RESET_VIEW = "RESET_VIEW"


class ReplayLastErrorCode(StrEnum):
    RUNTIME_INTEGRITY_FAILED = "REPLAY_RUNTIME_INTEGRITY_FAILED"
    SCENE_FAILED = "REPLAY_SCENE_FAILED"
    GUI_CLOSED = "REPLAY_GUI_CLOSED"
    CLEANUP_UNRESOLVED = "REPLAY_CLEANUP_UNRESOLVED"


class ReplayErrorCode(StrEnum):
    SCENARIO_NOT_FOUND = "REPLAY_SCENARIO_NOT_FOUND"
    SCENARIO_NOT_REPLAYABLE = "REPLAY_SCENARIO_NOT_REPLAYABLE"
    SESSION_ACTIVE = "REPLAY_SESSION_ACTIVE"
    SESSION_STALE = "REPLAY_SESSION_STALE"
    CONTROL_VERSION_STALE = "REPLAY_CONTROL_VERSION_STALE"
    CONTROL_INVALID_STATE = "REPLAY_CONTROL_INVALID_STATE"
    FRAME_BOUNDARY = "REPLAY_FRAME_BOUNDARY"
    REQUEST_INVALID = "REPLAY_REQUEST_INVALID"
    COMMAND_CHANNEL_FULL = "REPLAY_COMMAND_CHANNEL_FULL"
    CLEANUP_UNRESOLVED = "REPLAY_CLEANUP_UNRESOLVED"
    SERVER_SHUTTING_DOWN = "REPLAY_SERVER_SHUTTING_DOWN"
    RUNTIME_INTEGRITY_FAILED = "REPLAY_RUNTIME_INTEGRITY_FAILED"
    VERSION_EXHAUSTED = "REPLAY_VERSION_EXHAUSTED"
    SCENE_FAILED = "REPLAY_SCENE_FAILED"
    COMMAND_EXPIRED = "REPLAY_COMMAND_EXPIRED"
    START_TIMEOUT = "REPLAY_START_TIMEOUT"
    CONTROL_SETTLEMENT_UNKNOWN = "REPLAY_CONTROL_SETTLEMENT_UNKNOWN"


_HTTP_STATUS: Final[dict[ReplayErrorCode, int]] = {
    ReplayErrorCode.SCENARIO_NOT_FOUND: 404,
    ReplayErrorCode.SCENARIO_NOT_REPLAYABLE: 409,
    ReplayErrorCode.SESSION_ACTIVE: 409,
    ReplayErrorCode.SESSION_STALE: 409,
    ReplayErrorCode.CONTROL_VERSION_STALE: 409,
    ReplayErrorCode.CONTROL_INVALID_STATE: 409,
    ReplayErrorCode.FRAME_BOUNDARY: 409,
    ReplayErrorCode.REQUEST_INVALID: 422,
    ReplayErrorCode.COMMAND_CHANNEL_FULL: 429,
    ReplayErrorCode.CLEANUP_UNRESOLVED: 503,
    ReplayErrorCode.SERVER_SHUTTING_DOWN: 503,
    ReplayErrorCode.RUNTIME_INTEGRITY_FAILED: 503,
    ReplayErrorCode.VERSION_EXHAUSTED: 503,
    ReplayErrorCode.SCENE_FAILED: 500,
    ReplayErrorCode.COMMAND_EXPIRED: 504,
    ReplayErrorCode.START_TIMEOUT: 504,
    ReplayErrorCode.CONTROL_SETTLEMENT_UNKNOWN: 504,
}


class ReplayCoordinatorError(RuntimeError):
    def __init__(self, code: ReplayErrorCode) -> None:
        super().__init__(code.value)
        self.code = code
        self.http_status = _HTTP_STATUS[code]


class ReplayOwnerThreadSurvivedError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ReplayTimings:
    startup_seconds: float = 15.0
    control_seconds: float = 5.0
    idle_seconds: float = 600.0
    shutdown_seconds: float = 5.0
    liveness_seconds: float = 0.5
    cadence_seconds: float = 0.05
    tombstone_seconds: float = 60.0

    def __post_init__(self) -> None:
        values = (
            self.startup_seconds,
            self.control_seconds,
            self.idle_seconds,
            self.shutdown_seconds,
            self.liveness_seconds,
            self.cadence_seconds,
            self.tombstone_seconds,
        )
        if any(isinstance(value, bool) or not isinstance(value, float) or value <= 0 for value in values):
            raise ValueError("replay timing values must be positive floats")


@dataclass(frozen=True, slots=True)
class ReplayFrameProjection:
    frame_index: int
    semantic_snapshot_index: int
    route_configuration_index: int
    route_state: str
    phase: str
    boundary_snapshot: str
    is_key_snapshot: bool


@dataclass(frozen=True, slots=True)
class RecordedFailureProjection:
    semantic_snapshot_index: int = 352
    route_state: str = "DESTINATION_PLACE"
    phase: str = "RELEASE_BOUNDARY"
    boundary_snapshot: str = "POST"
    pair_index: int = 78
    signed_distance_m: float = -9.290505685985613e-07
    decision: str = EXPECTED_FAILURE_CODE


@dataclass(frozen=True, slots=True)
class ReplayQualificationProjection:
    overall_result: str = EXPECTED_B3_2_RESULT
    scientific_failure_count: int = 118
    forbidden_contact_failure_count: int = 0
    support_material_penetration_failure_count: int = 118
    required_support_missing_failure_count: int = 0
    failure_codes_present: tuple[str, ...] = (EXPECTED_FAILURE_CODE,)
    recorded_failure_example: RecordedFailureProjection = RecordedFailureProjection()


@dataclass(frozen=True, slots=True)
class ReplayStateProjection:
    contract_id: str
    contract_version: str
    scenario_id: str
    binding_id: str
    session_id: str | None
    control_version: int
    projection_version: int
    lifecycle_state: str
    command_in_flight: bool
    current_frame: ReplayFrameProjection | None
    frame_count: int
    key_snapshot_indices: tuple[int, ...]
    allowed_controls: tuple[str, ...]
    available_controls: tuple[str, ...]
    presentation_cadence_ms: int
    b2_sha256: str
    b3_2_sha256: str
    qualification: ReplayQualificationProjection
    presentation_labels: tuple[str, ...]
    physical_execution_authority: str
    last_error_code: str | None
    updated_at_utc: str


class ReplaySession(Protocol):
    @property
    def current_frame(self) -> FrozenReplayFrame: ...

    def open(self) -> ReplaySession: ...

    def apply_frame(self, frame_index: int) -> ReplayFrameReadback: ...

    def probe_connection(self) -> bool: ...

    def reset_view(self) -> None: ...

    def close(self) -> None: ...


@dataclass(slots=True)
class _AdmittedCommand:
    control: ReplayControl
    scenario_id: str
    session_id: str
    expected_control_version: int | None
    deadline: float
    future: Future[ReplayStateProjection]
    started: bool = False
    settlement: ReplayStateProjection | ReplayCoordinatorError | None = None


@dataclass(frozen=True, slots=True)
class _StopTombstone:
    scenario_id: str
    session_id: str
    expected_control_version: int
    expires_at: float
    response: ReplayStateProjection


class ReplayCoordinator:
    """Coordinate one registered replay through exactly one owner thread."""

    def __init__(
        self,
        session_factory: Callable[[], ReplaySession] = PyBulletEvidenceReplaySession,
        *,
        known_scenario_ids: frozenset[str] = frozenset({REPLAY_SCENARIO_ID}),
        timings: ReplayTimings = ReplayTimings(),
        monotonic_clock: Callable[[], float] = time.monotonic,
        utc_clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        if not callable(session_factory):
            raise TypeError("session_factory must be callable")
        if REPLAY_SCENARIO_ID not in known_scenario_ids:
            raise ValueError("registered replay scenario is absent")
        self._session_factory = session_factory
        self._known_scenario_ids = known_scenario_ids
        self._timings = timings
        self._monotonic = monotonic_clock
        self._utc_clock = utc_clock
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._ready = threading.Event()
        self._thread: threading.Thread | None = None
        self._started = False
        self._shutdown_requested = False
        self._shutdown_error: BaseException | None = None
        self._pending_command: _AdmittedCommand | None = None
        self._executing_command: _AdmittedCommand | None = None
        self._command_in_flight = False
        self._periodic_in_progress = False
        self._admission_waiters = 0
        self._internal_lifecycle = ReplayLifecycle.IDLE
        self._public_lifecycle = ReplayLifecycle.IDLE
        self._session_id: str | None = None
        self._provisional_session_id: str | None = None
        self._control_version = 0
        self._projection_version = 0
        self._current_frame: ReplayFrameProjection | None = None
        self._last_error: ReplayLastErrorCode | None = None
        self._updated_at_utc = self._utc_timestamp()
        self._last_activity: float | None = None
        self._next_cadence: float | None = None
        self._next_liveness: float | None = None
        self._stop_tombstone: _StopTombstone | None = None
        self._version_exhausted = False
        self._owner_session: ReplaySession | None = None

    def _utc_timestamp(self) -> str:
        value = self._utc_clock()
        if not isinstance(value, datetime) or value.tzinfo is None:
            raise ValueError("utc_clock must return an aware datetime")
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    def start(self) -> None:
        with self._condition:
            if self._started or self._thread is not None:
                raise RuntimeError("replay coordinator has already been started")
            self._started = True
            self._thread = threading.Thread(
                target=self._owner_loop,
                name="prototype5-replay-owner",
                daemon=False,
            )
            self._thread.start()
        if not self._ready.wait(timeout=self._timings.startup_seconds):
            raise RuntimeError("replay coordinator owner did not become ready")

    def shutdown(self) -> None:
        with self._condition:
            if not self._started:
                return
            self._shutdown_requested = True
            self._condition.notify_all()
            thread = self._thread
        if thread is None:
            raise RuntimeError("replay coordinator owner is unavailable")
        thread.join(timeout=self._timings.shutdown_seconds)
        if thread.is_alive():
            raise ReplayOwnerThreadSurvivedError("REPLAY_OWNER_THREAD_SURVIVED")
        with self._condition:
            self._started = False
            error = self._shutdown_error
        if error is not None:
            raise error

    def preflight_error(self) -> ReplayErrorCode | None:
        with self._lock:
            return ReplayErrorCode.VERSION_EXHAUSTED if self._version_exhausted else None

    def get_state(self) -> ReplayStateProjection:
        with self._lock:
            if self._version_exhausted:
                raise ReplayCoordinatorError(ReplayErrorCode.VERSION_EXHAUSTED)
            return self._projection_locked()

    def start_replay(self, scenario_id: str) -> ReplayStateProjection:
        self._resolve_scenario(scenario_id)
        deadline = self._monotonic() + self._timings.startup_seconds
        with self._condition:
            self._wait_for_periodic_locked(deadline)
            self._reject_common_locked()
            if self._public_lifecycle is ReplayLifecycle.CLEANUP_FAILED:
                raise ReplayCoordinatorError(ReplayErrorCode.CLEANUP_UNRESOLVED)
            if (
                self._public_lifecycle is not ReplayLifecycle.IDLE
                or self._session_id is not None
                or self._provisional_session_id is not None
            ):
                raise ReplayCoordinatorError(ReplayErrorCode.SESSION_ACTIVE)
            if self._command_in_flight:
                raise ReplayCoordinatorError(ReplayErrorCode.COMMAND_CHANNEL_FULL)
            provisional_session_id = secrets.token_urlsafe(32)
            command = _AdmittedCommand(
                control=ReplayControl.START,
                scenario_id=scenario_id,
                session_id=provisional_session_id,
                expected_control_version=None,
                deadline=deadline,
                future=Future(),
            )
            self._stop_tombstone = None
            self._provisional_session_id = provisional_session_id
            self._internal_lifecycle = ReplayLifecycle.STARTING
            self._admit_locked(command)
        return self._await_settlement(command)

    def control(
        self,
        *,
        scenario_id: str,
        session_id: str,
        expected_control_version: int,
        control: ReplayControl,
    ) -> ReplayStateProjection:
        self._resolve_scenario(scenario_id)
        if control is ReplayControl.START:
            raise ReplayCoordinatorError(ReplayErrorCode.CONTROL_INVALID_STATE)
        deadline = self._monotonic() + self._timings.control_seconds
        with self._condition:
            self._wait_for_periodic_locked(deadline)
            self._reject_common_locked()
            tombstone = self._eligible_tombstone_locked(
                scenario_id, session_id, expected_control_version, control
            )
            if tombstone is not None:
                return tombstone.response
            if self._session_id != session_id:
                raise ReplayCoordinatorError(ReplayErrorCode.SESSION_STALE)
            if self._control_version != expected_control_version:
                raise ReplayCoordinatorError(ReplayErrorCode.CONTROL_VERSION_STALE)
            if self._command_in_flight:
                raise ReplayCoordinatorError(ReplayErrorCode.COMMAND_CHANNEL_FULL)
            self._validate_control_locked(control)
            command = _AdmittedCommand(
                control=control,
                scenario_id=scenario_id,
                session_id=session_id,
                expected_control_version=expected_control_version,
                deadline=deadline,
                future=Future(),
            )
            if control is ReplayControl.STOP:
                self._internal_lifecycle = ReplayLifecycle.STOPPING
            self._last_activity = self._monotonic()
            self._admit_locked(command)
        return self._await_settlement(command)

    def _resolve_scenario(self, scenario_id: str) -> None:
        if scenario_id not in self._known_scenario_ids:
            raise ReplayCoordinatorError(ReplayErrorCode.SCENARIO_NOT_FOUND)
        if scenario_id != REPLAY_SCENARIO_ID:
            raise ReplayCoordinatorError(ReplayErrorCode.SCENARIO_NOT_REPLAYABLE)

    def _wait_for_periodic_locked(self, deadline: float) -> None:
        if not self._periodic_in_progress:
            return
        self._admission_waiters += 1
        try:
            while self._periodic_in_progress:
                remaining = deadline - self._monotonic()
                if remaining <= 0:
                    raise ReplayCoordinatorError(ReplayErrorCode.COMMAND_EXPIRED)
                self._condition.wait(timeout=remaining)
        finally:
            self._admission_waiters -= 1
            self._condition.notify_all()

    def _reject_common_locked(self) -> None:
        if self._version_exhausted:
            raise ReplayCoordinatorError(ReplayErrorCode.VERSION_EXHAUSTED)
        if self._shutdown_requested:
            raise ReplayCoordinatorError(ReplayErrorCode.SERVER_SHUTTING_DOWN)
        if not self._started:
            raise ReplayCoordinatorError(ReplayErrorCode.SERVER_SHUTTING_DOWN)

    def _eligible_tombstone_locked(
        self,
        scenario_id: str,
        session_id: str,
        expected_control_version: int,
        control: ReplayControl,
    ) -> _StopTombstone | None:
        tombstone = self._stop_tombstone
        if tombstone is not None and tombstone.expires_at <= self._monotonic():
            self._stop_tombstone = None
            tombstone = None
        if (
            self._public_lifecycle is ReplayLifecycle.IDLE
            and self._session_id is None
            and self._provisional_session_id is None
            and not self._command_in_flight
            and tombstone is not None
            and control is ReplayControl.STOP
            and (
                scenario_id,
                session_id,
                expected_control_version,
            )
            == (
                tombstone.scenario_id,
                tombstone.session_id,
                tombstone.expected_control_version,
            )
        ):
            return tombstone
        return None

    def _validate_control_locked(self, control: ReplayControl) -> None:
        lifecycle = self._public_lifecycle
        frame_index = None if self._current_frame is None else self._current_frame.frame_index
        legal = {
            ReplayLifecycle.PAUSED: {
                ReplayControl.RESUME,
                ReplayControl.NEXT_SNAPSHOT,
                ReplayControl.PREVIOUS_SNAPSHOT,
                ReplayControl.STOP,
                ReplayControl.RESET_VIEW,
            },
            ReplayLifecycle.PLAYING: {
                ReplayControl.PAUSE,
                ReplayControl.STOP,
                ReplayControl.RESET_VIEW,
            },
            ReplayLifecycle.COMPLETED: {
                ReplayControl.PREVIOUS_SNAPSHOT,
                ReplayControl.STOP,
                ReplayControl.RESET_VIEW,
            },
            ReplayLifecycle.FAILED: {ReplayControl.STOP},
            ReplayLifecycle.CLEANUP_FAILED: {ReplayControl.STOP},
        }
        if control not in legal.get(lifecycle, set()):
            raise ReplayCoordinatorError(ReplayErrorCode.CONTROL_INVALID_STATE)
        if (
            control is ReplayControl.NEXT_SNAPSHOT
            and (frame_index is None or frame_index >= REPLAY_FRAME_COUNT - 1)
        ) or (
            control is ReplayControl.PREVIOUS_SNAPSHOT
            and (frame_index is None or frame_index <= 0)
        ):
            raise ReplayCoordinatorError(ReplayErrorCode.FRAME_BOUNDARY)

    def _admit_locked(self, command: _AdmittedCommand) -> None:
        if self._command_in_flight or self._pending_command is not None:
            raise AssertionError("mutation admission ownership is inconsistent")
        self._command_in_flight = True
        self._pending_command = command
        self._condition.notify_all()

    def _await_settlement(self, command: _AdmittedCommand) -> ReplayStateProjection:
        remaining = max(0.0, command.deadline - self._monotonic())
        try:
            return command.future.result(timeout=remaining)
        except FutureTimeoutError:
            future_to_resolve: Future[ReplayStateProjection] | None = None
            error: ReplayCoordinatorError
            with self._condition:
                if isinstance(command.settlement, ReplayStateProjection):
                    return command.settlement
                if isinstance(command.settlement, ReplayCoordinatorError):
                    raise command.settlement
                if self._pending_command is command and not command.started:
                    self._pending_command = None
                    self._command_in_flight = False
                    self._provisional_session_id = None
                    self._internal_lifecycle = self._public_lifecycle
                    error = ReplayCoordinatorError(ReplayErrorCode.COMMAND_EXPIRED)
                    command.settlement = error
                    future_to_resolve = command.future
                    self._condition.notify_all()
                else:
                    code = (
                        ReplayErrorCode.START_TIMEOUT
                        if command.control is ReplayControl.START
                        else ReplayErrorCode.CONTROL_SETTLEMENT_UNKNOWN
                    )
                    raise ReplayCoordinatorError(code)
            if future_to_resolve is not None:
                future_to_resolve.set_exception(error)
            raise error

    def _owner_loop(self) -> None:
        self._ready.set()
        try:
            while True:
                command: _AdmittedCommand | None = None
                periodic: str | None = None
                pending_shutdown: _AdmittedCommand | None = None
                with self._condition:
                    now = self._monotonic()
                    if self._shutdown_requested:
                        if self._pending_command is None:
                            break
                        pending_shutdown = self._pending_command
                        self._pending_command = None
                    elif self._pending_command is not None:
                        command = self._pending_command
                        self._pending_command = None
                        command.started = True
                        self._executing_command = command
                    elif self._admission_waiters:
                        self._condition.wait()
                        continue
                    elif pending_shutdown is None:
                        periodic = self._due_periodic_locked(now)
                        if periodic is None:
                            self._condition.wait(timeout=self._wait_timeout_locked(now))
                            continue
                        self._periodic_in_progress = True
                if pending_shutdown is not None:
                    self._settle_shutdown_pending(pending_shutdown)
                    continue
                if command is not None:
                    if command.deadline <= self._monotonic():
                        self._settle_command_error(
                            command, ReplayErrorCode.COMMAND_EXPIRED
                        )
                    else:
                        self._execute_command(command)
                elif periodic is not None:
                    self._execute_periodic(periodic)
        except BaseException as exc:
            self._shutdown_error = exc
        finally:
            try:
                if self._owner_session is not None:
                    self._owner_session.close()
                    self._owner_session = None
            except BaseException as exc:
                if self._shutdown_error is None:
                    self._shutdown_error = ReplayCoordinatorError(
                        ReplayErrorCode.CLEANUP_UNRESOLVED
                    )
                else:
                    self._shutdown_error = BaseExceptionGroup(
                        "replay owner and cleanup failures",
                        [self._shutdown_error, exc],
                    )
            with self._condition:
                self._condition.notify_all()

    def _settle_shutdown_pending(self, command: _AdmittedCommand) -> None:
        self._settle_command_error(command, ReplayErrorCode.SERVER_SHUTTING_DOWN)

    def _due_periodic_locked(self, now: float) -> str | None:
        if self._version_exhausted or self._session_id is None:
            return None
        if self._last_activity is not None and now >= self._last_activity + self._timings.idle_seconds:
            return "idle"
        if self._next_liveness is not None and now >= self._next_liveness:
            return "liveness"
        if self._next_cadence is not None and now >= self._next_cadence:
            return "cadence"
        return None

    def _wait_timeout_locked(self, now: float) -> float | None:
        deadlines: list[float] = []
        if self._session_id is not None and self._last_activity is not None:
            deadlines.append(self._last_activity + self._timings.idle_seconds)
        if self._next_liveness is not None:
            deadlines.append(self._next_liveness)
        if self._next_cadence is not None:
            deadlines.append(self._next_cadence)
        return None if not deadlines else max(0.0, min(deadlines) - now)

    def _execute_command(self, command: _AdmittedCommand) -> None:
        if command.control is ReplayControl.START:
            self._execute_start(command)
            return
        if command.control is ReplayControl.STOP:
            self._execute_stop(command)
            return
        if self._would_exhaust(control_increment=1, projection_increment=1):
            self._latch_version_exhaustion(command)
            return
        if command.control is ReplayControl.PAUSE:
            self._commit_command_state(command, ReplayLifecycle.PAUSED)
        elif command.control is ReplayControl.RESUME:
            self._commit_command_state(command, ReplayLifecycle.PLAYING)
        elif command.control is ReplayControl.NEXT_SNAPSHOT:
            self._execute_navigation(command, 1)
        elif command.control is ReplayControl.PREVIOUS_SNAPSHOT:
            self._execute_navigation(command, -1)
        elif command.control is ReplayControl.RESET_VIEW:
            self._execute_reset_view(command)
        else:
            self._settle_command_error(command, ReplayErrorCode.CONTROL_INVALID_STATE)

    def _execute_start(self, command: _AdmittedCommand) -> None:
        session: ReplaySession | None = None
        try:
            session = self._session_factory()
            self._owner_session = session
            session.open()
            readback = session.apply_frame(0)
        except (FrozenEvidenceReplayError, ReplayRuntimeIntegrityError) as exc:
            self._settle_start_failure(command, session, exc, runtime=True)
            return
        except BaseException as exc:
            self._settle_start_failure(command, session, exc, runtime=False)
            return
        with self._condition:
            self._session_id = command.session_id
            self._provisional_session_id = None
            self._control_version = 1
            self._projection_version = 1
            self._public_lifecycle = ReplayLifecycle.PAUSED
            self._internal_lifecycle = ReplayLifecycle.PAUSED
            self._current_frame = self._frame_projection(readback.frame)
            self._last_error = None
            self._last_activity = self._monotonic()
            self._next_liveness = self._last_activity + self._timings.liveness_seconds
            self._next_cadence = None
            self._updated_at_utc = self._utc_timestamp()
            result = self._complete_command_locked(command)
        self._resolve_command_future(command, result)

    def _settle_start_failure(
        self,
        command: _AdmittedCommand,
        session: ReplaySession | None,
        error: BaseException,
        *,
        runtime: bool,
    ) -> None:
        cleanup_succeeded = self._cleanup_owner_session(session)
        if cleanup_succeeded:
            code = (
                ReplayErrorCode.RUNTIME_INTEGRITY_FAILED
                if runtime
                else ReplayErrorCode.SCENE_FAILED
            )
            last_error = (
                ReplayLastErrorCode.RUNTIME_INTEGRITY_FAILED
                if runtime
                else ReplayLastErrorCode.SCENE_FAILED
            )
            lifecycle = ReplayLifecycle.FAILED
        else:
            code = ReplayErrorCode.CLEANUP_UNRESOLVED
            last_error = ReplayLastErrorCode.CLEANUP_UNRESOLVED
            lifecycle = ReplayLifecycle.CLEANUP_FAILED
        with self._condition:
            self._session_id = command.session_id
            self._provisional_session_id = None
            self._control_version = 1
            self._projection_version = 1
            self._public_lifecycle = lifecycle
            self._internal_lifecycle = lifecycle
            self._current_frame = None
            self._last_error = last_error
            self._last_activity = self._monotonic()
            self._next_cadence = None
            self._next_liveness = None
            self._updated_at_utc = self._utc_timestamp()
            result = self._complete_command_locked(command, error_code=code)
        self._resolve_command_future(command, result)

    def _execute_navigation(self, command: _AdmittedCommand, delta: int) -> None:
        session = self._require_owner_session()
        with self._lock:
            if self._current_frame is None:
                raise AssertionError("navigation has no current frame")
            target = self._current_frame.frame_index + delta
        try:
            readback = session.apply_frame(target)
        except ReplayClientDisconnectedError:
            self._settle_command_gui_closed(command)
            return
        except BaseException:
            self._settle_frame_failure(command)
            return
        lifecycle = (
            ReplayLifecycle.COMPLETED
            if target == REPLAY_FRAME_COUNT - 1
            else ReplayLifecycle.PAUSED
        )
        self._commit_command_state(command, lifecycle, frame=readback.frame)

    def _execute_reset_view(self, command: _AdmittedCommand) -> None:
        try:
            self._require_owner_session().reset_view()
        except ReplayClientDisconnectedError:
            self._settle_command_gui_closed(command)
            return
        except BaseException:
            self._settle_frame_failure(command)
            return
        with self._lock:
            lifecycle = self._public_lifecycle
        self._commit_command_state(command, lifecycle)

    def _execute_stop(self, command: _AdmittedCommand) -> None:
        cleanup_succeeded = self._cleanup_owner_session(self._owner_session)
        if cleanup_succeeded:
            with self._condition:
                self._canonical_idle_locked()
                result = self._complete_command_locked(
                    command,
                    create_stop_tombstone=True,
                )
            self._resolve_command_future(command, result)
            return
        if self._would_exhaust(control_increment=1, projection_increment=1):
            self._latch_version_exhaustion(command)
            return
        with self._condition:
            self._advance_versions_locked(1, 1)
            self._public_lifecycle = ReplayLifecycle.CLEANUP_FAILED
            self._internal_lifecycle = ReplayLifecycle.CLEANUP_FAILED
            self._last_error = ReplayLastErrorCode.CLEANUP_UNRESOLVED
            self._next_cadence = None
            self._next_liveness = None
            self._updated_at_utc = self._utc_timestamp()
            result = self._complete_command_locked(
                command,
                error_code=ReplayErrorCode.CLEANUP_UNRESOLVED,
            )
        self._resolve_command_future(command, result)

    def _commit_command_state(
        self,
        command: _AdmittedCommand,
        lifecycle: ReplayLifecycle,
        *,
        frame: FrozenReplayFrame | None = None,
    ) -> None:
        with self._condition:
            self._advance_versions_locked(1, 1)
            self._public_lifecycle = lifecycle
            self._internal_lifecycle = lifecycle
            if frame is not None:
                self._current_frame = self._frame_projection(frame)
            self._last_error = None
            now = self._monotonic()
            self._next_cadence = (
                now + self._timings.cadence_seconds
                if lifecycle is ReplayLifecycle.PLAYING
                else None
            )
            if lifecycle in {
                ReplayLifecycle.PAUSED,
                ReplayLifecycle.PLAYING,
                ReplayLifecycle.COMPLETED,
            }:
                self._next_liveness = now + self._timings.liveness_seconds
            self._updated_at_utc = self._utc_timestamp()
            result = self._complete_command_locked(command)
        self._resolve_command_future(command, result)

    def _execute_periodic(self, periodic: str) -> None:
        if periodic == "idle":
            self._execute_idle_expiry()
        elif periodic == "liveness":
            self._execute_liveness()
        elif periodic == "cadence":
            self._execute_cadence()
        else:
            raise AssertionError("unknown replay periodic event")

    def _execute_idle_expiry(self) -> None:
        cleanup_succeeded = self._cleanup_owner_session(self._owner_session)
        if cleanup_succeeded:
            with self._condition:
                self._canonical_idle_locked()
                self._periodic_in_progress = False
                self._condition.notify_all()
            return
        if self._would_exhaust(1, 1):
            self._latch_version_exhaustion(None)
            return
        with self._condition:
            self._advance_versions_locked(1, 1)
            self._public_lifecycle = ReplayLifecycle.CLEANUP_FAILED
            self._internal_lifecycle = ReplayLifecycle.CLEANUP_FAILED
            self._last_error = ReplayLastErrorCode.CLEANUP_UNRESOLVED
            self._next_cadence = None
            self._next_liveness = None
            self._updated_at_utc = self._utc_timestamp()
            self._periodic_in_progress = False
            self._condition.notify_all()

    def _execute_liveness(self) -> None:
        try:
            connected = self._require_owner_session().probe_connection()
        except BaseException:
            connected = False
        if connected:
            with self._condition:
                self._next_liveness = self._monotonic() + self._timings.liveness_seconds
                self._periodic_in_progress = False
                self._condition.notify_all()
            return
        self._settle_periodic_gui_closed()

    def _settle_periodic_gui_closed(self) -> None:
        if self._would_exhaust(1, 1):
            self._latch_version_exhaustion(None)
            return
        cleanup_succeeded = self._cleanup_owner_session(self._owner_session)
        with self._condition:
            self._advance_versions_locked(1, 1)
            self._publish_gui_closed_locked(cleanup_succeeded)
            self._periodic_in_progress = False
            self._condition.notify_all()

    def _settle_command_gui_closed(self, command: _AdmittedCommand) -> None:
        if self._would_exhaust(1, 1):
            self._latch_version_exhaustion(command)
            return
        cleanup_succeeded = self._cleanup_owner_session(self._owner_session)
        with self._condition:
            self._advance_versions_locked(1, 1)
            self._publish_gui_closed_locked(cleanup_succeeded)
            result = self._complete_command_locked(
                command,
                error_code=(
                    None
                    if cleanup_succeeded
                    else ReplayErrorCode.CLEANUP_UNRESOLVED
                ),
            )
        self._resolve_command_future(command, result)

    def _publish_gui_closed_locked(self, cleanup_succeeded: bool) -> None:
        self._public_lifecycle = (
            ReplayLifecycle.FAILED
            if cleanup_succeeded
            else ReplayLifecycle.CLEANUP_FAILED
        )
        self._internal_lifecycle = self._public_lifecycle
        self._last_error = (
            ReplayLastErrorCode.GUI_CLOSED
            if cleanup_succeeded
            else ReplayLastErrorCode.CLEANUP_UNRESOLVED
        )
        self._next_liveness = None
        self._next_cadence = None
        self._updated_at_utc = self._utc_timestamp()

    def _execute_cadence(self) -> None:
        with self._lock:
            if self._current_frame is None:
                raise AssertionError("cadence has no current frame")
            target = self._current_frame.frame_index + 1
        control_increment = 1 if target == REPLAY_FRAME_COUNT - 1 else 0
        if self._would_exhaust(control_increment, 1):
            self._latch_version_exhaustion(None)
            return
        try:
            readback = self._require_owner_session().apply_frame(target)
        except ReplayClientDisconnectedError:
            self._settle_periodic_gui_closed()
            return
        except BaseException:
            self._settle_periodic_frame_failure()
            return
        with self._condition:
            self._advance_versions_locked(control_increment, 1)
            self._current_frame = self._frame_projection(readback.frame)
            self._public_lifecycle = (
                ReplayLifecycle.COMPLETED
                if target == REPLAY_FRAME_COUNT - 1
                else ReplayLifecycle.PLAYING
            )
            self._internal_lifecycle = self._public_lifecycle
            self._next_cadence = (
                None
                if self._public_lifecycle is ReplayLifecycle.COMPLETED
                else self._monotonic() + self._timings.cadence_seconds
            )
            self._updated_at_utc = self._utc_timestamp()
            self._periodic_in_progress = False
            self._condition.notify_all()

    def _settle_frame_failure(self, command: _AdmittedCommand) -> None:
        cleanup_succeeded = self._cleanup_owner_session(self._owner_session)
        if self._would_exhaust(1, 1):
            self._latch_version_exhaustion(command)
            return
        with self._condition:
            self._advance_versions_locked(1, 1)
            self._publish_scene_failure_locked(cleanup_succeeded)
            result = self._complete_command_locked(
                command,
                error_code=(
                    ReplayErrorCode.SCENE_FAILED
                    if cleanup_succeeded
                    else ReplayErrorCode.CLEANUP_UNRESOLVED
                ),
            )
        self._resolve_command_future(command, result)

    def _settle_periodic_frame_failure(self) -> None:
        cleanup_succeeded = self._cleanup_owner_session(self._owner_session)
        if self._would_exhaust(1, 1):
            self._latch_version_exhaustion(None)
            return
        with self._condition:
            self._advance_versions_locked(1, 1)
            self._publish_scene_failure_locked(cleanup_succeeded)
            self._periodic_in_progress = False
            self._condition.notify_all()

    def _publish_scene_failure_locked(self, cleanup_succeeded: bool) -> None:
        self._public_lifecycle = (
            ReplayLifecycle.FAILED
            if cleanup_succeeded
            else ReplayLifecycle.CLEANUP_FAILED
        )
        self._internal_lifecycle = self._public_lifecycle
        self._last_error = (
            ReplayLastErrorCode.SCENE_FAILED
            if cleanup_succeeded
            else ReplayLastErrorCode.CLEANUP_UNRESOLVED
        )
        self._next_cadence = None
        self._next_liveness = None
        self._updated_at_utc = self._utc_timestamp()

    def _would_exhaust(self, control_increment: int, projection_increment: int) -> bool:
        with self._lock:
            return (
                self._control_version > MAX_SAFE_INTEGER - control_increment
                or self._projection_version > MAX_SAFE_INTEGER - projection_increment
            )

    def _latch_version_exhaustion(self, command: _AdmittedCommand | None) -> None:
        with self._condition:
            self._version_exhausted = True
            self._next_cadence = None
            self._next_liveness = None
        self._cleanup_owner_session(self._owner_session)
        with self._condition:
            if command is not None:
                result = self._complete_command_locked(
                    command,
                    error_code=ReplayErrorCode.VERSION_EXHAUSTED,
                )
            else:
                self._periodic_in_progress = False
                self._condition.notify_all()
                result = None
        if command is not None and result is not None:
            self._resolve_command_future(command, result)

    def _cleanup_owner_session(self, session: ReplaySession | None) -> bool:
        if session is None:
            self._owner_session = None
            return True
        try:
            session.close()
        except BaseException:
            self._owner_session = session
            return False
        self._owner_session = None
        return True

    def _require_owner_session(self) -> ReplaySession:
        if self._owner_session is None:
            raise ReplaySessionStateError("replay session ownership is unavailable")
        return self._owner_session

    def _advance_versions_locked(self, control: int, projection: int) -> None:
        if (
            self._control_version > MAX_SAFE_INTEGER - control
            or self._projection_version > MAX_SAFE_INTEGER - projection
        ):
            raise AssertionError("version increment was not guarded")
        self._control_version += control
        self._projection_version += projection

    def _canonical_idle_locked(self) -> None:
        self._internal_lifecycle = ReplayLifecycle.IDLE
        self._public_lifecycle = ReplayLifecycle.IDLE
        self._session_id = None
        self._provisional_session_id = None
        self._control_version = 0
        self._projection_version = 0
        self._current_frame = None
        self._last_error = None
        self._last_activity = None
        self._next_cadence = None
        self._next_liveness = None
        self._updated_at_utc = self._utc_timestamp()

    def _settle_command_error(
        self,
        command: _AdmittedCommand,
        code: ReplayErrorCode,
    ) -> None:
        with self._condition:
            if command.control is ReplayControl.START and code in {
                ReplayErrorCode.COMMAND_EXPIRED,
                ReplayErrorCode.SERVER_SHUTTING_DOWN,
            }:
                self._provisional_session_id = None
                self._internal_lifecycle = self._public_lifecycle
            result = self._complete_command_locked(command, error_code=code)
        self._resolve_command_future(command, result)

    def _complete_command_locked(
        self,
        command: _AdmittedCommand,
        *,
        error_code: ReplayErrorCode | None = None,
        create_stop_tombstone: bool = False,
    ) -> ReplayStateProjection | ReplayCoordinatorError:
        if self._executing_command is command:
            self._executing_command = None
        if self._pending_command is command:
            self._pending_command = None
        self._command_in_flight = False
        self._internal_lifecycle = self._public_lifecycle
        result: ReplayStateProjection | ReplayCoordinatorError
        if error_code is None:
            result = self._projection_locked()
        else:
            result = ReplayCoordinatorError(error_code)
        if create_stop_tombstone:
            if not isinstance(result, ReplayStateProjection):
                raise AssertionError("STOP tombstone requires a successful projection")
            if command.expected_control_version is None:
                raise AssertionError("STOP has no control version")
            self._stop_tombstone = _StopTombstone(
                scenario_id=command.scenario_id,
                session_id=command.session_id,
                expected_control_version=command.expected_control_version,
                expires_at=self._monotonic() + self._timings.tombstone_seconds,
                response=result,
            )
        command.settlement = result
        self._condition.notify_all()
        return result

    @staticmethod
    def _resolve_command_future(
        command: _AdmittedCommand,
        result: ReplayStateProjection | ReplayCoordinatorError,
    ) -> None:
        if isinstance(result, ReplayCoordinatorError):
            command.future.set_exception(result)
        else:
            command.future.set_result(result)

    def _frame_projection(self, frame: FrozenReplayFrame) -> ReplayFrameProjection:
        return ReplayFrameProjection(
            frame_index=frame.semantic_snapshot_index,
            semantic_snapshot_index=frame.semantic_snapshot_index,
            route_configuration_index=frame.route_configuration_index,
            route_state=frame.route_state,
            phase=frame.phase,
            boundary_snapshot=frame.boundary_snapshot,
            is_key_snapshot=frame.semantic_snapshot_index in KEY_SNAPSHOT_INDICES,
        )

    def _available_controls_locked(self) -> tuple[str, ...]:
        if self._command_in_flight or self._shutdown_requested:
            return ()
        lifecycle = self._public_lifecycle
        if lifecycle is ReplayLifecycle.IDLE:
            return (ReplayControl.START.value,)
        if lifecycle is ReplayLifecycle.PAUSED:
            if self._current_frame is None:
                raise AssertionError("paused replay has no current frame")
            result = [ReplayControl.RESUME.value]
            if self._current_frame.frame_index < REPLAY_FRAME_COUNT - 1:
                result.append(ReplayControl.NEXT_SNAPSHOT.value)
            if self._current_frame.frame_index > 0:
                result.append(ReplayControl.PREVIOUS_SNAPSHOT.value)
            result.extend((ReplayControl.STOP.value, ReplayControl.RESET_VIEW.value))
            return tuple(result)
        if lifecycle is ReplayLifecycle.PLAYING:
            return (
                ReplayControl.PAUSE.value,
                ReplayControl.STOP.value,
                ReplayControl.RESET_VIEW.value,
            )
        if lifecycle is ReplayLifecycle.COMPLETED:
            return (
                ReplayControl.PREVIOUS_SNAPSHOT.value,
                ReplayControl.STOP.value,
                ReplayControl.RESET_VIEW.value,
            )
        if lifecycle in {ReplayLifecycle.FAILED, ReplayLifecycle.CLEANUP_FAILED}:
            return (ReplayControl.STOP.value,)
        raise AssertionError("transient lifecycle leaked into public projection")

    def _projection_locked(self) -> ReplayStateProjection:
        return ReplayStateProjection(
            contract_id="PROTOTYPE5_D3_REPLAY_STATE_V1",
            contract_version="1.0.0",
            scenario_id=REPLAY_SCENARIO_ID,
            binding_id=REPLAY_BINDING_ID,
            session_id=self._session_id,
            control_version=self._control_version,
            projection_version=self._projection_version,
            lifecycle_state=self._public_lifecycle.value,
            command_in_flight=self._command_in_flight,
            current_frame=self._current_frame,
            frame_count=REPLAY_FRAME_COUNT,
            key_snapshot_indices=KEY_SNAPSHOT_INDICES,
            allowed_controls=ALLOWED_CONTROLS,
            available_controls=self._available_controls_locked(),
            presentation_cadence_ms=50,
            b2_sha256=B2_SHA256,
            b3_2_sha256=B3_2_SHA256,
            qualification=ReplayQualificationProjection(),
            presentation_labels=PRESENTATION_LABELS,
            physical_execution_authority="NOT_IMPLEMENTED",
            last_error_code=None if self._last_error is None else self._last_error.value,
            updated_at_utc=self._updated_at_utc,
        )


__all__ = (
    "ALLOWED_CONTROLS",
    "KEY_SNAPSHOT_INDICES",
    "MAX_SAFE_INTEGER",
    "ReplayControl",
    "ReplayCoordinator",
    "ReplayCoordinatorError",
    "ReplayErrorCode",
    "ReplayFrameProjection",
    "ReplayLastErrorCode",
    "ReplayLifecycle",
    "ReplayOwnerThreadSurvivedError",
    "ReplayQualificationProjection",
    "ReplayStateProjection",
    "ReplayTimings",
)
