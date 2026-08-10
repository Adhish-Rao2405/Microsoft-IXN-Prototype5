from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.prototype5.final_demo_contract import (
    AUTHORITY_STATE_ORDER,
    EXPECTED_B3_2_FAILURE_CODES,
    REPLAY_CONTROL_ORDER,
    FinalDemoContract,
    FinalDemoContractIOError,
    FinalDemoContractJSONError,
    FinalDemoContractValidationError,
    load_final_demo_contract,
    validate_final_demo_contract,
)
from src.prototype5.governance_contract_v2 import FallbackReason


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs" / "prototype5" / "final_demo_scenarios_v1.json"
DOCUMENT = ROOT / "docs" / "prototype5" / "final_demonstrator_contract.md"
MODE_E = ROOT / "configs" / "prototype5" / "mode_e_industrial_benchmark.json"



def canonical_payload() -> dict[str, object]:
    payload = json.loads(CONFIG.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AssertionError("checked-in final-demo contract root must be an object")
    return payload


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sidecar_digest(path: Path) -> str:
    return path.read_text(encoding="utf-8").split()[0]


def test_contract_parses_under_strict_typed_schema() -> None:
    contract = load_final_demo_contract()

    assert isinstance(contract, FinalDemoContract)
    assert contract.qualified_integration_baseline.commit == (
        "c20a184bc40b5dfa7f4c4f1c7937b89e3d06c3df"
    )
    assert len(contract.scenario_contract.scenarios) == 10
    assert contract.scenario_contract.scenarios[0].display_name == (
        "Clear manufacturing typed request"
    )


@pytest.mark.parametrize(
    "invalid_root",
    [None, {}, [], "", 0],
    ids=["null", "empty-object", "array", "string", "numeric"],
)
def test_explicit_invalid_root_payloads_fail_closed(invalid_root: object) -> None:
    with pytest.raises(FinalDemoContractValidationError) as caught:
        validate_final_demo_contract(invalid_root)

    assert isinstance(caught.value.__cause__, ValidationError)


def test_loader_accepts_canonical_explicit_path_without_caching(
    tmp_path: Path,
) -> None:
    contract_path = tmp_path / "final_demo_contract.json"
    contract_path.write_bytes(CONFIG.read_bytes())

    first = load_final_demo_contract(contract_path)
    second = load_final_demo_contract(contract_path)

    assert first == load_final_demo_contract()
    assert second == first
    assert second is not first


def test_loader_rejects_non_path_argument() -> None:
    with pytest.raises(TypeError, match="path must be pathlib.Path"):
        load_final_demo_contract("final_demo_contract.json")  # type: ignore[arg-type]


def test_loader_distinguishes_missing_file_and_directory(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"

    with pytest.raises(FinalDemoContractIOError) as missing_error:
        load_final_demo_contract(missing)
    assert isinstance(missing_error.value.__cause__, FileNotFoundError)

    with pytest.raises(FinalDemoContractIOError) as directory_error:
        load_final_demo_contract(tmp_path)
    assert isinstance(
        directory_error.value.__cause__,
        (IsADirectoryError, PermissionError),
    )


def test_loader_rejects_invalid_utf8(tmp_path: Path) -> None:
    contract_path = tmp_path / "invalid-utf8.json"
    contract_path.write_bytes(b"\xff")

    with pytest.raises(FinalDemoContractIOError) as caught:
        load_final_demo_contract(contract_path)

    assert isinstance(caught.value.__cause__, UnicodeDecodeError)


@pytest.mark.parametrize(
    ("payload", "has_json_cause"),
    [
        (b"", False),
        (b" \n\t", False),
        (b"{not-json", True),
        (b"\xef\xbb\xbf" + CONFIG.read_bytes(), True),
    ],
    ids=["empty", "whitespace", "malformed", "utf8-bom"],
)
def test_loader_rejects_empty_or_noncanonical_json_text(
    tmp_path: Path,
    payload: bytes,
    has_json_cause: bool,
) -> None:
    contract_path = tmp_path / "invalid-json.json"
    contract_path.write_bytes(payload)

    with pytest.raises(FinalDemoContractJSONError) as caught:
        load_final_demo_contract(contract_path)

    assert isinstance(caught.value.__cause__, json.JSONDecodeError) is has_json_cause


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_loader_rejects_nonstandard_json_numeric_constants(
    tmp_path: Path,
    constant: str,
) -> None:
    contract_path = tmp_path / "nonstandard-constant.json"
    contract_path.write_text(constant, encoding="utf-8", newline="\n")

    with pytest.raises(FinalDemoContractJSONError) as caught:
        load_final_demo_contract(contract_path)

    assert type(caught.value.__cause__).__name__ == "_NonCanonicalJSONError"
    assert not isinstance(caught.value.__cause__, ValidationError)
    assert constant in str(caught.value.__cause__)


def test_loader_rejects_duplicate_json_object_keys(tmp_path: Path) -> None:
    contract_path = tmp_path / "duplicate-key.json"
    contract_path.write_text(
        '{"contract_id":"A","contract_id":"B"}',
        encoding="utf-8",
        newline="\n",
    )

    with pytest.raises(FinalDemoContractJSONError) as caught:
        load_final_demo_contract(contract_path)

    assert type(caught.value.__cause__).__name__ == "_NonCanonicalJSONError"
    assert not isinstance(caught.value.__cause__, ValidationError)
    assert "duplicate JSON object key" in str(caught.value.__cause__)


@pytest.mark.parametrize(
    "payload",
    ["null", "{}", "[]", '""', "0"],
    ids=["null", "empty-object", "array", "string", "numeric"],
)
def test_loader_rejects_invalid_json_roots(tmp_path: Path, payload: str) -> None:
    contract_path = tmp_path / "invalid-root.json"
    contract_path.write_text(payload, encoding="utf-8", newline="\n")

    with pytest.raises(FinalDemoContractValidationError) as caught:
        load_final_demo_contract(contract_path)

    assert isinstance(caught.value.__cause__, ValidationError)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload["scenario_contract"]["scenarios"][0][
            "replay_capability"
        ].__setitem__("classification", "UNSUPPORTED"),
        lambda payload: payload.__setitem__("contract_id", None),
        lambda payload: payload["scenario_contract"].__setitem__("scenarios", []),
        lambda payload: payload["scenario_contract"]["scenarios"][0].__setitem__(
            "scenario_id", ""
        ),
        lambda payload: payload["scenario_contract"]["scenarios"][0].__setitem__(
            "scenario_id", "   "
        ),
        lambda payload: payload["frozen_evidence_bindings"]["b2"].__setitem__(
            "sha256", "not-a-sha"
        ),
        lambda payload: payload["scenario_contract"]["scenarios"].append(
            copy.deepcopy(payload["scenario_contract"]["scenarios"][0])
        ),
        lambda payload: payload["scenario_contract"]["scenarios"].append(None),
        lambda payload: payload["scenario_contract"]["scenarios"][0].clear(),
        lambda payload: payload["scenario_contract"]["scenarios"][0].__setitem__(
            "scenario_id", None
        ),
        lambda payload: payload["scenario_contract"]["scenarios"][0].__setitem__(
            "presentation_classification", None
        ),
        lambda payload: payload["scenario_contract"]["scenarios"][0].__setitem__(
            "replay_capability", None
        ),
        lambda payload: payload["scenario_contract"]["scenarios"][0].__setitem__(
            "replay_capability", {}
        ),
        lambda payload: payload["scenario_contract"]["scenarios"][0][
            "replay_capability"
        ].__setitem__("classification", None),
        lambda payload: payload["scenario_contract"]["scenarios"][0].__setitem__(
            "authoritative_context", None
        ),
        lambda payload: payload["scenario_contract"]["scenarios"][0].__setitem__(
            "authoritative_context", {}
        ),
        lambda payload: payload["scenario_contract"]["scenarios"][0].__setitem__(
            "unexpected_nested_field", "REJECT_ME"
        ),
        lambda payload: payload["scenario_contract"]["scenarios"][0].pop(
            "authoritative_context"
        ),
        lambda payload: payload["frozen_evidence_bindings"].__setitem__("b2", None),
        lambda payload: payload["frozen_evidence_bindings"].__setitem__("b2", {}),
        lambda payload: payload["frozen_evidence_bindings"]["b2"].__setitem__(
            "path", ""
        ),
        lambda payload: payload["frozen_evidence_bindings"]["b2"].__setitem__(
            "sha256", None
        ),
        lambda payload: payload["frozen_evidence_bindings"]["b3_2"].__setitem__(
            "expected_failure_codes_present", []
        ),
        lambda payload: payload["frozen_evidence_bindings"]["b3_2"].pop(
            "expected_failure_codes_present"
        ),
    ],
)
def test_invalid_contract_mutations_fail_closed(mutation) -> None:
    payload = canonical_payload()
    mutation(payload)

    with pytest.raises(FinalDemoContractValidationError):
        validate_final_demo_contract(payload)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload["authority_taxonomy"]["ordered_states"].pop(),
        lambda payload: payload["authority_taxonomy"]["ordered_states"].append(
            "EXECUTION_AUTHORITY"
        ),
        lambda payload: payload["authority_taxonomy"]["ordered_states"].append(
            payload["authority_taxonomy"]["ordered_states"][-1]
        ),
        lambda payload: payload["authority_taxonomy"]["ordered_states"].reverse(),
        lambda payload: payload["authority_taxonomy"]["ordered_states"].__setitem__(
            -1, "EXECUTION_AUTHORITY"
        ),
        lambda payload: payload["authority_taxonomy"]["governance_decision"][
            "states"
        ].pop(),
        lambda payload: payload["authority_taxonomy"][
            "qualification_replay_access"
        ]["states"].reverse(),
        lambda payload: payload["authority_taxonomy"][
            "downstream_geometric_qualification"
        ]["states"].append("SAFE"),
    ],
)
def test_authority_taxonomy_mutations_fail_closed(mutation) -> None:
    payload = canonical_payload()
    mutation(payload)

    with pytest.raises(FinalDemoContractValidationError):
        validate_final_demo_contract(payload)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload.pop("provenance_policy"),
        lambda payload: payload["provenance_policy"].__setitem__(
            "invariant", "LIVE_MODEL_PROPOSAL == FROZEN_B2_PLAN"
        ),
        lambda payload: payload["provenance_policy"].__setitem__(
            "live_model_proposal_is_frozen_b2_provenance_source", True
        ),
        lambda payload: payload["provenance_policy"].__setitem__(
            "live_model_proposal_is_b3_1_b3_2_provenance_source", True
        ),
        lambda payload: payload["provenance_policy"].__setitem__(
            "sequential_presentation_relationship", "DERIVATIONAL"
        ),
        lambda payload: payload["provenance_policy"].__setitem__(
            "dedicated_replay_artifact_source", "CURRENT_MODEL_OUTPUT"
        ),
    ],
)
def test_live_frozen_provenance_mutations_fail_closed(mutation) -> None:
    payload = canonical_payload()
    mutation(payload)

    with pytest.raises(FinalDemoContractValidationError):
        validate_final_demo_contract(payload)


def frozen_replay_payload(payload: dict[str, object]) -> dict[str, object]:
    scenarios = payload["scenario_contract"]["scenarios"]
    return next(
        scenario
        for scenario in scenarios
        if scenario["scenario_id"] == "FROZEN_B2_PICK_PLACE_EVIDENCE_REPLAY"
    )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: frozen_replay_payload(payload).__setitem__(
            "presentation_classification", "SYNTHETIC_LIVE_DEMO"
        ),
        lambda payload: frozen_replay_payload(payload).__setitem__(
            "expected_high_level_outcome", "ACCEPT"
        ),
        lambda payload: frozen_replay_payload(payload).__setitem__(
            "expected_demonstration_purpose", "Perform fresh robot execution."
        ),
        lambda payload: frozen_replay_payload(payload).__setitem__(
            "outcome_basis", "Generated by the current live model proposal."
        ),
        lambda payload: payload["replay_claim_boundary"].__setitem__(
            "replay_is_fresh_execution", True
        ),
        lambda payload: payload["replay_claim_boundary"].__setitem__(
            "generated_by_current_model_output", True
        ),
        lambda payload: payload["state_transition_policy"].__setitem__(
            "governance_accept_automatically_grants_replay_access", True
        ),
        lambda payload: payload["state_transition_policy"].__setitem__(
            "governance_accept_requires_all_evaluated_gates", False
        ),
        lambda payload: payload["state_transition_policy"].__setitem__(
            "qualification_replay_access_establishes_geometric_pass", True
        ),
        lambda payload: payload["state_transition_policy"].__setitem__(
            "qualification_replay_access_establishes_physical_execution_authority",
            True,
        ),
        lambda payload: payload["state_transition_policy"].__setitem__(
            "geometric_pass_establishes_physical_safety", True
        ),
        lambda payload: payload["state_transition_policy"].__setitem__(
            "geometric_fail_rewrites_governance_result", True
        ),
        lambda payload: payload["state_transition_policy"].__setitem__(
            "physical_execution_authority_terminal_state", "IMPLEMENTED"
        ),
        lambda payload: frozen_replay_payload(payload)["authoritative_context"].__setitem__(
            "binding_id", "ARBITRARY_BINDING"
        ),
        lambda payload: frozen_replay_payload(payload).__setitem__(
            "scenario_id", "UNREGISTERED_REPLAY_OPERATION"
        ),
        lambda payload: frozen_replay_payload(payload)["replay_capability"].__setitem__(
            "classification", "GOVERNANCE_ONLY"
        ),
        lambda payload: payload["scenario_contract"]["scenarios"][0][
            "replay_capability"
        ].update(
            {
                "classification": "FROZEN_B2_REPLAY_COMPATIBLE",
                "qualification_replay_access": "SERVER_REGISTERED_ONLY",
                "pybullet_controls_may_be_exposed": True,
                "allowed_replay_controls": list(REPLAY_CONTROL_ORDER),
            }
        ),
        lambda payload: payload["scenario_contract"]["scenarios"][5][
            "replay_capability"
        ].update(
            {
                "classification": "FROZEN_B2_REPLAY_COMPATIBLE",
                "qualification_replay_access": "SERVER_REGISTERED_ONLY",
                "pybullet_controls_may_be_exposed": True,
                "allowed_replay_controls": list(REPLAY_CONTROL_ORDER),
            }
        ),
        lambda payload: payload["frozen_evidence_bindings"]["b2"].__setitem__(
            "sha256", "0" * 64
        ),
    ],
)
def test_replay_cross_field_mutations_fail_closed(mutation) -> None:
    payload = canonical_payload()
    mutation(payload)

    with pytest.raises(FinalDemoContractValidationError):
        validate_final_demo_contract(payload)


def test_browser_cannot_own_authoritative_safety_or_replay_fields() -> None:
    contract = load_final_demo_contract()
    boundary = contract.client_input_boundary
    forbidden = {
        "requester_role",
        "human_obstruction",
        "safety_interlock_state",
        "safety_interlock_enabled",
        "scene_geometry",
        "joint_states",
        "waypoints",
        "trajectory_coordinates",
        "urdf_paths",
        "collision_exclusions",
        "collision_tolerance",
        "b2_artifact_identity",
        "b3_2_artifact_identity",
        "permit_binding_fields",
    }

    assert set(boundary.forbidden_authoritative_fields) == forbidden
    assert forbidden.isdisjoint(boundary.allowed_fields)
    assert boundary.authoritative_context_owner == "SERVER"
    assert all(
        not scenario.client_overridable_context_fields
        for scenario in contract.scenario_contract.scenarios
    )


def test_exactly_one_registered_operation_is_replay_compatible() -> None:
    scenarios = load_final_demo_contract().scenario_contract.scenarios
    replay = [
        scenario
        for scenario in scenarios
        if scenario.replay_capability.classification
        == "FROZEN_B2_REPLAY_COMPATIBLE"
    ]

    assert [scenario.scenario_id for scenario in replay] == [
        "FROZEN_B2_PICK_PLACE_EVIDENCE_REPLAY"
    ]
    assert replay[0].authoritative_context.context_kind == (
        "FROZEN_B2_B3_2_BINDING"
    )
    assert replay[0].model_input_enabled is False


def test_mode_e_breadth_is_governance_only_and_source_bound() -> None:
    contract = load_final_demo_contract()
    scenarios = contract.scenario_contract.scenarios
    mode_e_scenarios = [
        scenario
        for scenario in scenarios
        if scenario.authoritative_context.context_kind == "FROZEN_MODE_E_EVIDENCE"
    ]
    benchmark = json.loads(MODE_E.read_text(encoding="utf-8"))
    cases = {case["id"]: case for case in benchmark["cases"]}

    assert {scenario.authoritative_context.benchmark_case_id for scenario in mode_e_scenarios} == {
        "E006",
        "E016",
        "E024",
        "E029",
    }
    for scenario in mode_e_scenarios:
        case_id = scenario.authoritative_context.benchmark_case_id
        assert scenario.command == cases[case_id]["command"]
        assert scenario.replay_capability.classification == "GOVERNANCE_ONLY"
        assert scenario.replay_capability.qualification_replay_access == "PROHIBITED"

    e001 = next(
        scenario
        for scenario in scenarios
        if scenario.source_reference.endswith("#E001")
    )
    assert e001.replay_capability.classification == "GOVERNANCE_ONLY"


def test_frozen_artifact_bytes_and_sidecars_match_registry() -> None:
    bindings = load_final_demo_contract().frozen_evidence_bindings

    for binding in (bindings.b2, bindings.b3_1, bindings.b3_2):
        artifact = ROOT / binding.path
        sidecar = ROOT / binding.digest_sidecar_path
        assert artifact.is_file()
        assert sidecar.is_file()
        assert sha256(artifact) == binding.sha256
        assert sidecar_digest(sidecar) == binding.sha256

    specification = ROOT / bindings.b3_2.specification_path
    assert specification.is_file()
    assert sha256(specification) == bindings.b3_2.specification_sha256


def test_frozen_b2_scene_and_b3_2_failure_are_not_reinterpreted() -> None:
    bindings = load_final_demo_contract().frozen_evidence_bindings
    b2 = json.loads((ROOT / bindings.b2.path).read_text(encoding="utf-8"))
    b32 = json.loads((ROOT / bindings.b3_2.path).read_text(encoding="utf-8"))

    assert b2["semantic_execution_tuple"] == bindings.scene_identity.model_dump()
    assert b32["result"]["overall_result"] == (
        bindings.b3_2.expected_terminal_status
    )
    assert b32["result"]["scientific_failure_count"] == 118
    actual_failure_codes = b32["result"]["failure_codes_present"]
    assert actual_failure_codes == list(EXPECTED_B3_2_FAILURE_CODES)
    assert bindings.b3_2.expected_failure_codes_present == actual_failure_codes

    provenance = b32["provenance"]["pybullet"]
    assert provenance["package_version"] == bindings.runtime_provenance.pybullet_package_version
    assert provenance["api_version"] == bindings.runtime_provenance.pybullet_api_version
    assert provenance["binary_sha256"] == bindings.runtime_provenance.pybullet_binary_sha256
    assert provenance["urdf_identity"] == bindings.runtime_provenance.kuka_urdf_identity
    assert provenance["urdf_sha256"] == bindings.runtime_provenance.kuka_urdf_sha256
    assert provenance["kuka_asset_manifest_sha256"] == (
        bindings.runtime_provenance.kuka_asset_manifest_sha256
    )
    assert b32["provenance"]["qualified_ci_wheel"]["sha256"] == (
        bindings.runtime_provenance.qualified_windows_wheel_sha256
    )
    assert b32["provenance"]["specification"] == {
        "freeze_commit": bindings.b3_2.specification_freeze_commit,
        "git_blob": bindings.b3_2.specification_git_blob,
        "identity": (
            "repository/"
            + bindings.b3_2.specification_path
        ),
        "sha256": bindings.b3_2.specification_sha256,
    }

    reference = bindings.recorded_failure_reference
    snapshot = b32["authoritative_fine_route"]["semantic_snapshots"][
        reference.semantic_snapshot_index
    ]
    observation = snapshot["observations"][reference.pair_index]
    pair = b32["collision_pair_inventory"]["pairs"][reference.pair_index]

    assert {
        "semantic_snapshot_index": snapshot["semantic_snapshot_index"],
        "route_state": snapshot["route_state"],
        "phase": snapshot["phase"],
        "boundary_snapshot": snapshot["boundary_snapshot"],
    } == {
        "semantic_snapshot_index": reference.semantic_snapshot_index,
        "route_state": reference.route_state,
        "phase": reference.phase,
        "boundary_snapshot": reference.boundary_snapshot,
    }
    assert observation == {
        "classification": reference.classification,
        "decision": reference.decision,
        "found": True,
        "pair_id": reference.pair_id,
        "pair_index": reference.pair_index,
        "permission": reference.permission,
        "separation_lower_bound_m": None,
        "signed_distance_m": reference.signed_distance_m,
    }
    assert pair["pair_id"] == reference.pair_id
    assert pair["query_signature"]["bodyA"] == reference.query_body_a
    assert pair["query_signature"]["bodyB"] == reference.query_body_b


def test_claim_vocabulary_and_layer_invariant_are_exact() -> None:
    contract = load_final_demo_contract()
    document = DOCUMENT.read_text(encoding="utf-8")
    required = {
        "UNTRUSTED PROPOSAL",
        "EXECUTION ELIGIBILITY",
        "QUALIFICATION_REPLAY_ACCESS",
        "EVIDENCE REPLAY",
        "NOT PHYSICAL EXECUTION",
        "PHYSICAL EXECUTION AUTHORITY: NOT_IMPLEMENTED",
        "LIVE DEMO TRACE — NOT FROZEN RESEARCH EVIDENCE",
        "PASSING LAYER N DOES NOT ESTABLISH LAYER N+1.",
        "LIVE_MODEL_PROPOSAL != FROZEN_B2_PLAN",
    }

    assert contract.authority_taxonomy.physical_execution_authority.state == (
        "NOT_IMPLEMENTED"
    )
    assert set(contract.replay_claim_boundary.required_labels) == {
        "EVIDENCE REPLAY",
        "NOT PHYSICAL EXECUTION",
    }
    assert contract.authority_taxonomy.ordered_states == list(AUTHORITY_STATE_ORDER)
    assert contract.provenance_policy.model_dump() == {
        "invariant": "LIVE_MODEL_PROPOSAL != FROZEN_B2_PLAN",
        "live_inference_output_state": "UNTRUSTED_PROPOSAL",
        "live_governance_may_contextualise_frozen_evidence": True,
        "live_model_proposal_is_frozen_b2_provenance_source": False,
        "live_model_proposal_is_b3_1_b3_2_provenance_source": False,
        "sequential_presentation_relationship": "CONTEXTUAL_ONLY_NOT_DERIVATIONAL",
        "frozen_evidence_provenance": "INDEPENDENT_HISTORICAL_PROVENANCE",
        "dedicated_replay_artifact_source": "EXACT_BOUND_FROZEN_ARTIFACTS_ONLY",
    }
    assert contract.state_transition_policy.model_dump() == {
        "governance_accept_requires_all_evaluated_gates": True,
        "governance_accept_automatically_grants_replay_access": False,
        "qualification_replay_access_establishes_geometric_pass": False,
        "qualification_replay_access_establishes_physical_execution_authority": False,
        "geometric_pass_establishes_physical_safety": False,
        "geometric_fail_rewrites_governance_result": False,
        "physical_execution_authority_terminal_state": "NOT_IMPLEMENTED",
    }
    assert contract.replay_claim_boundary.replay_is_fresh_execution is False
    assert (
        contract.replay_claim_boundary.generated_by_current_model_output is False
    )
    assert all(term in document for term in required)


def test_rejection_invariants_forbid_all_replay_progression() -> None:
    invariants = load_final_demo_contract().rejection_invariants

    assert set(invariants.governance_reject_or_clarify) >= {
        "EXECUTION_ELIGIBILITY_FALSE",
        "NO_QUALIFICATION_REPLAY_CAPABILITY",
        "NO_REPLAY_SESSION_ADVANCE",
        "NO_B2_ROUTE_INITIATION",
        "NO_PYBULLET_REPLAY_START",
        "NO_POLICY_REJECTION_PROVIDER_SHOPPING",
        "PHYSICAL_EXECUTION_AUTHORITY_NOT_IMPLEMENTED",
    }
    assert set(invariants.governance_only_scenario) == {
        "NO_QUALIFICATION_REPLAY_CAPABILITY_REGARDLESS_OF_ACCEPT",
        "NO_PYBULLET_REPLAY_OPERATION",
    }
    assert "NO_FINAL_EXECUTION_APPROVAL_CLAIM" in invariants.b3_2_fail


def test_auto_fallback_matches_existing_structural_routing_contract() -> None:
    contract = load_final_demo_contract().auto_provider_contract
    existing_reasons = {reason.value for reason in FallbackReason if reason is not FallbackReason.NONE}

    assert set(contract.fallback_allowed_for) == existing_reasons
    assert set(contract.fallback_prohibited_for) == {
        "SEMANTIC_POLICY_REJECTION",
        "AMBIGUITY",
        "SAFETY_REJECTION",
        "ROLE_ACTION_POLICY_REJECTION",
        "DOWNSTREAM_GEOMETRIC_QUALIFICATION_FAIL",
    }
    assert contract.provider_shopping_after_governance_rejection is False


def test_voice_trace_fallback_and_healthcare_scope_are_bounded() -> None:
    contract = load_final_demo_contract()

    assert contract.voice_contract.chain == [
        "WAV",
        "STT",
        "RAW_TRANSCRIPT",
        "OPERATOR_REVIEW",
        "READY_TRANSCRIPT",
        "SAME_CANONICAL_GOVERNANCE_RUNNER",
    ]
    assert contract.voice_contract.direct_voice_to_robot_path is False
    assert contract.trace_categories.frozen_research_evidence.mutable is False
    assert contract.trace_categories.live_demo_trace.label == (
        "LIVE DEMO TRACE — NOT FROZEN RESEARCH EVIDENCE"
    )
    assert contract.trace_categories.live_demo_trace.required_fields == [
        "trace_id",
        "selected_provider",
        "resolved_model",
        "timestamp",
    ]
    assert contract.deterministic_fallback_contract.presentation_source_states == [
        "LIVE",
        "RECORDED_FALLBACK",
        "FROZEN_RESEARCH_EVIDENCE",
    ]
    assert contract.healthcare_scope.state == "OUT_OF_SCOPE_FOR_FINAL_DEMO"


def test_null_empty_and_boundary_rules_are_complete_and_fail_closed() -> None:
    rules = {
        rule.input: rule for rule in load_final_demo_contract().input_validation_contract
    }

    assert set(rules) == {
        "command",
        "scenario_id",
        "inference_mode",
        "reviewed_transcript",
        "wav_audio",
        "model_proposal",
        "routing_record",
        "governance_gate_record",
        "replay_operation",
    }
    assert set(rules["command"].invalid_conditions) == {
        "NULL",
        "EMPTY",
        "WHITESPACE_ONLY",
    }
    assert set(rules["scenario_id"].invalid_conditions) >= {
        "NULL",
        "EMPTY",
        "WHITESPACE_ONLY",
        "ABSENT",
        "UNSUPPORTED",
    }
    assert "NULL" in rules["inference_mode"].invalid_conditions
    assert "ZERO_BYTES" in rules["wav_audio"].invalid_conditions
    assert all(
        "NO_SESSION" in rule.required_outcome
        for rule in rules.values()
    )


def test_contract_files_are_valid_utf8_without_placeholders() -> None:
    for path in (CONFIG, DOCUMENT):
        payload = path.read_bytes()
        assert not payload.startswith(b"\xef\xbb\xbf")
        assert b"\x00" not in payload
        payload.decode("utf-8")

    config_text = CONFIG.read_text(encoding="utf-8")
    document_text = DOCUMENT.read_text(encoding="utf-8")
    assert json.loads(config_text)["schema_version"] == "1.0.0"
    assert "TODO" not in config_text + document_text
    assert "FIXME" not in config_text + document_text
