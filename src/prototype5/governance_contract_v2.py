"""Versioned governance and evidence contracts for the integrated demonstrator.

This module contains data contracts and invariants only. It does not call a
model, evaluate a policy, issue an execution permit, or start a simulator.
Historical Prototype 3-5 evidence remains immutable and is represented only
through an explicitly non-converting legacy reference.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


EVIDENCE_SCHEMA_VERSION = "2.0.0"
LEGACY_SEMANTIC_METRIC = "LEGACY_HYBRID_DECISION_SCORE"
SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
COMMIT_PATTERN = re.compile(r"^[0-9a-fA-F]{40}$")
REASON_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")


class InputMode(StrEnum):
    TYPED = "TYPED"
    VOICE = "VOICE"


class EvaluationMode(StrEnum):
    LIVE = "LIVE"
    EVALUATION = "EVALUATION"


class DomainId(StrEnum):
    MANUFACTURING = "MANUFACTURING"
    HEALTHCARE_SYNTHETIC = "HEALTHCARE_SYNTHETIC"


class InferenceMode(StrEnum):
    LOCAL = "LOCAL"
    CLOUD = "CLOUD"
    AUTO = "AUTO"


class ProviderId(StrEnum):
    FOUNDRY_LOCAL = "FOUNDRY_LOCAL"
    CLOUD = "CLOUD"
    NONE = "NONE"


class FallbackReason(StrEnum):
    NONE = "NONE"
    LOCAL_UNAVAILABLE = "LOCAL_UNAVAILABLE"
    LOCAL_MODEL_NOT_READY = "LOCAL_MODEL_NOT_READY"
    LOCAL_TIMEOUT = "LOCAL_TIMEOUT"
    LOCAL_TRANSPORT_ERROR = "LOCAL_TRANSPORT_ERROR"
    LOCAL_EMPTY_RESPONSE = "LOCAL_EMPTY_RESPONSE"
    LOCAL_PARSE_FAILURE = "LOCAL_PARSE_FAILURE"
    LOCAL_JSON_FAILURE = "LOCAL_JSON_FAILURE"
    LOCAL_SCHEMA_FAILURE = "LOCAL_SCHEMA_FAILURE"
    LOCAL_CIRCUIT_OPEN = "LOCAL_CIRCUIT_OPEN"
    LOCAL_ROLLING_RELIABILITY_BELOW_THRESHOLD = (
        "LOCAL_ROLLING_RELIABILITY_BELOW_THRESHOLD"
    )
    LOCAL_LATENCY_THRESHOLD_EXCEEDED = "LOCAL_LATENCY_THRESHOLD_EXCEEDED"


class TranscriptStatus(StrEnum):
    NOT_APPLICABLE = "NOT_APPLICABLE"
    READY = "READY"
    PARTIAL = "PARTIAL"
    EMPTY = "EMPTY"
    BACKEND_UNAVAILABLE = "BACKEND_UNAVAILABLE"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class GateStatus(StrEnum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    NOT_ASSESSABLE = "NOT_ASSESSABLE"
    NOT_EVALUATED = "NOT_EVALUATED"
    ERROR = "ERROR"


class PlanSemanticStatus(StrEnum):
    VALID = "VALID"
    INVALID = "INVALID"
    NOT_ASSESSABLE_NO_PROPOSAL = "NOT_ASSESSABLE_NO_PROPOSAL"
    NOT_ASSESSABLE_PARSE_FAILED = "NOT_ASSESSABLE_PARSE_FAILED"
    NOT_ASSESSABLE_SCHEMA_INVALID = "NOT_ASSESSABLE_SCHEMA_INVALID"
    NOT_ASSESSABLE_MISSING_ORACLE = "NOT_ASSESSABLE_MISSING_ORACLE"
    NOT_ASSESSABLE_MISSING_REQUIRED_CONTEXT = (
        "NOT_ASSESSABLE_MISSING_REQUIRED_CONTEXT"
    )
    NOT_EVALUATED = "NOT_EVALUATED"
    ERROR = "ERROR"


class CorrectnessStatus(StrEnum):
    CORRECT = "CORRECT"
    INCORRECT = "INCORRECT"
    NOT_ASSESSABLE = "NOT_ASSESSABLE"
    NOT_EVALUATED = "NOT_EVALUATED"
    ERROR = "ERROR"


class FinalDecision(StrEnum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    CLARIFY = "CLARIFY"
    ERROR = "ERROR"


class SimulationStatus(StrEnum):
    NOT_REQUESTED = "NOT_REQUESTED"
    NOT_STARTED = "NOT_STARTED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    STOPPED_BY_OPERATOR = "STOPPED_BY_OPERATOR"
    FAILED = "FAILED"


class GateId(StrEnum):
    PARSE = "PARSE"
    JSON = "JSON"
    SCHEMA = "SCHEMA"
    SEMANTICS = "SEMANTICS"
    AMBIGUITY = "AMBIGUITY"
    SAFETY = "SAFETY"
    AUTHORITY = "AUTHORITY"


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class GateReasonRecord(ContractModel):
    gate: GateId
    reason_codes: tuple[str, ...]

    @field_validator("reason_codes")
    @classmethod
    def reason_codes_are_valid(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if not values:
            raise ValueError("gate reason record requires at least one reason")
        if len(values) != len(set(values)):
            raise ValueError("gate reason codes must be unique")
        for value in values:
            if not REASON_CODE_PATTERN.fullmatch(value):
                raise ValueError(f"invalid gate reason code: {value}")
        return values


class GateLatencyRecord(ContractModel):
    gate: GateId
    latency_ms: float = Field(ge=0)


class RoutingRecordV2(ContractModel):
    requested_mode: InferenceMode
    selected_provider: ProviderId
    selected_model: str | None = None
    local_attempted: bool
    cloud_attempted: bool
    fallback_triggered: bool = False
    fallback_reason: FallbackReason = FallbackReason.NONE
    local_latency_ms: float | None = Field(default=None, ge=0)
    cloud_latency_ms: float | None = Field(default=None, ge=0)

    @field_validator("selected_model")
    @classmethod
    def selected_model_is_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("selected_model must not be blank")
        return value

    @model_validator(mode="after")
    def validate_route(self) -> "RoutingRecordV2":
        if self.selected_provider is ProviderId.NONE and self.selected_model is not None:
            raise ValueError("selected_model requires a selected provider")
        if self.selected_provider is not ProviderId.NONE and self.selected_model is None:
            raise ValueError("selected provider requires selected_model")

        if self.fallback_triggered:
            if self.requested_mode is not InferenceMode.AUTO:
                raise ValueError("fallback is permitted only in AUTO mode")
            if self.fallback_reason is FallbackReason.NONE:
                raise ValueError("fallback requires an operational fallback reason")
            if not self.local_attempted or not self.cloud_attempted:
                raise ValueError("fallback requires both local and cloud attempts")
            if self.selected_provider not in (ProviderId.CLOUD, ProviderId.NONE):
                raise ValueError("fallback can select cloud or end without a provider")
        elif self.fallback_reason is not FallbackReason.NONE:
            raise ValueError("fallback_reason must be NONE when fallback was not triggered")

        if self.requested_mode is InferenceMode.LOCAL:
            if not self.local_attempted or self.cloud_attempted:
                raise ValueError("LOCAL mode must attempt local only")
            if self.selected_provider not in (ProviderId.FOUNDRY_LOCAL, ProviderId.NONE):
                raise ValueError("LOCAL mode cannot select cloud")
        elif self.requested_mode is InferenceMode.CLOUD:
            if self.local_attempted or not self.cloud_attempted:
                raise ValueError("CLOUD mode must attempt cloud only")
            if self.selected_provider not in (ProviderId.CLOUD, ProviderId.NONE):
                raise ValueError("CLOUD mode cannot select local")
        elif not self.local_attempted:
            if self.cloud_attempted or self.selected_provider is not ProviderId.NONE:
                raise ValueError("AUTO mode cannot select or attempt cloud before local")

        if self.local_latency_ms is not None and not self.local_attempted:
            raise ValueError("local latency requires a local attempt")
        if self.cloud_latency_ms is not None and not self.cloud_attempted:
            raise ValueError("cloud latency requires a cloud attempt")
        return self


class ProvenanceRecordV2(ContractModel):
    source_repository: str = Field(min_length=1)
    software_commit: str
    prompt_id: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    model_provider: ProviderId
    model_id: str | None = None
    benchmark_sha256: str | None = None
    oracle_sha256: str | None = None
    policy_sha256: str

    @field_validator(
        "benchmark_sha256",
        "oracle_sha256",
        "policy_sha256",
    )
    @classmethod
    def hashes_are_sha256(cls, value: str | None) -> str | None:
        if value is not None and not SHA256_PATTERN.fullmatch(value):
            raise ValueError("hash fields must contain 64 hexadecimal characters")
        return value.lower() if value is not None else None

    @field_validator("software_commit")
    @classmethod
    def commit_is_full_sha(cls, value: str) -> str:
        if not COMMIT_PATTERN.fullmatch(value):
            raise ValueError("software_commit must be a full 40-character Git SHA")
        return value.lower()

    @model_validator(mode="after")
    def model_matches_provider(self) -> "ProvenanceRecordV2":
        if self.model_provider is ProviderId.NONE and self.model_id is not None:
            raise ValueError("model_id requires a model provider")
        if self.model_provider is not ProviderId.NONE and not self.model_id:
            raise ValueError("model provider requires model_id")
        return self


class GovernanceRecordV2(ContractModel):
    record_id: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)
    timestamp_utc: str

    evaluation_mode: EvaluationMode
    input_mode: InputMode
    normalised_command: str | None = None
    typed_text: str | None = None
    transcript_text: str | None = None
    transcript_status: TranscriptStatus = TranscriptStatus.NOT_APPLICABLE
    transcript_backend: str | None = None
    transcript_confidence: float | None = Field(default=None, ge=0, le=1)
    audio_sha256: str | None = None

    domain_id: DomainId
    benchmark_id: str | None = None
    policy_id: str = Field(min_length=1)
    oracle_version: str | None = None
    evidence_schema_version: Literal["2.0.0"] = EVIDENCE_SCHEMA_VERSION

    routing: RoutingRecordV2
    raw_response_sha256: str | None = None
    raw_response_present: bool
    provider_latency_ms: float | None = Field(default=None, ge=0)

    parse_status: GateStatus
    json_status: GateStatus
    schema_status: GateStatus
    plan_semantic_status: PlanSemanticStatus
    ambiguity_status: GateStatus
    safety_status: GateStatus
    authority_status: GateStatus

    gate_reasons: tuple[GateReasonRecord, ...] = ()
    gate_latencies: tuple[GateLatencyRecord, ...] = ()

    expected_decision: FinalDecision | None = None
    decision_correctness_status: CorrectnessStatus
    final_decision: FinalDecision
    execution_eligible: bool
    decision_reason_codes: tuple[str, ...]

    validation_latency_ms: float = Field(ge=0)
    total_pipeline_latency_ms: float = Field(ge=0)

    execution_permit_id: str | None = None
    simulation_status: SimulationStatus = SimulationStatus.NOT_REQUESTED
    provenance: ProvenanceRecordV2

    @field_validator("timestamp_utc")
    @classmethod
    def timestamp_is_utc(cls, value: str) -> str:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("timestamp_utc must be an ISO-8601 timestamp") from exc
        if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
            raise ValueError("timestamp_utc must include a UTC offset")
        return value

    @field_validator("audio_sha256", "raw_response_sha256")
    @classmethod
    def content_hashes_are_sha256(cls, value: str | None) -> str | None:
        if value is not None and not SHA256_PATTERN.fullmatch(value):
            raise ValueError("content hashes must contain 64 hexadecimal characters")
        return value.lower() if value is not None else None

    @field_validator("decision_reason_codes")
    @classmethod
    def decision_reasons_are_valid(
        cls, values: tuple[str, ...]
    ) -> tuple[str, ...]:
        if not values:
            raise ValueError("at least one decision reason code is required")
        if len(values) != len(set(values)):
            raise ValueError("decision reason codes must be unique")
        for value in values:
            if not REASON_CODE_PATTERN.fullmatch(value):
                raise ValueError(f"invalid decision reason code: {value}")
        return values

    @model_validator(mode="after")
    def validate_record_invariants(self) -> "GovernanceRecordV2":
        self._validate_gate_records()
        self._validate_input()
        self._validate_evaluation_mode()
        self._validate_response()
        self._validate_gate_dependencies()
        self._validate_decision()
        self._validate_simulation()
        self._validate_latency()
        return self

    def _validate_gate_records(self) -> None:
        reason_gates = [record.gate for record in self.gate_reasons]
        if len(reason_gates) != len(set(reason_gates)):
            raise ValueError("only one gate reason record is permitted per gate")
        latency_gates = [record.gate for record in self.gate_latencies]
        if len(latency_gates) != len(set(latency_gates)):
            raise ValueError("only one gate latency record is permitted per gate")

    def _validate_input(self) -> None:
        if self.input_mode is InputMode.TYPED:
            if not self.typed_text or not self.typed_text.strip():
                raise ValueError("typed input requires typed_text")
            if not self.normalised_command or not self.normalised_command.strip():
                raise ValueError("typed input requires normalised_command")
            if self.transcript_status is not TranscriptStatus.NOT_APPLICABLE:
                raise ValueError("typed input cannot have a transcript status")
            if any(
                value is not None
                for value in (
                    self.transcript_text,
                    self.transcript_backend,
                    self.transcript_confidence,
                    self.audio_sha256,
                )
            ):
                raise ValueError("typed input cannot contain voice provenance")
            return

        if self.typed_text is not None:
            raise ValueError("voice input cannot populate typed_text")
        if self.transcript_status is TranscriptStatus.NOT_APPLICABLE:
            raise ValueError("voice input requires a transcript status")
        if self.transcript_status in (TranscriptStatus.READY, TranscriptStatus.PARTIAL):
            if not self.transcript_text or not self.transcript_text.strip():
                raise ValueError("ready or partial voice input requires transcript_text")
            if not self.transcript_backend or not self.transcript_backend.strip():
                raise ValueError("ready or partial voice input requires transcript_backend")
            if not self.normalised_command or not self.normalised_command.strip():
                raise ValueError("ready or partial voice input requires normalised_command")
            if not self.audio_sha256:
                raise ValueError("ready or partial voice input requires audio_sha256")
        elif self.transcript_text:
            raise ValueError("failed, empty, cancelled, or unavailable voice input has no transcript")
        elif self.normalised_command is not None:
            raise ValueError(
                "failed, empty, cancelled, or unavailable voice input has no command"
            )

        if self.transcript_status is not TranscriptStatus.READY:
            if self.routing.selected_provider is not ProviderId.NONE:
                raise ValueError("non-ready transcript cannot select an inference provider")
            if self.routing.local_attempted or self.routing.cloud_attempted:
                raise ValueError("non-ready transcript cannot call an inference provider")

    def _validate_evaluation_mode(self) -> None:
        if self.evaluation_mode is EvaluationMode.LIVE:
            if self.expected_decision is not None:
                raise ValueError("live mode cannot invent an expected decision")
            if self.decision_correctness_status is not CorrectnessStatus.NOT_EVALUATED:
                raise ValueError("live mode decision correctness must be NOT_EVALUATED")
            return

        if not self.benchmark_id or not self.oracle_version:
            raise ValueError("evaluation mode requires benchmark_id and oracle_version")
        if self.expected_decision is None:
            raise ValueError("evaluation mode requires expected_decision")
        if self.decision_correctness_status is CorrectnessStatus.NOT_EVALUATED:
            raise ValueError("evaluation mode must evaluate decision correctness")

    def _validate_response(self) -> None:
        if self.raw_response_present:
            if self.routing.selected_provider is ProviderId.NONE:
                raise ValueError("raw response requires a selected provider")
            if not self.raw_response_sha256:
                raise ValueError("raw response requires raw_response_sha256")
        else:
            if self.raw_response_sha256 is not None:
                raise ValueError("raw_response_sha256 requires raw_response_present")
            if any(
                status is GateStatus.PASSED
                for status in (
                    self.parse_status,
                    self.json_status,
                    self.schema_status,
                )
            ):
                raise ValueError("missing raw response cannot pass structural gates")
            if self.plan_semantic_status is PlanSemanticStatus.VALID:
                raise ValueError("missing raw response cannot produce semantic VALID")

        if self.routing.selected_provider is not self.provenance.model_provider:
            raise ValueError("routing and provenance providers must match")
        if self.routing.selected_model != self.provenance.model_id:
            raise ValueError("routing and provenance model identifiers must match")
        if self.routing.selected_provider is ProviderId.NONE:
            if self.provider_latency_ms is not None:
                raise ValueError("provider latency requires a selected provider")
        elif self.provider_latency_ms is None:
            raise ValueError("selected provider requires provider_latency_ms")
        elif self.routing.selected_provider is ProviderId.FOUNDRY_LOCAL:
            if self.routing.local_latency_ms != self.provider_latency_ms:
                raise ValueError("provider latency must match selected local latency")
        elif self.routing.cloud_latency_ms != self.provider_latency_ms:
            raise ValueError("provider latency must match selected cloud latency")

    def _validate_gate_dependencies(self) -> None:
        if self.parse_status is not GateStatus.PASSED:
            if self.json_status is GateStatus.PASSED or self.schema_status is GateStatus.PASSED:
                raise ValueError("non-passing parse cannot produce passing JSON or schema")
            if self.plan_semantic_status is PlanSemanticStatus.VALID:
                raise ValueError("non-passing parse cannot produce semantic VALID")

        if self.json_status is not GateStatus.PASSED:
            if self.schema_status is GateStatus.PASSED:
                raise ValueError("non-passing JSON cannot produce passing schema")
            if self.plan_semantic_status is PlanSemanticStatus.VALID:
                raise ValueError("non-passing JSON cannot produce semantic VALID")

        if self.schema_status is not GateStatus.PASSED:
            if self.plan_semantic_status is PlanSemanticStatus.VALID:
                raise ValueError("non-passing schema cannot produce semantic VALID")

        if self.plan_semantic_status is PlanSemanticStatus.VALID:
            required = (self.parse_status, self.json_status, self.schema_status)
            if any(status is not GateStatus.PASSED for status in required):
                raise ValueError("semantic VALID requires parse, JSON, and schema PASSED")

    def _validate_decision(self) -> None:
        mandatory_pass = (
            self.parse_status is GateStatus.PASSED
            and self.json_status is GateStatus.PASSED
            and self.schema_status is GateStatus.PASSED
            and self.plan_semantic_status is PlanSemanticStatus.VALID
            and self.ambiguity_status is GateStatus.PASSED
            and self.safety_status is GateStatus.PASSED
            and self.authority_status is GateStatus.PASSED
        )

        if self.execution_eligible != mandatory_pass:
            raise ValueError(
                "execution_eligible must equal the conjunction of all mandatory gates"
            )
        if self.execution_eligible and self.final_decision is not FinalDecision.ACCEPT:
            raise ValueError("execution-eligible record must have final decision ACCEPT")
        if not self.execution_eligible and self.final_decision is FinalDecision.ACCEPT:
            raise ValueError("ACCEPT requires execution eligibility")

    def _validate_simulation(self) -> None:
        if self.execution_permit_id is not None and not self.execution_eligible:
            raise ValueError("execution permit requires execution eligibility")
        active_or_finished = self.simulation_status not in (
            SimulationStatus.NOT_REQUESTED,
            SimulationStatus.NOT_STARTED,
        )
        if active_or_finished:
            if not self.execution_eligible or self.execution_permit_id is None:
                raise ValueError(
                    "queued or executed simulation requires eligibility and a permit"
                )

    def _validate_latency(self) -> None:
        if self.total_pipeline_latency_ms < self.validation_latency_ms:
            raise ValueError("total latency cannot be less than validation latency")
        gate_total = sum(record.latency_ms for record in self.gate_latencies)
        if gate_total > self.validation_latency_ms + 0.001:
            raise ValueError("gate latency total cannot exceed validation latency")


class LegacyMetricReference(ContractModel):
    """Read-only description of legacy evidence without semantic conversion."""

    source_repository: str = Field(min_length=1)
    source_commit: str
    source_path: str = Field(min_length=1)
    source_sha256: str
    legacy_schema_version: str = Field(min_length=1)
    legacy_semantic_score: float | None = None
    legacy_semantic_valid: bool | None = None
    legacy_safety_valid: bool | None = None
    legacy_false_accept: bool | None = None
    semantic_metric_classification: Literal[
        "LEGACY_HYBRID_DECISION_SCORE"
    ] = LEGACY_SEMANTIC_METRIC
    v2_plan_semantic_status: Literal[
        "NOT_ASSESSABLE_MISSING_ORACLE"
    ] = PlanSemanticStatus.NOT_ASSESSABLE_MISSING_ORACLE
    v2_safety_status: Literal["NOT_ASSESSABLE"] = GateStatus.NOT_ASSESSABLE
    migration_warnings: tuple[str, ...] = (
        "LEGACY_SEMANTIC_FIELD_NOT_CONVERTED",
        "LEGACY_SAFETY_BOOLEAN_NOT_CONVERTED",
    )

    @field_validator("source_commit")
    @classmethod
    def source_commit_is_full_sha(cls, value: str) -> str:
        if not COMMIT_PATTERN.fullmatch(value):
            raise ValueError("source_commit must be a full 40-character Git SHA")
        return value.lower()

    @field_validator("source_sha256")
    @classmethod
    def source_hash_is_sha256(cls, value: str) -> str:
        if not SHA256_PATTERN.fullmatch(value):
            raise ValueError("source_sha256 must contain 64 hexadecimal characters")
        return value.lower()

    @field_validator("source_path")
    @classmethod
    def source_path_is_repository_relative(cls, value: str) -> str:
        normalised = value.replace("\\", "/")
        if normalised.startswith("/") or re.match(r"^[A-Za-z]:/", normalised):
            raise ValueError("source_path must be repository-relative")
        if any(part == ".." for part in normalised.split("/")):
            raise ValueError("source_path cannot escape the repository")
        return normalised


def build_legacy_metric_reference(
    payload: Mapping[str, Any],
    *,
    source_repository: str,
    source_commit: str,
    source_path: str,
    source_sha256: str,
    legacy_schema_version: str = "1.x",
) -> LegacyMetricReference:
    """Expose legacy fields while refusing to infer v2 semantic or safety status."""

    return LegacyMetricReference(
        source_repository=source_repository,
        source_commit=source_commit,
        source_path=source_path,
        source_sha256=source_sha256,
        legacy_schema_version=legacy_schema_version,
        legacy_semantic_score=payload.get("semantic_score"),
        legacy_semantic_valid=payload.get("semantic_valid"),
        legacy_safety_valid=payload.get("safety_valid"),
        legacy_false_accept=payload.get("false_accept"),
    )
