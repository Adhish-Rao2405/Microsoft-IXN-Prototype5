"""Authoritative server-side execution state for governed simulation.

`GovernanceRecordV2` remains immutable governance-time evidence. Runtime
execution state lives here, so there is exactly one source of truth for
permit lifecycle and simulation progress.
"""

from __future__ import annotations

import secrets
import threading
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum

from pydantic import Field

from .canonical_governance_runner import (
    CanonicalGovernanceResultV2,
    InternalGovernanceExecutionContextV1,
)
from .execution_permit import (
    DEFAULT_PERMIT_TTL_SECONDS,
    ExecutionPermitV1,
    SupportedOperationV1,
    build_execution_permit,
    compute_plan_hash,
    derive_supported_operation,
    format_canonical_timestamp,
    validate_permit_secret,
)
from .governance_contract_v2 import (
    ContractModel,
    FinalDecision,
    SimulationStatus,
)
from .manufacturing_policy_v2 import CommandInterpretationV2
from .task_proposal_v2 import ActionType, StructuredTaskProposalV2


DEFAULT_SESSION_TTL_SECONDS = 600
DEFAULT_SESSION_CAPACITY = 20


class PermitState(StrEnum):
    """Irreversible parent-side authority lifecycle.

    Temporal validity is a separate axis: a consumed permit may later verify
    as expired without the session ever ceasing to record that this trace
    already spent its single execution authority.
    """

    NOT_ISSUED = "NOT_ISSUED"
    CONSUMED = "CONSUMED"


class SimulationOutcome(StrEnum):
    """Detailed execution outcome, distinct from lifecycle SimulationStatus."""

    COMPLETED = "COMPLETED"
    REJECTED_INVALID_PERMIT = "REJECTED_INVALID_PERMIT"
    REJECTED_REPLAYED_PERMIT = "REJECTED_REPLAYED_PERMIT"
    REJECTED_EXPIRED_PERMIT = "REJECTED_EXPIRED_PERMIT"
    REJECTED_PLAN_MISMATCH = "REJECTED_PLAN_MISMATCH"
    REJECTED_POLICY_MISMATCH = "REJECTED_POLICY_MISMATCH"
    REJECTED_SCENE_MISMATCH = "REJECTED_SCENE_MISMATCH"
    REJECTED_OBJECT_MISMATCH = "REJECTED_OBJECT_MISMATCH"
    REJECTED_SOURCE_MISMATCH = "REJECTED_SOURCE_MISMATCH"
    REJECTED_DESTINATION_MISMATCH = "REJECTED_DESTINATION_MISMATCH"
    EXECUTION_TIMEOUT = "EXECUTION_TIMEOUT"
    WORKER_FAILED = "WORKER_FAILED"
    STOPPED = "STOPPED"


class ExecutionClaimReason(StrEnum):
    """Fail-closed reasons a claim attempt was refused."""

    TRACE_NOT_FOUND_OR_EXPIRED = "TRACE_NOT_FOUND_OR_EXPIRED"
    GOVERNANCE_RECORD_NOT_EXECUTION_ELIGIBLE = (
        "GOVERNANCE_RECORD_NOT_EXECUTION_ELIGIBLE"
    )
    EXECUTION_PROVENANCE_INCOMPLETE = "EXECUTION_PROVENANCE_INCOMPLETE"
    UNSUPPORTED_SIMULATION_OPERATION = "UNSUPPORTED_SIMULATION_OPERATION"
    EXECUTION_AUTHORITY_ALREADY_CLAIMED = "EXECUTION_AUTHORITY_ALREADY_CLAIMED"


class DuplicateExecutionTraceError(RuntimeError):
    """Raised when a trace_id would replace an existing governance snapshot."""

    code = "DUPLICATE_EXECUTION_TRACE"


class ExecutionRegistryAtCapacityError(RuntimeError):
    """Raised when capacity can only be reclaimed by deleting active authority."""

    code = "EXECUTION_REGISTRY_AT_CAPACITY"


ACTIVE_SIMULATION_STATUSES = frozenset(
    {
        SimulationStatus.QUEUED,
        SimulationStatus.RUNNING,
    }
)


class ExecutionGovernanceSnapshotV1(ContractModel):
    """Immutable governance-time execution context retained for issuance."""

    trace_id: str = Field(min_length=1)
    governance_record_id: str = Field(min_length=1)
    canonical_result: CanonicalGovernanceResultV2
    interpretation: CommandInterpretationV2 | None
    policy_id: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    policy_sha256: str
    captured_at_utc: str

    @property
    def proposal(self) -> StructuredTaskProposalV2 | None:
        return self.canonical_result.proposal

    @property
    def execution_eligible(self) -> bool:
        return self.canonical_result.governance_record.execution_eligible

    @property
    def final_decision(self) -> FinalDecision:
        return self.canonical_result.governance_record.final_decision

    @property
    def scene_id(self) -> str:
        return self.canonical_result.request.scene.scene_id

    @property
    def scene_state_version(self) -> str:
        return self.canonical_result.request.scene.state_version


class ExecutionSessionStateV1(ContractModel):
    """Frozen view of runtime state; never carries the permit signature."""

    trace_id: str
    governance_record_id: str
    execution_eligible: bool
    permit_state: PermitState
    permit_id: str | None
    execution_id: str | None
    simulation_status: SimulationStatus
    outcome: SimulationOutcome | None
    reason_code: str | None
    issued_at_utc: str | None
    consumed_at_utc: str | None


@dataclass
class ExecutionSessionV1:
    """Mutable runtime state guarded by the registry lock."""

    snapshot: ExecutionGovernanceSnapshotV1
    permit_state: PermitState = PermitState.NOT_ISSUED
    permit: ExecutionPermitV1 | None = None
    execution_id: str | None = None
    simulation_status: SimulationStatus = SimulationStatus.NOT_STARTED
    outcome: SimulationOutcome | None = None
    reason_code: str | None = None
    issued_at_utc: str | None = None
    consumed_at_utc: str | None = None

    @property
    def trace_id(self) -> str:
        return self.snapshot.trace_id

    def state_view(self) -> ExecutionSessionStateV1:
        return ExecutionSessionStateV1(
            trace_id=self.snapshot.trace_id,
            governance_record_id=self.snapshot.governance_record_id,
            execution_eligible=self.snapshot.execution_eligible,
            permit_state=self.permit_state,
            permit_id=self.permit.permit_id if self.permit is not None else None,
            execution_id=self.execution_id,
            simulation_status=self.simulation_status,
            outcome=self.outcome,
            reason_code=self.reason_code,
            issued_at_utc=self.issued_at_utc,
            consumed_at_utc=self.consumed_at_utc,
        )


@dataclass(frozen=True)
class PermitClaimResultV1:
    """Result of the single atomic issue-and-claim transaction."""

    claimed: bool
    permit: ExecutionPermitV1 | None = None
    execution_id: str | None = None
    proposal: StructuredTaskProposalV2 | None = None
    reason_code: ExecutionClaimReason | None = None


def build_execution_snapshot(
    context: InternalGovernanceExecutionContextV1,
    *,
    captured_at: datetime,
) -> ExecutionGovernanceSnapshotV1:
    """Capture governance-time execution provenance exactly as it was decided."""

    record = context.result.governance_record
    evaluation = context.policy_evaluation
    return ExecutionGovernanceSnapshotV1(
        trace_id=record.trace_id,
        governance_record_id=record.record_id,
        canonical_result=context.result,
        interpretation=evaluation.interpretation if evaluation is not None else None,
        policy_id=context.policy_id,
        policy_version=context.policy_version,
        policy_sha256=context.policy_sha256,
        captured_at_utc=format_canonical_timestamp(captured_at),
    )


class ExecutionSessionRegistry:
    """Bounded in-memory registry of governance traces and permit lifecycle.

    Process-local by design: the Prototype 5 demonstrator runs as a single
    FastAPI application process.

    Two independent reclamation axes:

    * TTL expiry, which is the unconditional time-based backstop;
    * capacity pressure, which is registration-order (FIFO) and never removes
      a QUEUED or RUNNING session.

    Reads do not refresh ordering, so polling a trace's status cannot keep it
    alive past its registration position.
    """

    def __init__(
        self,
        *,
        secret: bytes | bytearray | None = None,
        ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS,
        capacity: int = DEFAULT_SESSION_CAPACITY,
        permit_ttl_seconds: int = DEFAULT_PERMIT_TTL_SECONDS,
        utc_clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        if not 1 <= ttl_seconds <= 3600:
            raise ValueError("ttl_seconds must be between 1 and 3600")
        if not 1 <= capacity <= 1000:
            raise ValueError("capacity must be between 1 and 1000")
        if not 1 <= permit_ttl_seconds <= 3600:
            raise ValueError("permit_ttl_seconds must be between 1 and 3600")
        self.ttl_seconds = ttl_seconds
        self.capacity = capacity
        self.permit_ttl_seconds = permit_ttl_seconds
        self._secret = (
            secrets.token_bytes(32)
            if secret is None
            else validate_permit_secret(secret)
        )
        self._utc_clock = utc_clock or (lambda: datetime.now(timezone.utc))
        self._id_factory = id_factory or (lambda: secrets.token_hex(16))
        self._lock = threading.Lock()
        self._sessions: OrderedDict[
            str, tuple[ExecutionSessionV1, datetime]
        ] = OrderedDict()

    def register(
        self, context: InternalGovernanceExecutionContextV1
    ) -> ExecutionSessionStateV1:
        """Retain every completed governance trace, executable or not."""

        now = self._utc_clock()
        snapshot = build_execution_snapshot(context, captured_at=now)
        session = ExecutionSessionV1(snapshot=snapshot)
        if not snapshot.execution_eligible:
            session.simulation_status = SimulationStatus.NOT_REQUESTED
        expiry = now + timedelta(seconds=self.ttl_seconds)
        with self._lock:
            self._evict_expired_locked(now)
            if snapshot.trace_id in self._sessions:
                raise DuplicateExecutionTraceError(
                    DuplicateExecutionTraceError.code
                )
            self._make_room_locked()
            self._sessions[snapshot.trace_id] = (session, expiry)
            return session.state_view()

    def get_state(self, trace_id: str) -> ExecutionSessionStateV1 | None:
        with self._lock:
            self._evict_expired_locked(self._utc_clock())
            entry = self._sessions.get(trace_id)
            return entry[0].state_view() if entry is not None else None

    def issue_and_claim(self, trace_id: str) -> PermitClaimResultV1:
        """Issue exactly one permit for an eligible trace and claim it atomically.

        Issuance and consumption are a single transaction, so no reusable
        ISSUED window is ever externally observable, and a trace can yield at
        most one permit over its lifetime.
        """

        now = self._utc_clock()
        with self._lock:
            self._evict_expired_locked(now)
            entry = self._sessions.get(trace_id)
            if entry is None:
                return PermitClaimResultV1(
                    claimed=False,
                    reason_code=ExecutionClaimReason.TRACE_NOT_FOUND_OR_EXPIRED,
                )
            session, _ = entry
            if session.permit_state is not PermitState.NOT_ISSUED:
                return PermitClaimResultV1(
                    claimed=False,
                    reason_code=ExecutionClaimReason.EXECUTION_AUTHORITY_ALREADY_CLAIMED,
                )

            snapshot = session.snapshot
            if (
                not snapshot.execution_eligible
                or snapshot.final_decision is not FinalDecision.ACCEPT
            ):
                return PermitClaimResultV1(
                    claimed=False,
                    reason_code=(
                        ExecutionClaimReason
                        .GOVERNANCE_RECORD_NOT_EXECUTION_ELIGIBLE
                    ),
                )

            proposal = snapshot.proposal
            interpretation = snapshot.interpretation
            if proposal is None or interpretation is None:
                return PermitClaimResultV1(
                    claimed=False,
                    reason_code=(
                        ExecutionClaimReason.EXECUTION_PROVENANCE_INCOMPLETE
                    ),
                )

            operation = _authorised_operation(interpretation, proposal)
            if operation is None:
                return PermitClaimResultV1(
                    claimed=False,
                    reason_code=(
                        ExecutionClaimReason.UNSUPPORTED_SIMULATION_OPERATION
                    ),
                )

            permit = build_execution_permit(
                permit_id=self._id_factory(),
                trace_id=snapshot.trace_id,
                governance_record_id=snapshot.governance_record_id,
                plan_hash=compute_plan_hash(proposal),
                policy_id=snapshot.policy_id,
                policy_version=snapshot.policy_version,
                policy_sha256=snapshot.policy_sha256,
                scene_id=snapshot.scene_id,
                scene_state_version=snapshot.scene_state_version,
                operation=operation,
                issued_at=now,
                secret=self._secret,
                ttl_seconds=self.permit_ttl_seconds,
            )

            # A just-in-time permit cannot be expired at claim time: the clock
            # is read once and the expiry derives from that same instant.
            # Later expiry is a temporal fact reported by verification, not a
            # lifecycle change: the session stays CONSUMED because this trace
            # has irreversibly spent its one execution authority.
            session.permit = permit
            session.permit_state = PermitState.CONSUMED
            session.execution_id = self._id_factory()
            session.issued_at_utc = permit.issued_at_utc
            session.consumed_at_utc = format_canonical_timestamp(now)
            session.simulation_status = SimulationStatus.QUEUED
            return PermitClaimResultV1(
                claimed=True,
                permit=permit,
                execution_id=session.execution_id,
                proposal=proposal,
            )

    def verification_secret(self) -> bytes:
        """Expose the signing secret to in-process trusted components only."""

        return self._secret

    def _make_room_locked(self) -> None:
        """Free one slot using registration-order eviction, never active authority.

        Eviction is FIFO by registration order; reads deliberately do not
        refresh position, so status polling cannot keep a stale trace alive.
        A QUEUED or RUNNING session is never evicted, because deleting it
        would orphan an execution that still owes an audit result.
        """

        while len(self._sessions) >= self.capacity:
            victim = next(
                (
                    trace_id
                    for trace_id, (session, _) in self._sessions.items()
                    if session.simulation_status not in ACTIVE_SIMULATION_STATUSES
                ),
                None,
            )
            if victim is None:
                raise ExecutionRegistryAtCapacityError(
                    ExecutionRegistryAtCapacityError.code
                )
            self._sessions.pop(victim, None)

    def _evict_expired_locked(self, now: datetime) -> None:
        """Reclaim aged sessions, never an execution that still owes a result.

        An execution can legitimately outlive the registration TTL of the
        governance trace that authorised it. Deleting it here would orphan
        the execution and break the governance-to-audit chain, so QUEUED and
        RUNNING sessions are exempt from TTL as well as capacity reclamation.

        Slice-2 contract: when a session leaves an active state, its
        retention deadline must be recomputed from the terminal time, not
        from the original governance-registration time, or a just-completed
        result would be eligible for immediate deletion.
        """

        expired = [
            trace_id
            for trace_id, (session, expiry) in self._sessions.items()
            if expiry <= now
            and session.simulation_status not in ACTIVE_SIMULATION_STATUSES
        ]
        for trace_id in expired:
            self._sessions.pop(trace_id, None)


def _authorised_operation(
    interpretation: CommandInterpretationV2,
    proposal: StructuredTaskProposalV2,
) -> SupportedOperationV1 | None:
    """Derive the bounded operation from governance-time authority.

    The governance-time interpretation is the authority source. The validated
    proposal must independently reduce to the same bounded operation, so a
    permit can never authorise something the evaluated plan did not describe.
    """

    if interpretation.action is not ActionType.MOVE:
        return None
    if (
        interpretation.object_id is None
        or interpretation.source_id is None
        or interpretation.destination_id is None
    ):
        return None
    authorised = SupportedOperationV1(
        action=ActionType.MOVE,
        object_id=interpretation.object_id,
        source_id=interpretation.source_id,
        destination_id=interpretation.destination_id,
    )
    derived = derive_supported_operation(proposal)
    if derived is None or derived != authorised:
        return None
    return authorised
