"""Strict loader and immutable schema for the final-demonstrator contract.

This module validates the frozen D0 scenario registry. It does not execute
models, evaluate governance requests, run PyBullet, verify research artifact
bytes, issue permits, or grant physical execution authority.
"""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Annotated, Final, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    field_validator,
    model_validator,
)


DEFAULT_FINAL_DEMO_CONTRACT_PATH: Final[Path] = (
    Path(__file__).resolve().parents[2]
    / "configs"
    / "prototype5"
    / "final_demo_scenarios_v1.json"
)

__all__ = (
    "DEFAULT_FINAL_DEMO_CONTRACT_PATH",
    "FinalDemoContract",
    "FinalDemoContractIOError",
    "FinalDemoContractJSONError",
    "FinalDemoContractLoadError",
    "FinalDemoContractValidationError",
    "load_final_demo_contract",
    "validate_final_demo_contract",
)

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


class FinalDemoContractLoadError(RuntimeError):
    """Base class for explicit final-demo contract loading failures."""


class FinalDemoContractIOError(FinalDemoContractLoadError):
    """The configured contract could not be read as UTF-8 text."""


class FinalDemoContractJSONError(FinalDemoContractLoadError):
    """The contract was empty, invalid JSON, or violated canonical JSON rules."""


class FinalDemoContractValidationError(FinalDemoContractLoadError):
    """The decoded JSON violated the frozen D0 structural contract."""

    def __init__(self, validation_error: ValidationError) -> None:
        super().__init__("final-demo contract validation failed")
        self.validation_error = validation_error


class _NonCanonicalJSONError(ValueError):
    """The JSON text uses syntax forbidden by the strict contract boundary."""


def _reject_json_constant(value: str) -> object:
    raise _NonCanonicalJSONError(
        f"non-standard JSON numeric constant is forbidden: {value}"
    )


def _reject_duplicate_json_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _NonCanonicalJSONError(
                f"duplicate JSON object key is forbidden: {key}"
            )
        result[key] = value
    return result


def _read_contract_json(path: Path) -> object:
    if not isinstance(path, Path):
        raise TypeError("path must be pathlib.Path")

    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise FinalDemoContractIOError(
            f"unable to read final-demo contract: {path}"
        ) from exc

    if not raw.strip():
        raise FinalDemoContractJSONError(
            f"final-demo contract is empty: {path}"
        )

    try:
        return json.loads(
            raw,
            parse_constant=_reject_json_constant,
            object_pairs_hook=_reject_duplicate_json_keys,
        )
    except (json.JSONDecodeError, _NonCanonicalJSONError) as exc:
        raise FinalDemoContractJSONError(
            f"final-demo contract is invalid or non-canonical JSON: {path}"
        ) from exc


def validate_final_demo_contract(payload: object) -> FinalDemoContract:
    """Validate exactly ``payload`` without default substitution or coercion."""

    try:
        return FinalDemoContract.model_validate(payload)
    except ValidationError as exc:
        raise FinalDemoContractValidationError(exc) from exc


def load_final_demo_contract(
    path: Path = DEFAULT_FINAL_DEMO_CONTRACT_PATH,
) -> FinalDemoContract:
    """Read and strictly validate one final-demonstrator registry file."""

    return validate_final_demo_contract(_read_contract_json(path))
