from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from src.prototype5.final_demo_contract import load_final_demo_contract
from src.prototype5.final_demo_presentation import (
    FinalDemoManifest,
    FinalDemoPresentationRegistry,
    FinalDemoScenarioInferenceForbiddenError,
    FinalDemoScenarioNotFoundError,
    load_final_demo_presentation,
)


def test_manifest_is_exact_bounded_d0_projection() -> None:
    registry = load_final_demo_presentation()
    manifest = registry.manifest

    assert manifest.contract_id == "PROTOTYPE5_FINAL_DEMONSTRATOR_D0"
    assert manifest.contract_version == "1.0.0"
    assert manifest.authority_taxonomy == (
        "UNTRUSTED_PROPOSAL",
        "GOVERNANCE_DECISION",
        "EXECUTION_ELIGIBILITY",
        "QUALIFICATION_REPLAY_ACCESS",
        "DOWNSTREAM_GEOMETRIC_QUALIFICATION",
        "PHYSICAL_EXECUTION_AUTHORITY_NOT_IMPLEMENTED",
    )
    assert manifest.physical_execution_authority_state == "NOT_IMPLEMENTED"
    assert manifest.healthcare_scope == "OUT_OF_SCOPE_FOR_FINAL_DEMO"
    assert manifest.d2_replay_enabled is False
    assert len(manifest.scenarios) == 10
    assert len({scenario.scenario_id for scenario in manifest.scenarios}) == 10


def test_manifest_exposes_exactly_one_registered_replay_reference() -> None:
    manifest = load_final_demo_presentation().manifest
    replay = [
        scenario
        for scenario in manifest.scenarios
        if scenario.replay_capability_classification
        == "FROZEN_B2_REPLAY_COMPATIBLE"
    ]
    assert [scenario.scenario_id for scenario in replay] == [
        "FROZEN_B2_PICK_PLACE_EVIDENCE_REPLAY"
    ]
    assert replay[0].qualification_replay_access == "SERVER_REGISTERED_ONLY"
    assert replay[0].downstream_geometric_qualification == "FAIL"
    assert replay[0].model_input_enabled is False


def test_manifest_serialisation_contains_no_forbidden_runtime_identity() -> None:
    rendered = json.dumps(
        load_final_demo_presentation().manifest.model_dump(mode="json"),
        sort_keys=True,
    ).lower()
    for forbidden in (
        "artifact_path",
        "artifact_sha",
        "sha256",
        "joint_vector",
        "joint_positions",
        "scene_geometry",
        "urdf",
        "collision_tolerance",
        "physics_client",
        "permit_id",
        "signature",
    ):
        assert forbidden not in rendered


@pytest.mark.parametrize(
    ("scenario_id", "role", "obstruction", "interlock"),
    [
        ("MANUFACTURING_TYPED_ACCEPT", "operator", False, True),
        ("MANUFACTURING_UNSAFE_REJECT", "operator", True, True),
        ("MANUFACTURING_AMBIGUOUS_CLARIFY", "operator", False, True),
        ("MANUFACTURING_SCHEMA_VALID_INELIGIBLE", "operator", False, True),
        ("MANUFACTURING_OBSERVER_ROLE_REJECT", "observer", False, True),
    ],
)
def test_live_scenario_context_is_resolved_from_d0(
    scenario_id: str,
    role: str,
    obstruction: bool,
    interlock: bool,
) -> None:
    resolved = load_final_demo_presentation().resolve_live_scenario(scenario_id)
    assert resolved.scenario_id == scenario_id
    assert resolved.domain_id == "MANUFACTURING"
    assert resolved.scene_id == "manufacturing_demo_scene"
    assert resolved.scene_state_version == "1.0.0"
    assert resolved.requester_persona_id == f"SYNTHETIC_{role.upper()}"
    assert resolved.requester_role == role
    assert resolved.human_obstruction is obstruction
    assert resolved.safety_interlock_enabled is interlock


@pytest.mark.parametrize(
    "scenario_id",
    [
        "MODE_E_CONVEYOR_GOVERNANCE",
        "MODE_E_WAREHOUSE_GOVERNANCE",
        "MODE_E_HUMAN_PROXIMITY_GOVERNANCE",
        "MODE_E_RESTRICTED_ZONE_GOVERNANCE",
        "FROZEN_B2_PICK_PLACE_EVIDENCE_REPLAY",
    ],
)
def test_evidence_only_scenarios_cannot_resolve_for_live_inference(
    scenario_id: str,
) -> None:
    with pytest.raises(
        FinalDemoScenarioInferenceForbiddenError,
        match="SCENARIO_LIVE_INFERENCE_FORBIDDEN",
    ):
        load_final_demo_presentation().resolve_live_scenario(scenario_id)


@pytest.mark.parametrize("scenario_id", [None, "", " ", "UNKNOWN_SCENARIO"])
def test_unknown_or_invalid_scenario_fails_closed(scenario_id: object) -> None:
    with pytest.raises(FinalDemoScenarioNotFoundError, match="SCENARIO_NOT_FOUND"):
        load_final_demo_presentation().resolve_live_scenario(scenario_id)  # type: ignore[arg-type]


def test_manifest_model_rejects_mutation_and_unknown_fields() -> None:
    manifest = load_final_demo_presentation().manifest
    with pytest.raises(ValidationError):
        FinalDemoManifest.model_validate(
            {**manifest.model_dump(), "unexpected": "forbidden"}
        )
    with pytest.raises(ValidationError):
        FinalDemoManifest.model_validate(
            {**manifest.model_dump(), "d2_replay_enabled": True}
        )
    with pytest.raises(ValidationError):
        FinalDemoManifest.model_validate(
            {**manifest.model_dump(), "physical_execution_authority_state": "READY"}
        )
    with pytest.raises(ValidationError):
        manifest.d2_replay_enabled = True  # type: ignore[misc]


def test_registry_detaches_from_mutable_d0_collections() -> None:
    contract = load_final_demo_contract()
    registry = FinalDemoPresentationRegistry.from_contract(contract)
    manifest_before = registry.manifest
    resolved_before = registry.resolve_live_scenario("MANUFACTURING_TYPED_ACCEPT")

    scenarios = contract.scenario_contract.scenarios
    live = scenarios[0]
    replay = scenarios[-1]
    live.allowed_inference_modes.clear()
    live.client_overridable_context_fields.append("requester_role")
    replay.replay_capability.allowed_replay_controls.clear()
    scenarios.clear()

    assert registry.manifest == manifest_before
    assert registry.resolve_live_scenario("MANUFACTURING_TYPED_ACCEPT") == resolved_before
    assert registry.manifest.scenarios[0].allowed_inference_modes == (
        "LOCAL",
        "CLOUD",
        "AUTO",
    )
    assert len(registry.manifest.scenarios) == 10
