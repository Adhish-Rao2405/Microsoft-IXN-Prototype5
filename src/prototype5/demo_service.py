"""Application service for the typed integrated demonstrator."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, field_validator

from .canonical_governance_runner import CanonicalGovernanceRequestV2
from .governance_contract_v2 import ContractModel, DomainId, InferenceMode
from .hybrid_inference_router import (
    HybridGovernanceResultV1,
    HybridInferenceRouter,
    LocalHealthSnapshotV1,
)
from .manufacturing_policy_v2 import (
    ManufacturingSceneStateV2,
    RequesterContextV2,
    SceneObjectStateV2,
)


FROZEN_BASELINE_TAG = "prototype5-governance-reproducibility-complete"
FROZEN_BASELINE_COMMIT = "711ed03a19ce38013db1b2fdaf197961381024d9"


class AvailabilityStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_ASSESSED = "NOT_ASSESSED"


class TypedCommandApiRequest(ContractModel):
    command: str = Field(min_length=1, max_length=1000)
    inference_mode: InferenceMode
    domain_id: DomainId = DomainId.MANUFACTURING
    requester_role: str = "operator"
    human_obstruction: bool = False
    safety_interlock_enabled: bool = True

    @field_validator("command")
    @classmethod
    def command_is_not_whitespace(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("command must not be blank")
        return stripped

    @field_validator("requester_role")
    @classmethod
    def requester_role_is_supported(cls, value: str) -> str:
        if value not in {"operator", "observer", "supervisor"}:
            raise ValueError("unsupported requester role")
        return value


class DemoStatusResponse(ContractModel):
    service_status: str
    frozen_baseline_tag: str
    frozen_baseline_commit: str
    software_commit: str
    evidence_schema_version: str
    supported_domains: tuple[DomainId, ...]
    supported_inference_modes: tuple[InferenceMode, ...]
    local_status: AvailabilityStatus
    cloud_status: AvailabilityStatus
    speech_status: AvailabilityStatus
    simulator_status: AvailabilityStatus
    local_health: LocalHealthSnapshotV1


class DomainNotAvailableError(ValueError):
    pass


class DemoApplicationService:
    def __init__(
        self,
        *,
        router: HybridInferenceRouter,
        software_commit: str,
        cloud_configured: bool,
    ) -> None:
        self.router = router
        self.software_commit = software_commit
        self.cloud_configured = cloud_configured

    def status(self) -> DemoStatusResponse:
        health = self.router.local_health_snapshot()
        local_status = AvailabilityStatus.NOT_ASSESSED
        if health.rolling_sample_count or health.last_failure_reason.value != "NONE":
            local_status = (
                AvailabilityStatus.AVAILABLE
                if health.local_available and health.local_model_ready
                else AvailabilityStatus.UNAVAILABLE
            )
        return DemoStatusResponse(
            service_status="READY",
            frozen_baseline_tag=FROZEN_BASELINE_TAG,
            frozen_baseline_commit=FROZEN_BASELINE_COMMIT,
            software_commit=self.software_commit,
            evidence_schema_version="2.0.0",
            supported_domains=(DomainId.MANUFACTURING,),
            supported_inference_modes=(
                InferenceMode.LOCAL,
                InferenceMode.CLOUD,
                InferenceMode.AUTO,
            ),
            local_status=local_status,
            cloud_status=(
                AvailabilityStatus.AVAILABLE
                if self.cloud_configured
                else AvailabilityStatus.UNAVAILABLE
            ),
            speech_status=AvailabilityStatus.NOT_ASSESSED,
            simulator_status=AvailabilityStatus.NOT_ASSESSED,
            local_health=health,
        )

    def submit_typed(
        self, api_request: TypedCommandApiRequest
    ) -> HybridGovernanceResultV1:
        if api_request.domain_id is not DomainId.MANUFACTURING:
            raise DomainNotAvailableError(
                "SYNTHETIC_HEALTHCARE_DOMAIN_NOT_IMPLEMENTED"
            )
        canonical_request = CanonicalGovernanceRequestV2(
            input_mode="TYPED",
            typed_text=api_request.command,
            domain_id=api_request.domain_id,
            scene=self._scene(api_request),
            requester=RequesterContextV2(
                requester_id=f"synthetic_{api_request.requester_role}_ui",
                role=api_request.requester_role,
            ),
            requested_inference_mode=api_request.inference_mode,
            evaluation_mode="LIVE",
        )
        return self.router.route(canonical_request)

    @staticmethod
    def _scene(api_request: TypedCommandApiRequest) -> ManufacturingSceneStateV2:
        return ManufacturingSceneStateV2(
            scene_id="manufacturing_demo_scene",
            state_version="1.0.0",
            objects=(
                SceneObjectStateV2(
                    object_id="blue_component", location_id="input_tray_a"
                ),
                SceneObjectStateV2(
                    object_id="red_component", location_id="conveyor_a"
                ),
                SceneObjectStateV2(
                    object_id="component_a", location_id="warehouse_rack_a"
                ),
                SceneObjectStateV2(
                    object_id="inspection_part",
                    location_id="inspection_station",
                ),
            ),
            human_obstruction=api_request.human_obstruction,
            safety_interlock_enabled=api_request.safety_interlock_enabled,
        )
