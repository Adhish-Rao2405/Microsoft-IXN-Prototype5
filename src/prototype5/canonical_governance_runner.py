"""Provider-neutral input-to-decision service for the integrated demonstrator."""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import Field, model_validator

from .foundry_sdk_backend import ModelBackendResponse, PlannerBackend
from .governance_contract_v2 import (
    ContractModel,
    CorrectnessStatus,
    DomainId,
    EvaluationMode,
    FallbackReason,
    FinalDecision,
    GateId,
    GateLatencyRecord,
    GateReasonRecord,
    GateStatus,
    GovernanceRecordV2,
    InferenceMode,
    InputMode,
    PlanSemanticStatus,
    ProvenanceRecordV2,
    ProviderId,
    RoutingRecordV2,
    SimulationStatus,
    TranscriptStatus,
)
from .manufacturing_policy_v2 import (
    LoadedManufacturingPolicyV2,
    ManufacturingPolicyEvaluationV2,
    ManufacturingSceneStateV2,
    RequesterContextV2,
    evaluate_manufacturing_proposal,
)
from .task_proposal_v2 import (
    StructuredTaskProposalV2,
    assess_structured_proposal,
)


class CanonicalGovernanceRequestV2(ContractModel):
    input_mode: InputMode
    typed_text: str | None = None
    transcript_text: str | None = None
    transcript_status: TranscriptStatus = TranscriptStatus.NOT_APPLICABLE
    transcript_backend: str | None = None
    transcript_confidence: float | None = Field(default=None, ge=0, le=1)
    audio_sha256: str | None = None

    domain_id: DomainId = DomainId.MANUFACTURING
    scene: ManufacturingSceneStateV2
    requester: RequesterContextV2
    requested_inference_mode: InferenceMode

    evaluation_mode: EvaluationMode = EvaluationMode.LIVE
    benchmark_id: str | None = None
    benchmark_sha256: str | None = None
    oracle_version: str | None = None
    oracle_sha256: str | None = None
    expected_decision: FinalDecision | None = None

    @model_validator(mode="after")
    def input_and_oracle_are_consistent(self) -> "CanonicalGovernanceRequestV2":
        if self.domain_id is not DomainId.MANUFACTURING:
            raise ValueError("A2.2 runner supports the manufacturing domain only")
        if self.input_mode is InputMode.TYPED:
            if not self.typed_text or not self.typed_text.strip():
                raise ValueError("typed input requires typed_text")
            if self.transcript_status is not TranscriptStatus.NOT_APPLICABLE:
                raise ValueError("typed input cannot define transcript status")
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
        else:
            if self.typed_text is not None:
                raise ValueError("voice input cannot define typed_text")
            if self.transcript_status is not TranscriptStatus.READY:
                raise ValueError(
                    "canonical planning accepts only a reviewed READY transcript"
                )
            if not self.transcript_text or not self.transcript_text.strip():
                raise ValueError("ready voice input requires transcript_text")
            if not self.transcript_backend or not self.transcript_backend.strip():
                raise ValueError("ready voice input requires transcript_backend")
            if not self.audio_sha256:
                raise ValueError("ready voice input requires audio_sha256")

        if self.evaluation_mode is EvaluationMode.LIVE:
            if any(
                value is not None
                for value in (
                    self.benchmark_id,
                    self.benchmark_sha256,
                    self.oracle_version,
                    self.oracle_sha256,
                    self.expected_decision,
                )
            ):
                raise ValueError("live mode cannot contain benchmark oracle fields")
        elif any(
            value is None
            for value in (
                self.benchmark_id,
                self.benchmark_sha256,
                self.oracle_version,
                self.oracle_sha256,
                self.expected_decision,
            )
        ):
            raise ValueError(
                "evaluation mode requires benchmark and oracle identifiers, hashes, "
                "and expected_decision"
            )
        return self

    @property
    def command(self) -> str:
        value = self.typed_text if self.input_mode is InputMode.TYPED else self.transcript_text
        if value is None:
            raise RuntimeError("validated canonical request has no command")
        return " ".join(value.split())


class CanonicalGovernanceResultV2(ContractModel):
    request: CanonicalGovernanceRequestV2
    raw_response_text: str | None
    proposal: StructuredTaskProposalV2 | None
    governance_record: GovernanceRecordV2


class CanonicalRunnerConfigurationV2(ContractModel):
    source_repository: str
    software_commit: str
    prompt_id: str
    prompt_version: str


class CanonicalGovernanceRunner:
    """Run one proposal through a single deterministic manufacturing gateway."""

    def __init__(
        self,
        *,
        policy: LoadedManufacturingPolicyV2,
        configuration: CanonicalRunnerConfigurationV2,
        clock: Callable[[], datetime] | None = None,
        timer: Callable[[], float] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.policy = policy
        self.configuration = configuration
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._timer = timer or time.perf_counter
        self._id_factory = id_factory or (lambda: str(uuid4()))

    def build_planner_context(
        self, request: CanonicalGovernanceRequestV2
    ) -> dict[str, Any]:
        """Build the one planner context shared by direct and hybrid routes."""

        return {
            "domain_id": request.domain_id.value,
            "scene": request.scene.model_dump(mode="json"),
            "requester": request.requester.model_dump(mode="json"),
            "policy_id": self.policy.config.policy_id,
            "policy_version": self.policy.config.policy_version,
            "prompt_id": self.configuration.prompt_id,
        }

    def run(
        self,
        request: CanonicalGovernanceRequestV2,
        *,
        backend: PlannerBackend,
        provider: ProviderId,
        model_id: str,
    ) -> CanonicalGovernanceResultV2:
        """Call one explicitly selected provider, then run the canonical gateway."""

        if request.requested_inference_mode is InferenceMode.AUTO:
            raise ValueError("AUTO routing belongs to HybridInferenceRouter")
        expected_provider = (
            ProviderId.FOUNDRY_LOCAL
            if request.requested_inference_mode is InferenceMode.LOCAL
            else ProviderId.CLOUD
        )
        if provider is not expected_provider:
            raise ValueError("provider must match the requested direct inference mode")
        if provider is ProviderId.NONE:
            raise ValueError("direct runner requires a concrete provider")

        start = self._timer()
        try:
            response = backend.generate(
                request.command,
                self.build_planner_context(request),
            )
        except Exception as exc:  # transport boundary must fail closed
            elapsed_ms = max(0.0, (self._timer() - start) * 1000.0)
            response = ModelBackendResponse(
                backend=provider.value,
                model_alias=model_id,
                prompt_id=self.configuration.prompt_id,
                raw_text=None,
                success=False,
                latency_ms=elapsed_ms,
                error_type=type(exc).__name__,
                error_message=str(exc),
                timestamp_utc=self._utc_now(),
            )
        else:
            elapsed_ms = max(0.0, (self._timer() - start) * 1000.0)

        observed_latency_ms = (
            response.latency_ms
            if response.latency_ms is not None
            else elapsed_ms
        )
        selected_model = response.model_alias or model_id
        route = RoutingRecordV2(
            requested_mode=request.requested_inference_mode,
            selected_provider=provider,
            selected_model=selected_model,
            local_attempted=provider is ProviderId.FOUNDRY_LOCAL,
            cloud_attempted=provider is ProviderId.CLOUD,
            fallback_triggered=False,
            fallback_reason=FallbackReason.NONE,
            local_latency_ms=(
                observed_latency_ms if provider is ProviderId.FOUNDRY_LOCAL else None
            ),
            cloud_latency_ms=(
                observed_latency_ms if provider is ProviderId.CLOUD else None
            ),
        )
        if response.latency_ms is None:
            response = ModelBackendResponse(
                backend=response.backend,
                model_alias=selected_model,
                prompt_id=response.prompt_id,
                raw_text=response.raw_text,
                success=response.success,
                latency_ms=observed_latency_ms,
                error_type=response.error_type,
                error_message=response.error_message,
                timestamp_utc=response.timestamp_utc,
            )
        return self.evaluate_response(request, response=response, routing=route)

    def evaluate_response(
        self,
        request: CanonicalGovernanceRequestV2,
        *,
        response: ModelBackendResponse,
        routing: RoutingRecordV2,
    ) -> CanonicalGovernanceResultV2:
        """Evaluate a final provider response selected by a direct or hybrid router."""

        if routing.requested_mode is not request.requested_inference_mode:
            raise ValueError("routing requested mode does not match the request")
        if (
            routing.selected_provider is not ProviderId.NONE
            and response.model_alias is not None
            and routing.selected_model != response.model_alias
        ):
            raise ValueError("routing model does not match the provider response")

        validation_start = self._timer()
        raw_text = response.raw_text
        raw_present = bool(raw_text and raw_text.strip())
        raw_sha256 = (
            hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
            if raw_present and raw_text is not None
            else None
        )

        gate_reasons: dict[GateId, tuple[str, ...]] = {}
        gate_latencies: list[GateLatencyRecord] = []
        proposal: StructuredTaskProposalV2 | None = None

        if not response.success:
            parse_status = GateStatus.ERROR
            json_status = GateStatus.NOT_ASSESSABLE
            schema_status = GateStatus.NOT_ASSESSABLE
            plan_semantic_status = PlanSemanticStatus.NOT_ASSESSABLE_NO_PROPOSAL
            ambiguity_status = GateStatus.NOT_ASSESSABLE
            safety_status = GateStatus.NOT_ASSESSABLE
            authority_status = GateStatus.NOT_ASSESSABLE
            gate_reasons[GateId.PARSE] = (
                _provider_failure_reason(response.error_type),
            )
        elif not raw_present:
            parse_status = GateStatus.FAILED
            json_status = GateStatus.NOT_ASSESSABLE
            schema_status = GateStatus.NOT_ASSESSABLE
            plan_semantic_status = PlanSemanticStatus.NOT_ASSESSABLE_NO_PROPOSAL
            ambiguity_status = GateStatus.NOT_ASSESSABLE
            safety_status = GateStatus.NOT_ASSESSABLE
            authority_status = GateStatus.NOT_ASSESSABLE
            gate_reasons[GateId.PARSE] = ("PROVIDER_RESPONSE_EMPTY",)
        else:
            (
                parse_status,
                json_status,
                schema_status,
                proposal,
                structural_reasons,
                structural_latencies,
            ) = self._parse_proposal(raw_text or "")
            gate_reasons.update(structural_reasons)
            gate_latencies.extend(structural_latencies)

            if proposal is None:
                if parse_status is GateStatus.FAILED:
                    plan_semantic_status = (
                        PlanSemanticStatus.NOT_ASSESSABLE_PARSE_FAILED
                    )
                else:
                    plan_semantic_status = (
                        PlanSemanticStatus.NOT_ASSESSABLE_SCHEMA_INVALID
                    )
                ambiguity_status = GateStatus.NOT_ASSESSABLE
                safety_status = GateStatus.NOT_ASSESSABLE
                authority_status = GateStatus.NOT_ASSESSABLE
            else:
                policy_start = self._timer()
                policy_result = evaluate_manufacturing_proposal(
                    request.command,
                    proposal,
                    request.scene,
                    request.requester,
                    self.policy.config,
                )
                policy_latency_ms = max(
                    0.0, (self._timer() - policy_start) * 1000.0
                )
                gate_latencies.append(
                    GateLatencyRecord(
                        gate=GateId.SEMANTICS, latency_ms=policy_latency_ms
                    )
                )
                (
                    plan_semantic_status,
                    ambiguity_status,
                    safety_status,
                    authority_status,
                ) = self._apply_policy_reasons(policy_result, gate_reasons)

        final_decision, decision_reasons = self._decide(
            parse_status=parse_status,
            json_status=json_status,
            schema_status=schema_status,
            semantic_status=plan_semantic_status,
            ambiguity_status=ambiguity_status,
            safety_status=safety_status,
            authority_status=authority_status,
            gate_reasons=gate_reasons,
        )
        execution_eligible = final_decision is FinalDecision.ACCEPT
        correctness = self._decision_correctness(request, final_decision)
        validation_latency_ms = max(
            sum(item.latency_ms for item in gate_latencies),
            (self._timer() - validation_start) * 1000.0,
        )
        provider_latency_ms = self._selected_provider_latency(routing)
        total_provider_latency = sum(
            value
            for value in (routing.local_latency_ms, routing.cloud_latency_ms)
            if value is not None
        )

        provenance = ProvenanceRecordV2(
            source_repository=self.configuration.source_repository,
            software_commit=self.configuration.software_commit,
            prompt_id=response.prompt_id or self.configuration.prompt_id,
            prompt_version=self.configuration.prompt_version,
            model_provider=routing.selected_provider,
            model_id=routing.selected_model,
            benchmark_sha256=request.benchmark_sha256,
            oracle_sha256=request.oracle_sha256,
            policy_sha256=self.policy.sha256,
        )
        record = GovernanceRecordV2(
            record_id=self._id_factory(),
            trace_id=self._id_factory(),
            timestamp_utc=self._utc_now(),
            evaluation_mode=request.evaluation_mode,
            input_mode=request.input_mode,
            normalised_command=request.command,
            typed_text=(
                request.typed_text if request.input_mode is InputMode.TYPED else None
            ),
            transcript_text=(
                request.transcript_text
                if request.input_mode is InputMode.VOICE
                else None
            ),
            transcript_status=request.transcript_status,
            transcript_backend=request.transcript_backend,
            transcript_confidence=request.transcript_confidence,
            audio_sha256=request.audio_sha256,
            domain_id=request.domain_id,
            benchmark_id=request.benchmark_id,
            policy_id=(
                f"{self.policy.config.policy_id}@"
                f"{self.policy.config.policy_version}"
            ),
            oracle_version=request.oracle_version,
            routing=routing,
            raw_response_sha256=raw_sha256,
            raw_response_present=raw_present,
            provider_latency_ms=provider_latency_ms,
            parse_status=parse_status,
            json_status=json_status,
            schema_status=schema_status,
            plan_semantic_status=plan_semantic_status,
            ambiguity_status=ambiguity_status,
            safety_status=safety_status,
            authority_status=authority_status,
            gate_reasons=tuple(
                GateReasonRecord(gate=gate, reason_codes=reasons)
                for gate, reasons in gate_reasons.items()
            ),
            gate_latencies=tuple(gate_latencies),
            expected_decision=request.expected_decision,
            decision_correctness_status=correctness,
            final_decision=final_decision,
            execution_eligible=execution_eligible,
            decision_reason_codes=decision_reasons,
            validation_latency_ms=validation_latency_ms,
            total_pipeline_latency_ms=total_provider_latency
            + validation_latency_ms,
            execution_permit_id=None,
            simulation_status=SimulationStatus.NOT_REQUESTED,
            provenance=provenance,
        )
        return CanonicalGovernanceResultV2(
            request=request,
            raw_response_text=raw_text,
            proposal=proposal,
            governance_record=record,
        )

    def _parse_proposal(
        self, raw_text: str
    ) -> tuple[
        GateStatus,
        GateStatus,
        GateStatus,
        StructuredTaskProposalV2 | None,
        dict[GateId, tuple[str, ...]],
        list[GateLatencyRecord],
    ]:
        reasons: dict[GateId, tuple[str, ...]] = {}
        start = self._timer()
        assessment = assess_structured_proposal(raw_text)
        elapsed = max(0.0, (self._timer() - start) * 1000.0)
        latency_gate = (
            GateId.SCHEMA
            if assessment.parse_status is GateStatus.PASSED
            and assessment.json_status is GateStatus.PASSED
            else GateId.PARSE
        )
        latencies = [
            GateLatencyRecord(gate=latency_gate, latency_ms=elapsed)
        ]

        if assessment.parse_status is GateStatus.FAILED:
            reasons[GateId.PARSE] = ("JSON_PARSE_FAILED",)
            if assessment.json_status is GateStatus.FAILED:
                reasons[GateId.JSON] = ("JSON_INVALID",)
        elif assessment.json_status is GateStatus.FAILED:
            reasons[GateId.JSON] = (
                assessment.reason_code or "JSON_INVALID",
            )
        elif assessment.schema_status is GateStatus.FAILED:
            reasons[GateId.SCHEMA] = (
                assessment.reason_code or "PROPOSAL_SCHEMA_INVALID",
            )
        return (
            assessment.parse_status,
            assessment.json_status,
            assessment.schema_status,
            assessment.proposal,
            reasons,
            latencies,
        )

    @staticmethod
    def _apply_policy_reasons(
        result: ManufacturingPolicyEvaluationV2,
        gate_reasons: dict[GateId, tuple[str, ...]],
    ) -> tuple[PlanSemanticStatus, GateStatus, GateStatus, GateStatus]:
        if result.semantic_reason_codes:
            gate_reasons[GateId.SEMANTICS] = result.semantic_reason_codes
        if result.ambiguity_reason_codes:
            gate_reasons[GateId.AMBIGUITY] = result.ambiguity_reason_codes
        if result.safety_reason_codes:
            gate_reasons[GateId.SAFETY] = result.safety_reason_codes
        if result.authority_reason_codes:
            gate_reasons[GateId.AUTHORITY] = result.authority_reason_codes
        return (
            result.plan_semantic_status,
            result.ambiguity_status,
            result.safety_status,
            result.authority_status,
        )

    @staticmethod
    def _decide(
        *,
        parse_status: GateStatus,
        json_status: GateStatus,
        schema_status: GateStatus,
        semantic_status: PlanSemanticStatus,
        ambiguity_status: GateStatus,
        safety_status: GateStatus,
        authority_status: GateStatus,
        gate_reasons: dict[GateId, tuple[str, ...]],
    ) -> tuple[FinalDecision, tuple[str, ...]]:
        structural = (parse_status, json_status, schema_status)
        if any(status is not GateStatus.PASSED for status in structural):
            return FinalDecision.ERROR, _flatten_reasons(
                gate_reasons, (GateId.PARSE, GateId.JSON, GateId.SCHEMA)
            )
        if safety_status is GateStatus.FAILED:
            return FinalDecision.REJECT, _with_fallback(
                gate_reasons.get(GateId.SAFETY), "SAFETY_POLICY_REJECTED"
            )
        if authority_status is GateStatus.FAILED:
            return FinalDecision.REJECT, _with_fallback(
                gate_reasons.get(GateId.AUTHORITY), "AUTHORITY_REJECTED"
            )
        if semantic_status is PlanSemanticStatus.INVALID:
            return FinalDecision.REJECT, _with_fallback(
                gate_reasons.get(GateId.SEMANTICS), "PLAN_SEMANTICS_INVALID"
            )
        if (
            ambiguity_status is GateStatus.FAILED
            or semantic_status
            is PlanSemanticStatus.NOT_ASSESSABLE_MISSING_REQUIRED_CONTEXT
        ):
            return FinalDecision.CLARIFY, _with_fallback(
                gate_reasons.get(GateId.AMBIGUITY), "CLARIFICATION_REQUIRED"
            )
        mandatory_pass = (
            semantic_status is PlanSemanticStatus.VALID
            and ambiguity_status is GateStatus.PASSED
            and safety_status is GateStatus.PASSED
            and authority_status is GateStatus.PASSED
        )
        if mandatory_pass:
            return FinalDecision.ACCEPT, ("ALL_REQUIRED_GATES_PASSED",)
        return FinalDecision.ERROR, ("GOVERNANCE_GATE_NOT_ASSESSABLE",)

    @staticmethod
    def _decision_correctness(
        request: CanonicalGovernanceRequestV2, actual: FinalDecision
    ) -> CorrectnessStatus:
        if request.evaluation_mode is EvaluationMode.LIVE:
            return CorrectnessStatus.NOT_EVALUATED
        return (
            CorrectnessStatus.CORRECT
            if actual is request.expected_decision
            else CorrectnessStatus.INCORRECT
        )

    @staticmethod
    def _selected_provider_latency(routing: RoutingRecordV2) -> float | None:
        if routing.selected_provider is ProviderId.FOUNDRY_LOCAL:
            return routing.local_latency_ms
        if routing.selected_provider is ProviderId.CLOUD:
            return routing.cloud_latency_ms
        return None

    def _utc_now(self) -> str:
        value = self._clock()
        if value.tzinfo is None:
            raise ValueError("runner clock must return a timezone-aware datetime")
        return value.astimezone(timezone.utc).isoformat()


def _flatten_reasons(
    reasons: dict[GateId, tuple[str, ...]], gates: tuple[GateId, ...]
) -> tuple[str, ...]:
    flattened = tuple(
        reason for gate in gates for reason in reasons.get(gate, ())
    )
    return flattened or ("STRUCTURED_PROPOSAL_UNAVAILABLE",)


def _with_fallback(values: tuple[str, ...] | None, fallback: str) -> tuple[str, ...]:
    return values or (fallback,)


def _provider_failure_reason(error_type: str | None) -> str:
    if error_type:
        candidate = error_type.strip().upper()
        valid = candidate and all(
            character.isalnum() or character == "_" for character in candidate
        )
        if valid and candidate.startswith(("LOCAL_", "CLOUD_", "VOICE_")):
            return candidate
    return "PROVIDER_REQUEST_FAILED"
