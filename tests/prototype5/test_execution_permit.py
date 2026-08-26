from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from src.prototype5.execution_permit import (
    PERMIT_SIGNING_DOMAIN,
    _verify_permit_signature,
    ExecutionPermitV1,
    PermitVerificationResult,
    SupportedOperationV1,
    build_execution_permit,
    canonical_bytes,
    compute_plan_hash,
    derive_supported_operation,
    format_canonical_timestamp,
    parse_canonical_timestamp,
    sign_permit_payload,
    verify_execution_permit,
)
from src.prototype5.governance_contract_v2 import ContractModel
from src.prototype5.task_proposal_v2 import (
    ActionStepV2,
    ActionType,
    StructuredTaskProposalV2,
)


SECRET = b"\x00" * 32
OTHER_SECRET = b"\x01" * 32
ISSUED_AT = datetime(2026, 8, 2, 12, 0, 0, tzinfo=timezone.utc)
POLICY_SHA = "c" * 64

GOLDEN_CANONICAL_JSON = (
    '{"actions":[{"action":"MOVE","destination_id":"assembly_fixture_b",'
    '"duration_ms":null,"object_id":"blue_component","source_id":"input_tray_a"}]}'
)
GOLDEN_PLAN_HASH = (
    "19bfdec21bb0f1a1f0cd2f015bdc899c862f58ba02b815d9ac26f9ef0347f4d2"
)
GOLDEN_SIGNATURE = (
    "1334cbf937d14b91fd86fc28c278e8aefb71a97051f72ad4df116d85466dc297"
)


def move_proposal(
    *,
    object_id: str = "blue_component",
    source_id: str = "input_tray_a",
    destination_id: str = "assembly_fixture_b",
) -> StructuredTaskProposalV2:
    return StructuredTaskProposalV2(
        actions=(
            ActionStepV2(
                action=ActionType.MOVE,
                object_id=object_id,
                source_id=source_id,
                destination_id=destination_id,
            ),
        )
    )


def pick_place_proposal(
    *,
    object_id: str = "blue_component",
    source_id: str = "input_tray_a",
    destination_id: str = "assembly_fixture_b",
) -> StructuredTaskProposalV2:
    return StructuredTaskProposalV2(
        actions=(
            ActionStepV2(
                action=ActionType.PICK,
                object_id=object_id,
                source_id=source_id,
            ),
            ActionStepV2(
                action=ActionType.PLACE,
                object_id=object_id,
                destination_id=destination_id,
            ),
        )
    )


def permit(
    *,
    proposal: StructuredTaskProposalV2 | None = None,
    issued_at: datetime = ISSUED_AT,
    secret: bytes = SECRET,
    ttl_seconds: int = 60,
) -> ExecutionPermitV1:
    resolved = proposal if proposal is not None else move_proposal()
    operation = derive_supported_operation(resolved)
    assert operation is not None
    return build_execution_permit(
        permit_id="permit-golden-1",
        trace_id="trace-golden-1",
        governance_record_id="record-golden-1",
        plan_hash=compute_plan_hash(resolved),
        policy_id="prototype5_manufacturing_policy_v2",
        policy_version="2.0.0",
        policy_sha256=POLICY_SHA,
        scene_id="manufacturing_demo_scene",
        scene_state_version="1.0.0",
        operation=operation,
        issued_at=issued_at,
        secret=secret,
        ttl_seconds=ttl_seconds,
    )


# --------------------------------------------------------------------------
# canonical bytes
# --------------------------------------------------------------------------


def test_canonical_bytes_match_the_frozen_golden_vector():
    assert canonical_bytes(move_proposal()).decode("utf-8") == GOLDEN_CANONICAL_JSON
    assert compute_plan_hash(move_proposal()) == GOLDEN_PLAN_HASH


def test_keyword_argument_order_does_not_change_canonical_bytes():
    first = ActionStepV2(
        action=ActionType.MOVE,
        object_id="blue_component",
        source_id="input_tray_a",
        destination_id="assembly_fixture_b",
    )
    second = ActionStepV2(
        destination_id="assembly_fixture_b",
        source_id="input_tray_a",
        object_id="blue_component",
        action=ActionType.MOVE,
    )
    assert canonical_bytes(
        StructuredTaskProposalV2(actions=(first,))
    ) == canonical_bytes(StructuredTaskProposalV2(actions=(second,)))


def test_declaration_order_of_an_equivalent_model_does_not_change_bytes():
    class Ascending(ContractModel):
        alpha: str
        beta: str

    class Descending(ContractModel):
        beta: str
        alpha: str

    assert canonical_bytes(Ascending(alpha="1", beta="2")) == canonical_bytes(
        Descending(beta="2", alpha="1")
    )


def test_nested_key_order_is_stable_but_action_order_is_significant():
    forward = pick_place_proposal()
    reversed_actions = StructuredTaskProposalV2(
        actions=(forward.actions[1], forward.actions[0])
    )
    assert canonical_bytes(forward) != canonical_bytes(reversed_actions)


def test_non_ascii_content_is_encoded_stably():
    class Text(ContractModel):
        value: str

    encoded = canonical_bytes(Text(value="fixture-é中"))
    assert encoded.decode("utf-8") == '{"value":"fixture-é中"}'
    assert canonical_bytes(Text(value="fixture-é中")) == encoded


def test_non_finite_floats_are_rejected():
    class Measurement(ContractModel):
        value: float

    with pytest.raises(ValueError):
        canonical_bytes(Measurement(value=float("nan")))


def test_null_fields_are_retained_in_canonical_bytes():
    assert '"duration_ms":null' in canonical_bytes(move_proposal()).decode("utf-8")


# --------------------------------------------------------------------------
# canonical timestamps
# --------------------------------------------------------------------------


def test_canonical_timestamp_emits_exactly_one_representation():
    assert (
        format_canonical_timestamp(ISSUED_AT) == "2026-08-02T12:00:00.000000+00:00"
    )


def test_zero_microseconds_still_emits_six_fractional_digits():
    assert format_canonical_timestamp(ISSUED_AT).endswith(".000000+00:00")


def test_non_utc_input_is_normalised_to_utc_on_emission():
    other_zone = timezone(timedelta(hours=1))
    same_instant = ISSUED_AT.astimezone(other_zone)
    assert format_canonical_timestamp(same_instant) == format_canonical_timestamp(
        ISSUED_AT
    )


def test_naive_datetimes_are_refused():
    with pytest.raises(ValueError):
        format_canonical_timestamp(datetime(2026, 8, 2, 12, 0, 0))


def test_canonical_timestamp_round_trips_exactly():
    text = format_canonical_timestamp(ISSUED_AT)
    assert parse_canonical_timestamp(text) == ISSUED_AT
    assert format_canonical_timestamp(parse_canonical_timestamp(text)) == text


@pytest.mark.parametrize(
    "value",
    [
        "2026-08-02T12:00:00.000000Z",
        "2026-08-02T12:00:00+00:00",
        "2026-08-02T12:00:00.000+00:00",
        "2026-08-02T13:00:00.000000+01:00",
        "2026-08-02 12:00:00.000000+00:00",
    ],
)
def test_equivalent_or_alternate_timestamp_spellings_are_rejected(value: str):
    with pytest.raises(ValueError):
        parse_canonical_timestamp(value)


def test_permit_rejects_a_non_canonical_timestamp_field():
    payload = permit().model_dump(mode="json")
    payload["issued_at_utc"] = "2026-08-02T12:00:00.000000Z"
    with pytest.raises(ValidationError):
        ExecutionPermitV1.model_validate(payload)


# --------------------------------------------------------------------------
# supported operation derivation
# --------------------------------------------------------------------------


def test_single_move_derives_the_bounded_operation():
    operation = derive_supported_operation(move_proposal())
    assert operation == SupportedOperationV1(
        action=ActionType.MOVE,
        object_id="blue_component",
        source_id="input_tray_a",
        destination_id="assembly_fixture_b",
    )


def test_pick_then_place_derives_the_same_bounded_operation():
    assert derive_supported_operation(
        pick_place_proposal()
    ) == derive_supported_operation(move_proposal())


def test_pick_and_place_for_different_objects_is_refused():
    proposal = StructuredTaskProposalV2(
        actions=(
            ActionStepV2(
                action=ActionType.PICK,
                object_id="blue_component",
                source_id="input_tray_a",
            ),
            ActionStepV2(
                action=ActionType.PLACE,
                object_id="red_component",
                destination_id="assembly_fixture_b",
            ),
        )
    )
    assert derive_supported_operation(proposal) is None


@pytest.mark.parametrize(
    "proposal",
    [
        StructuredTaskProposalV2(
            actions=(ActionStepV2(action=ActionType.STOP),)
        ),
        StructuredTaskProposalV2(
            actions=(ActionStepV2(action=ActionType.WAIT, duration_ms=100),)
        ),
        StructuredTaskProposalV2(
            actions=(
                ActionStepV2(
                    action=ActionType.INSPECT, object_id="blue_component"
                ),
            )
        ),
        StructuredTaskProposalV2(
            actions=(
                ActionStepV2(
                    action=ActionType.MOVE,
                    object_id="blue_component",
                    source_id="input_tray_a",
                    destination_id="assembly_fixture_b",
                ),
                ActionStepV2(action=ActionType.STOP),
            )
        ),
    ],
)
def test_unsupported_proposal_shapes_are_refused(
    proposal: StructuredTaskProposalV2,
):
    assert derive_supported_operation(proposal) is None


def test_supported_operation_rejects_non_move_actions():
    with pytest.raises(ValidationError):
        SupportedOperationV1(
            action=ActionType.PICK,
            object_id="blue_component",
            source_id="input_tray_a",
            destination_id="assembly_fixture_b",
        )


# --------------------------------------------------------------------------
# permit issue and verify
# --------------------------------------------------------------------------


def test_issued_permit_matches_the_golden_signature():
    assert permit().signature == GOLDEN_SIGNATURE


def test_signing_payload_is_domain_separated():
    payload = permit().signing_payload()
    assert payload.domain == PERMIT_SIGNING_DOMAIN
    assert "domain" in canonical_bytes(payload).decode("utf-8")


def test_valid_permit_verifies_against_its_proposal_and_context():
    assert (
        verify(permit(), proposal=move_proposal())
        is PermitVerificationResult.VALID
    )


def test_permit_verifies_against_the_equivalent_pick_place_proposal():
    issued = permit(proposal=pick_place_proposal())
    assert (
        verify(issued, proposal=pick_place_proposal())
        is PermitVerificationResult.VALID
    )


@pytest.mark.parametrize(
    "omitted",
    [
        "proposal",
        "expected_scene_id",
        "expected_scene_state_version",
        "expected_policy_id",
        "expected_policy_version",
        "expected_policy_sha256",
    ],
)
def test_execution_verification_cannot_omit_any_binding(omitted: str):
    """A partial call must not be able to yield VALID; it must not compile."""

    context = {
        "proposal": move_proposal(),
        "expected_scene_id": "manufacturing_demo_scene",
        "expected_scene_state_version": "1.0.0",
        "expected_policy_id": "prototype5_manufacturing_policy_v2",
        "expected_policy_version": "2.0.0",
        "expected_policy_sha256": POLICY_SHA,
    }
    context.pop(omitted)
    with pytest.raises(TypeError):
        verify_execution_permit(
            permit(), secret=SECRET, now=ISSUED_AT, **context
        )


def test_signature_only_check_is_not_sufficient_for_execution():
    """The narrow helper says the bytes are authentic, nothing more."""

    proposal = move_proposal()
    operation = derive_supported_operation(proposal)
    assert operation is not None
    mismatched_scene = build_execution_permit(
        permit_id="permit-scene",
        trace_id="trace-golden-1",
        governance_record_id="record-golden-1",
        plan_hash=compute_plan_hash(proposal),
        policy_id="prototype5_manufacturing_policy_v2",
        policy_version="2.0.0",
        policy_sha256=POLICY_SHA,
        scene_id="some_other_scene",
        scene_state_version="1.0.0",
        operation=operation,
        issued_at=ISSUED_AT,
        secret=SECRET,
        ttl_seconds=60,
    )
    assert _verify_permit_signature(mismatched_scene, secret=SECRET) is True
    assert verify(mismatched_scene) is PermitVerificationResult.SCENE_MISMATCH


def test_a_different_secret_fails_verification():
    assert verify(permit(), secret=OTHER_SECRET) is (
        PermitVerificationResult.INVALID_SIGNATURE
    )


@pytest.mark.parametrize(
    "field_name,replacement",
    [
        ("permit_id", "permit-forged"),
        ("trace_id", "trace-forged"),
        ("governance_record_id", "record-forged"),
        ("plan_hash", "d" * 64),
        ("policy_id", "forged_policy"),
        ("policy_version", "9.9.9"),
        ("policy_sha256", "e" * 64),
        ("scene_id", "forged_scene"),
        ("scene_state_version", "9.9.9"),
        ("object_id", "red_component"),
        ("source_id", "conveyor_a"),
        ("destination_id", "restricted_zone"),
        ("issued_at_utc", "2026-08-02T11:00:00.000000+00:00"),
        ("expires_at_utc", "2026-08-02T23:59:00.000000+00:00"),
    ],
)
def test_tampering_with_any_bound_field_fails_verification(
    field_name: str, replacement: str
):
    payload = permit().model_dump(mode="json")
    payload[field_name] = replacement
    tampered = ExecutionPermitV1.model_validate(payload)
    assert verify(tampered) is PermitVerificationResult.INVALID_SIGNATURE


def test_tampering_with_the_signature_itself_fails_verification():
    payload = permit().model_dump(mode="json")
    payload["signature"] = "f" * 64
    tampered = ExecutionPermitV1.model_validate(payload)
    assert verify(tampered) is PermitVerificationResult.INVALID_SIGNATURE


def test_expired_permit_is_rejected_at_its_expiry_instant():
    issued = permit()
    assert verify(issued, now=ISSUED_AT + timedelta(seconds=59)) is (
        PermitVerificationResult.VALID
    )
    assert verify(issued, now=ISSUED_AT + timedelta(seconds=60)) is (
        PermitVerificationResult.EXPIRED
    )


def test_signature_is_checked_before_expiry():
    payload = permit().model_dump(mode="json")
    payload["object_id"] = "red_component"
    tampered = ExecutionPermitV1.model_validate(payload)
    assert verify(tampered, now=ISSUED_AT + timedelta(days=1)) is (
        PermitVerificationResult.INVALID_SIGNATURE
    )


def test_a_proposal_with_a_different_plan_hash_is_refused():
    issued = permit()
    other = move_proposal(destination_id="destination_bin_b")
    assert verify(issued, proposal=other) is PermitVerificationResult.PLAN_MISMATCH


def test_a_permit_bound_to_a_different_operation_than_its_plan_is_refused():
    """A signer bug binding plan A's hash to operation B must not execute."""

    proposal = move_proposal()
    operation = derive_supported_operation(proposal)
    assert operation is not None
    divergent = build_execution_permit(
        permit_id="permit-divergent",
        trace_id="trace-golden-1",
        governance_record_id="record-golden-1",
        plan_hash=compute_plan_hash(proposal),
        policy_id="prototype5_manufacturing_policy_v2",
        policy_version="2.0.0",
        policy_sha256=POLICY_SHA,
        scene_id="manufacturing_demo_scene",
        scene_state_version="1.0.0",
        operation=SupportedOperationV1(
            action=ActionType.MOVE,
            object_id="red_component",
            source_id="input_tray_a",
            destination_id="assembly_fixture_b",
        ),
        issued_at=ISSUED_AT,
        secret=SECRET,
        ttl_seconds=60,
    )
    assert _verify_permit_signature(divergent, secret=SECRET) is True
    assert verify(divergent, proposal=proposal) is (
        PermitVerificationResult.OBJECT_MISMATCH
    )


@pytest.mark.parametrize(
    "kwargs,expected",
    [
        ({"expected_scene_id": "other_scene"}, PermitVerificationResult.SCENE_MISMATCH),
        (
            {"expected_scene_state_version": "9.9.9"},
            PermitVerificationResult.SCENE_MISMATCH,
        ),
        (
            {"expected_policy_id": "other_policy"},
            PermitVerificationResult.POLICY_MISMATCH,
        ),
        (
            {"expected_policy_version": "9.9.9"},
            PermitVerificationResult.POLICY_MISMATCH,
        ),
        (
            {"expected_policy_sha256": "d" * 64},
            PermitVerificationResult.POLICY_MISMATCH,
        ),
    ],
)
def test_local_context_mismatches_are_reported_distinctly(kwargs, expected):
    assert verify(permit(), **kwargs) is expected


def test_matching_local_context_verifies():
    assert (
        verify(
            permit(),
            expected_scene_id="manufacturing_demo_scene",
            expected_scene_state_version="1.0.0",
            expected_policy_id="prototype5_manufacturing_policy_v2",
            expected_policy_version="2.0.0",
            expected_policy_sha256=POLICY_SHA,
        )
        is PermitVerificationResult.VALID
    )


def test_short_or_non_bytes_secrets_are_refused():
    with pytest.raises(ValueError):
        sign_permit_payload(permit().signing_payload(), secret=b"\x00" * 31)
    with pytest.raises(TypeError):
        sign_permit_payload(permit().signing_payload(), secret="not-bytes")


def test_signing_secret_never_appears_in_permit_output():
    secret = bytes(range(32))
    issued = permit(secret=secret)
    rendered = "\n".join(
        (
            issued.model_dump_json(),
            repr(issued),
            str(issued.model_dump(mode="json")),
            canonical_bytes(issued.signing_payload()).decode("utf-8"),
        )
    )
    assert secret.hex() not in rendered
    for chunk_start in range(0, 24):
        assert secret[chunk_start : chunk_start + 8].hex() not in rendered


def test_permit_is_immutable():
    issued = permit()
    with pytest.raises(ValidationError):
        issued.object_id = "red_component"


def verify(
    issued: ExecutionPermitV1,
    *,
    now: datetime = ISSUED_AT,
    secret: bytes = SECRET,
    **overrides: object,
) -> PermitVerificationResult:
    """Verify with the complete S1 execution context unless a test overrides it."""

    context: dict[str, object] = {
        "proposal": move_proposal(),
        "expected_scene_id": "manufacturing_demo_scene",
        "expected_scene_state_version": "1.0.0",
        "expected_policy_id": "prototype5_manufacturing_policy_v2",
        "expected_policy_version": "2.0.0",
        "expected_policy_sha256": POLICY_SHA,
    }
    context.update(overrides)
    return verify_execution_permit(issued, secret=secret, now=now, **context)
