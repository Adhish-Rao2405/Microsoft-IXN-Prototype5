"""Presentation-safe projection and server-owned scenario resolution for D2.

The browser may request a registered scenario identifier.  This module owns
the authoritative D0 lookup and exposes no research artifact location, digest,
robot state, geometry, replay control, or execution permit data.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

from .final_demo_contract import (
    AUTHORITY_STATE_ORDER,
    FinalDemoContract,
    LiveManufacturingContext,
    Scenario,
    load_final_demo_contract,
)


ScenarioId = Annotated[
    str,
    StringConstraints(
        strict=True,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Z][A-Z0-9_]*$",
    ),
]
NonBlank = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, min_length=1),
]

AuthorityState = Literal[
    "UNTRUSTED_PROPOSAL",
    "GOVERNANCE_DECISION",
    "EXECUTION_ELIGIBILITY",
    "QUALIFICATION_REPLAY_ACCESS",
    "DOWNSTREAM_GEOMETRIC_QUALIFICATION",
    "PHYSICAL_EXECUTION_AUTHORITY_NOT_IMPLEMENTED",
]
InferenceMode = Literal["LOCAL", "CLOUD", "AUTO"]
PresentationClassification = Literal[
    "SYNTHETIC_LIVE_DEMO",
    "FROZEN_RESEARCH_EVIDENCE",
    "FROZEN_EVIDENCE_REPLAY",
]
EvidenceClassification = Literal[
    "LIVE_DEMO_TRACE_NOT_FROZEN_RESEARCH_EVIDENCE",
    "FROZEN_RESEARCH_EVIDENCE_EXACT_REGISTERED_ARTIFACT",
    "EVIDENCE_REPLAY_NOT_PHYSICAL_EXECUTION",
]
ReplayCapabilityClassification = Literal[
    "GOVERNANCE_ONLY",
    "FROZEN_B2_REPLAY_COMPATIBLE",
]
ReplayAccessPresentationState = Literal["PROHIBITED", "SERVER_REGISTERED_ONLY"]
DownstreamQualificationPresentationState = Literal["FAIL", "NOT_APPLICABLE"]


class StrictPresentationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class FinalDemoScenarioPresentation(StrictPresentationModel):
    scenario_id: ScenarioId
    display_name: NonBlank
    presentation_classification: PresentationClassification
    model_input_enabled: bool
    allowed_inference_modes: tuple[InferenceMode, ...]
    registered_command: NonBlank
    demonstration_purpose: NonBlank
    evidence_classification: EvidenceClassification
    replay_capability_classification: ReplayCapabilityClassification
    qualification_replay_access: ReplayAccessPresentationState
    downstream_geometric_qualification: DownstreamQualificationPresentationState
    claim_boundary_note: NonBlank


class FinalDemoManifest(StrictPresentationModel):
    contract_id: Literal["PROTOTYPE5_FINAL_DEMONSTRATOR_D0"]
    contract_version: Literal["1.0.0"]
    authority_taxonomy: tuple[AuthorityState, ...]
    physical_execution_authority_state: Literal["NOT_IMPLEMENTED"]
    healthcare_scope: Literal["OUT_OF_SCOPE_FOR_FINAL_DEMO"]
    d2_replay_enabled: Literal[False]
    scenarios: tuple[FinalDemoScenarioPresentation, ...]


@dataclass(frozen=True, slots=True)
class ResolvedLiveScenario:
    scenario_id: str
    domain_id: Literal["MANUFACTURING"]
    scene_id: Literal["manufacturing_demo_scene"]
    scene_state_version: Literal["1.0.0"]
    requester_persona_id: Literal[
        "SYNTHETIC_OPERATOR",
        "SYNTHETIC_OBSERVER",
        "SYNTHETIC_SUPERVISOR",
    ]
    requester_role: Literal["operator", "observer", "supervisor"]
    human_obstruction: bool
    safety_interlock_enabled: bool


@dataclass(frozen=True, slots=True)
class _RegisteredScenarioSnapshot:
    presentation: FinalDemoScenarioPresentation
    live_context: ResolvedLiveScenario | None


class FinalDemoScenarioError(ValueError):
    """Base failure for a requested D0 scenario identifier."""


class FinalDemoScenarioNotFoundError(FinalDemoScenarioError):
    """The requested scenario identifier is not registered by D0."""


class FinalDemoScenarioInferenceForbiddenError(FinalDemoScenarioError):
    """The registered scenario is evidence-only and cannot invoke inference."""


@dataclass(frozen=True, slots=True)
class FinalDemoPresentationRegistry:
    manifest: FinalDemoManifest
    _scenarios: Mapping[str, _RegisteredScenarioSnapshot]

    @classmethod
    def from_contract(
        cls,
        contract: FinalDemoContract,
    ) -> FinalDemoPresentationRegistry:
        if not isinstance(contract, FinalDemoContract):
            raise TypeError("contract must be FinalDemoContract")

        snapshots = tuple(
            _snapshot_scenario(scenario)
            for scenario in contract.scenario_contract.scenarios
        )
        registered = {
            snapshot.presentation.scenario_id: snapshot for snapshot in snapshots
        }
        manifest = FinalDemoManifest(
            contract_id=contract.contract_id,
            contract_version=contract.schema_version,
            authority_taxonomy=tuple(contract.authority_taxonomy.ordered_states),
            physical_execution_authority_state=(
                contract.authority_taxonomy.physical_execution_authority.state
            ),
            healthcare_scope=contract.healthcare_scope.state,
            d2_replay_enabled=False,
            scenarios=tuple(snapshot.presentation for snapshot in snapshots),
        )
        if manifest.authority_taxonomy != AUTHORITY_STATE_ORDER:
            raise ValueError("presentation authority taxonomy differs from D0")
        return cls(manifest=manifest, _scenarios=MappingProxyType(registered))

    def resolve_live_scenario(self, scenario_id: str) -> ResolvedLiveScenario:
        if not isinstance(scenario_id, str) or not scenario_id:
            raise FinalDemoScenarioNotFoundError("SCENARIO_NOT_FOUND")
        snapshot = self._scenarios.get(scenario_id)
        if snapshot is None:
            raise FinalDemoScenarioNotFoundError("SCENARIO_NOT_FOUND")
        if snapshot.live_context is None:
            raise FinalDemoScenarioInferenceForbiddenError(
                "SCENARIO_LIVE_INFERENCE_FORBIDDEN"
            )
        return snapshot.live_context


def load_final_demo_presentation() -> FinalDemoPresentationRegistry:
    """Load the canonical D0 registry and construct its safe D2 projection."""

    return FinalDemoPresentationRegistry.from_contract(load_final_demo_contract())


def _snapshot_scenario(scenario: Scenario) -> _RegisteredScenarioSnapshot:
    evidence_classification: EvidenceClassification
    if scenario.presentation_classification == "SYNTHETIC_LIVE_DEMO":
        evidence_classification = (
            "LIVE_DEMO_TRACE_NOT_FROZEN_RESEARCH_EVIDENCE"
        )
    elif scenario.presentation_classification == "FROZEN_RESEARCH_EVIDENCE":
        evidence_classification = (
            "FROZEN_RESEARCH_EVIDENCE_EXACT_REGISTERED_ARTIFACT"
        )
    else:
        evidence_classification = "EVIDENCE_REPLAY_NOT_PHYSICAL_EXECUTION"

    downstream_state: DownstreamQualificationPresentationState = (
        "FAIL"
        if scenario.replay_capability.classification
        == "FROZEN_B2_REPLAY_COMPATIBLE"
        else "NOT_APPLICABLE"
    )
    presentation = FinalDemoScenarioPresentation(
        scenario_id=scenario.scenario_id,
        display_name=scenario.display_name,
        presentation_classification=scenario.presentation_classification,
        model_input_enabled=scenario.model_input_enabled,
        allowed_inference_modes=tuple(scenario.allowed_inference_modes),
        registered_command=scenario.command,
        demonstration_purpose=scenario.expected_demonstration_purpose,
        evidence_classification=evidence_classification,
        replay_capability_classification=scenario.replay_capability.classification,
        qualification_replay_access=(
            scenario.replay_capability.qualification_replay_access
        ),
        downstream_geometric_qualification=downstream_state,
        claim_boundary_note=scenario.claim_boundary_notes,
    )
    live_context: ResolvedLiveScenario | None = None
    if scenario.model_input_enabled:
        if not isinstance(scenario.authoritative_context, LiveManufacturingContext):
            raise ValueError("live presentation scenario lacks manufacturing context")
        context = scenario.authoritative_context
        live_context = ResolvedLiveScenario(
            scenario_id=scenario.scenario_id,
            domain_id=scenario.domain,
            scene_id=context.scene_id,
            scene_state_version=context.scene_state_version,
            requester_persona_id=context.requester_persona_id,
            requester_role=context.requester_role,
            human_obstruction=context.human_obstruction,
            safety_interlock_enabled=context.safety_interlock_enabled,
        )
    return _RegisteredScenarioSnapshot(
        presentation=presentation,
        live_context=live_context,
    )


__all__ = (
    "FinalDemoManifest",
    "FinalDemoPresentationRegistry",
    "FinalDemoScenarioInferenceForbiddenError",
    "FinalDemoScenarioNotFoundError",
    "FinalDemoScenarioPresentation",
    "ResolvedLiveScenario",
    "load_final_demo_presentation",
)
