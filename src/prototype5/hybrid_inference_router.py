"""Local, cloud, and local-first routing without governance-policy shopping."""

from __future__ import annotations

import hashlib
import json
import math
import statistics
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path

from pydantic import Field

from .canonical_governance_runner import (
    CanonicalGovernanceRequestV2,
    CanonicalGovernanceResultV2,
    CanonicalGovernanceRunner,
)
from .foundry_sdk_backend import ModelBackendResponse, PlannerBackend
from .governance_contract_v2 import (
    ContractModel,
    FallbackReason,
    GateStatus,
    InferenceMode,
    ProviderId,
    RoutingRecordV2,
)
from .task_proposal_v2 import assess_structured_proposal


class CircuitState(StrEnum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class ProviderAvailabilityV2(ContractModel):
    available: bool
    model_ready: bool
    detail_code: str


class HybridRoutingPolicyV1(ContractModel):
    routing_policy_id: str
    routing_policy_version: str
    local_timeout_ms: int = Field(gt=0, le=300_000)
    local_max_consecutive_failures: int = Field(gt=0, le=20)
    local_circuit_open_seconds: int = Field(gt=0, le=3600)
    rolling_window_size: int = Field(ge=2, le=1000)
    minimum_structured_success_rate: float = Field(ge=0, le=1)
    maximum_local_p95_latency_ms: int = Field(gt=0, le=300_000)
    maximum_provider_attempts: int = Field(ge=1, le=1)


class LoadedHybridRoutingPolicyV1(ContractModel):
    config: HybridRoutingPolicyV1
    sha256: str


class LocalAttemptSampleV1(ContractModel):
    structured_success: bool
    route_success: bool
    latency_ms: float = Field(ge=0)
    failure_reason: FallbackReason


class LocalHealthSnapshotV1(ContractModel):
    circuit_state: CircuitState
    local_available: bool
    local_model_ready: bool
    consecutive_failures: int = Field(ge=0)
    rolling_sample_count: int = Field(ge=0)
    rolling_structured_success_rate: float | None = Field(default=None, ge=0, le=1)
    rolling_p50_latency_ms: float | None = Field(default=None, ge=0)
    rolling_p95_latency_ms: float | None = Field(default=None, ge=0)
    last_failure_reason: FallbackReason
    last_circuit_transition: str | None = None


class HybridGovernanceResultV1(ContractModel):
    routing_policy_id: str
    routing_policy_version: str
    routing_policy_sha256: str
    local_health: LocalHealthSnapshotV1
    canonical_result: CanonicalGovernanceResultV2


@dataclass(frozen=True)
class InferenceProviderBinding:
    provider_id: ProviderId
    model_id: str
    backend: PlannerBackend
    availability_probe: Callable[[], ProviderAvailabilityV2] | None = None

    def __post_init__(self) -> None:
        if self.provider_id not in (ProviderId.FOUNDRY_LOCAL, ProviderId.CLOUD):
            raise ValueError("provider binding must be local or cloud")
        if not self.model_id.strip():
            raise ValueError("provider binding requires model_id")
        if (
            self.provider_id is ProviderId.FOUNDRY_LOCAL
            and self.availability_probe is None
        ):
            raise ValueError("local provider requires an availability probe")


@dataclass
class _LocalHealthState:
    circuit_state: CircuitState = CircuitState.CLOSED
    consecutive_failures: int = 0
    opened_at: float | None = None
    last_failure_reason: FallbackReason = FallbackReason.NONE
    last_circuit_transition: str | None = None
    local_available: bool = True
    local_model_ready: bool = True


def load_hybrid_routing_policy(path: Path) -> LoadedHybridRoutingPolicyV1:
    raw = path.read_bytes()
    return LoadedHybridRoutingPolicyV1(
        config=HybridRoutingPolicyV1.model_validate(
            json.loads(raw.decode("utf-8"))
        ),
        sha256=hashlib.sha256(raw).hexdigest(),
    )


class HybridInferenceRouter:
    """Select a provider using operational evidence, then call one gateway."""

    def __init__(
        self,
        *,
        local: InferenceProviderBinding,
        cloud: InferenceProviderBinding,
        governance_runner: CanonicalGovernanceRunner,
        routing_policy: LoadedHybridRoutingPolicyV1,
        timer: Callable[[], float] | None = None,
        utc_clock: Callable[[], datetime] | None = None,
    ) -> None:
        if local.provider_id is not ProviderId.FOUNDRY_LOCAL:
            raise ValueError("local binding must use FOUNDRY_LOCAL")
        if cloud.provider_id is not ProviderId.CLOUD:
            raise ValueError("cloud binding must use CLOUD")
        self.local = local
        self.cloud = cloud
        self.governance_runner = governance_runner
        self.routing_policy = routing_policy
        self._timer = timer or time.monotonic
        self._utc_clock = utc_clock or (lambda: datetime.now(timezone.utc))
        self._state = _LocalHealthState()
        self._samples: deque[LocalAttemptSampleV1] = deque(
            maxlen=routing_policy.config.rolling_window_size
        )

    def route(
        self, request: CanonicalGovernanceRequestV2
    ) -> HybridGovernanceResultV1:
        if request.requested_inference_mode is InferenceMode.LOCAL:
            result = self._route_local_only(request)
        elif request.requested_inference_mode is InferenceMode.CLOUD:
            result = self._route_cloud_only(request)
        else:
            result = self._route_auto(request)
        return HybridGovernanceResultV1(
            routing_policy_id=self.routing_policy.config.routing_policy_id,
            routing_policy_version=self.routing_policy.config.routing_policy_version,
            routing_policy_sha256=self.routing_policy.sha256,
            local_health=self.local_health_snapshot(),
            canonical_result=result,
        )

    def local_health_snapshot(self) -> LocalHealthSnapshotV1:
        latencies = [sample.latency_ms for sample in self._samples]
        successes = sum(sample.structured_success for sample in self._samples)
        sample_count = len(self._samples)
        return LocalHealthSnapshotV1(
            circuit_state=self._state.circuit_state,
            local_available=self._state.local_available,
            local_model_ready=self._state.local_model_ready,
            consecutive_failures=self._state.consecutive_failures,
            rolling_sample_count=sample_count,
            rolling_structured_success_rate=(
                successes / sample_count if sample_count else None
            ),
            rolling_p50_latency_ms=(
                float(statistics.median(latencies)) if latencies else None
            ),
            rolling_p95_latency_ms=(
                _nearest_rank_percentile(latencies, 0.95) if latencies else None
            ),
            last_failure_reason=self._state.last_failure_reason,
            last_circuit_transition=self._state.last_circuit_transition,
        )

    def _route_local_only(
        self, request: CanonicalGovernanceRequestV2
    ) -> CanonicalGovernanceResultV2:
        preflight_reason = self._local_preflight()
        if preflight_reason is not None:
            return self._evaluate_skipped_direct(
                request,
                reason_code="LOCAL_BACKEND_UNAVAILABLE"
                if preflight_reason is FallbackReason.LOCAL_UNAVAILABLE
                else preflight_reason.value,
            )

        response = self._invoke(self.local, request)
        failure_reason = self._classify_local_failure(response)
        self._record_local_attempt(response, failure_reason)
        if failure_reason is not None and not response.success:
            response = _with_error_type(response, failure_reason.value)
        route = self._direct_route(request, self.local, response)
        return self.governance_runner.evaluate_response(
            request, response=response, routing=route
        )

    def _route_cloud_only(
        self, request: CanonicalGovernanceRequestV2
    ) -> CanonicalGovernanceResultV2:
        response = self._invoke(self.cloud, request)
        if not response.success:
            response = _with_error_type(
                response, _classify_cloud_failure(response)
            )
        route = self._direct_route(request, self.cloud, response)
        return self.governance_runner.evaluate_response(
            request, response=response, routing=route
        )

    def _route_auto(
        self, request: CanonicalGovernanceRequestV2
    ) -> CanonicalGovernanceResultV2:
        preflight_reason = self._local_preflight()
        if preflight_reason is not None:
            return self._fallback_to_cloud(
                request,
                reason=preflight_reason,
                local_attempted=False,
                local_latency_ms=None,
            )

        local_response = self._invoke(self.local, request)
        fallback_reason = self._classify_local_failure(local_response)
        self._record_local_attempt(local_response, fallback_reason)
        if fallback_reason is None:
            route = RoutingRecordV2(
                requested_mode=InferenceMode.AUTO,
                selected_provider=ProviderId.FOUNDRY_LOCAL,
                selected_model=local_response.model_alias or self.local.model_id,
                local_attempted=True,
                cloud_attempted=False,
                local_latency_ms=local_response.latency_ms,
            )
            return self.governance_runner.evaluate_response(
                request, response=local_response, routing=route
            )
        return self._fallback_to_cloud(
            request,
            reason=fallback_reason,
            local_attempted=True,
            local_latency_ms=local_response.latency_ms,
        )

    def _fallback_to_cloud(
        self,
        request: CanonicalGovernanceRequestV2,
        *,
        reason: FallbackReason,
        local_attempted: bool,
        local_latency_ms: float | None,
    ) -> CanonicalGovernanceResultV2:
        cloud_response = self._invoke(self.cloud, request)
        if not cloud_response.success:
            cloud_response = _with_error_type(
                cloud_response, _classify_cloud_failure(cloud_response)
            )
        route = RoutingRecordV2(
            requested_mode=InferenceMode.AUTO,
            selected_provider=ProviderId.CLOUD,
            selected_model=cloud_response.model_alias or self.cloud.model_id,
            local_attempted=local_attempted,
            cloud_attempted=True,
            fallback_triggered=True,
            fallback_reason=reason,
            local_latency_ms=local_latency_ms,
            cloud_latency_ms=cloud_response.latency_ms,
        )
        return self.governance_runner.evaluate_response(
            request, response=cloud_response, routing=route
        )

    def _evaluate_skipped_direct(
        self,
        request: CanonicalGovernanceRequestV2,
        *,
        reason_code: str,
    ) -> CanonicalGovernanceResultV2:
        response = ModelBackendResponse(
            backend=ProviderId.NONE.value,
            model_alias=None,
            prompt_id=self.governance_runner.configuration.prompt_id,
            raw_text=None,
            success=False,
            latency_ms=None,
            error_type=reason_code,
            error_message=reason_code,
            timestamp_utc=self._utc_now(),
        )
        route = RoutingRecordV2(
            requested_mode=request.requested_inference_mode,
            selected_provider=ProviderId.NONE,
            selected_model=None,
            local_attempted=False,
            cloud_attempted=False,
        )
        return self.governance_runner.evaluate_response(
            request, response=response, routing=route
        )

    def _direct_route(
        self,
        request: CanonicalGovernanceRequestV2,
        binding: InferenceProviderBinding,
        response: ModelBackendResponse,
    ) -> RoutingRecordV2:
        return RoutingRecordV2(
            requested_mode=request.requested_inference_mode,
            selected_provider=binding.provider_id,
            selected_model=response.model_alias or binding.model_id,
            local_attempted=binding.provider_id is ProviderId.FOUNDRY_LOCAL,
            cloud_attempted=binding.provider_id is ProviderId.CLOUD,
            local_latency_ms=(
                response.latency_ms
                if binding.provider_id is ProviderId.FOUNDRY_LOCAL
                else None
            ),
            cloud_latency_ms=(
                response.latency_ms
                if binding.provider_id is ProviderId.CLOUD
                else None
            ),
        )

    def _invoke(
        self,
        binding: InferenceProviderBinding,
        request: CanonicalGovernanceRequestV2,
    ) -> ModelBackendResponse:
        started = self._timer()
        context = self.governance_runner.build_planner_context(request)
        context.update(
            {
                "routing_policy_id": self.routing_policy.config.routing_policy_id,
            }
        )
        if binding.provider_id is ProviderId.FOUNDRY_LOCAL:
            context["request_timeout_ms"] = (
                self.routing_policy.config.local_timeout_ms
            )
        try:
            response = binding.backend.generate(request.command, context)
        except Exception as exc:  # provider boundary fails closed
            elapsed_ms = max(0.0, (self._timer() - started) * 1000.0)
            prefix = "LOCAL" if binding.provider_id is ProviderId.FOUNDRY_LOCAL else "CLOUD"
            return ModelBackendResponse(
                backend=binding.provider_id.value,
                model_alias=binding.model_id,
                prompt_id=self.governance_runner.configuration.prompt_id,
                raw_text=None,
                success=False,
                latency_ms=elapsed_ms,
                error_type=f"{prefix}_TRANSPORT_ERROR",
                error_message=f"{type(exc).__name__}: {exc}",
                timestamp_utc=self._utc_now(),
            )
        elapsed_ms = max(0.0, (self._timer() - started) * 1000.0)
        return ModelBackendResponse(
            backend=response.backend,
            model_alias=response.model_alias or binding.model_id,
            prompt_id=response.prompt_id,
            raw_text=response.raw_text,
            success=response.success,
            latency_ms=(
                response.latency_ms
                if response.latency_ms is not None
                else elapsed_ms
            ),
            error_type=response.error_type,
            error_message=response.error_message,
            timestamp_utc=response.timestamp_utc,
        )

    def _local_preflight(self) -> FallbackReason | None:
        probe = self.local.availability_probe
        if probe is None:
            raise RuntimeError("validated local binding has no availability probe")
        try:
            availability = probe()
        except Exception:
            availability = ProviderAvailabilityV2(
                available=False,
                model_ready=False,
                detail_code="LOCAL_HEALTH_PROBE_ERROR",
            )
        self._state.local_available = availability.available
        self._state.local_model_ready = availability.model_ready
        if not availability.available:
            self._state.last_failure_reason = FallbackReason.LOCAL_UNAVAILABLE
            return FallbackReason.LOCAL_UNAVAILABLE
        if not availability.model_ready:
            self._state.last_failure_reason = FallbackReason.LOCAL_MODEL_NOT_READY
            return FallbackReason.LOCAL_MODEL_NOT_READY

        now = self._timer()
        if self._state.circuit_state is CircuitState.OPEN:
            opened_at = self._state.opened_at
            elapsed = now - opened_at if opened_at is not None else 0.0
            if elapsed < self.routing_policy.config.local_circuit_open_seconds:
                self._state.last_failure_reason = FallbackReason.LOCAL_CIRCUIT_OPEN
                return FallbackReason.LOCAL_CIRCUIT_OPEN
            self._transition(CircuitState.HALF_OPEN, "OPEN_TO_HALF_OPEN")

        if (
            self._state.circuit_state is CircuitState.CLOSED
            and len(self._samples) == self._samples.maxlen
        ):
            snapshot = self.local_health_snapshot()
            if (
                snapshot.rolling_structured_success_rate is not None
                and snapshot.rolling_structured_success_rate
                < self.routing_policy.config.minimum_structured_success_rate
            ):
                self._open_circuit(
                    FallbackReason.LOCAL_ROLLING_RELIABILITY_BELOW_THRESHOLD,
                    "CLOSED_TO_OPEN_ROLLING_RELIABILITY",
                )
                return FallbackReason.LOCAL_ROLLING_RELIABILITY_BELOW_THRESHOLD
            if (
                snapshot.rolling_p95_latency_ms is not None
                and snapshot.rolling_p95_latency_ms
                > self.routing_policy.config.maximum_local_p95_latency_ms
            ):
                self._open_circuit(
                    FallbackReason.LOCAL_LATENCY_THRESHOLD_EXCEEDED,
                    "CLOSED_TO_OPEN_P95_LATENCY",
                )
                return FallbackReason.LOCAL_LATENCY_THRESHOLD_EXCEEDED
        return None

    def _classify_local_failure(
        self, response: ModelBackendResponse
    ) -> FallbackReason | None:
        error_type = (response.error_type or "").casefold()
        if "timeout" in error_type:
            return FallbackReason.LOCAL_TIMEOUT
        if not response.success:
            if "empty" in error_type:
                return FallbackReason.LOCAL_EMPTY_RESPONSE
            if any(
                marker in error_type
                for marker in (
                    "missing_base_url",
                    "endpoint_unavailable",
                    "unavailable",
                    "connection",
                )
            ):
                return FallbackReason.LOCAL_UNAVAILABLE
            if any(
                marker in error_type
                for marker in (
                    "bad_model_alias",
                    "empty_model_list",
                    "no_preferred_model",
                    "model_not_ready",
                )
            ):
                return FallbackReason.LOCAL_MODEL_NOT_READY
            return FallbackReason.LOCAL_TRANSPORT_ERROR
        if response.raw_text is None or not response.raw_text.strip():
            return FallbackReason.LOCAL_EMPTY_RESPONSE
        latency_ms = response.latency_ms or 0.0
        if latency_ms > self.routing_policy.config.local_timeout_ms:
            return FallbackReason.LOCAL_TIMEOUT
        assessment = assess_structured_proposal(response.raw_text)
        if assessment.parse_status is not GateStatus.PASSED:
            return FallbackReason.LOCAL_PARSE_FAILURE
        if assessment.json_status is not GateStatus.PASSED:
            return FallbackReason.LOCAL_JSON_FAILURE
        if assessment.schema_status is not GateStatus.PASSED:
            return FallbackReason.LOCAL_SCHEMA_FAILURE
        if (
            latency_ms
            > self.routing_policy.config.maximum_local_p95_latency_ms
        ):
            return FallbackReason.LOCAL_LATENCY_THRESHOLD_EXCEEDED
        return None

    def _record_local_attempt(
        self,
        response: ModelBackendResponse,
        failure_reason: FallbackReason | None,
    ) -> None:
        route_success = failure_reason is None
        structural_success = _is_structurally_successful(response)
        sample = LocalAttemptSampleV1(
            structured_success=structural_success,
            route_success=route_success,
            latency_ms=response.latency_ms or 0.0,
            failure_reason=failure_reason or FallbackReason.NONE,
        )
        if self._state.circuit_state is CircuitState.HALF_OPEN and route_success:
            self._samples.clear()
            self._state.consecutive_failures = 0
            self._state.last_failure_reason = FallbackReason.NONE
            self._transition(CircuitState.CLOSED, "HALF_OPEN_TO_CLOSED")
        self._samples.append(sample)
        if route_success:
            self._state.consecutive_failures = 0
            self._state.last_failure_reason = FallbackReason.NONE
            return

        self._state.consecutive_failures += 1
        self._state.last_failure_reason = failure_reason or FallbackReason.NONE
        if (
            self._state.circuit_state is CircuitState.HALF_OPEN
            or self._state.consecutive_failures
            >= self.routing_policy.config.local_max_consecutive_failures
        ):
            self._open_circuit(
                failure_reason or FallbackReason.LOCAL_TRANSPORT_ERROR,
                (
                    "HALF_OPEN_TO_OPEN"
                    if self._state.circuit_state is CircuitState.HALF_OPEN
                    else "CLOSED_TO_OPEN_CONSECUTIVE_FAILURES"
                ),
            )

    def _open_circuit(
        self, reason: FallbackReason, transition: str
    ) -> None:
        self._state.last_failure_reason = reason
        self._state.opened_at = self._timer()
        self._transition(CircuitState.OPEN, transition)

    def _transition(self, state: CircuitState, label: str) -> None:
        self._state.circuit_state = state
        self._state.last_circuit_transition = label

    def _utc_now(self) -> str:
        value = self._utc_clock()
        if value.tzinfo is None:
            raise ValueError("router UTC clock must be timezone-aware")
        return value.astimezone(timezone.utc).isoformat()


def _nearest_rank_percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile * len(ordered)))
    return float(ordered[rank - 1])


def _with_error_type(
    response: ModelBackendResponse, error_type: str
) -> ModelBackendResponse:
    return ModelBackendResponse(
        backend=response.backend,
        model_alias=response.model_alias,
        prompt_id=response.prompt_id,
        raw_text=response.raw_text,
        success=False,
        latency_ms=response.latency_ms,
        error_type=error_type,
        error_message=response.error_message,
        timestamp_utc=response.timestamp_utc,
    )


def _classify_cloud_failure(response: ModelBackendResponse) -> str:
    error_type = (response.error_type or "").casefold()
    if "auth" in error_type or "401" in error_type or "403" in error_type:
        return "CLOUD_AUTHENTICATION_FAILED"
    if "timeout" in error_type:
        return "CLOUD_TIMEOUT"
    return "CLOUD_BACKEND_UNAVAILABLE"


def _is_structurally_successful(response: ModelBackendResponse) -> bool:
    if not response.success:
        return False
    assessment = assess_structured_proposal(response.raw_text)
    return all(
        status is GateStatus.PASSED
        for status in (
            assessment.parse_status,
            assessment.json_status,
            assessment.schema_status,
        )
    )
