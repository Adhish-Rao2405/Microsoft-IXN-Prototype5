from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable

import pytest

from src.prototype5.frozen_evidence_replay import (
    REPLAY_SCENARIO_ID,
    FrozenEvidenceReplayPlan,
    load_registered_frozen_evidence_replay,
)
from src.prototype5.pybullet_evidence_replay import ReplayClientDisconnectedError
from src.prototype5.replay_coordinator import (
    MAX_SAFE_INTEGER,
    ReplayControl,
    ReplayCoordinator,
    ReplayCoordinatorError,
    ReplayErrorCode,
    ReplayLifecycle,
    ReplayTimings,
)


@pytest.fixture(scope="module")
def plan() -> FrozenEvidenceReplayPlan:
    return load_registered_frozen_evidence_replay()


@dataclass(frozen=True, slots=True)
class _Readback:
    frame: object


class _FakeSession:
    def __init__(self, plan: FrozenEvidenceReplayPlan) -> None:
        self.plan = plan
        self.owner_thread = threading.get_ident()
        self.frame_index: int | None = None
        self.connected = True
        self.closed = False
        self.fail_open = False
        self.fail_apply = False
        self.fail_apply_client_disconnected = False
        self.fail_reset = False
        self.fail_reset_client_disconnected = False
        self.fail_close = False
        self.block_open: threading.Event | None = None
        self.block_reset: threading.Event | None = None
        self.block_frame: threading.Event | None = None
        self.block_probe: threading.Event | None = None
        self.block_close: threading.Event | None = None
        self.open_started = threading.Event()
        self.frame_started = threading.Event()
        self.probe_started = threading.Event()
        self.close_started = threading.Event()
        self.calls: list[tuple[str, int]] = []
        self.applied_frames: list[int] = []

    def _owned(self, operation: str) -> None:
        assert threading.get_ident() == self.owner_thread
        self.calls.append((operation, threading.get_ident()))

    def open(self) -> _FakeSession:
        self._owned("open")
        self.open_started.set()
        if self.block_open is not None:
            assert self.block_open.wait(timeout=5)
        if self.fail_open:
            raise RuntimeError("scene failure")
        return self

    def apply_frame(self, frame_index: int) -> _Readback:
        self._owned("apply_frame")
        if frame_index > 0 and self.block_frame is not None:
            self.frame_started.set()
            assert self.block_frame.wait(timeout=5)
        if self.fail_apply:
            raise RuntimeError("frame failure")
        if self.fail_apply_client_disconnected:
            self.connected = False
            raise ReplayClientDisconnectedError(
                "PyBullet replay client disconnected unexpectedly"
            )
        self.frame_index = frame_index
        self.applied_frames.append(frame_index)
        return _Readback(self.plan.frame_at(frame_index))

    @property
    def current_frame(self) -> object:
        self._owned("current_frame")
        assert self.frame_index is not None
        return self.plan.frame_at(self.frame_index)

    def probe_connection(self) -> bool:
        self._owned("probe_connection")
        self.probe_started.set()
        if self.block_probe is not None:
            assert self.block_probe.wait(timeout=5)
        return self.connected

    def reset_view(self) -> None:
        self._owned("reset_view")
        if self.block_reset is not None:
            assert self.block_reset.wait(timeout=5)
        if self.fail_reset:
            raise RuntimeError("view reset failure")
        if self.fail_reset_client_disconnected:
            self.connected = False
            raise ReplayClientDisconnectedError(
                "PyBullet replay client disconnected unexpectedly"
            )

    def close(self) -> None:
        self._owned("close")
        self.close_started.set()
        if self.block_close is not None:
            assert self.block_close.wait(timeout=5)
        if self.fail_close:
            raise RuntimeError("cleanup failure")
        self.closed = True
        self.connected = False


class _Factory:
    def __init__(self, plan: FrozenEvidenceReplayPlan) -> None:
        self.plan = plan
        self.sessions: list[_FakeSession] = []
        self.configure: Callable[[_FakeSession], None] | None = None

    def __call__(self) -> _FakeSession:
        session = _FakeSession(self.plan)
        if self.configure is not None:
            self.configure(session)
        self.sessions.append(session)
        return session


def _timings(**overrides: float) -> ReplayTimings:
    values = {
        "startup_seconds": 1.0,
        "control_seconds": 1.0,
        "idle_seconds": 100.0,
        "shutdown_seconds": 1.0,
        "liveness_seconds": 100.0,
        "cadence_seconds": 100.0,
        "tombstone_seconds": 10.0,
    }
    values.update(overrides)
    return ReplayTimings(**values)


def _coordinator(
    factory: _Factory,
    *,
    timings: ReplayTimings | None = None,
) -> ReplayCoordinator:
    coordinator = ReplayCoordinator(
        factory,
        known_scenario_ids=frozenset({REPLAY_SCENARIO_ID, "KNOWN_NON_REPLAY"}),
        timings=timings or _timings(),
    )
    coordinator.start()
    return coordinator


def _eventually(predicate: Callable[[], bool], timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            raise AssertionError("condition did not settle before deadline")
        time.sleep(0.005)


def _start(coordinator: ReplayCoordinator):
    return coordinator.start_replay(REPLAY_SCENARIO_ID)


def _control(coordinator: ReplayCoordinator, state, control: ReplayControl):
    return coordinator.control(
        scenario_id=REPLAY_SCENARIO_ID,
        session_id=state.session_id,
        expected_control_version=state.control_version,
        control=control,
    )


def _invoke_in_thread(operation: Callable[[], object]) -> tuple[threading.Thread, list[object]]:
    results: list[object] = []

    def invoke() -> None:
        try:
            results.append(operation())
        except BaseException as exc:
            results.append(exc)

    worker = threading.Thread(target=invoke)
    worker.start()
    return worker, results


def _committed_projection_tuple(coordinator: ReplayCoordinator) -> tuple[object, ...]:
    with coordinator._condition:
        return _committed_projection_tuple_locked(coordinator)


def _committed_projection_tuple_locked(
    coordinator: ReplayCoordinator,
) -> tuple[object, ...]:
    return (
        coordinator._session_id,
        coordinator._public_lifecycle,
        coordinator._control_version,
        coordinator._projection_version,
        coordinator._current_frame,
        coordinator._last_error,
        coordinator._updated_at_utc,
    )


def test_canonical_idle_projection_is_exact(plan: FrozenEvidenceReplayPlan) -> None:
    factory = _Factory(plan)
    coordinator = _coordinator(factory)
    try:
        state = coordinator.get_state()
        assert (state.lifecycle_state, state.session_id) == ("IDLE", None)
        assert (state.control_version, state.projection_version) == (0, 0)
        assert state.current_frame is None
        assert state.command_in_flight is False
        assert state.last_error_code is None
        assert state.available_controls == ("START",)
        assert factory.sessions == []
    finally:
        coordinator.shutdown()


def test_complete_registered_control_sequence_and_stop_retry(
    plan: FrozenEvidenceReplayPlan,
) -> None:
    factory = _Factory(plan)
    coordinator = _coordinator(factory)
    try:
        state = _start(coordinator)
        assert (state.lifecycle_state, state.current_frame.frame_index) == ("PAUSED", 0)
        state = _control(coordinator, state, ReplayControl.NEXT_SNAPSHOT)
        assert state.current_frame.frame_index == 1
        state = _control(coordinator, state, ReplayControl.PREVIOUS_SNAPSHOT)
        assert state.current_frame.frame_index == 0
        state = _control(coordinator, state, ReplayControl.RESET_VIEW)
        state = _control(coordinator, state, ReplayControl.RESUME)
        assert state.lifecycle_state == "PLAYING"
        state = _control(coordinator, state, ReplayControl.PAUSE)
        stopped_session = state.session_id
        stopped_version = state.control_version
        state = _control(coordinator, state, ReplayControl.STOP)
        assert (state.lifecycle_state, state.session_id) == ("IDLE", None)
        retry = coordinator.control(
            scenario_id=REPLAY_SCENARIO_ID,
            session_id=stopped_session,
            expected_control_version=stopped_version,
            control=ReplayControl.STOP,
        )
        assert retry == state
        assert factory.sessions[0].closed
    finally:
        coordinator.shutdown()


@pytest.mark.parametrize(
    ("scenario_id", "code"),
    [
        ("UNKNOWN", ReplayErrorCode.SCENARIO_NOT_FOUND),
        ("KNOWN_NON_REPLAY", ReplayErrorCode.SCENARIO_NOT_REPLAYABLE),
    ],
)
def test_scenario_resolution_is_server_owned(
    plan: FrozenEvidenceReplayPlan,
    scenario_id: str,
    code: ReplayErrorCode,
) -> None:
    coordinator = _coordinator(_Factory(plan))
    try:
        with pytest.raises(ReplayCoordinatorError) as raised:
            coordinator.start_replay(scenario_id)
        assert raised.value.code is code
    finally:
        coordinator.shutdown()


def test_stale_session_version_and_frame_boundary_fail_closed(
    plan: FrozenEvidenceReplayPlan,
) -> None:
    coordinator = _coordinator(_Factory(plan))
    try:
        state = _start(coordinator)
        with pytest.raises(ReplayCoordinatorError) as raised:
            coordinator.control(
                scenario_id=REPLAY_SCENARIO_ID,
                session_id="stale",
                expected_control_version=state.control_version,
                control=ReplayControl.STOP,
            )
        assert raised.value.code is ReplayErrorCode.SESSION_STALE
        with pytest.raises(ReplayCoordinatorError) as raised:
            coordinator.control(
                scenario_id=REPLAY_SCENARIO_ID,
                session_id=state.session_id,
                expected_control_version=state.control_version + 1,
                control=ReplayControl.STOP,
            )
        assert raised.value.code is ReplayErrorCode.CONTROL_VERSION_STALE
        with pytest.raises(ReplayCoordinatorError) as raised:
            _control(coordinator, state, ReplayControl.PREVIOUS_SNAPSHOT)
        assert raised.value.code is ReplayErrorCode.FRAME_BOUNDARY
    finally:
        coordinator.shutdown()


def test_concurrent_start_has_one_owner_and_no_backlog(
    plan: FrozenEvidenceReplayPlan,
) -> None:
    factory = _Factory(plan)
    release = threading.Event()
    factory.configure = lambda session: setattr(session, "block_open", release)
    coordinator = _coordinator(factory)
    results: list[object] = []

    def invoke_start() -> None:
        try:
            results.append(_start(coordinator))
        except BaseException as exc:
            results.append(exc)

    first = threading.Thread(target=invoke_start)
    first.start()
    _eventually(lambda: bool(factory.sessions))
    try:
        with pytest.raises(ReplayCoordinatorError) as raised:
            _start(coordinator)
        assert raised.value.code is ReplayErrorCode.SESSION_ACTIVE
        release.set()
        first.join(timeout=2)
        assert not first.is_alive()
        assert len(results) == 1 and not isinstance(results[0], BaseException)
    finally:
        release.set()
        coordinator.shutdown()


def test_started_timeout_retains_admission_until_owner_settlement(
    plan: FrozenEvidenceReplayPlan,
) -> None:
    factory = _Factory(plan)
    coordinator = _coordinator(factory, timings=_timings(control_seconds=0.05))
    state = _start(coordinator)
    release = threading.Event()
    factory.sessions[0].block_reset = release
    try:
        with pytest.raises(ReplayCoordinatorError) as raised:
            _control(coordinator, state, ReplayControl.RESET_VIEW)
        assert raised.value.code is ReplayErrorCode.CONTROL_SETTLEMENT_UNKNOWN
        assert coordinator.get_state().command_in_flight is True
        with pytest.raises(ReplayCoordinatorError) as busy:
            _control(coordinator, state, ReplayControl.STOP)
        assert busy.value.code is ReplayErrorCode.COMMAND_CHANNEL_FULL
        release.set()
        _eventually(lambda: not coordinator.get_state().command_in_flight)
        assert coordinator.get_state().control_version == state.control_version + 1
    finally:
        release.set()
        coordinator.shutdown()


def test_start_expiry_before_owner_execution_performs_zero_session_work(
    plan: FrozenEvidenceReplayPlan,
) -> None:
    factory = _Factory(plan)
    coordinator = ReplayCoordinator(
        factory,
        known_scenario_ids=frozenset({REPLAY_SCENARIO_ID}),
        timings=_timings(startup_seconds=0.02),
    )
    with coordinator._condition:
        coordinator._started = True
    try:
        with pytest.raises(ReplayCoordinatorError) as raised:
            _start(coordinator)
        assert raised.value.code is ReplayErrorCode.COMMAND_EXPIRED
        assert factory.sessions == []
        with coordinator._condition:
            assert coordinator._command_in_flight is False
            assert coordinator._pending_command is None
            assert coordinator._provisional_session_id is None
    finally:
        with coordinator._condition:
            coordinator._started = False


def test_started_start_timeout_keeps_admission_and_get_recovers_outcome(
    plan: FrozenEvidenceReplayPlan,
) -> None:
    factory = _Factory(plan)
    release_open = threading.Event()
    factory.configure = lambda session: setattr(session, "block_open", release_open)
    coordinator = _coordinator(factory, timings=_timings(startup_seconds=0.05))
    try:
        with pytest.raises(ReplayCoordinatorError) as raised:
            _start(coordinator)
        assert raised.value.code is ReplayErrorCode.START_TIMEOUT
        unsettled = coordinator.get_state()
        assert unsettled.lifecycle_state == "IDLE"
        assert unsettled.session_id is None
        assert unsettled.command_in_flight is True
        with pytest.raises(ReplayCoordinatorError) as busy:
            _start(coordinator)
        assert busy.value.code is ReplayErrorCode.SESSION_ACTIVE

        release_open.set()
        _eventually(lambda: not coordinator.get_state().command_in_flight)
        recovered = coordinator.get_state()
        assert recovered.lifecycle_state == "PAUSED"
        assert recovered.session_id is not None
        assert (recovered.control_version, recovered.projection_version) == (1, 1)
    finally:
        release_open.set()
        coordinator.shutdown()


def test_failed_start_is_recoverable_by_authoritative_get_then_stop(
    plan: FrozenEvidenceReplayPlan,
) -> None:
    factory = _Factory(plan)
    factory.configure = lambda session: setattr(session, "fail_open", True)
    coordinator = _coordinator(factory)
    try:
        with pytest.raises(ReplayCoordinatorError) as raised:
            _start(coordinator)
        assert raised.value.code is ReplayErrorCode.SCENE_FAILED
        failed = coordinator.get_state()
        assert failed.lifecycle_state == "FAILED"
        assert failed.session_id is not None
        assert (failed.control_version, failed.projection_version) == (1, 1)
        assert failed.last_error_code == "REPLAY_SCENE_FAILED"
        recovered = _control(coordinator, failed, ReplayControl.STOP)
        assert recovered.lifecycle_state == "IDLE"
    finally:
        coordinator.shutdown()


def test_stop_tombstone_expires_and_old_stop_becomes_stale(
    plan: FrozenEvidenceReplayPlan,
) -> None:
    coordinator = _coordinator(
        _Factory(plan), timings=_timings(tombstone_seconds=0.02)
    )
    state = _start(coordinator)
    _control(coordinator, state, ReplayControl.STOP)
    time.sleep(0.03)
    try:
        with pytest.raises(ReplayCoordinatorError) as raised:
            _control(coordinator, state, ReplayControl.STOP)
        assert raised.value.code is ReplayErrorCode.SESSION_STALE
        assert coordinator._stop_tombstone is None
    finally:
        coordinator.shutdown()


def test_old_stop_tombstone_cannot_supersede_new_session(
    plan: FrozenEvidenceReplayPlan,
) -> None:
    coordinator = _coordinator(_Factory(plan))
    try:
        first = _start(coordinator)
        first_id, first_version = first.session_id, first.control_version
        _control(coordinator, first, ReplayControl.STOP)
        second = _start(coordinator)
        with pytest.raises(ReplayCoordinatorError) as raised:
            coordinator.control(
                scenario_id=REPLAY_SCENARIO_ID,
                session_id=first_id,
                expected_control_version=first_version,
                control=ReplayControl.STOP,
            )
        assert raised.value.code is ReplayErrorCode.SESSION_STALE
        assert coordinator.get_state().session_id == second.session_id
    finally:
        coordinator.shutdown()


def test_old_stop_tombstone_is_invalidated_during_provisional_new_start(
    plan: FrozenEvidenceReplayPlan,
) -> None:
    factory = _Factory(plan)
    coordinator = _coordinator(factory)
    release_start = threading.Event()
    try:
        first = _start(coordinator)
        first_id, first_version = first.session_id, first.control_version
        _control(coordinator, first, ReplayControl.STOP)
        factory.configure = lambda session: setattr(session, "block_open", release_start)
        worker, results = _invoke_in_thread(lambda: _start(coordinator))
        _eventually(lambda: len(factory.sessions) == 2)
        assert factory.sessions[1].open_started.wait(timeout=1)

        with pytest.raises(ReplayCoordinatorError) as raised:
            coordinator.control(
                scenario_id=REPLAY_SCENARIO_ID,
                session_id=first_id,
                expected_control_version=first_version,
                control=ReplayControl.STOP,
            )
        assert raised.value.code is ReplayErrorCode.SESSION_STALE
        assert coordinator._stop_tombstone is None

        release_start.set()
        worker.join(timeout=2)
        assert not worker.is_alive()
        assert len(results) == 1 and not isinstance(results[0], BaseException)
        assert coordinator.get_state().session_id == results[0].session_id
    finally:
        release_start.set()
        coordinator.shutdown()


def test_stop_tombstone_is_not_eligible_before_stop_settlement(
    plan: FrozenEvidenceReplayPlan,
) -> None:
    factory = _Factory(plan)
    coordinator = _coordinator(factory)
    state = _start(coordinator)
    release_close = threading.Event()
    factory.sessions[0].block_close = release_close
    worker, results = _invoke_in_thread(
        lambda: _control(coordinator, state, ReplayControl.STOP)
    )
    assert factory.sessions[0].close_started.wait(timeout=1)
    try:
        with coordinator._condition:
            assert coordinator._stop_tombstone is None
            assert coordinator._command_in_flight is True
        with pytest.raises(ReplayCoordinatorError) as raised:
            _control(coordinator, state, ReplayControl.STOP)
        assert raised.value.code is ReplayErrorCode.COMMAND_CHANNEL_FULL

        release_close.set()
        worker.join(timeout=2)
        assert not worker.is_alive()
        assert len(results) == 1 and not isinstance(results[0], BaseException)
        retry = _control(coordinator, state, ReplayControl.STOP)
        assert retry == results[0]
    finally:
        release_close.set()
        coordinator.shutdown()


def test_success_projection_and_admission_release_publish_atomically(
    plan: FrozenEvidenceReplayPlan,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = _Factory(plan)
    coordinator = _coordinator(factory)
    state = _start(coordinator)
    release_frame = threading.Event()
    release_future = threading.Event()
    future_publish_started = threading.Event()
    factory.sessions[0].block_frame = release_frame
    original = coordinator._resolve_command_future

    def delayed_future(command, result) -> None:
        future_publish_started.set()
        assert release_future.wait(timeout=5)
        original(command, result)

    monkeypatch.setattr(coordinator, "_resolve_command_future", delayed_future)
    worker, results = _invoke_in_thread(
        lambda: _control(coordinator, state, ReplayControl.NEXT_SNAPSHOT)
    )
    assert factory.sessions[0].frame_started.wait(timeout=1)
    try:
        unsettled = coordinator.get_state()
        assert unsettled.current_frame.frame_index == 0
        assert unsettled.projection_version == state.projection_version
        assert unsettled.command_in_flight is True

        release_frame.set()
        assert future_publish_started.wait(timeout=1)
        published = coordinator.get_state()
        assert published.current_frame.frame_index == 1
        assert published.projection_version == state.projection_version + 1
        assert published.command_in_flight is False

        release_future.set()
        worker.join(timeout=2)
        assert not worker.is_alive()
        assert results == [published]
    finally:
        release_frame.set()
        release_future.set()
        coordinator.shutdown()


def test_stable_failure_and_admission_release_publish_atomically(
    plan: FrozenEvidenceReplayPlan,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = _Factory(plan)
    coordinator = _coordinator(factory)
    state = _start(coordinator)
    release_frame = threading.Event()
    release_future = threading.Event()
    future_publish_started = threading.Event()
    session = factory.sessions[0]
    session.block_frame = release_frame
    session.fail_apply = True
    original = coordinator._resolve_command_future

    def delayed_future(command, result) -> None:
        future_publish_started.set()
        assert release_future.wait(timeout=5)
        original(command, result)

    monkeypatch.setattr(coordinator, "_resolve_command_future", delayed_future)
    worker, results = _invoke_in_thread(
        lambda: _control(coordinator, state, ReplayControl.NEXT_SNAPSHOT)
    )
    assert session.frame_started.wait(timeout=1)
    try:
        unsettled = coordinator.get_state()
        assert unsettled.lifecycle_state == "PAUSED"
        assert unsettled.projection_version == state.projection_version
        assert unsettled.command_in_flight is True

        release_frame.set()
        assert future_publish_started.wait(timeout=1)
        published = coordinator.get_state()
        assert published.lifecycle_state == "FAILED"
        assert published.last_error_code == "REPLAY_SCENE_FAILED"
        assert published.command_in_flight is False

        release_future.set()
        worker.join(timeout=2)
        assert not worker.is_alive()
        assert len(results) == 1
        assert isinstance(results[0], ReplayCoordinatorError)
        assert results[0].code is ReplayErrorCode.SCENE_FAILED
    finally:
        release_frame.set()
        release_future.set()
        coordinator.shutdown()


def test_gui_liveness_loss_publishes_closed_failure(plan: FrozenEvidenceReplayPlan) -> None:
    factory = _Factory(plan)
    coordinator = _coordinator(factory, timings=_timings(liveness_seconds=0.02))
    try:
        state = _start(coordinator)
        factory.sessions[0].connected = False
        _eventually(lambda: coordinator.get_state().lifecycle_state == "FAILED")
        failed = coordinator.get_state()
        assert failed.session_id == state.session_id
        assert failed.last_error_code == "REPLAY_GUI_CLOSED"
    finally:
        coordinator.shutdown()


def test_cadence_client_disconnect_uses_gui_closed_taxonomy_and_stop_recovers(
    plan: FrozenEvidenceReplayPlan,
) -> None:
    factory = _Factory(plan)
    coordinator = _coordinator(factory)
    try:
        paused = _start(coordinator)
        playing = _control(coordinator, paused, ReplayControl.RESUME)
        session = factory.sessions[0]
        session.connected = False
        session.fail_apply_client_disconnected = True
        with coordinator._condition:
            coordinator._next_liveness = time.monotonic() + 100.0
            coordinator._next_cadence = time.monotonic()
            coordinator._condition.notify_all()

        _eventually(lambda: coordinator.get_state().lifecycle_state == "FAILED")
        failed = coordinator.get_state()
        assert failed.session_id == playing.session_id
        assert failed.current_frame == playing.current_frame
        assert failed.current_frame.frame_index == 0
        assert failed.control_version == playing.control_version + 1
        assert failed.projection_version == playing.projection_version + 1
        assert failed.last_error_code == "REPLAY_GUI_CLOSED"
        assert session.applied_frames == [0]
        assert [name for name, _ in session.calls].count("apply_frame") == 2
        assert "probe_connection" not in [name for name, _ in session.calls]
        with coordinator._condition:
            assert coordinator._next_cadence is None
            assert coordinator._next_liveness is None
            assert coordinator._periodic_in_progress is False

        idle = _control(coordinator, failed, ReplayControl.STOP)
        assert idle.lifecycle_state == "IDLE"
        assert idle.session_id is None
        assert (idle.control_version, idle.projection_version) == (0, 0)
        assert idle.current_frame is None
        assert idle.last_error_code is None
    finally:
        coordinator.shutdown()


def test_cadence_generic_apply_failure_remains_scene_failed(
    plan: FrozenEvidenceReplayPlan,
) -> None:
    factory = _Factory(plan)
    coordinator = _coordinator(factory)
    try:
        paused = _start(coordinator)
        playing = _control(coordinator, paused, ReplayControl.RESUME)
        session = factory.sessions[0]
        session.fail_apply = True
        with coordinator._condition:
            coordinator._next_liveness = time.monotonic() + 100.0
            coordinator._next_cadence = time.monotonic()
            coordinator._condition.notify_all()

        _eventually(lambda: coordinator.get_state().lifecycle_state == "FAILED")
        failed = coordinator.get_state()
        assert failed.session_id == playing.session_id
        assert failed.current_frame == playing.current_frame
        assert failed.current_frame.frame_index == 0
        assert failed.last_error_code == "REPLAY_SCENE_FAILED"
        assert session.applied_frames == [0]
        assert "probe_connection" not in [name for name, _ in session.calls]
        with coordinator._condition:
            assert coordinator._next_cadence is None
            assert coordinator._next_liveness is None
            assert coordinator._periodic_in_progress is False
    finally:
        coordinator.shutdown()


def test_navigation_client_disconnect_returns_gui_closed_state_and_stop_recovers(
    plan: FrozenEvidenceReplayPlan,
) -> None:
    factory = _Factory(plan)
    coordinator = _coordinator(factory)
    try:
        paused = _start(coordinator)
        session = factory.sessions[0]
        session.connected = False
        session.fail_apply_client_disconnected = True

        failed = _control(coordinator, paused, ReplayControl.NEXT_SNAPSHOT)
        assert failed.lifecycle_state == "FAILED"
        assert failed.session_id == paused.session_id
        assert failed.current_frame == paused.current_frame
        assert failed.current_frame.frame_index == 0
        assert failed.control_version == paused.control_version + 1
        assert failed.projection_version == paused.projection_version + 1
        assert failed.last_error_code == "REPLAY_GUI_CLOSED"
        assert session.applied_frames == [0]
        assert "probe_connection" not in [name for name, _ in session.calls]
        with coordinator._condition:
            assert coordinator._next_cadence is None
            assert coordinator._next_liveness is None

        idle = _control(coordinator, failed, ReplayControl.STOP)
        assert idle.lifecycle_state == "IDLE"
        assert idle.session_id is None
        assert (idle.control_version, idle.projection_version) == (0, 0)
        assert idle.current_frame is None
        assert idle.last_error_code is None
    finally:
        coordinator.shutdown()


def test_playing_reset_client_disconnect_returns_gui_closed_state_and_stop_recovers(
    plan: FrozenEvidenceReplayPlan,
) -> None:
    factory = _Factory(plan)
    coordinator = _coordinator(factory)
    try:
        paused = _start(coordinator)
        playing = _control(coordinator, paused, ReplayControl.RESUME)
        session = factory.sessions[0]
        session.connected = False
        session.fail_reset_client_disconnected = True

        failed = _control(coordinator, playing, ReplayControl.RESET_VIEW)
        assert failed.lifecycle_state == "FAILED"
        assert failed.session_id == playing.session_id
        assert failed.current_frame == playing.current_frame
        assert failed.current_frame.frame_index == 0
        assert failed.control_version == playing.control_version + 1
        assert failed.projection_version == playing.projection_version + 1
        assert failed.last_error_code == "REPLAY_GUI_CLOSED"
        assert "probe_connection" not in [name for name, _ in session.calls]
        with coordinator._condition:
            assert coordinator._next_cadence is None
            assert coordinator._next_liveness is None

        idle = _control(coordinator, failed, ReplayControl.STOP)
        assert idle.lifecycle_state == "IDLE"
        assert idle.session_id is None
        assert (idle.control_version, idle.projection_version) == (0, 0)
        assert idle.current_frame is None
        assert idle.last_error_code is None
    finally:
        coordinator.shutdown()


def test_navigation_generic_apply_failure_remains_scene_failed(
    plan: FrozenEvidenceReplayPlan,
) -> None:
    factory = _Factory(plan)
    coordinator = _coordinator(factory)
    try:
        paused = _start(coordinator)
        session = factory.sessions[0]
        session.fail_apply = True

        with pytest.raises(ReplayCoordinatorError) as raised:
            _control(coordinator, paused, ReplayControl.NEXT_SNAPSHOT)
        assert raised.value.code is ReplayErrorCode.SCENE_FAILED
        failed = coordinator.get_state()
        assert failed.lifecycle_state == "FAILED"
        assert failed.current_frame == paused.current_frame
        assert failed.last_error_code == "REPLAY_SCENE_FAILED"
    finally:
        coordinator.shutdown()


def test_reset_view_generic_failure_remains_scene_failed(
    plan: FrozenEvidenceReplayPlan,
) -> None:
    factory = _Factory(plan)
    coordinator = _coordinator(factory)
    try:
        paused = _start(coordinator)
        session = factory.sessions[0]
        session.fail_reset = True

        with pytest.raises(ReplayCoordinatorError) as raised:
            _control(coordinator, paused, ReplayControl.RESET_VIEW)
        assert raised.value.code is ReplayErrorCode.SCENE_FAILED
        failed = coordinator.get_state()
        assert failed.lifecycle_state == "FAILED"
        assert failed.current_frame == paused.current_frame
        assert failed.last_error_code == "REPLAY_SCENE_FAILED"
    finally:
        coordinator.shutdown()


def test_cleanup_failure_retains_session_for_stop_recovery(
    plan: FrozenEvidenceReplayPlan,
) -> None:
    factory = _Factory(plan)
    coordinator = _coordinator(factory)
    state = _start(coordinator)
    factory.sessions[0].fail_close = True
    try:
        with pytest.raises(ReplayCoordinatorError) as raised:
            _control(coordinator, state, ReplayControl.STOP)
        assert raised.value.code is ReplayErrorCode.CLEANUP_UNRESOLVED
        failed = coordinator.get_state()
        assert failed.lifecycle_state == "CLEANUP_FAILED"
        assert failed.session_id == state.session_id
        assert failed.last_error_code == "REPLAY_CLEANUP_UNRESOLVED"
        factory.sessions[0].fail_close = False
        recovered = _control(coordinator, failed, ReplayControl.STOP)
        assert recovered.lifecycle_state == "IDLE"
    finally:
        factory.sessions[0].fail_close = False
        coordinator.shutdown()


def test_request_driven_version_exhaustion_latches_until_restart(
    plan: FrozenEvidenceReplayPlan,
) -> None:
    factory = _Factory(plan)
    coordinator = _coordinator(factory)
    state = _start(coordinator)
    with coordinator._condition:
        coordinator._control_version = MAX_SAFE_INTEGER
        coordinator._projection_version = MAX_SAFE_INTEGER
        state = coordinator._projection_locked()
    committed = _committed_projection_tuple(coordinator)
    try:
        with pytest.raises(ReplayCoordinatorError) as raised:
            _control(coordinator, state, ReplayControl.RESET_VIEW)
        assert raised.value.code is ReplayErrorCode.VERSION_EXHAUSTED
        assert coordinator.preflight_error() is ReplayErrorCode.VERSION_EXHAUSTED
        with pytest.raises(ReplayCoordinatorError) as read_error:
            coordinator.get_state()
        assert read_error.value.code is ReplayErrorCode.VERSION_EXHAUSTED
        assert _committed_projection_tuple(coordinator) == committed
        assert factory.sessions[0].closed
    finally:
        coordinator.shutdown()


def test_automatic_frame_version_exhaustion_latches_without_wrap(
    plan: FrozenEvidenceReplayPlan,
) -> None:
    factory = _Factory(plan)
    coordinator = _coordinator(factory, timings=_timings(cadence_seconds=0.02))
    state = _start(coordinator)
    state = _control(coordinator, state, ReplayControl.RESUME)
    with coordinator._condition:
        coordinator._projection_version = MAX_SAFE_INTEGER
        committed = _committed_projection_tuple_locked(coordinator)
        coordinator._next_cadence = time.monotonic()
        coordinator._condition.notify_all()
    try:
        _eventually(lambda: coordinator.preflight_error() is ReplayErrorCode.VERSION_EXHAUSTED)
        assert _committed_projection_tuple(coordinator) == committed
        assert factory.sessions[0].closed
    finally:
        coordinator.shutdown()


def test_failure_publication_exhaustion_preserves_committed_projection(
    plan: FrozenEvidenceReplayPlan,
) -> None:
    factory = _Factory(plan)
    coordinator = _coordinator(factory)
    state = _start(coordinator)
    release_frame = threading.Event()
    session = factory.sessions[0]
    session.block_frame = release_frame
    session.fail_apply = True
    worker, results = _invoke_in_thread(
        lambda: _control(coordinator, state, ReplayControl.NEXT_SNAPSHOT)
    )
    assert session.frame_started.wait(timeout=1)
    with coordinator._condition:
        coordinator._control_version = MAX_SAFE_INTEGER
        coordinator._projection_version = MAX_SAFE_INTEGER
    committed = _committed_projection_tuple(coordinator)
    try:
        release_frame.set()
        worker.join(timeout=2)
        assert not worker.is_alive()
        assert len(results) == 1 and isinstance(results[0], ReplayCoordinatorError)
        assert results[0].code is ReplayErrorCode.VERSION_EXHAUSTED
        assert _committed_projection_tuple(coordinator) == committed
        assert coordinator.preflight_error() is ReplayErrorCode.VERSION_EXHAUSTED
    finally:
        release_frame.set()
        coordinator.shutdown()


def test_idle_expiry_failure_exhaustion_preserves_committed_projection(
    plan: FrozenEvidenceReplayPlan,
) -> None:
    factory = _Factory(plan)
    coordinator = _coordinator(factory)
    _start(coordinator)
    release_close = threading.Event()
    session = factory.sessions[0]
    session.block_close = release_close
    session.fail_close = True
    with coordinator._condition:
        coordinator._last_activity = time.monotonic() - 101.0
        coordinator._condition.notify_all()
    assert session.close_started.wait(timeout=1)
    with coordinator._condition:
        coordinator._control_version = MAX_SAFE_INTEGER
        coordinator._projection_version = MAX_SAFE_INTEGER
    committed = _committed_projection_tuple(coordinator)
    try:
        release_close.set()
        _eventually(lambda: coordinator.preflight_error() is ReplayErrorCode.VERSION_EXHAUSTED)
        assert _committed_projection_tuple(coordinator) == committed
        assert coordinator._owner_session is session
    finally:
        session.fail_close = False
        release_close.set()
        coordinator.shutdown()


def test_automatic_event_first_exhaustion_prevents_waiting_control_admission(
    plan: FrozenEvidenceReplayPlan,
) -> None:
    factory = _Factory(plan)
    coordinator = _coordinator(factory)
    state = _start(coordinator)
    release_probe = threading.Event()
    session = factory.sessions[0]
    session.connected = False
    session.block_probe = release_probe
    with coordinator._condition:
        coordinator._next_liveness = time.monotonic()
        coordinator._condition.notify_all()
    assert session.probe_started.wait(timeout=1)
    worker, results = _invoke_in_thread(
        lambda: _control(coordinator, state, ReplayControl.STOP)
    )
    _eventually(lambda: coordinator._admission_waiters == 1)
    with coordinator._condition:
        coordinator._control_version = MAX_SAFE_INTEGER
        coordinator._projection_version = MAX_SAFE_INTEGER
    committed = _committed_projection_tuple(coordinator)
    try:
        release_probe.set()
        worker.join(timeout=2)
        assert not worker.is_alive()
        assert len(results) == 1 and isinstance(results[0], ReplayCoordinatorError)
        assert results[0].code is ReplayErrorCode.VERSION_EXHAUSTED
        assert _committed_projection_tuple(coordinator) == committed
        assert coordinator._command_in_flight is False
    finally:
        release_probe.set()
        coordinator.shutdown()


def test_external_command_first_exhaustion_starts_no_periodic_work(
    plan: FrozenEvidenceReplayPlan,
) -> None:
    factory = _Factory(plan)
    coordinator = _coordinator(factory)
    state = _start(coordinator)
    with coordinator._condition:
        coordinator._control_version = MAX_SAFE_INTEGER
        coordinator._projection_version = MAX_SAFE_INTEGER
        state = coordinator._projection_locked()
    committed = _committed_projection_tuple(coordinator)
    calls_before = list(factory.sessions[0].calls)
    try:
        with pytest.raises(ReplayCoordinatorError) as raised:
            _control(coordinator, state, ReplayControl.RESET_VIEW)
        assert raised.value.code is ReplayErrorCode.VERSION_EXHAUSTED
        assert _committed_projection_tuple(coordinator) == committed
        assert "reset_view" not in [name for name, _ in factory.sessions[0].calls]
        assert factory.sessions[0].calls[: len(calls_before)] == calls_before
    finally:
        coordinator.shutdown()


def test_exhaustion_cleanup_failure_retains_live_owner_for_shutdown_retry(
    plan: FrozenEvidenceReplayPlan,
) -> None:
    factory = _Factory(plan)
    coordinator = _coordinator(factory)
    state = _start(coordinator)
    session = factory.sessions[0]
    session.fail_close = True
    with coordinator._condition:
        coordinator._control_version = MAX_SAFE_INTEGER
        coordinator._projection_version = MAX_SAFE_INTEGER
        state = coordinator._projection_locked()
    committed = _committed_projection_tuple(coordinator)
    try:
        with pytest.raises(ReplayCoordinatorError) as raised:
            _control(coordinator, state, ReplayControl.RESET_VIEW)
        assert raised.value.code is ReplayErrorCode.VERSION_EXHAUSTED
        assert coordinator._owner_session is session
        assert _committed_projection_tuple(coordinator) == committed
    finally:
        session.fail_close = False
        coordinator.shutdown()


def test_all_session_operations_run_on_one_non_daemon_owner_thread(
    plan: FrozenEvidenceReplayPlan,
) -> None:
    factory = _Factory(plan)
    coordinator = _coordinator(factory)
    try:
        state = _start(coordinator)
        _control(coordinator, state, ReplayControl.RESET_VIEW)
        owner_ids = {thread_id for _, thread_id in factory.sessions[0].calls}
        assert owner_ids == {factory.sessions[0].owner_thread}
        assert factory.sessions[0].owner_thread != threading.get_ident()
        assert coordinator._thread is not None and not coordinator._thread.daemon
    finally:
        coordinator.shutdown()
    assert coordinator._thread is not None and not coordinator._thread.is_alive()


def test_sequential_cadence_reaches_frame_468_without_skipping(
    plan: FrozenEvidenceReplayPlan,
) -> None:
    factory = _Factory(plan)
    coordinator = _coordinator(factory, timings=_timings(cadence_seconds=0.001))
    try:
        state = _start(coordinator)
        resumed = _control(coordinator, state, ReplayControl.RESUME)
        _eventually(
            lambda: coordinator.get_state().lifecycle_state == "COMPLETED",
            timeout=12.0,
        )
        completed = coordinator.get_state()
        assert factory.sessions[0].applied_frames == list(range(469))
        assert completed.current_frame.frame_index == 468
        assert completed.control_version == resumed.control_version + 1
        assert completed.projection_version == resumed.projection_version + 468
    finally:
        coordinator.shutdown()


def test_admission_waits_for_started_cadence_then_pause_executes_next(
    plan: FrozenEvidenceReplayPlan,
) -> None:
    factory = _Factory(plan)
    coordinator = _coordinator(factory, timings=_timings(cadence_seconds=0.01))
    state = _start(coordinator)
    release = threading.Event()
    factory.sessions[0].block_frame = release
    state = _control(coordinator, state, ReplayControl.RESUME)
    _eventually(
        lambda: sum(name == "apply_frame" for name, _ in factory.sessions[0].calls) >= 2
    )
    results: list[object] = []

    def pause() -> None:
        try:
            results.append(_control(coordinator, state, ReplayControl.PAUSE))
        except BaseException as exc:
            results.append(exc)

    worker = threading.Thread(target=pause)
    worker.start()
    time.sleep(0.02)
    assert worker.is_alive()
    release.set()
    worker.join(timeout=2)
    try:
        assert not worker.is_alive()
        assert len(results) == 1 and not isinstance(results[0], BaseException)
        paused = results[0]
        assert paused.lifecycle_state == "PAUSED"
        assert paused.current_frame.frame_index == 1
        assert factory.sessions[0].applied_frames == [0, 1]
    finally:
        release.set()
        coordinator.shutdown()


def test_admission_waiter_deadline_releases_waiter_ownership(
    plan: FrozenEvidenceReplayPlan,
) -> None:
    factory = _Factory(plan)
    coordinator = _coordinator(
        factory,
        timings=_timings(cadence_seconds=0.01, control_seconds=0.03),
    )
    state = _start(coordinator)
    release_frame = threading.Event()
    factory.sessions[0].block_frame = release_frame
    state = _control(coordinator, state, ReplayControl.RESUME)
    assert factory.sessions[0].frame_started.wait(timeout=1)
    try:
        with pytest.raises(ReplayCoordinatorError) as raised:
            _control(coordinator, state, ReplayControl.PAUSE)
        assert raised.value.code is ReplayErrorCode.COMMAND_EXPIRED
        with coordinator._condition:
            assert coordinator._admission_waiters == 0
            assert coordinator._command_in_flight is False
        release_frame.set()
        _eventually(lambda: coordinator._periodic_in_progress is False)
    finally:
        release_frame.set()
        coordinator.shutdown()


def test_concurrent_navigation_reserves_exactly_one_mutation_slot(
    plan: FrozenEvidenceReplayPlan,
) -> None:
    factory = _Factory(plan)
    coordinator = _coordinator(factory)
    state = _start(coordinator)
    release_frame = threading.Event()
    factory.sessions[0].block_frame = release_frame
    worker, results = _invoke_in_thread(
        lambda: _control(coordinator, state, ReplayControl.NEXT_SNAPSHOT)
    )
    assert factory.sessions[0].frame_started.wait(timeout=1)
    try:
        with pytest.raises(ReplayCoordinatorError) as raised:
            _control(coordinator, state, ReplayControl.NEXT_SNAPSHOT)
        assert raised.value.code is ReplayErrorCode.COMMAND_CHANNEL_FULL
        release_frame.set()
        worker.join(timeout=2)
        assert not worker.is_alive()
        assert len(results) == 1 and not isinstance(results[0], BaseException)
        assert factory.sessions[0].applied_frames == [0, 1]
    finally:
        release_frame.set()
        coordinator.shutdown()


@pytest.mark.parametrize("control", [ReplayControl.STOP, ReplayControl.RESET_VIEW])
def test_admitted_stop_or_reset_view_overtakes_next_cadence(
    plan: FrozenEvidenceReplayPlan,
    control: ReplayControl,
) -> None:
    factory = _Factory(plan)
    coordinator = _coordinator(factory, timings=_timings(cadence_seconds=0.01))
    state = _start(coordinator)
    release_frame = threading.Event()
    factory.sessions[0].block_frame = release_frame
    state = _control(coordinator, state, ReplayControl.RESUME)
    assert factory.sessions[0].frame_started.wait(timeout=1)
    worker, results = _invoke_in_thread(lambda: _control(coordinator, state, control))
    _eventually(lambda: coordinator._admission_waiters == 1)
    try:
        release_frame.set()
        worker.join(timeout=2)
        assert not worker.is_alive()
        assert len(results) == 1 and not isinstance(results[0], BaseException)
        if control is ReplayControl.STOP:
            assert results[0].lifecycle_state == "IDLE"
            assert factory.sessions[0].applied_frames == [0, 1]
        else:
            calls = [name for name, _ in factory.sessions[0].calls]
            reset_position = calls.index("reset_view")
            apply_positions = [index for index, name in enumerate(calls) if name == "apply_frame"]
            assert len(apply_positions) >= 2
            assert len(apply_positions) == 2 or reset_position < apply_positions[2]
    finally:
        release_frame.set()
        coordinator.shutdown()


@pytest.mark.parametrize("control", [ReplayControl.PAUSE, ReplayControl.STOP])
def test_admitted_pause_or_stop_overtakes_next_liveness_poll(
    plan: FrozenEvidenceReplayPlan,
    control: ReplayControl,
) -> None:
    factory = _Factory(plan)
    coordinator = _coordinator(factory)
    state = _start(coordinator)
    if control is ReplayControl.PAUSE:
        state = _control(coordinator, state, ReplayControl.RESUME)
    release_probe = threading.Event()
    session = factory.sessions[0]
    session.block_probe = release_probe
    with coordinator._condition:
        coordinator._next_liveness = time.monotonic()
        coordinator._condition.notify_all()
    assert session.probe_started.wait(timeout=1)
    worker, results = _invoke_in_thread(lambda: _control(coordinator, state, control))
    _eventually(lambda: coordinator._admission_waiters == 1)
    try:
        release_probe.set()
        worker.join(timeout=2)
        assert not worker.is_alive()
        assert len(results) == 1 and not isinstance(results[0], BaseException)
        assert results[0].lifecycle_state == (
            "PAUSED" if control is ReplayControl.PAUSE else "IDLE"
        )
        assert sum(name == "probe_connection" for name, _ in session.calls) == 1
    finally:
        release_probe.set()
        coordinator.shutdown()


def test_control_waiting_at_idle_expiry_revalidates_after_expiry_settles(
    plan: FrozenEvidenceReplayPlan,
) -> None:
    factory = _Factory(plan)
    coordinator = _coordinator(factory)
    state = _start(coordinator)
    release_close = threading.Event()
    session = factory.sessions[0]
    session.block_close = release_close
    with coordinator._condition:
        coordinator._last_activity = time.monotonic() - 101.0
        coordinator._condition.notify_all()
    assert session.close_started.wait(timeout=1)
    worker, results = _invoke_in_thread(
        lambda: _control(coordinator, state, ReplayControl.RESET_VIEW)
    )
    _eventually(lambda: coordinator._admission_waiters == 1)
    try:
        release_close.set()
        worker.join(timeout=2)
        assert not worker.is_alive()
        assert len(results) == 1 and isinstance(results[0], ReplayCoordinatorError)
        assert results[0].code is ReplayErrorCode.SESSION_STALE
        assert "reset_view" not in [name for name, _ in session.calls]
        assert coordinator.get_state().lifecycle_state == "IDLE"
    finally:
        release_close.set()
        coordinator.shutdown()


def test_successful_idle_expiry_creates_no_stop_tombstone(
    plan: FrozenEvidenceReplayPlan,
) -> None:
    coordinator = _coordinator(_Factory(plan), timings=_timings(idle_seconds=0.02))
    state = _start(coordinator)
    _eventually(lambda: coordinator.get_state().lifecycle_state == "IDLE")
    try:
        with pytest.raises(ReplayCoordinatorError) as raised:
            coordinator.control(
                scenario_id=REPLAY_SCENARIO_ID,
                session_id=state.session_id,
                expected_control_version=state.control_version,
                control=ReplayControl.STOP,
            )
        assert raised.value.code is ReplayErrorCode.SESSION_STALE
        assert coordinator._stop_tombstone is None
    finally:
        coordinator.shutdown()


@pytest.mark.parametrize(
    "target_lifecycle",
    [
        ReplayLifecycle.PAUSED,
        ReplayLifecycle.PLAYING,
        ReplayLifecycle.COMPLETED,
        ReplayLifecycle.FAILED,
        ReplayLifecycle.CLEANUP_FAILED,
    ],
)
def test_shutdown_cleans_every_stable_owned_lifecycle(
    plan: FrozenEvidenceReplayPlan,
    target_lifecycle: ReplayLifecycle,
) -> None:
    factory = _Factory(plan)
    if target_lifecycle is ReplayLifecycle.FAILED:
        factory.configure = lambda session: setattr(session, "fail_open", True)
    coordinator = _coordinator(factory)
    try:
        if target_lifecycle is ReplayLifecycle.FAILED:
            with pytest.raises(ReplayCoordinatorError):
                _start(coordinator)
        else:
            state = _start(coordinator)
            if target_lifecycle is ReplayLifecycle.PLAYING:
                _control(coordinator, state, ReplayControl.RESUME)
            elif target_lifecycle is ReplayLifecycle.COMPLETED:
                with coordinator._condition:
                    coordinator._public_lifecycle = ReplayLifecycle.COMPLETED
                    coordinator._internal_lifecycle = ReplayLifecycle.COMPLETED
                    coordinator._current_frame = coordinator._frame_projection(
                        plan.frame_at(468)
                    )
                    coordinator._next_cadence = None
            elif target_lifecycle is ReplayLifecycle.CLEANUP_FAILED:
                factory.sessions[0].fail_close = True
                with pytest.raises(ReplayCoordinatorError):
                    _control(coordinator, state, ReplayControl.STOP)
                factory.sessions[0].fail_close = False
        with coordinator._condition:
            assert coordinator._public_lifecycle is target_lifecycle
    finally:
        if factory.sessions:
            factory.sessions[0].fail_close = False
        coordinator.shutdown()
    assert coordinator._thread is not None and not coordinator._thread.is_alive()


def test_shutdown_during_started_starting_operation_is_bounded(
    plan: FrozenEvidenceReplayPlan,
) -> None:
    factory = _Factory(plan)
    release_open = threading.Event()
    factory.configure = lambda session: setattr(session, "block_open", release_open)
    coordinator = _coordinator(factory, timings=_timings(shutdown_seconds=2.0))
    start_worker, start_results = _invoke_in_thread(lambda: _start(coordinator))
    _eventually(lambda: bool(factory.sessions))
    assert factory.sessions[0].open_started.wait(timeout=1)
    with coordinator._condition:
        assert coordinator._internal_lifecycle is ReplayLifecycle.STARTING
    shutdown_worker, shutdown_results = _invoke_in_thread(coordinator.shutdown)
    try:
        release_open.set()
        start_worker.join(timeout=2)
        shutdown_worker.join(timeout=3)
        assert not start_worker.is_alive()
        assert not shutdown_worker.is_alive()
        assert len(start_results) == 1
        assert len(shutdown_results) == 1 and shutdown_results[0] is None
        assert coordinator._thread is not None and not coordinator._thread.is_alive()
    finally:
        release_open.set()
        if shutdown_worker.is_alive():
            shutdown_worker.join(timeout=3)


def test_shutdown_during_started_stopping_operation_is_bounded(
    plan: FrozenEvidenceReplayPlan,
) -> None:
    factory = _Factory(plan)
    coordinator = _coordinator(factory, timings=_timings(shutdown_seconds=2.0))
    state = _start(coordinator)
    release_close = threading.Event()
    factory.sessions[0].block_close = release_close
    stop_worker, stop_results = _invoke_in_thread(
        lambda: _control(coordinator, state, ReplayControl.STOP)
    )
    assert factory.sessions[0].close_started.wait(timeout=1)
    with coordinator._condition:
        assert coordinator._internal_lifecycle is ReplayLifecycle.STOPPING
    shutdown_worker, shutdown_results = _invoke_in_thread(coordinator.shutdown)
    try:
        release_close.set()
        stop_worker.join(timeout=2)
        shutdown_worker.join(timeout=3)
        assert not stop_worker.is_alive()
        assert not shutdown_worker.is_alive()
        assert len(stop_results) == 1 and not isinstance(
            stop_results[0], BaseException
        )
        assert len(shutdown_results) == 1 and shutdown_results[0] is None
        assert coordinator._thread is not None and not coordinator._thread.is_alive()
    finally:
        release_close.set()
        if shutdown_worker.is_alive():
            shutdown_worker.join(timeout=3)
