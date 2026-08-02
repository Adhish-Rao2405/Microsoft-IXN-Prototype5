"""Signed one-time execution capability for governed simulation.

This module contains cryptographic and structural primitives only. It does not
read policy, call a model, evaluate governance, own session state, or start a
simulator. Permit authority is derived exclusively from governance-time
evidence supplied by the caller.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from datetime import datetime, timedelta, timezone
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator

from .governance_contract_v2 import SHA256_PATTERN, ContractModel
from .task_proposal_v2 import ActionType, StructuredTaskProposalV2


PERMIT_SIGNING_DOMAIN = "prototype5.execution_permit.v1"
DEFAULT_PERMIT_TTL_SECONDS = 60
MINIMUM_SECRET_BYTES = 32

CANONICAL_TIMESTAMP_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}\+00:00$"
)


class PermitVerificationResult(StrEnum):
    """Outcome of verifying a permit against a secret, clock and local context."""

    VALID = "VALID"
    INVALID_SIGNATURE = "INVALID_SIGNATURE"
    EXPIRED = "EXPIRED"
    PLAN_MISMATCH = "PLAN_MISMATCH"
    POLICY_MISMATCH = "POLICY_MISMATCH"
    SCENE_MISMATCH = "SCENE_MISMATCH"
    OBJECT_MISMATCH = "OBJECT_MISMATCH"
    SOURCE_MISMATCH = "SOURCE_MISMATCH"
    DESTINATION_MISMATCH = "DESTINATION_MISMATCH"
    UNSUPPORTED_OPERATION = "UNSUPPORTED_OPERATION"


def canonical_bytes(payload: BaseModel) -> bytes:
    """Return the one canonical byte encoding used for hashing and signing.

    The encoding is deliberately independent of Pydantic field declaration
    order so that innocent model refactoring cannot change a hash or a
    signature.
    """

    return json.dumps(
        payload.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def format_canonical_timestamp(value: datetime) -> str:
    """Emit the single permitted textual representation of an instant."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("canonical timestamps require a timezone-aware datetime")
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")


def parse_canonical_timestamp(value: str) -> datetime:
    """Parse only the canonical representation; equivalent spellings are refused."""

    if not CANONICAL_TIMESTAMP_PATTERN.fullmatch(value):
        raise ValueError(
            "permit timestamps must use YYYY-MM-DDTHH:MM:SS.ffffff+00:00"
        )
    return datetime.fromisoformat(value)


class SupportedOperationV1(ContractModel):
    """The one bounded manufacturing operation S1 may execute."""

    action: ActionType
    object_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    destination_id: str = Field(min_length=1)

    @field_validator("action")
    @classmethod
    def action_is_bounded_move(cls, value: ActionType) -> ActionType:
        if value is not ActionType.MOVE:
            raise ValueError("S1 supports the MOVE operation only")
        return value


def derive_supported_operation(
    proposal: StructuredTaskProposalV2,
) -> SupportedOperationV1 | None:
    """Reduce a validated proposal to its bounded operation, or refuse it.

    Only the two proposal shapes already accepted by the manufacturing
    semantics are supported: a single MOVE, or the equivalent PICK followed by
    PLACE for the same object. Any other shape returns None and must not
    execute.
    """

    actions = proposal.actions
    if len(actions) == 1 and actions[0].action is ActionType.MOVE:
        move = actions[0]
        if (
            move.object_id is None
            or move.source_id is None
            or move.destination_id is None
        ):
            return None
        return SupportedOperationV1(
            action=ActionType.MOVE,
            object_id=move.object_id,
            source_id=move.source_id,
            destination_id=move.destination_id,
        )
    if (
        len(actions) == 2
        and actions[0].action is ActionType.PICK
        and actions[1].action is ActionType.PLACE
    ):
        pick, place = actions
        if pick.object_id is None or pick.object_id != place.object_id:
            return None
        if pick.source_id is None or place.destination_id is None:
            return None
        return SupportedOperationV1(
            action=ActionType.MOVE,
            object_id=pick.object_id,
            source_id=pick.source_id,
            destination_id=place.destination_id,
        )
    return None


def compute_plan_hash(proposal: StructuredTaskProposalV2) -> str:
    """Hash the validated proposal, never the raw provider text."""

    return hashlib.sha256(canonical_bytes(proposal)).hexdigest()


class _PermitSigningPayloadV1(ContractModel):
    """Domain-separated signing payload; every bound field except the signature."""

    domain: str = PERMIT_SIGNING_DOMAIN
    permit_id: str
    trace_id: str
    governance_record_id: str
    plan_hash: str
    policy_id: str
    policy_version: str
    policy_sha256: str
    scene_id: str
    scene_state_version: str
    action: ActionType
    object_id: str
    source_id: str
    destination_id: str
    issued_at_utc: str
    expires_at_utc: str


class ExecutionPermitV1(ContractModel):
    """Immutable signed capability authorising exactly one bounded operation."""

    permit_id: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)
    governance_record_id: str = Field(min_length=1)
    plan_hash: str
    policy_id: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    policy_sha256: str
    scene_id: str = Field(min_length=1)
    scene_state_version: str = Field(min_length=1)
    action: ActionType
    object_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    destination_id: str = Field(min_length=1)
    issued_at_utc: str
    expires_at_utc: str
    signature: str

    @field_validator("plan_hash", "policy_sha256", "signature")
    @classmethod
    def hashes_are_sha256(cls, value: str) -> str:
        if not SHA256_PATTERN.fullmatch(value):
            raise ValueError("permit hash fields must contain 64 hexadecimal characters")
        return value.lower()

    @field_validator("issued_at_utc", "expires_at_utc")
    @classmethod
    def timestamps_are_canonical(cls, value: str) -> str:
        parse_canonical_timestamp(value)
        return value

    @field_validator("action")
    @classmethod
    def action_is_bounded_move(cls, value: ActionType) -> ActionType:
        if value is not ActionType.MOVE:
            raise ValueError("S1 permits authorise the MOVE operation only")
        return value

    @property
    def operation(self) -> SupportedOperationV1:
        return SupportedOperationV1(
            action=self.action,
            object_id=self.object_id,
            source_id=self.source_id,
            destination_id=self.destination_id,
        )

    def signing_payload(self) -> _PermitSigningPayloadV1:
        return _PermitSigningPayloadV1(
            permit_id=self.permit_id,
            trace_id=self.trace_id,
            governance_record_id=self.governance_record_id,
            plan_hash=self.plan_hash,
            policy_id=self.policy_id,
            policy_version=self.policy_version,
            policy_sha256=self.policy_sha256,
            scene_id=self.scene_id,
            scene_state_version=self.scene_state_version,
            action=self.action,
            object_id=self.object_id,
            source_id=self.source_id,
            destination_id=self.destination_id,
            issued_at_utc=self.issued_at_utc,
            expires_at_utc=self.expires_at_utc,
        )


def sign_permit_payload(payload: _PermitSigningPayloadV1, *, secret: bytes) -> str:
    _require_secret(secret)
    return hmac.new(secret, canonical_bytes(payload), hashlib.sha256).hexdigest()


def build_execution_permit(
    *,
    permit_id: str,
    trace_id: str,
    governance_record_id: str,
    plan_hash: str,
    policy_id: str,
    policy_version: str,
    policy_sha256: str,
    scene_id: str,
    scene_state_version: str,
    operation: SupportedOperationV1,
    issued_at: datetime,
    secret: bytes,
    ttl_seconds: int = DEFAULT_PERMIT_TTL_SECONDS,
) -> ExecutionPermitV1:
    """Mint one signed capability from already-validated governance-time values.

    Every argument must be supplied explicitly; nothing is defaulted or
    inferred, so missing execution provenance fails before a permit exists.
    """

    _require_secret(secret)
    if ttl_seconds <= 0:
        raise ValueError("permit ttl_seconds must be positive")
    issued_at_utc = format_canonical_timestamp(issued_at)
    expires_at_utc = format_canonical_timestamp(
        issued_at + timedelta(seconds=ttl_seconds)
    )
    payload = _PermitSigningPayloadV1(
        permit_id=permit_id,
        trace_id=trace_id,
        governance_record_id=governance_record_id,
        plan_hash=plan_hash,
        policy_id=policy_id,
        policy_version=policy_version,
        policy_sha256=policy_sha256,
        scene_id=scene_id,
        scene_state_version=scene_state_version,
        action=operation.action,
        object_id=operation.object_id,
        source_id=operation.source_id,
        destination_id=operation.destination_id,
        issued_at_utc=issued_at_utc,
        expires_at_utc=expires_at_utc,
    )
    return ExecutionPermitV1(
        permit_id=permit_id,
        trace_id=trace_id,
        governance_record_id=governance_record_id,
        plan_hash=plan_hash,
        policy_id=policy_id,
        policy_version=policy_version,
        policy_sha256=policy_sha256,
        scene_id=scene_id,
        scene_state_version=scene_state_version,
        action=operation.action,
        object_id=operation.object_id,
        source_id=operation.source_id,
        destination_id=operation.destination_id,
        issued_at_utc=issued_at_utc,
        expires_at_utc=expires_at_utc,
        signature=sign_permit_payload(payload, secret=secret),
    )


def verify_execution_permit(
    permit: ExecutionPermitV1,
    *,
    secret: bytes,
    now: datetime,
    proposal: StructuredTaskProposalV2 | None = None,
    expected_scene_id: str | None = None,
    expected_scene_state_version: str | None = None,
    expected_policy_id: str | None = None,
    expected_policy_version: str | None = None,
    expected_policy_sha256: str | None = None,
) -> PermitVerificationResult:
    """Verify a permit against a secret, a clock and optional local context.

    When a proposal is supplied the plan hash preimage is recomputed and the
    proposal's bounded operation must equal the operation the permit
    authorises, so a signed permit cannot bind one plan's hash to a different
    operation.
    """

    _require_secret(secret)
    expected_signature = sign_permit_payload(permit.signing_payload(), secret=secret)
    if not hmac.compare_digest(expected_signature, permit.signature):
        return PermitVerificationResult.INVALID_SIGNATURE

    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("permit verification requires a timezone-aware clock")
    if now >= parse_canonical_timestamp(permit.expires_at_utc):
        return PermitVerificationResult.EXPIRED

    if proposal is not None:
        if compute_plan_hash(proposal) != permit.plan_hash:
            return PermitVerificationResult.PLAN_MISMATCH
        operation = derive_supported_operation(proposal)
        if operation is None:
            return PermitVerificationResult.UNSUPPORTED_OPERATION
        if operation.object_id != permit.object_id:
            return PermitVerificationResult.OBJECT_MISMATCH
        if operation.source_id != permit.source_id:
            return PermitVerificationResult.SOURCE_MISMATCH
        if operation.destination_id != permit.destination_id:
            return PermitVerificationResult.DESTINATION_MISMATCH
        if operation.action is not permit.action:
            return PermitVerificationResult.PLAN_MISMATCH

    if expected_scene_id is not None and expected_scene_id != permit.scene_id:
        return PermitVerificationResult.SCENE_MISMATCH
    if (
        expected_scene_state_version is not None
        and expected_scene_state_version != permit.scene_state_version
    ):
        return PermitVerificationResult.SCENE_MISMATCH
    if expected_policy_id is not None and expected_policy_id != permit.policy_id:
        return PermitVerificationResult.POLICY_MISMATCH
    if (
        expected_policy_version is not None
        and expected_policy_version != permit.policy_version
    ):
        return PermitVerificationResult.POLICY_MISMATCH
    if (
        expected_policy_sha256 is not None
        and expected_policy_sha256.lower() != permit.policy_sha256
    ):
        return PermitVerificationResult.POLICY_MISMATCH

    return PermitVerificationResult.VALID


def _require_secret(secret: bytes) -> None:
    if not isinstance(secret, (bytes, bytearray)):
        raise TypeError("permit secret must be raw bytes")
    if len(secret) < MINIMUM_SECRET_BYTES:
        raise ValueError(
            f"permit secret must be at least {MINIMUM_SECRET_BYTES} bytes"
        )
