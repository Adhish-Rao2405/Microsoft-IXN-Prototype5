from __future__ import annotations

import copy
import hashlib
import json
import math
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pybullet as pb
import pytest

from src.prototype5 import frozen_evidence_replay as replay
from src.prototype5 import pybullet_evidence_replay as visual
from src.prototype5.final_demo_contract import load_final_demo_contract


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def plan() -> replay.FrozenEvidenceReplayPlan:
    return replay.load_registered_frozen_evidence_replay()


def _json(path: str) -> dict[str, object]:
    value = json.loads((ROOT / path).read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _session(
    plan: replay.FrozenEvidenceReplayPlan,
    *,
    connection_mode: int = pb.DIRECT,
) -> visual.PyBulletEvidenceReplaySession:
    return visual.PyBulletEvidenceReplaySession._from_attested_plan(
        plan,
        connection_mode=connection_mode,
    )


def test_canonical_registered_replay_is_exact(
    plan: replay.FrozenEvidenceReplayPlan,
) -> None:
    assert plan.scenario_id == replay.REPLAY_SCENARIO_ID
    assert plan.binding_id == replay.REPLAY_BINDING_ID
    assert len(plan.snapshots) == 10
    assert tuple(snapshot.replay_index for snapshot in plan.snapshots) == tuple(range(10))
    assert tuple(snapshot.semantic_snapshot_index for snapshot in plan.snapshots) == (
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
    assert tuple(snapshot.b2_route_index for snapshot in plan.snapshots) == (
        0,
        1,
        2,
        2,
        3,
        4,
        5,
        5,
        6,
        7,
    )
    assert tuple(
        (
            snapshot.semantic_snapshot_index,
            snapshot.route_configuration_index,
            snapshot.b2_route_index,
            snapshot.route_state,
            snapshot.phase,
            snapshot.boundary_snapshot,
        )
        for snapshot in plan.snapshots
    ) == tuple(
        (
            point.semantic_snapshot_index,
            point.route_configuration_index,
            point.b2_route_index,
            point.route_state,
            point.phase,
            point.boundary_snapshot,
        )
        for point in replay.EXPECTED_REPLAY_POINTS
    )


def test_artifact_attestations_match_registered_bytes(
    plan: replay.FrozenEvidenceReplayPlan,
) -> None:
    contract = load_final_demo_contract()
    expected = {
        contract.frozen_evidence_bindings.b2.path: contract.frozen_evidence_bindings.b2.sha256,
        contract.frozen_evidence_bindings.b3_1.path: contract.frozen_evidence_bindings.b3_1.sha256,
        contract.frozen_evidence_bindings.b3_2.path: contract.frozen_evidence_bindings.b3_2.sha256,
        contract.frozen_evidence_bindings.b3_2.specification_path: (
            contract.frozen_evidence_bindings.b3_2.specification_sha256
        ),
    }
    assert {item.logical_path: item.sha256 for item in plan.artifacts} == expected
    for item in plan.artifacts:
        payload = (ROOT / item.logical_path).read_bytes()
        assert item.byte_count == len(payload)
        assert hashlib.sha256(payload).hexdigest() == item.sha256


def test_only_dedicated_scenario_is_replay_compatible() -> None:
    contract = load_final_demo_contract()
    compatible = [
        scenario
        for scenario in contract.scenario_contract.scenarios
        if scenario.replay_capability.classification == "FROZEN_B2_REPLAY_COMPATIBLE"
    ]
    assert [scenario.scenario_id for scenario in compatible] == [
        replay.REPLAY_SCENARIO_ID
    ]
    assert compatible[0].replay_capability.qualification_replay_access == (
        "SERVER_REGISTERED_ONLY"
    )
    assert compatible[0].client_overridable_context_fields == []
    assert compatible[0].model_input_enabled is False


def test_mode_e_and_live_scenarios_cannot_replay() -> None:
    contract = load_final_demo_contract()
    for scenario in contract.scenario_contract.scenarios:
        if scenario.scenario_id == replay.REPLAY_SCENARIO_ID:
            continue
        assert scenario.replay_capability.classification == "GOVERNANCE_ONLY"
        assert scenario.replay_capability.qualification_replay_access == "PROHIBITED"
        assert scenario.replay_capability.allowed_replay_controls == []
        assert scenario.replay_capability.pybullet_controls_may_be_exposed is False


def test_claim_boundary_cannot_be_misrepresented(
    plan: replay.FrozenEvidenceReplayPlan,
) -> None:
    claims = plan.claim_boundary
    assert claims.required_labels == (
        "EVIDENCE REPLAY",
        "NOT PHYSICAL EXECUTION",
    )
    assert isinstance(claims.required_labels, tuple)
    assert claims.reconstructs_frozen_states is True
    assert claims.consumes_immutable_evidence is True
    assert claims.performs_new_ik is False
    assert claims.optimises_trajectory is False
    assert claims.generates_new_collision_result is False
    assert claims.proves_dynamic_feasibility is False
    assert claims.proves_physical_robot_safety is False
    assert claims.authorises_physical_execution is False
    assert claims.replay_is_fresh_execution is False
    assert claims.generated_by_current_model_output is False
    assert claims.discrete_sampling_limitation == (
        "Discrete sampling cannot prove the absence of collision between evaluated "
        "configurations."
    )


def test_claim_boundary_is_deeply_immutable(
    plan: replay.FrozenEvidenceReplayPlan,
) -> None:
    claims = plan.claim_boundary

    with pytest.raises(AttributeError):
        claims.required_labels.append("EVIDENCE REPLAY")  # type: ignore[attr-defined]
    with pytest.raises(AttributeError):
        claims.required_labels.clear()  # type: ignore[attr-defined]
    with pytest.raises(TypeError):
        claims.required_labels[0] = "NOT PHYSICAL EXECUTION"  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        claims.authorises_physical_execution = True  # type: ignore[misc]
    with pytest.raises(replay.ReplayDomainError, match="claim semantics changed"):
        replace(claims, performs_new_ik=True)

    assert claims.required_labels == replay.EXPECTED_REPLAY_CLAIM_LABELS
    assert claims.authorises_physical_execution is False


def test_claim_boundary_snapshot_does_not_retain_d0_list() -> None:
    contract = load_final_demo_contract()
    d0_labels = contract.replay_claim_boundary.required_labels
    isolated_plan = replay._load_registered_frozen_evidence_replay_from_root(
        ROOT,
        contract,
    )

    d0_labels.append("EVIDENCE REPLAY")

    assert len(d0_labels) == 3
    assert isolated_plan.claim_boundary.required_labels == (
        "EVIDENCE REPLAY",
        "NOT PHYSICAL EXECUTION",
    )


def test_b3_2_failure_is_preserved(plan: replay.FrozenEvidenceReplayPlan) -> None:
    qualification = plan.qualification
    assert qualification.overall_result == "B3_2_FAIL_DISCRETE_ROUTE_QUALIFICATION"
    assert qualification.scientific_failure_count == 118
    assert qualification.failure_codes_present == (
        "B3_2_FAIL_SUPPORT_MATERIAL_PENETRATION",
    )
    assert qualification.forbidden_contact_failure_count == 0
    assert qualification.support_material_penetration_failure_count == 118
    assert qualification.required_support_missing_failure_count == 0


def test_recorded_destination_release_failure_is_exact(
    plan: replay.FrozenEvidenceReplayPlan,
) -> None:
    failure = plan.qualification.recorded_failure
    assert failure.semantic_snapshot_index == 352
    assert failure.route_state == "DESTINATION_PLACE"
    assert failure.phase == "RELEASE_BOUNDARY"
    assert failure.boundary_snapshot == "POST"
    assert failure.pair_id == "component_environment:destination_floor"
    assert failure.pair_index == 78
    assert failure.query_body_a == "component"
    assert failure.query_body_b == "destination_floor"
    assert failure.signed_distance_m == -9.290505685985613e-7
    assert failure.classification == "MATERIAL_PENETRATION"
    assert failure.permission == "REQUIRED_SUPPORT"
    assert failure.decision == "B3_2_FAIL_SUPPORT_MATERIAL_PENETRATION"


def test_boundary_snapshots_preserve_duplicate_joint_states(
    plan: replay.FrozenEvidenceReplayPlan,
) -> None:
    source_pre, source_post = plan.snapshots[2:4]
    release_pre, release_post = plan.snapshots[6:8]
    assert source_pre.boundary_snapshot == "PRE"
    assert source_post.boundary_snapshot == "POST"
    assert source_pre.phase == source_post.phase == "ATTACHMENT_BOUNDARY"
    assert source_pre.joint_positions == source_post.joint_positions
    assert source_pre.route_configuration_index == source_post.route_configuration_index
    assert source_pre.component_position_m != source_post.component_position_m
    assert source_pre.component_quaternion_xyzw == source_post.component_quaternion_xyzw
    assert release_pre.boundary_snapshot == "PRE"
    assert release_post.boundary_snapshot == "POST"
    assert release_pre.phase == release_post.phase == "RELEASE_BOUNDARY"
    assert release_pre.joint_positions == release_post.joint_positions
    assert release_pre.route_configuration_index == release_post.route_configuration_index
    assert release_pre.component_position_m == release_post.component_position_m
    assert release_pre.component_quaternion_xyzw == release_post.component_quaternion_xyzw


def test_home_round_trip_is_not_deduplicated(
    plan: replay.FrozenEvidenceReplayPlan,
) -> None:
    assert plan.snapshots[0].route_state == "HOME"
    assert plan.snapshots[-1].route_state == "HOME"
    assert plan.snapshots[0].joint_positions == plan.snapshots[-1].joint_positions
    assert plan.snapshots[0].phase == "SOURCE_SUPPORTED"
    assert plan.snapshots[-1].phase == "DESTINATION_SUPPORTED"


@pytest.mark.parametrize("invalid_index", [None, True, -1, 10, 1.0, "1"])
def test_snapshot_lookup_fails_closed(
    plan: replay.FrozenEvidenceReplayPlan,
    invalid_index: object,
) -> None:
    with pytest.raises(replay.ReplayDomainError):
        plan.snapshot_at(invalid_index)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "invalid_joints",
    [
        (),
        (0.0,) * 6,
        (0.0,) * 8,
        (None,) + (0.0,) * 6,
        (True,) + (0.0,) * 6,
        ("0",) + (0.0,) * 6,
        (math.nan,) + (0.0,) * 6,
        (math.inf,) + (0.0,) * 6,
        (-math.inf,) + (0.0,) * 6,
    ],
    ids=[
        "empty",
        "short",
        "long",
        "null",
        "bool",
        "string",
        "nan",
        "infinity",
        "negative-infinity",
    ],
)
def test_snapshot_rejects_invalid_joint_vectors(
    plan: replay.FrozenEvidenceReplayPlan,
    invalid_joints: object,
) -> None:
    with pytest.raises(replay.ReplayDomainError):
        replace(plan.snapshots[0], joint_positions=invalid_joints)  # type: ignore[arg-type]


def test_snapshot_rejects_unknown_route_state(
    plan: replay.FrozenEvidenceReplayPlan,
) -> None:
    with pytest.raises(replay.ReplayDomainError, match="unknown frozen route state"):
        replace(plan.snapshots[0], route_state="INTERPOLATED")


def test_snapshot_rejects_malformed_component_pose(
    plan: replay.FrozenEvidenceReplayPlan,
) -> None:
    with pytest.raises(replay.ReplayDomainError):
        replace(plan.snapshots[0], component_position_m=())
    with pytest.raises(replay.ReplayDomainError):
        replace(plan.snapshots[0], component_quaternion_xyzw=(0.0, 0.0, 0.0, 0.5))


def test_plan_rejects_empty_duplicate_or_out_of_order_snapshots(
    plan: replay.FrozenEvidenceReplayPlan,
) -> None:
    with pytest.raises(replay.ReplayDomainError):
        replace(plan, snapshots=())
    duplicate = (plan.snapshots[0], *plan.snapshots[1:-1], plan.snapshots[0])
    with pytest.raises(replay.ReplayDomainError):
        replace(plan, snapshots=duplicate)
    reordered = (plan.snapshots[1], plan.snapshots[0], *plan.snapshots[2:])
    with pytest.raises(replay.ReplayDomainError):
        replace(plan, snapshots=reordered)


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"\xff",
        b"\xef\xbb\xbf{}",
        b"{not-json",
        b"null",
        b"[]",
        b'"scalar"',
        b"0",
        b"NaN",
        b"Infinity",
        b"-Infinity",
        b'{"key":1,"key":2}',
    ],
    ids=[
        "empty",
        "invalid-utf8",
        "bom",
        "malformed",
        "null-root",
        "array-root",
        "string-root",
        "numeric-root",
        "nan",
        "infinity",
        "negative-infinity",
        "duplicate-key",
    ],
)
def test_artifact_json_boundary_is_strict(payload: bytes) -> None:
    with pytest.raises(replay.ReplayArtifactFormatError):
        replay._strict_json_bytes(payload, "test.json")


def test_registered_path_rejects_traversal_and_missing_file(tmp_path: Path) -> None:
    with pytest.raises(replay.ReplayArtifactAccessError):
        replay._resolve_registered_path(tmp_path, "../outside.json")
    with pytest.raises(replay.ReplayArtifactAccessError):
        replay._resolve_registered_path(tmp_path, "missing.json")


@pytest.mark.parametrize("binding_name", ["b2", "b3_1", "b3_2", "specification"])
def test_each_missing_registered_artifact_fails_closed(
    tmp_path: Path,
    binding_name: str,
) -> None:
    bindings = load_final_demo_contract().frozen_evidence_bindings
    registered = {
        "b2": (bindings.b2.path, bindings.b2.sha256),
        "b3_1": (bindings.b3_1.path, bindings.b3_1.sha256),
        "b3_2": (bindings.b3_2.path, bindings.b3_2.sha256),
        "specification": (
            bindings.b3_2.specification_path,
            bindings.b3_2.specification_sha256,
        ),
    }
    logical_path, digest = registered[binding_name]
    with pytest.raises(replay.ReplayArtifactAccessError):
        replay._read_attested_bytes(tmp_path, logical_path, digest)


def test_tampered_artifact_copy_fails_attestation(tmp_path: Path) -> None:
    logical_path = "artifact.json"
    payload = b'{"value":"frozen"}\n'
    path = tmp_path / logical_path
    path.write_bytes(payload + b"tampered")
    with pytest.raises(replay.ReplayArtifactIntegrityError):
        replay._read_attested_bytes(
            tmp_path,
            logical_path,
            hashlib.sha256(payload).hexdigest(),
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("empty-plan", "B2 ordered plan cardinality changed"),
        ("short-joints", "must contain 7 values"),
        ("null-joint", "must be numeric"),
        ("bool-joint", "must be numeric"),
        ("string-joint", "must be numeric"),
        ("nan-joint", "must be finite"),
        ("duplicate-index", "B2 route order changed"),
        ("unknown-state", "B2 route order changed"),
        ("scene-mismatch", "B2 scene identity differs"),
    ],
)
def test_b2_structural_mutations_fail_closed(mutation: str, message: str) -> None:
    contract = load_final_demo_contract()
    payload = copy.deepcopy(_json(contract.frozen_evidence_bindings.b2.path))
    ordered_plan = payload["ordered_plan"]
    assert isinstance(ordered_plan, list)
    if mutation == "empty-plan":
        payload["ordered_plan"] = []
    elif mutation == "short-joints":
        ordered_plan[0]["joint_vector"] = [0.0] * 6
    elif mutation == "null-joint":
        ordered_plan[0]["joint_vector"][0] = None
    elif mutation == "bool-joint":
        ordered_plan[0]["joint_vector"][0] = True
    elif mutation == "string-joint":
        ordered_plan[0]["joint_vector"][0] = "0"
    elif mutation == "nan-joint":
        ordered_plan[0]["joint_vector"][0] = math.nan
    elif mutation == "duplicate-index":
        ordered_plan[1]["route_index"] = 0
    elif mutation == "unknown-state":
        ordered_plan[1]["state"] = "INTERPOLATED"
    elif mutation == "scene-mismatch":
        payload["semantic_execution_tuple"]["scene_id"] = "attacker-scene"
    with pytest.raises(replay.ReplayArtifactFormatError, match=message):
        replay._parse_b2(payload, contract.frozen_evidence_bindings.scene_identity)


def test_b2_replay_route_index_rejects_boolean_alias() -> None:
    contract = load_final_demo_contract()
    payload = copy.deepcopy(_json(contract.frozen_evidence_bindings.b2.path))
    payload["ordered_plan"][1]["replay"]["route_index"] = True

    with pytest.raises(replay.ReplayArtifactFormatError):
        replay._parse_b2(
            payload,
            contract.frozen_evidence_bindings.scene_identity,
        )


def test_b3_1_identity_mutation_fails_closed() -> None:
    contract = load_final_demo_contract()
    payload = _json(contract.frozen_evidence_bindings.b3_1.path)
    payload["schema_identifier"] = "wrong"
    with pytest.raises(replay.ReplayArtifactFormatError, match="B3.1 schema"):
        replay._parse_b3_1(payload)


@pytest.mark.parametrize(
    "mutation",
    ["pass-result", "failure-count", "empty-snapshots", "recorded-decision"],
)
def test_b3_2_mutations_cannot_rewrite_frozen_failure(mutation: str) -> None:
    contract = load_final_demo_contract()
    b2 = _json(contract.frozen_evidence_bindings.b2.path)
    vectors = replay._parse_b2(b2, contract.frozen_evidence_bindings.scene_identity)
    payload = copy.deepcopy(_json(contract.frozen_evidence_bindings.b3_2.path))
    if mutation == "pass-result":
        payload["result"]["overall_result"] = "PASS"
    elif mutation == "failure-count":
        payload["result"]["scientific_failure_count"] = 0
    elif mutation == "empty-snapshots":
        payload["authoritative_fine_route"]["semantic_snapshots"] = []
    elif mutation == "recorded-decision":
        payload["authoritative_fine_route"]["semantic_snapshots"][352][
            "observations"
        ][78]["decision"] = "PASS"
    with pytest.raises(replay.ReplayArtifactFormatError):
        replay._parse_b3_2(payload, vectors, contract)


@pytest.mark.parametrize(
    "field",
    ["semantic_snapshot_index", "route_configuration_index"],
)
def test_b3_2_snapshot_indices_reject_boolean_zero_alias(field: str) -> None:
    contract = load_final_demo_contract()
    b2 = _json(contract.frozen_evidence_bindings.b2.path)
    vectors = replay._parse_b2(
        b2,
        contract.frozen_evidence_bindings.scene_identity,
    )
    payload = copy.deepcopy(_json(contract.frozen_evidence_bindings.b3_2.path))
    payload["authoritative_fine_route"]["semantic_snapshots"][0][field] = False

    with pytest.raises(replay.ReplayArtifactFormatError):
        replay._parse_b3_2(payload, vectors, contract)


def test_b3_2_failure_summary_rejects_boolean_zero_alias() -> None:
    contract = load_final_demo_contract()
    b2 = _json(contract.frozen_evidence_bindings.b2.path)
    vectors = replay._parse_b2(
        b2,
        contract.frozen_evidence_bindings.scene_identity,
    )
    payload = copy.deepcopy(_json(contract.frozen_evidence_bindings.b3_2.path))
    payload["result"]["failure_summary"]["B3_2_FAIL_FORBIDDEN_CONTACT"] = False

    with pytest.raises(replay.ReplayArtifactFormatError):
        replay._parse_b3_2(payload, vectors, contract)


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [("physics_steps", False), ("fresh_direct_session", 1)],
)
def test_b3_2_authoritative_route_rejects_bool_int_aliases(
    field: str,
    invalid_value: object,
) -> None:
    contract = load_final_demo_contract()
    b2 = _json(contract.frozen_evidence_bindings.b2.path)
    vectors = replay._parse_b2(
        b2,
        contract.frozen_evidence_bindings.scene_identity,
    )
    payload = copy.deepcopy(_json(contract.frozen_evidence_bindings.b3_2.path))
    payload["authoritative_fine_route"][field] = invalid_value

    with pytest.raises(replay.ReplayArtifactFormatError):
        replay._parse_b3_2(payload, vectors, contract)


def test_recorded_failure_pair_index_rejects_float_alias() -> None:
    contract = load_final_demo_contract()
    b2 = _json(contract.frozen_evidence_bindings.b2.path)
    vectors = replay._parse_b2(
        b2,
        contract.frozen_evidence_bindings.scene_identity,
    )
    payload = copy.deepcopy(
        _json(contract.frozen_evidence_bindings.b3_2.path)
    )
    payload["authoritative_fine_route"]["semantic_snapshots"][352][
        "observations"
    ][78]["pair_index"] = 78.0

    with pytest.raises(replay.ReplayArtifactFormatError):
        replay._parse_b3_2(
            payload,
            vectors,
            contract,
        )


def test_runtime_attestation_matches_frozen_contract(
    plan: replay.FrozenEvidenceReplayPlan,
) -> None:
    observed = visual.attest_replay_runtime(plan)
    expected = plan.runtime_provenance
    assert observed.pybullet_package_version == expected.pybullet_package_version
    assert observed.pybullet_api_version == expected.pybullet_api_version
    assert observed.pybullet_binary_sha256 == expected.pybullet_binary_sha256
    assert observed.kuka_urdf_sha256 == expected.kuka_urdf_sha256
    assert observed.kuka_asset_manifest_sha256 == expected.kuka_asset_manifest_sha256


def test_public_session_constructor_resolves_server_registered_plan(
    monkeypatch: pytest.MonkeyPatch,
    plan: replay.FrozenEvidenceReplayPlan,
) -> None:
    calls: list[None] = []

    def registered_loader() -> replay.FrozenEvidenceReplayPlan:
        calls.append(None)
        return plan

    monkeypatch.setattr(visual, "load_registered_frozen_evidence_replay", registered_loader)
    session = visual.PyBulletEvidenceReplaySession()
    assert calls == [None]
    assert session.plan is plan
    session.close()


def test_direct_scene_loads_exact_body_and_joint_inventory(
    plan: replay.FrozenEvidenceReplayPlan,
) -> None:
    session = _session(plan)
    session.open()
    client_id = session.client_id
    try:
        assert pb.isConnected(client_id)
        assert pb.getNumBodies(physicsClientId=client_id) == 8
        assert pb.getNumJoints(session.robot_body, physicsClientId=client_id) == 7
        assert tuple(
            pb.getJointInfo(session.robot_body, index, physicsClientId=client_id)[1]
            for index in replay.CONTROLLED_JOINT_INDICES
        ) == tuple(f"lbr_iiwa_joint_{index + 1}".encode() for index in range(7))
    finally:
        session.close()
    assert not pb.isConnected(client_id)


@pytest.mark.parametrize("replay_index", [0, 4, 7, 9])
def test_snapshot_application_is_deterministic(
    plan: replay.FrozenEvidenceReplayPlan,
    replay_index: int,
) -> None:
    with _session(plan) as session:
        first = session.apply_snapshot(replay_index)
        session.apply_snapshot(0)
        second = session.apply_snapshot(replay_index)
        assert first.joint_positions == first.snapshot.joint_positions
        assert second.joint_positions == first.joint_positions
        assert second.component_position_m == first.component_position_m
        assert second.component_quaternion_xyzw == first.component_quaternion_xyzw


def test_identical_quaternion_representation_is_accepted(
    plan: replay.FrozenEvidenceReplayPlan,
) -> None:
    quaternion = plan.snapshots[4].component_quaternion_xyzw

    assert visual._quaternion_matches_rotation(quaternion, quaternion)


def test_sign_negated_equivalent_quaternion_is_accepted(
    plan: replay.FrozenEvidenceReplayPlan,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _session(plan)
    snapshot = plan.snapshots[4]
    equivalent_orientation = tuple(
        -component for component in snapshot.component_quaternion_xyzw
    )
    monkeypatch.setattr(
        visual.pb,
        "getBasePositionAndOrientation",
        lambda *_args, **_kwargs: (
            snapshot.component_position_m,
            equivalent_orientation,
        ),
    )

    with session:
        readback = session.apply_snapshot(4)

    assert readback.component_quaternion_xyzw == equivalent_orientation


def test_materially_different_quaternion_is_rejected(
    plan: replay.FrozenEvidenceReplayPlan,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _session(plan).open()
    client_id = session.client_id
    snapshot = plan.snapshots[0]
    monkeypatch.setattr(
        visual.pb,
        "getBasePositionAndOrientation",
        lambda *_args, **_kwargs: (
            snapshot.component_position_m,
            (0.0, 0.0, 1.0, 0.0),
        ),
    )

    with pytest.raises(visual.ReplaySceneError, match="orientation differs"):
        session.apply_snapshot(0)

    assert not pb.isConnected(client_id)


def test_position_mismatch_is_rejected_with_equivalent_orientation(
    plan: replay.FrozenEvidenceReplayPlan,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _session(plan).open()
    client_id = session.client_id
    snapshot = plan.snapshots[0]
    different_position = (
        snapshot.component_position_m[0] + 1.0e-12,
        snapshot.component_position_m[1],
        snapshot.component_position_m[2],
    )
    equivalent_orientation = tuple(
        -component for component in snapshot.component_quaternion_xyzw
    )
    monkeypatch.setattr(
        visual.pb,
        "getBasePositionAndOrientation",
        lambda *_args, **_kwargs: (
            different_position,
            equivalent_orientation,
        ),
    )

    with pytest.raises(visual.ReplaySceneError, match="position differs"):
        session.apply_snapshot(0)

    assert not pb.isConnected(client_id)


def test_navigation_is_bounded(plan: replay.FrozenEvidenceReplayPlan) -> None:
    with _session(plan) as session:
        assert session.next_snapshot().snapshot.replay_index == 0
        assert session.next_snapshot().snapshot.replay_index == 1
        assert session.previous_snapshot().snapshot.replay_index == 0
        with pytest.raises(replay.ReplayDomainError):
            session.previous_snapshot()
        session.apply_snapshot(9)
        with pytest.raises(replay.ReplayDomainError):
            session.next_snapshot()


def test_current_snapshot_requires_successful_application(
    plan: replay.FrozenEvidenceReplayPlan,
) -> None:
    with _session(plan) as session:
        with pytest.raises(visual.ReplaySessionStateError):
            _ = session.current_snapshot


def test_close_is_idempotent_and_use_after_close_fails(
    plan: replay.FrozenEvidenceReplayPlan,
) -> None:
    session = _session(plan).open()
    client_id = session.client_id
    session.close()
    session.close()
    assert not pb.isConnected(client_id)
    with pytest.raises(visual.ReplaySessionStateError):
        session.apply_snapshot(0)
    with pytest.raises(visual.ReplaySessionStateError):
        session.open()


def test_context_manager_disconnects_after_caller_exception(
    plan: replay.FrozenEvidenceReplayPlan,
) -> None:
    client_id: int | None = None
    with pytest.raises(RuntimeError, match="caller failure"):
        with _session(plan) as session:
            client_id = session.client_id
            raise RuntimeError("caller failure")
    assert client_id is not None
    assert not pb.isConnected(client_id)


def test_cleanup_pending_retains_client_and_close_retries(
    monkeypatch: pytest.MonkeyPatch,
    plan: replay.FrozenEvidenceReplayPlan,
) -> None:
    session = _session(plan)
    actual_disconnect = visual.pb.disconnect
    client_id: int | None = None

    def fail_disconnect(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("injected disconnect failure")

    try:
        with pytest.raises(
            visual.ReplaySessionStateError,
            match="disconnect failed",
        ) as error:
            with session:
                client_id = session.client_id
                monkeypatch.setattr(visual.pb, "disconnect", fail_disconnect)

        assert isinstance(error.value.__cause__, RuntimeError)
        assert str(error.value.__cause__) == "injected disconnect failure"
        assert client_id is not None
        assert pb.isConnected(client_id)
        assert session.lifecycle_state == "CLEANUP_PENDING"
        assert session.cleanup_pending is True
        assert session.is_open is False
        assert session._client_id == client_id

        operations = (
            lambda: session.apply_snapshot(0),
            session.next_snapshot,
            session.previous_snapshot,
            lambda: session.current_snapshot,
            session.open,
        )
        for operation in operations:
            with pytest.raises(
                visual.ReplaySessionStateError,
                match="cleanup is pending",
            ):
                operation()

        monkeypatch.setattr(visual.pb, "disconnect", actual_disconnect)
        session.close()

        assert not pb.isConnected(client_id)
        assert session.lifecycle_state == "CLOSED"
        assert session.cleanup_pending is False
        assert session._client_id is None
        session.close()
    finally:
        monkeypatch.setattr(visual.pb, "disconnect", actual_disconnect)
        if client_id is not None and pb.isConnected(client_id):
            actual_disconnect(physicsClientId=client_id)


def test_context_manager_preserves_body_and_cleanup_failures(
    monkeypatch: pytest.MonkeyPatch,
    plan: replay.FrozenEvidenceReplayPlan,
) -> None:
    session = _session(plan)
    actual_disconnect = visual.pb.disconnect
    client_id: int | None = None

    def fail_disconnect(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("injected disconnect failure")

    try:
        with pytest.raises(ExceptionGroup) as error:
            with session:
                client_id = session.client_id
                monkeypatch.setattr(visual.pb, "disconnect", fail_disconnect)
                raise ValueError("body failure")

        body_error, cleanup_error = error.value.exceptions
        assert isinstance(body_error, ValueError)
        assert str(body_error) == "body failure"
        assert isinstance(cleanup_error, visual.ReplaySessionStateError)
        assert str(cleanup_error) == "PyBullet replay disconnect failed"
        assert isinstance(cleanup_error.__cause__, RuntimeError)
        assert str(cleanup_error.__cause__) == "injected disconnect failure"
        assert client_id is not None
        assert pb.isConnected(client_id)
        assert session.cleanup_pending is True
        assert session._client_id == client_id

        monkeypatch.setattr(visual.pb, "disconnect", actual_disconnect)
        session.close()

        assert not pb.isConnected(client_id)
        assert session.lifecycle_state == "CLOSED"
    finally:
        monkeypatch.setattr(visual.pb, "disconnect", actual_disconnect)
        if client_id is not None and pb.isConnected(client_id):
            actual_disconnect(physicsClientId=client_id)


def test_application_and_cleanup_failures_retain_client_ownership(
    monkeypatch: pytest.MonkeyPatch,
    plan: replay.FrozenEvidenceReplayPlan,
) -> None:
    session = _session(plan).open()
    client_id = session.client_id
    actual_disconnect = visual.pb.disconnect

    def fail_disconnect(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("injected disconnect failure")

    try:
        monkeypatch.setattr(
            visual.pb,
            "resetJointState",
            lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("state failure")),
        )
        monkeypatch.setattr(visual.pb, "disconnect", fail_disconnect)

        with pytest.raises(visual.ReplaySceneError) as error:
            session.apply_snapshot(0)

        failures = error.value.__cause__
        assert isinstance(failures, ExceptionGroup)
        state_error, cleanup_error = failures.exceptions
        assert isinstance(state_error, RuntimeError)
        assert str(state_error) == "state failure"
        assert isinstance(cleanup_error, RuntimeError)
        assert str(cleanup_error) == "injected disconnect failure"
        assert pb.isConnected(client_id)
        assert session.cleanup_pending is True
        assert session._client_id == client_id

        monkeypatch.setattr(visual.pb, "disconnect", actual_disconnect)
        session.close()

        assert not pb.isConnected(client_id)
        assert session.lifecycle_state == "CLOSED"
    finally:
        monkeypatch.setattr(visual.pb, "disconnect", actual_disconnect)
        if pb.isConnected(client_id):
            actual_disconnect(physicsClientId=client_id)


def test_connect_failure_is_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    plan: replay.FrozenEvidenceReplayPlan,
) -> None:
    monkeypatch.setattr(visual, "attest_replay_runtime", lambda _: None)
    monkeypatch.setattr(visual.pb, "connect", lambda _: -1)
    session = _session(plan)
    with pytest.raises(visual.ReplaySceneError, match="connection failed"):
        session.open()
    assert session.is_open is False


@pytest.mark.parametrize("failure", ["urdf", "invalid-body", "topology"])
def test_scene_construction_failure_disconnects(
    monkeypatch: pytest.MonkeyPatch,
    plan: replay.FrozenEvidenceReplayPlan,
    failure: str,
) -> None:
    actual_connect = visual.pb.connect
    client_ids: list[int] = []

    def recording_connect(mode: int) -> int:
        client_id = actual_connect(mode)
        client_ids.append(client_id)
        return client_id

    monkeypatch.setattr(visual, "attest_replay_runtime", lambda _: None)
    monkeypatch.setattr(visual.pb, "connect", recording_connect)
    if failure == "urdf":
        monkeypatch.setattr(
            visual.b31,
            "load_kuka",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("urdf")),
        )
    elif failure == "invalid-body":
        monkeypatch.setattr(visual.b31, "load_kuka", lambda *_args, **_kwargs: -1)
    else:
        monkeypatch.setattr(visual.b31, "kuka_link_inventory", lambda *_args: ())
    session = _session(plan)
    with pytest.raises(visual.ReplaySceneError):
        session.open()
    assert len(client_ids) == 1
    assert not pb.isConnected(client_ids[0])
    assert session.is_open is False


def test_scene_construction_keyboard_interrupt_disconnects(
    monkeypatch: pytest.MonkeyPatch,
    plan: replay.FrozenEvidenceReplayPlan,
) -> None:
    session = _session(plan)
    actual_connect = visual.pb.connect
    actual_disconnect = visual.pb.disconnect
    client_id: int | None = None

    def recording_connect(mode: int) -> int:
        nonlocal client_id
        client_id = actual_connect(mode)
        return client_id

    def interrupt_load(*_args: object, **_kwargs: object) -> None:
        raise KeyboardInterrupt("construction interrupted")

    monkeypatch.setattr(visual, "attest_replay_runtime", lambda _: None)
    monkeypatch.setattr(visual.pb, "connect", recording_connect)
    monkeypatch.setattr(visual.b31, "load_kuka", interrupt_load)

    try:
        with pytest.raises(KeyboardInterrupt, match="construction interrupted"):
            session.open()

        assert client_id is not None
        assert not pb.isConnected(client_id)
        assert session.lifecycle_state == "CLOSED"
    finally:
        if client_id is not None and pb.isConnected(client_id):
            actual_disconnect(physicsClientId=client_id)


def test_snapshot_application_failure_disconnects(
    monkeypatch: pytest.MonkeyPatch,
    plan: replay.FrozenEvidenceReplayPlan,
) -> None:
    session = _session(plan).open()
    client_id = session.client_id
    monkeypatch.setattr(
        visual.pb,
        "resetJointState",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("reset failed")),
    )
    with pytest.raises(visual.ReplaySceneError):
        session.apply_snapshot(0)
    assert not pb.isConnected(client_id)
    assert session.is_open is False


def test_snapshot_keyboard_interrupt_disconnects(
    monkeypatch: pytest.MonkeyPatch,
    plan: replay.FrozenEvidenceReplayPlan,
) -> None:
    session = _session(plan).open()
    client_id = session.client_id
    actual_disconnect = visual.pb.disconnect

    def interrupt_reset(**_kwargs: object) -> None:
        raise KeyboardInterrupt("snapshot interrupted")

    monkeypatch.setattr(visual.pb, "resetJointState", interrupt_reset)

    try:
        with pytest.raises(KeyboardInterrupt, match="snapshot interrupted"):
            session.apply_snapshot(0)

        assert not pb.isConnected(client_id)
        assert session.lifecycle_state == "CLOSED"
    finally:
        if pb.isConnected(client_id):
            actual_disconnect(physicsClientId=client_id)


def test_disconnect_keyboard_interrupt_retains_ownership_until_retry(
    monkeypatch: pytest.MonkeyPatch,
    plan: replay.FrozenEvidenceReplayPlan,
) -> None:
    session = _session(plan).open()
    client_id = session.client_id
    actual_disconnect = visual.pb.disconnect

    def interrupt_disconnect(*_args: object, **_kwargs: object) -> None:
        raise KeyboardInterrupt("disconnect interrupted")

    try:
        monkeypatch.setattr(visual.pb, "disconnect", interrupt_disconnect)
        with pytest.raises(KeyboardInterrupt, match="disconnect interrupted"):
            session.close()

        assert session.lifecycle_state == "CLEANUP_PENDING"
        assert session.cleanup_pending is True
        assert session._client_id == client_id
        assert pb.isConnected(client_id)

        monkeypatch.setattr(visual.pb, "disconnect", actual_disconnect)
        session.close()

        assert not pb.isConnected(client_id)
        assert session.lifecycle_state == "CLOSED"
    finally:
        monkeypatch.setattr(visual.pb, "disconnect", actual_disconnect)
        if pb.isConnected(client_id):
            actual_disconnect(physicsClientId=client_id)


def test_keyboard_interrupt_and_cleanup_failure_preserve_both(
    monkeypatch: pytest.MonkeyPatch,
    plan: replay.FrozenEvidenceReplayPlan,
) -> None:
    session = _session(plan).open()
    client_id = session.client_id
    actual_disconnect = visual.pb.disconnect

    def interrupt_reset(**_kwargs: object) -> None:
        raise KeyboardInterrupt("snapshot interrupted")

    def fail_disconnect(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("injected disconnect failure")

    try:
        monkeypatch.setattr(visual.pb, "resetJointState", interrupt_reset)
        monkeypatch.setattr(visual.pb, "disconnect", fail_disconnect)

        with pytest.raises(BaseExceptionGroup) as error:
            session.apply_snapshot(0)

        original, cleanup = error.value.exceptions
        assert isinstance(original, KeyboardInterrupt)
        assert str(original) == "snapshot interrupted"
        assert isinstance(cleanup, RuntimeError)
        assert str(cleanup) == "injected disconnect failure"
        assert session.lifecycle_state == "CLEANUP_PENDING"
        assert session.cleanup_pending is True
        assert session._client_id == client_id
        assert pb.isConnected(client_id)

        monkeypatch.setattr(visual.pb, "disconnect", actual_disconnect)
        session.close()

        assert not pb.isConnected(client_id)
        assert session.lifecycle_state == "CLOSED"
    finally:
        monkeypatch.setattr(visual.pb, "disconnect", actual_disconnect)
        if pb.isConnected(client_id):
            actual_disconnect(physicsClientId=client_id)


def test_nonfinite_readback_disconnects(
    monkeypatch: pytest.MonkeyPatch,
    plan: replay.FrozenEvidenceReplayPlan,
) -> None:
    session = _session(plan).open()
    client_id = session.client_id
    monkeypatch.setattr(
        visual.pb,
        "getJointState",
        lambda *_args, **_kwargs: (math.nan, 0.0, (0.0,) * 6, 0.0),
    )
    with pytest.raises(visual.ReplaySceneError, match="non-finite"):
        session.apply_snapshot(0)
    assert not pb.isConnected(client_id)


def test_replay_path_never_calls_scientific_generating_operations(
    monkeypatch: pytest.MonkeyPatch,
    plan: replay.FrozenEvidenceReplayPlan,
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("scientific-generating operation called from replay")

    for name in (
        "calculateInverseKinematics",
        "stepSimulation",
        "getClosestPoints",
        "getContactPoints",
    ):
        monkeypatch.setattr(visual.pb, name, forbidden)
    with _session(plan) as session:
        session.apply_snapshot(0)
        session.apply_snapshot(7)
        session.apply_snapshot(9)


def test_session_rejects_null_plan_and_invalid_modes(
    plan: replay.FrozenEvidenceReplayPlan,
) -> None:
    with pytest.raises(TypeError):
        visual.PyBulletEvidenceReplaySession._from_attested_plan(  # type: ignore[arg-type]
            None
        )
    for mode in (None, True, -1, 999):
        with pytest.raises(ValueError):
            _session(plan, connection_mode=mode)  # type: ignore[arg-type]
