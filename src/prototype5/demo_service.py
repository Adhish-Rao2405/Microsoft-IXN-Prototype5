"""Application service for typed and reviewed recorded-voice commands."""

from __future__ import annotations

import threading
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Annotated, Literal, Protocol

from pydantic import ConfigDict, StringConstraints, field_validator

from .canonical_governance_runner import CanonicalGovernanceRequestV2
from .execution_session import (
    DEFAULT_SESSION_CAPACITY,
    DEFAULT_SESSION_TTL_SECONDS,
    ExecutionSessionRegistry,
    ExecutionSessionStateV1,
)
from .final_demo_presentation import (
    FinalDemoManifest,
    FinalDemoPresentationRegistry,
    ResolvedLiveScenario,
    load_final_demo_presentation,
)
from .governance_contract_v2 import (
    ContractModel,
    DomainId,
    InferenceMode,
    TranscriptStatus,
)
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
from .recorded_speech import (
    RecordedTranscriptionResultV1,
    SpeechWorkerBusyError,
)


FROZEN_BASELINE_TAG = "prototype5-governance-reproducibility-complete"
FROZEN_BASELINE_COMMIT = "711ed03a19ce38013db1b2fdaf197961381024d9"


class AvailabilityStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_ASSESSED = "NOT_ASSESSED"


ScenarioId = Annotated[
    str,
    StringConstraints(
        strict=True,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Z][A-Z0-9_]*$",
    ),
]
CommandText = Annotated[
    str,
    StringConstraints(strict=True, min_length=1, max_length=1000),
]
TranscriptionId = Annotated[
    str,
    StringConstraints(strict=True, min_length=1, max_length=200),
]
InferenceModeValue = Literal["LOCAL", "CLOUD", "AUTO"]


class TypedCommandApiRequest(ContractModel):
    """Strict internal command object with explicit D0 scenario identity."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    scenario_id: ScenarioId
    command: CommandText
    inference_mode: InferenceModeValue

    @field_validator("command")
    @classmethod
    def command_is_not_whitespace(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("command must not be blank")
        return stripped


class TypedCommandHttpRequest(TypedCommandApiRequest):
    """Strict browser boundary: scenario identity is mandatory."""

    scenario_id: ScenarioId


class VoiceCommandApiRequest(ContractModel):
    """Strict internal voice object with explicit D0 scenario identity."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    scenario_id: ScenarioId
    transcription_id: TranscriptionId
    reviewed_transcript_text: CommandText
    inference_mode: InferenceModeValue

    @field_validator("reviewed_transcript_text")
    @classmethod
    def transcript_is_not_whitespace(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("reviewed transcript must not be blank")
        return stripped


class VoiceCommandHttpRequest(VoiceCommandApiRequest):
    """Strict browser boundary: scenario identity is mandatory."""

    scenario_id: ScenarioId


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


class SpeechBackendUnavailableError(RuntimeError):
    pass


class SpeechCapacityUnavailableError(RuntimeError):
    pass


class TranscriptNotReadyError(ValueError):
    pass


class TranscriptRegistryError(RuntimeError):
    pass


class RecordedAudioTranscriber(Protocol):
    @property
    def is_worker_configured(self) -> bool: ...

    def transcribe_wav(
        self,
        audio_bytes: bytes,
        *,
        original_filename: str,
    ) -> RecordedTranscriptionResultV1: ...


@dataclass(frozen=True, slots=True)
class _AuthoritativeGovernanceContext:
    domain_id: DomainId
    requester: RequesterContextV2
    scene: ManufacturingSceneStateV2


class DemoApplicationService:
    def __init__(
        self,
        *,
        router: HybridInferenceRouter,
        software_commit: str,
        cloud_configured: bool,
        speech_transcriber: RecordedAudioTranscriber | None = None,
        transcript_ttl_seconds: int = 600,
        transcript_registry_capacity: int = 20,
        utc_clock: Callable[[], datetime] | None = None,
        execution_registry: ExecutionSessionRegistry | None = None,
        execution_ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS,
        execution_registry_capacity: int = DEFAULT_SESSION_CAPACITY,
        final_demo_presentation: FinalDemoPresentationRegistry | None = None,
    ) -> None:
        if not 1 <= transcript_ttl_seconds <= 3600:
            raise ValueError("transcript_ttl_seconds must be between 1 and 3600")
        if not 1 <= transcript_registry_capacity <= 1000:
            raise ValueError(
                "transcript_registry_capacity must be between 1 and 1000"
            )
        self.router = router
        self.software_commit = software_commit
        self.cloud_configured = cloud_configured
        self.speech_transcriber = speech_transcriber
        self.transcript_ttl_seconds = transcript_ttl_seconds
        self.transcript_registry_capacity = transcript_registry_capacity
        self._utc_clock = utc_clock or (lambda: datetime.now(timezone.utc))
        self._transcript_lock = threading.Lock()
        self._transcripts: OrderedDict[
            str, tuple[RecordedTranscriptionResultV1, datetime]
        ] = OrderedDict()
        self._last_speech_status = AvailabilityStatus.NOT_ASSESSED
        self.final_demo_presentation = (
            final_demo_presentation or load_final_demo_presentation()
        )
        self.execution_registry = execution_registry or ExecutionSessionRegistry(
            ttl_seconds=execution_ttl_seconds,
            capacity=execution_registry_capacity,
            utc_clock=self._utc_clock,
        )

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
            speech_status=self._speech_status(),
            simulator_status=AvailabilityStatus.NOT_ASSESSED,
            local_health=health,
        )

    def manifest(self) -> FinalDemoManifest:
        """Return the immutable presentation-safe D0 projection."""

        return self.final_demo_presentation.manifest

    def submit_typed(
        self, api_request: TypedCommandApiRequest
    ) -> HybridGovernanceResultV1:
        context = self._authoritative_context(api_request.scenario_id)
        canonical_request = CanonicalGovernanceRequestV2(
            input_mode="TYPED",
            typed_text=api_request.command,
            domain_id=context.domain_id,
            scene=context.scene,
            requester=context.requester,
            requested_inference_mode=InferenceMode(api_request.inference_mode),
            evaluation_mode="LIVE",
        )
        return self._route_and_register(canonical_request)

    def transcribe_recorded(
        self,
        audio_bytes: bytes,
        *,
        original_filename: str,
    ) -> RecordedTranscriptionResultV1:
        if self.speech_transcriber is None:
            raise SpeechBackendUnavailableError("VOICE_BACKEND_UNAVAILABLE")
        try:
            result = self.speech_transcriber.transcribe_wav(
                audio_bytes,
                original_filename=original_filename,
            )
        except SpeechWorkerBusyError as exc:
            raise SpeechCapacityUnavailableError("SPEECH_BUSY") from exc
        with self._transcript_lock:
            self._last_speech_status = (
                AvailabilityStatus.AVAILABLE
                if result.transcript_status
                in (TranscriptStatus.READY, TranscriptStatus.EMPTY)
                else AvailabilityStatus.UNAVAILABLE
            )
            if result.transcript_status is TranscriptStatus.READY:
                self._evict_expired_locked()
                if result.transcription_id in self._transcripts:
                    raise TranscriptRegistryError(
                        "TRANSCRIPTION_ID_COLLISION"
                    )
                expiry = self._utc_clock() + timedelta(
                    seconds=self.transcript_ttl_seconds
                )
                self._transcripts[result.transcription_id] = (result, expiry)
                self._transcripts.move_to_end(result.transcription_id)
                while len(self._transcripts) > self.transcript_registry_capacity:
                    self._transcripts.popitem(last=False)
        return result

    def submit_voice(
        self,
        api_request: VoiceCommandApiRequest,
    ) -> HybridGovernanceResultV1:
        context = self._authoritative_context(api_request.scenario_id)
        transcript = self._claim_transcript(api_request.transcription_id)
        canonical_request = CanonicalGovernanceRequestV2(
            input_mode="VOICE",
            transcription_id=transcript.transcription_id,
            original_transcript_text=transcript.transcript_text,
            transcript_text=api_request.reviewed_transcript_text,
            transcript_status="READY",
            transcript_backend=transcript.transcript_backend,
            transcript_confidence=transcript.transcript_confidence,
            audio_sha256=transcript.audio.audio_sha256,
            domain_id=context.domain_id,
            scene=context.scene,
            requester=context.requester,
            requested_inference_mode=InferenceMode(api_request.inference_mode),
            evaluation_mode="LIVE",
        )
        return self._route_and_register(canonical_request)

    def _route_and_register(
        self, canonical_request: CanonicalGovernanceRequestV2
    ) -> HybridGovernanceResultV1:
        """Route one request and retain its governance-time execution context.

        Every completed trace is registered, including non-executable ones, so
        a later execution attempt can be refused with an accurate reason
        instead of appearing never to have existed. The internal context is
        never returned to the caller.
        """

        result, context = self.router.route_with_execution_context(
            canonical_request
        )
        self.execution_registry.register(context)
        return result

    def execution_state(self, trace_id: str) -> ExecutionSessionStateV1 | None:
        return self.execution_registry.get_state(trace_id)

    def _claim_transcript(
        self,
        transcription_id: str,
    ) -> RecordedTranscriptionResultV1:
        with self._transcript_lock:
            self._evict_expired_locked()
            entry = self._transcripts.pop(transcription_id, None)
        if entry is None:
            raise TranscriptNotReadyError(
                "TRANSCRIPT_NOT_READY_OR_EXPIRED"
            )
        result, _ = entry
        if result.transcript_status is not TranscriptStatus.READY:
            raise TranscriptNotReadyError("TRANSCRIPT_NOT_READY_OR_EXPIRED")
        return result

    def _evict_expired_locked(self) -> None:
        now = self._utc_clock()
        expired = [
            transcript_id
            for transcript_id, (_, expiry) in self._transcripts.items()
            if expiry <= now
        ]
        for transcript_id in expired:
            self._transcripts.pop(transcript_id, None)

    def _speech_status(self) -> AvailabilityStatus:
        if self.speech_transcriber is None:
            return AvailabilityStatus.UNAVAILABLE
        if not self.speech_transcriber.is_worker_configured:
            return AvailabilityStatus.UNAVAILABLE
        with self._transcript_lock:
            return self._last_speech_status

    @staticmethod
    def _scene(scenario: ResolvedLiveScenario) -> ManufacturingSceneStateV2:
        return ManufacturingSceneStateV2(
            scene_id=scenario.scene_id,
            state_version=scenario.scene_state_version,
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
            human_obstruction=scenario.human_obstruction,
            safety_interlock_enabled=scenario.safety_interlock_enabled,
        )

    def _authoritative_context(
        self,
        scenario_id: str,
    ) -> _AuthoritativeGovernanceContext:
        scenario = self.final_demo_presentation.resolve_live_scenario(scenario_id)
        return _AuthoritativeGovernanceContext(
            domain_id=DomainId(scenario.domain_id),
            requester=RequesterContextV2(
                requester_id=f"synthetic_{scenario.requester_role}_ui",
                role=scenario.requester_role,
            ),
            scene=self._scene(scenario),
        )
