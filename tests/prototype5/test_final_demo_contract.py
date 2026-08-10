from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal

import pytest
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    field_validator,
    model_validator,
)

from src.prototype5.governance_contract_v2 import FallbackReason


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs" / "prototype5" / "final_demo_scenarios_v1.json"
DOCUMENT = ROOT / "docs" / "prototype5" / "final_demonstrator_contract.md"
MODE_E = ROOT / "configs" / "prototype5" / "mode_e_industrial_benchmark.json"

NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
ScenarioId = Annotated[
    str,
    StringConstraints(pattern=r"^[A-Z][A-Z0-9_]*$", min_length=1),
]
Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
GitSha = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{40}$")]

InferenceMode = Literal["LOCAL", "CLOUD", "AUTO"]
CapabilityClassification = Literal[
    "GOVERNANCE_ONLY", "FROZEN_B2_REPLAY_COMPATIBLE"
]
AUTHORITY_STATE_ORDER = (
    "UNTRUSTED_PROPOSAL",
    "GOVERNANCE_DECISION",
    "EXECUTION_ELIGIBILITY",
    "QUALIFICATION_REPLAY_ACCESS",
    "DOWNSTREAM_GEOMETRIC_QUALIFICATION",
    "PHYSICAL_EXECUTION_AUTHORITY_NOT_IMPLEMENTED",
)
GOVERNANCE_DECISION_STATES = ("ACCEPT", "CLARIFY", "REJECT")
REPLAY_ACCESS_STATES = ("NOT_REQUESTED", "DENIED", "GRANTED")
GEOMETRIC_QUALIFICATION_STATES = (
    "PASS",
    "FAIL",
    "NOT_APPLICABLE",
    "NOT_REQUESTED",
)
CAPABILITY_CLASSIFICATIONS = (
    "GOVERNANCE_ONLY",
    "FROZEN_B2_REPLAY_COMPATIBLE",
)
EXPECTED_B3_2_FAILURE_CODES = ("B3_2_FAIL_SUPPORT_MATERIAL_PENETRATION",)
REPLAY_CONTROL_ORDER = (
    "START",
    "PAUSE",
    "RESUME",
    "NEXT_SNAPSHOT",
    "PREVIOUS_SNAPSHOT",
    "STOP",
    "RESET_VIEW",
)
TRUST_CHAIN = (
    "MODEL_OR_PROVIDER",
    "UNTRUSTED_PROPOSAL",
    "PARSE",
    "JSON_VALIDITY",
    "SCHEMA_VALIDITY",
    "POLICY_SCOPED_SEMANTIC_VALIDITY",
    "AMBIGUITY_OR_CLARIFICATION",
    "SAFETY_AND_ROLE_ACTION_POLICY",
    "EXECUTION_ELIGIBILITY",
    "OPTIONAL_QUALIFICATION_REPLAY_ACCESS",
    "FROZEN_B2_KINEMATIC_PLAN",
    "FROZEN_B3_2_GEOMETRIC_QUALIFICATION",
    "PHYSICAL_EXECUTION_AUTHORITY_NOT_IMPLEMENTED",
)
PRESENTATION_SOURCE_STATES = (
    "LIVE",
    "RECORDED_FALLBACK",
    "FROZEN_RESEARCH_EVIDENCE",
)
_MISSING = object()


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class QualifiedBaseline(StrictModel):
    commit: GitSha
    tree: GitSha


class ModelProposalTaxonomy(StrictModel):
    label: Literal["UNTRUSTED PROPOSAL"]
    authority: Literal["NONE"]
    description: NonBlank


class GovernanceDecisionTaxonomy(StrictModel):
    states: list[Literal["ACCEPT", "CLARIFY", "REJECT"]]
    description: NonBlank

    @model_validator(mode="after")
    def states_are_exact(self) -> GovernanceDecisionTaxonomy:
        if self.states != list(GOVERNANCE_DECISION_STATES):
            raise ValueError("governance decision states must be exact and ordered")
        return self


class ExecutionEligibilityTaxonomy(StrictModel):
    label: Literal["EXECUTION ELIGIBILITY"]
    description: NonBlank
    does_not_establish: list[NonBlank] = Field(min_length=1)


class QualificationReplayTaxonomy(StrictModel):
    label: Literal["QUALIFICATION_REPLAY_ACCESS"]
    states: list[Literal["NOT_REQUESTED", "DENIED", "GRANTED"]]
    description: NonBlank

    @model_validator(mode="after")
    def states_are_exact(self) -> QualificationReplayTaxonomy:
        if self.states != list(REPLAY_ACCESS_STATES):
            raise ValueError("qualification replay states must be exact and ordered")
        return self


class GeometricQualificationTaxonomy(StrictModel):
    label: Literal["DOWNSTREAM GEOMETRIC QUALIFICATION"]
    states: list[Literal["PASS", "FAIL", "NOT_APPLICABLE", "NOT_REQUESTED"]]
    frozen_b3_2_state: Literal["FAIL"]

    @model_validator(mode="after")
    def states_are_exact(self) -> GeometricQualificationTaxonomy:
        if self.states != list(GEOMETRIC_QUALIFICATION_STATES):
            raise ValueError("geometric qualification states must be exact and ordered")
        return self


class PhysicalAuthorityTaxonomy(StrictModel):
    label: Literal["PHYSICAL EXECUTION AUTHORITY"]
    state: Literal["NOT_IMPLEMENTED"]
    description: NonBlank


class AuthorityTaxonomy(StrictModel):
    ordered_states: list[
        Literal[
            "UNTRUSTED_PROPOSAL",
            "GOVERNANCE_DECISION",
            "EXECUTION_ELIGIBILITY",
            "QUALIFICATION_REPLAY_ACCESS",
            "DOWNSTREAM_GEOMETRIC_QUALIFICATION",
            "PHYSICAL_EXECUTION_AUTHORITY_NOT_IMPLEMENTED",
        ]
    ]
    model_proposal: ModelProposalTaxonomy
    governance_decision: GovernanceDecisionTaxonomy
    execution_eligibility: ExecutionEligibilityTaxonomy
    qualification_replay_access: QualificationReplayTaxonomy
    downstream_geometric_qualification: GeometricQualificationTaxonomy
    physical_execution_authority: PhysicalAuthorityTaxonomy
    layer_invariant: Literal["PASSING LAYER N DOES NOT ESTABLISH LAYER N+1."]

    @model_validator(mode="after")
    def ordered_taxonomy_is_exact(self) -> AuthorityTaxonomy:
        if self.ordered_states != list(AUTHORITY_STATE_ORDER):
            raise ValueError("authority taxonomy must be exact and ordered")
        return self


class ProvenancePolicy(StrictModel):
    invariant: Literal["LIVE_MODEL_PROPOSAL != FROZEN_B2_PLAN"]
    live_inference_output_state: Literal["UNTRUSTED_PROPOSAL"]
    live_governance_may_contextualise_frozen_evidence: Literal[True]
    live_model_proposal_is_frozen_b2_provenance_source: Literal[False]
    live_model_proposal_is_b3_1_b3_2_provenance_source: Literal[False]
    sequential_presentation_relationship: Literal[
        "CONTEXTUAL_ONLY_NOT_DERIVATIONAL"
    ]
    frozen_evidence_provenance: Literal["INDEPENDENT_HISTORICAL_PROVENANCE"]
    dedicated_replay_artifact_source: Literal["EXACT_BOUND_FROZEN_ARTIFACTS_ONLY"]


class StateTransitionPolicy(StrictModel):
    governance_accept_requires_all_evaluated_gates: Literal[True]
    governance_accept_automatically_grants_replay_access: Literal[False]
    qualification_replay_access_establishes_geometric_pass: Literal[False]
    qualification_replay_access_establishes_physical_execution_authority: Literal[
        False
    ]
    geometric_pass_establishes_physical_safety: Literal[False]
    geometric_fail_rewrites_governance_result: Literal[False]
    physical_execution_authority_terminal_state: Literal["NOT_IMPLEMENTED"]


class ClientInputBoundary(StrictModel):
    allowed_fields: list[NonBlank] = Field(min_length=1)
    forbidden_authoritative_fields: list[NonBlank] = Field(min_length=1)
    authoritative_context_owner: Literal["SERVER"]
    unknown_fields_policy: Literal["REJECT"]


class LiveManufacturingContext(StrictModel):
    context_kind: Literal["LIVE_SYNTHETIC_MANUFACTURING"]
    scene_id: Literal["manufacturing_demo_scene"]
    scene_state_version: Literal["1.0.0"]
    requester_persona_id: Literal[
        "SYNTHETIC_OPERATOR", "SYNTHETIC_OBSERVER", "SYNTHETIC_SUPERVISOR"
    ]
    requester_role: Literal["operator", "observer", "supervisor"]
    human_obstruction: bool
    safety_interlock_enabled: bool

    @model_validator(mode="after")
    def persona_and_role_are_bound(self) -> LiveManufacturingContext:
        expected_role = {
            "SYNTHETIC_OPERATOR": "operator",
            "SYNTHETIC_OBSERVER": "observer",
            "SYNTHETIC_SUPERVISOR": "supervisor",
        }[self.requester_persona_id]
        if self.requester_role != expected_role:
            raise ValueError("synthetic persona and role binding must be exact")
        return self


class FrozenModeEContext(StrictModel):
    context_kind: Literal["FROZEN_MODE_E_EVIDENCE"]
    benchmark_case_id: Annotated[str, StringConstraints(pattern=r"^E\d{3}$")]
    benchmark_policy_id: Literal["prototype5_mode_e_industrial_policy_v1"]


class FrozenReplayContext(StrictModel):
    context_kind: Literal["FROZEN_B2_B3_2_BINDING"]
    binding_id: Literal["FROZEN_B2_B3_2_EVIDENCE_V1"]


AuthoritativeContext = Annotated[
    LiveManufacturingContext | FrozenModeEContext | FrozenReplayContext,
    Field(discriminator="context_kind"),
]


class ReplayCapability(StrictModel):
    classification: CapabilityClassification
    qualification_replay_access: Literal["PROHIBITED", "SERVER_REGISTERED_ONLY"]
    pybullet_controls_may_be_exposed: bool
    allowed_replay_controls: list[
        Literal[
            "START",
            "PAUSE",
            "RESUME",
            "NEXT_SNAPSHOT",
            "PREVIOUS_SNAPSHOT",
            "STOP",
            "RESET_VIEW",
        ]
    ]

    @model_validator(mode="after")
    def classification_controls_are_consistent(self) -> ReplayCapability:
        if self.classification == "GOVERNANCE_ONLY":
            if self.qualification_replay_access != "PROHIBITED":
                raise ValueError("governance-only replay access must be prohibited")
            if self.pybullet_controls_may_be_exposed or self.allowed_replay_controls:
                raise ValueError("governance-only scenarios cannot expose replay controls")
        else:
            if self.qualification_replay_access != "SERVER_REGISTERED_ONLY":
                raise ValueError("frozen replay must be server registered")
            if not self.pybullet_controls_may_be_exposed:
                raise ValueError("registered replay controls must be explicitly exposed")
            if not self.allowed_replay_controls:
                raise ValueError("registered replay controls cannot be empty")
        return self


class Scenario(StrictModel):
    scenario_id: ScenarioId
    display_name: NonBlank
    domain: Literal["MANUFACTURING"]
    presentation_classification: Literal[
        "SYNTHETIC_LIVE_DEMO",
        "FROZEN_RESEARCH_EVIDENCE",
        "FROZEN_EVIDENCE_REPLAY",
    ]
    command: NonBlank
    source_reference: NonBlank
    model_input_enabled: bool
    allowed_inference_modes: list[InferenceMode]
    expected_demonstration_purpose: NonBlank
    expected_high_level_outcome: Literal[
        "ACCEPT", "CLARIFY", "REJECT", "NOT_PREDETERMINED", "FROZEN_B3_2_FAIL"
    ]
    outcome_basis: NonBlank
    authoritative_context: AuthoritativeContext
    client_overridable_context_fields: list[NonBlank]
    replay_capability: ReplayCapability
    claim_boundary_notes: NonBlank

    @model_validator(mode="after")
    def execution_path_is_consistent(self) -> Scenario:
        context_kind = self.authoritative_context.context_kind
        if context_kind == "LIVE_SYNTHETIC_MANUFACTURING":
            if not self.model_input_enabled:
                raise ValueError("live governance scenarios require model input")
            if self.allowed_inference_modes != ["LOCAL", "CLOUD", "AUTO"]:
                raise ValueError("live governance modes must be bounded and ordered")
            if self.presentation_classification != "SYNTHETIC_LIVE_DEMO":
                raise ValueError("live governance must be presented as a live demo")
        else:
            if self.model_input_enabled or self.allowed_inference_modes:
                raise ValueError("frozen evidence scenarios cannot invoke inference")
        if self.client_overridable_context_fields:
            raise ValueError("authoritative scenario context cannot be client-overridden")
        if context_kind == "FROZEN_B2_B3_2_BINDING":
            if self.replay_capability.classification != "FROZEN_B2_REPLAY_COMPATIBLE":
                raise ValueError("frozen replay context requires replay compatibility")
            exact_replay_fields = {
                "scenario_id": "FROZEN_B2_PICK_PLACE_EVIDENCE_REPLAY",
                "display_name": "Frozen B2/B3.2 evidence replay",
                "presentation_classification": "FROZEN_EVIDENCE_REPLAY",
                "command": "Display the registered frozen B2/B3.2 evidence replay.",
                "source_reference": (
                    "results/prototype5/scene_calibration/"
                    "phase_b2_kinematic_plan.json"
                ),
                "expected_demonstration_purpose": (
                    "Replay exact frozen B2 states and display the independent "
                    "frozen B3.2 geometric qualification failure."
                ),
                "expected_high_level_outcome": "FROZEN_B3_2_FAIL",
                "outcome_basis": (
                    "The operation is bound directly to immutable B2/B3.1/B3.2 "
                    "evidence identities and does not depend on natural-language "
                    "or model-proposal similarity."
                ),
                "claim_boundary_notes": (
                    "EVIDENCE REPLAY only. NOT PHYSICAL EXECUTION. The frozen "
                    "B3.2 FAIL remains independent of governance acceptance."
                ),
            }
            actual_replay_fields = {
                "scenario_id": self.scenario_id,
                "display_name": self.display_name,
                "presentation_classification": self.presentation_classification,
                "command": self.command,
                "source_reference": self.source_reference,
                "expected_demonstration_purpose": self.expected_demonstration_purpose,
                "expected_high_level_outcome": self.expected_high_level_outcome,
                "outcome_basis": self.outcome_basis,
                "claim_boundary_notes": self.claim_boundary_notes,
            }
            if actual_replay_fields != exact_replay_fields:
                raise ValueError("frozen replay semantics must remain exact")
            if self.replay_capability.allowed_replay_controls != list(
                REPLAY_CONTROL_ORDER
            ):
                raise ValueError("frozen replay controls must be exact and ordered")
        elif context_kind == "FROZEN_MODE_E_EVIDENCE":
            if self.presentation_classification != "FROZEN_RESEARCH_EVIDENCE":
                raise ValueError("Mode E cases must be presented as frozen evidence")
            if self.replay_capability.classification != "GOVERNANCE_ONLY":
                raise ValueError("Mode E cases cannot be replay compatible")
        elif self.replay_capability.classification != "GOVERNANCE_ONLY":
            raise ValueError("only frozen replay context may be replay compatible")
        return self


class ScenarioContract(StrictModel):
    capability_classifications: list[CapabilityClassification]
    scenarios: list[Scenario] = Field(min_length=1)

    @model_validator(mode="after")
    def registry_is_unique_and_bounded(self) -> ScenarioContract:
        if self.capability_classifications != list(CAPABILITY_CLASSIFICATIONS):
            raise ValueError("capability classifications must be exact and ordered")
        ids = [scenario.scenario_id for scenario in self.scenarios]
        if len(ids) != len(set(ids)):
            raise ValueError("scenario IDs must be unique")
        replay = [
            scenario
            for scenario in self.scenarios
            if scenario.replay_capability.classification
            == "FROZEN_B2_REPLAY_COMPATIBLE"
        ]
        if [scenario.scenario_id for scenario in replay] != [
            "FROZEN_B2_PICK_PLACE_EVIDENCE_REPLAY"
        ]:
            raise ValueError("exactly the dedicated frozen replay operation is compatible")
        return self


class ArtifactBinding(StrictModel):
    path: NonBlank
    sha256: Sha256
    digest_sidecar_path: NonBlank

    @field_validator("path", "digest_sidecar_path")
    @classmethod
    def path_is_bounded(cls, value: str) -> str:
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or "*" in value or "?" in value:
            raise ValueError("evidence paths must be bounded repository-relative paths")
        return value


class B2Binding(ArtifactBinding):
    path: Literal[
        "results/prototype5/scene_calibration/phase_b2_kinematic_plan.json"
    ]
    sha256: Literal[
        "a5a468145aea5aa21a649cccd1de3d6d2f8f15349d4b326db9380a6ad1256554"
    ]
    digest_sidecar_path: Literal[
        "results/prototype5/scene_calibration/phase_b2_kinematic_plan.json.sha256"
    ]


class B31Binding(ArtifactBinding):
    path: Literal[
        "results/prototype5/scene_calibration/phase_b3_1_collision_qualification.json"
    ]
    sha256: Literal[
        "004783320d3af4d1de45aaeee3f6da09829d6ad395d49221bac054452fa5af02"
    ]
    digest_sidecar_path: Literal[
        "results/prototype5/scene_calibration/phase_b3_1_collision_qualification.json.sha256"
    ]


class B32Binding(ArtifactBinding):
    path: Literal[
        "results/prototype5/scene_calibration/"
        "phase_b3_2_discrete_route_collision_qualification.json"
    ]
    sha256: Literal[
        "11c8b83f8c4d0545c9a8df604046a335acb00121a51bf6e1d5b39504991c1798"
    ]
    digest_sidecar_path: Literal[
        "results/prototype5/scene_calibration/"
        "phase_b3_2_discrete_route_collision_qualification.json.sha256"
    ]
    specification_path: Literal[
        "docs/prototype5/phase_b3_2_discrete_route_collision_qualification_spec.md"
    ]
    specification_sha256: Literal[
        "ffdcf517d56e32ae5b5a175bef89e015489a3d23ab7c1a4856c9987da7e4344a"
    ]
    specification_freeze_commit: Literal[
        "a7ca2243c33097c4dd2b4a6afa3c79b1da7e41f2"
    ]
    specification_git_blob: Literal[
        "5b63ae433315ea94cd58c734bcf379367dafcd71"
    ]
    expected_terminal_status: Literal[
        "B3_2_FAIL_DISCRETE_ROUTE_QUALIFICATION"
    ]
    expected_scientific_failure_count: Literal[118]
    expected_failure_codes_present: list[
        Literal["B3_2_FAIL_SUPPORT_MATERIAL_PENETRATION"]
    ]

    @field_validator("specification_path")
    @classmethod
    def specification_path_is_bounded(cls, value: str) -> str:
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or "*" in value or "?" in value:
            raise ValueError("specification path must be repository-relative")
        return value

    @model_validator(mode="after")
    def failure_codes_are_exact(self) -> B32Binding:
        if self.expected_failure_codes_present != list(EXPECTED_B3_2_FAILURE_CODES):
            raise ValueError("B3.2 failure codes must match frozen evidence exactly")
        return self


class SceneIdentity(StrictModel):
    scene_id: Literal["manufacturing_demo_scene"]
    scene_state_version: Literal["1.0.0"]
    operation: Literal["MOVE"]
    object: Literal["blue_component"]
    source: Literal["input_tray_a"]
    destination: Literal["assembly_fixture_b"]


class RuntimeProvenance(StrictModel):
    pybullet_package_version: Literal["3.2.7"]
    pybullet_api_version: Literal[202010061]
    pybullet_binary_sha256: Literal[
        "e8a99694353e508f9e934a57494c177ddb9317cde94781da8bb68670c2334e40"
    ]
    kuka_urdf_identity: Literal["pybullet_data/kuka_iiwa/model.urdf"]
    kuka_urdf_sha256: Literal[
        "5c13c5b4bb88b5265223e0ec9a7706cbf81e9bb21cc0e18534273755a041788c"
    ]
    kuka_asset_manifest_sha256: Literal[
        "cee6f5a30f860c1302cb7ef69f0da2c0736a283fe87b87504f0141438c544fb3"
    ]
    qualified_windows_wheel_sha256: Literal[
        "de6f71be9d8b78f4413a2bc958971725d2b061c4bf2d733e62488683c384726b"
    ]


class RecordedFailureReference(StrictModel):
    semantic_snapshot_index: Literal[352]
    route_state: Literal["DESTINATION_PLACE"]
    phase: Literal["RELEASE_BOUNDARY"]
    boundary_snapshot: Literal["POST"]
    pair_id: Literal["component_environment:destination_floor"]
    pair_index: Literal[78]
    query_body_a: Literal["component"]
    query_body_b: Literal["destination_floor"]
    signed_distance_m: Literal[-9.290505685985613e-7]
    classification: Literal["MATERIAL_PENETRATION"]
    permission: Literal["REQUIRED_SUPPORT"]
    decision: Literal["B3_2_FAIL_SUPPORT_MATERIAL_PENETRATION"]


class FrozenEvidenceBindings(StrictModel):
    binding_id: Literal["FROZEN_B2_B3_2_EVIDENCE_V1"]
    b2: B2Binding
    b3_1: B31Binding
    b3_2: B32Binding
    scene_identity: SceneIdentity
    runtime_provenance: RuntimeProvenance
    recorded_failure_reference: RecordedFailureReference


class ReplayClaimBoundary(StrictModel):
    required_labels: list[Literal["EVIDENCE REPLAY", "NOT PHYSICAL EXECUTION"]]
    reconstructs_frozen_states: Literal[True]
    consumes_immutable_evidence: Literal[True]
    performs_new_ik: Literal[False]
    optimises_trajectory: Literal[False]
    generates_new_collision_result: Literal[False]
    proves_dynamic_feasibility: Literal[False]
    proves_physical_robot_safety: Literal[False]
    authorises_physical_execution: Literal[False]
    replay_is_fresh_execution: Literal[False]
    generated_by_current_model_output: Literal[False]
    discrete_sampling_limitation: Literal[
        "Discrete sampling cannot prove the absence of collision between evaluated configurations."
    ]

    @model_validator(mode="after")
    def required_labels_are_exact(self) -> ReplayClaimBoundary:
        if self.required_labels != ["EVIDENCE REPLAY", "NOT PHYSICAL EXECUTION"]:
            raise ValueError("replay claim labels must be exact and ordered")
        return self


class RejectionInvariants(StrictModel):
    governance_reject_or_clarify: list[NonBlank] = Field(min_length=1)
    governance_only_scenario: list[NonBlank] = Field(min_length=1)
    b3_2_fail: list[NonBlank] = Field(min_length=1)


class AutoProviderContract(StrictModel):
    fallback_allowed_for: list[NonBlank] = Field(min_length=1)
    fallback_prohibited_for: list[NonBlank] = Field(min_length=1)
    provider_shopping_after_governance_rejection: Literal[False]


class VoiceContract(StrictModel):
    chain: list[NonBlank] = Field(min_length=1)
    direct_voice_to_robot_path: Literal[False]
    unavailability_outcome: Literal["FAIL_CLOSED_NO_GOVERNANCE_OR_REPLAY_SESSION"]
    new_stt_research_authorised: Literal[False]


class FrozenResearchTraceCategory(StrictModel):
    label: Literal["FROZEN RESEARCH EVIDENCE"]
    mutable: Literal[False]
    supports_dissertation_claims: Literal[True]
    required_fields: list[NonBlank] = Field(min_length=1)

    @model_validator(mode="after")
    def required_fields_are_exact(self) -> FrozenResearchTraceCategory:
        if self.required_fields != [
            "artifact_path",
            "sha256",
            "schema_identifier",
            "provenance",
        ]:
            raise ValueError("frozen evidence trace fields must be exact")
        return self


class LiveDemoTraceCategory(StrictModel):
    label: Literal["LIVE DEMO TRACE — NOT FROZEN RESEARCH EVIDENCE"]
    mutable: Literal[True]
    supports_dissertation_claims: Literal[False]
    required_fields: list[NonBlank] = Field(min_length=1)

    @model_validator(mode="after")
    def required_fields_are_exact(self) -> LiveDemoTraceCategory:
        if self.required_fields != [
            "trace_id",
            "selected_provider",
            "resolved_model",
            "timestamp",
        ]:
            raise ValueError("live demo trace fields must be exact")
        return self


class TraceCategories(StrictModel):
    frozen_research_evidence: FrozenResearchTraceCategory
    live_demo_trace: LiveDemoTraceCategory


class DeterministicFallbackContract(StrictModel):
    presentation_source_states: list[
        Literal["LIVE", "RECORDED_FALLBACK", "FROZEN_RESEARCH_EVIDENCE"]
    ]
    permitted_sources: list[NonBlank] = Field(min_length=1)
    recorded_fallback_must_not_be_labelled_fresh: Literal[True]
    hidden_provider_substitution: Literal[False]

    @model_validator(mode="after")
    def presentation_states_are_exact(self) -> DeterministicFallbackContract:
        if self.presentation_source_states != list(PRESENTATION_SOURCE_STATES):
            raise ValueError("presentation source states must be exact and ordered")
        return self


class HealthcareScope(StrictModel):
    state: Literal["OUT_OF_SCOPE_FOR_FINAL_DEMO"]
    policy_implementation_authorised: Literal[False]
    scenario_implementation_authorised: Literal[False]


class InputValidationRule(StrictModel):
    input: NonBlank
    invalid_conditions: list[NonBlank] = Field(min_length=1)
    required_outcome: NonBlank


class FinalDemoContract(StrictModel):
    schema_identifier: Literal["prototype5.final_demonstrator_contract"]
    schema_version: Literal["1.0.0"]
    contract_id: Literal["PROTOTYPE5_FINAL_DEMONSTRATOR_D0"]
    qualified_integration_baseline: QualifiedBaseline
    authority_taxonomy: AuthorityTaxonomy
    provenance_policy: ProvenancePolicy
    state_transition_policy: StateTransitionPolicy
    trust_chain: list[NonBlank] = Field(min_length=1)
    client_input_boundary: ClientInputBoundary
    scenario_contract: ScenarioContract
    frozen_evidence_bindings: FrozenEvidenceBindings
    replay_claim_boundary: ReplayClaimBoundary
    rejection_invariants: RejectionInvariants
    auto_provider_contract: AutoProviderContract
    voice_contract: VoiceContract
    trace_categories: TraceCategories
    deterministic_fallback_contract: DeterministicFallbackContract
    healthcare_scope: HealthcareScope
    input_validation_contract: list[InputValidationRule] = Field(min_length=1)

    @model_validator(mode="after")
    def input_rule_names_are_unique(self) -> FinalDemoContract:
        if self.trust_chain != list(TRUST_CHAIN):
            raise ValueError("trust chain must be exact and ordered")
        names = [rule.input for rule in self.input_validation_contract]
        if len(names) != len(set(names)):
            raise ValueError("input validation rules must be unique")
        return self


def raw_contract() -> dict[str, object]:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def validated_contract(payload: object = _MISSING) -> FinalDemoContract:
    candidate = raw_contract() if payload is _MISSING else payload
    return FinalDemoContract.model_validate(candidate)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sidecar_digest(path: Path) -> str:
    return path.read_text(encoding="utf-8").split()[0]


def test_contract_parses_under_strict_typed_schema() -> None:
    contract = validated_contract()

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
    with pytest.raises(ValidationError):
        validated_contract(invalid_root)


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
    payload = raw_contract()
    mutation(payload)

    with pytest.raises(ValidationError):
        FinalDemoContract.model_validate(payload)


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
    payload = raw_contract()
    mutation(payload)

    with pytest.raises(ValidationError):
        FinalDemoContract.model_validate(payload)


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
    payload = raw_contract()
    mutation(payload)

    with pytest.raises(ValidationError):
        FinalDemoContract.model_validate(payload)


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
    payload = raw_contract()
    mutation(payload)

    with pytest.raises(ValidationError):
        FinalDemoContract.model_validate(payload)


def test_browser_cannot_own_authoritative_safety_or_replay_fields() -> None:
    contract = validated_contract()
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
    scenarios = validated_contract().scenario_contract.scenarios
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
    contract = validated_contract()
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
    bindings = validated_contract().frozen_evidence_bindings

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
    bindings = validated_contract().frozen_evidence_bindings
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
    contract = validated_contract()
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
    invariants = validated_contract().rejection_invariants

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
    contract = validated_contract().auto_provider_contract
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
    contract = validated_contract()

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
        rule.input: rule for rule in validated_contract().input_validation_contract
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
