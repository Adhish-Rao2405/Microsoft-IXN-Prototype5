"""D4.3 typed versus operator-reviewed voice modality invariance tests.

These controlled tests begin after speech recognition. They use the existing
test-scoped deterministic raw-proposal backend and the normal public service
seams. They do not evaluate a microphone, Nemotron, ASR accuracy, model
stochasticity, or physical execution.
"""

from __future__ import annotations

import hashlib
import json
import types
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from itertools import count
from pathlib import Path
from threading import Barrier, Lock
from typing import Any, Union, get_args, get_origin

import pytest
from pydantic import BaseModel, ValidationError

from src.prototype5.canonical_governance_runner import (
    CanonicalGovernanceRequestV2,
    CanonicalGovernanceRunner,
    CanonicalRunnerConfigurationV2,
)
from src.prototype5.demo_service import (
    DemoApplicationService,
    TranscriptNotReadyError,
    TypedCommandApiRequest,
    VoiceCommandApiRequest,
)
from src.prototype5.execution_session import ExecutionSessionRegistry
from src.prototype5.foundry_sdk_backend import ModelBackendResponse
from src.prototype5.governance_contract_v2 import (
    InferenceMode,
    ProviderId,
    TranscriptStatus,
)
from src.prototype5.hybrid_inference_router import (
    HybridGovernanceResultV1,
    HybridInferenceRouter,
    InferenceProviderBinding,
    ProviderAvailabilityV2,
    load_hybrid_routing_policy,
)
from src.prototype5.manufacturing_policy_v2 import load_manufacturing_policy
from src.prototype5.recorded_speech import (
    NEMOTRON_SPEECH_EXECUTION_PROVIDER,
    NEMOTRON_SPEECH_MODEL_ID,
    NEMOTRON_TRANSCRIPT_BACKEND,
    QUALIFIED_FOUNDRY_CORE_VERSION,
    QUALIFIED_FOUNDRY_SDK_VERSION,
    RecordedAudioMetadataV1,
    RecordedTranscriptionResultV1,
)
from tests.prototype5.d2_3_e2e_server import DeterministicRawProposalBackend


ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = ROOT / "configs" / "prototype5" / "d4_3_modality_invariance_matrix_v1.json"
SCENARIO_PATH = ROOT / "configs" / "prototype5" / "final_demo_scenarios_v1.json"
POLICY_PATH = ROOT / "configs" / "prototype5" / "manufacturing_policy_v2.json"
ROUTING_POLICY_PATH = ROOT / "configs" / "prototype5" / "hybrid_routing_policy_v1.json"
FROZEN_D4_2_SHA = "f8d8894e2c6fd7d1076da02ecef3018b04a5f9fa"
FIXED_TIME = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)
CONTROLLED_AUDIO_SHA256 = "a" * 64

CLAIM_BOUNDARY = {
    "evaluates_real_microphone": False,
    "evaluates_real_nemotron": False,
    "evaluates_asr_accuracy": False,
    "evaluates_model_stochasticity": False,
    "evaluates_physical_execution": False,
}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


MATRIX = _load_json(MATRIX_PATH)
SCENARIO_CONTRACT = _load_json(SCENARIO_PATH)
SCENARIOS = {
    scenario["scenario_id"]: scenario
    for scenario in SCENARIO_CONTRACT["scenario_contract"]["scenarios"]
}
PAIR_CASES = tuple(
    {
        **condition,
        "pair_id": f"{condition['condition_id']}__{mode}",
        "routing_mode": mode,
    }
    for condition in MATRIX["conditions"]
    for mode in MATRIX["routing_modes"]
)


class _MutableClock:
    def __init__(self) -> None:
        self.now = FIXED_TIME

    def __call__(self) -> datetime:
        return self.now


class _ObservedDeterministicBackend(DeterministicRawProposalBackend):
    """Observed wrapper around the existing network-free D2.3 provider seam."""

    def __init__(
        self,
        provider: ProviderId,
        model_id: str,
        *,
        failure: Exception | None = None,
    ) -> None:
        super().__init__(provider, model_id)
        self.failure = failure
        self.invocation_count = 0
        self.network_call_count = 0
        self.commands: list[str] = []
        self.contexts: list[dict[str, object] | None] = []
        self._lock = Lock()

    def generate(
        self,
        command: str,
        context: dict[str, object] | None = None,
    ) -> ModelBackendResponse:
        with self._lock:
            self.invocation_count += 1
            self.commands.append(command)
            self.contexts.append(context)
        if self.failure is not None:
            raise self.failure
        return super().generate(command, context)


class _ControlledTranscriber:
    """Controlled transcription fixture; not real speech or Nemotron evidence."""

    def __init__(
        self,
        *,
        transcription_id: str,
        transcript_text: str,
        transcript_status: TranscriptStatus = TranscriptStatus.READY,
        clock: _MutableClock,
    ) -> None:
        self.transcription_id = transcription_id
        self.transcript_text = transcript_text
        self.transcript_status = transcript_status
        self.clock = clock
        self.invocation_count = 0

    @property
    def is_worker_configured(self) -> bool:
        return True

    def transcribe_wav(
        self,
        audio_bytes: bytes,
        *,
        original_filename: str,
    ) -> RecordedTranscriptionResultV1:
        self.invocation_count += 1
        return RecordedTranscriptionResultV1(
            transcription_id=self.transcription_id,
            timestamp_utc=self.clock().isoformat(),
            transcript_status=self.transcript_status,
            transcript_text=self.transcript_text,
            transcript_backend=NEMOTRON_TRANSCRIPT_BACKEND,
            transcript_confidence=0.9,
            audio=RecordedAudioMetadataV1(
                original_filename=original_filename,
                audio_sha256=CONTROLLED_AUDIO_SHA256,
                audio_bytes=len(audio_bytes),
                sample_rate_hz=16_000,
                channels=1,
                bits_per_sample=16,
                frame_count=1,
                duration_ms=1.0,
            ),
            resolved_model_id=NEMOTRON_SPEECH_MODEL_ID,
            execution_provider=NEMOTRON_SPEECH_EXECUTION_PROVIDER,
            sdk_version=QUALIFIED_FOUNDRY_SDK_VERSION,
            core_version=QUALIFIED_FOUNDRY_CORE_VERSION,
            model_cached_before=True,
            model_loaded_before=True,
            segment_count=1,
            transcription_latency_ms=1.0,
            error_code=(
                "TRANSCRIPTION_PARTIAL"
                if self.transcript_status is TranscriptStatus.PARTIAL
                else None
            ),
        )


@dataclass
class _Harness:
    service: DemoApplicationService
    router: HybridInferenceRouter
    local_backend: _ObservedDeterministicBackend
    cloud_backend: _ObservedDeterministicBackend
    transcriber: _ControlledTranscriber
    clock: _MutableClock
    initial_operational_projection: dict[str, Any]


def _build_harness(
    *,
    raw_transcript: str,
    transcription_id: str,
    transcript_status: TranscriptStatus = TranscriptStatus.READY,
    transcript_ttl_seconds: int = 600,
    provider_failure: Exception | None = None,
) -> _Harness:
    clock = _MutableClock()
    record_ids = count(1)
    execution_ids = count(1)
    local_model = "d4-3-deterministic-local-model"
    cloud_model = "d4-3-deterministic-cloud-model"
    local_backend = _ObservedDeterministicBackend(
        ProviderId.FOUNDRY_LOCAL,
        local_model,
        failure=provider_failure,
    )
    cloud_backend = _ObservedDeterministicBackend(
        ProviderId.CLOUD,
        cloud_model,
        failure=provider_failure,
    )
    runner = CanonicalGovernanceRunner(
        policy=load_manufacturing_policy(POLICY_PATH),
        configuration=CanonicalRunnerConfigurationV2(
            source_repository="Adhish-Rao2405/Microsoft-IXN-Prototype5",
            software_commit=FROZEN_D4_2_SHA,
            prompt_id="prototype5_integrated_demo_v2",
            prompt_version="2.0.0",
        ),
        clock=clock,
        timer=lambda: 0.0,
        id_factory=lambda: f"d4-3-record-{next(record_ids)}",
    )
    router = HybridInferenceRouter(
        local=InferenceProviderBinding(
            provider_id=ProviderId.FOUNDRY_LOCAL,
            model_id=local_model,
            backend=local_backend,
            availability_probe=lambda: ProviderAvailabilityV2(
                available=True,
                model_ready=True,
                detail_code="D4_3_CONTROLLED_READY",
            ),
        ),
        cloud=InferenceProviderBinding(
            provider_id=ProviderId.CLOUD,
            model_id=cloud_model,
            backend=cloud_backend,
        ),
        governance_runner=runner,
        routing_policy=load_hybrid_routing_policy(ROUTING_POLICY_PATH),
        timer=lambda: 0.0,
        utc_clock=clock,
    )
    transcriber = _ControlledTranscriber(
        transcription_id=transcription_id,
        transcript_text=raw_transcript,
        transcript_status=transcript_status,
        clock=clock,
    )
    service = DemoApplicationService(
        router=router,
        software_commit=FROZEN_D4_2_SHA,
        cloud_configured=True,
        speech_transcriber=transcriber,
        transcript_ttl_seconds=transcript_ttl_seconds,
        utc_clock=clock,
        execution_registry=ExecutionSessionRegistry(
            secret=b"d4-3-deterministic-execution-secret",
            utc_clock=clock,
            id_factory=lambda: f"d4-3-execution-{next(execution_ids)}",
        ),
    )
    return _Harness(
        service=service,
        router=router,
        local_backend=local_backend,
        cloud_backend=cloud_backend,
        transcriber=transcriber,
        clock=clock,
        initial_operational_projection=_p5_router_operational_control_projection(
            router.local_health_snapshot().model_dump(mode="json")
        ),
    )


def _normalised_command(request: dict[str, Any]) -> str:
    command = request["typed_text"] if request["input_mode"] == "TYPED" else request["transcript_text"]
    assert isinstance(command, str)
    return " ".join(command.split())


def _scenario_replay_projection(
    service: DemoApplicationService,
    scenario_id: str,
) -> dict[str, str]:
    matches = tuple(
        scenario
        for scenario in service.manifest().scenarios
        if scenario.scenario_id == scenario_id
    )
    assert len(matches) == 1
    scenario = matches[0]
    return {
        "replay_policy_scenario_id": scenario.scenario_id,
        "qualification_replay_access": scenario.qualification_replay_access,
    }


def _p1_canonical_governance_input_projection(result: dict[str, Any]) -> dict[str, Any]:
    request = result["canonical_result"]["request"]
    return {
        "normalised_command": _normalised_command(request),
        "domain_id": request["domain_id"],
        "scene": request["scene"],
        "requester": request["requester"],
        "requested_inference_mode": request["requested_inference_mode"],
        "evaluation_mode": request["evaluation_mode"],
        "benchmark_id": request["benchmark_id"],
        "benchmark_sha256": request["benchmark_sha256"],
        "oracle_version": request["oracle_version"],
        "oracle_sha256": request["oracle_sha256"],
        "expected_decision": request["expected_decision"],
    }


def _p2_provider_proposal_control_projection(result: dict[str, Any]) -> dict[str, Any]:
    canonical = result["canonical_result"]
    record = canonical["governance_record"]
    routing = record["routing"]
    return {
        "requested_mode": routing["requested_mode"],
        "selected_provider": routing["selected_provider"],
        "selected_model": routing["selected_model"],
        "local_attempted": routing["local_attempted"],
        "cloud_attempted": routing["cloud_attempted"],
        "fallback_triggered": routing["fallback_triggered"],
        "fallback_reason": routing["fallback_reason"],
        "raw_response_text": canonical["raw_response_text"],
        "raw_response_sha256": record["raw_response_sha256"],
        "raw_response_present": record["raw_response_present"],
        "proposal": canonical["proposal"],
        "model_provider": record["provenance"]["model_provider"],
        "model_id": record["provenance"]["model_id"],
    }


def _p3_governance_outcome_projection(result: dict[str, Any]) -> dict[str, Any]:
    record = result["canonical_result"]["governance_record"]
    return {
        "normalised_command": record["normalised_command"],
        "evaluation_mode": record["evaluation_mode"],
        "domain_id": record["domain_id"],
        "benchmark_id": record["benchmark_id"],
        "policy_id": record["policy_id"],
        "oracle_version": record["oracle_version"],
        "evidence_schema_version": record["evidence_schema_version"],
        "parse_status": record["parse_status"],
        "json_status": record["json_status"],
        "schema_status": record["schema_status"],
        "plan_semantic_status": record["plan_semantic_status"],
        "ambiguity_status": record["ambiguity_status"],
        "safety_status": record["safety_status"],
        "authority_status": record["authority_status"],
        "gate_reasons": record["gate_reasons"],
        "expected_decision": record["expected_decision"],
        "decision_correctness_status": record["decision_correctness_status"],
        "final_decision": record["final_decision"],
        "execution_eligible": record["execution_eligible"],
        "decision_reason_codes": record["decision_reason_codes"],
        "stable_provenance": {
            "source_repository": record["provenance"]["source_repository"],
            "software_commit": record["provenance"]["software_commit"],
            "prompt_id": record["provenance"]["prompt_id"],
            "prompt_version": record["provenance"]["prompt_version"],
            "benchmark_sha256": record["provenance"]["benchmark_sha256"],
            "oracle_sha256": record["provenance"]["oracle_sha256"],
            "policy_sha256": record["provenance"]["policy_sha256"],
        },
    }


def _p4_authority_projection(
    result: dict[str, Any], service: DemoApplicationService, *, scenario_id: str
) -> dict[str, Any]:
    record = result["canonical_result"]["governance_record"]
    execution_state = service.execution_state(record["trace_id"])
    assert execution_state is not None
    manifest = service.manifest()
    replay_projection = _scenario_replay_projection(service, scenario_id)
    return {
        "governance_execution_eligible": record["execution_eligible"],
        "governance_execution_permit_id": record["execution_permit_id"],
        "governance_simulation_status": record["simulation_status"],
        "session_execution_eligible": execution_state.execution_eligible,
        "session_permit_state": execution_state.permit_state.value,
        "session_permit_id": execution_state.permit_id,
        "session_simulation_status": execution_state.simulation_status.value,
        **replay_projection,
        "physical_execution_authority": manifest.physical_execution_authority_state,
    }


def _p5_router_operational_control_projection(health: dict[str, Any]) -> dict[str, Any]:
    return {
        "circuit_state": health["circuit_state"],
        "local_available": health["local_available"],
        "local_model_ready": health["local_model_ready"],
        "consecutive_failures": health["consecutive_failures"],
        "rolling_sample_count": health["rolling_sample_count"],
        "rolling_structured_success_rate": health["rolling_structured_success_rate"],
        "rolling_p50_latency_ms": health["rolling_p50_latency_ms"],
        "rolling_p95_latency_ms": health["rolling_p95_latency_ms"],
        "last_failure_reason": health["last_failure_reason"],
        "last_circuit_transition": health["last_circuit_transition"],
    }


P1_CANONICAL_GOVERNANCE_INPUT_PROJECTION = _p1_canonical_governance_input_projection
P2_PROVIDER_PROPOSAL_CONTROL_PROJECTION = _p2_provider_proposal_control_projection
P3_GOVERNANCE_OUTCOME_PROJECTION = _p3_governance_outcome_projection
P4_AUTHORITY_PROJECTION = _p4_authority_projection
P5_ROUTER_OPERATIONAL_CONTROL_PROJECTION = _p5_router_operational_control_projection


def _model_leaf_paths(model: type[BaseModel], prefix: str = "") -> set[str]:
    leaves: set[str] = set()
    for name, field in model.model_fields.items():
        path = f"{prefix}.{name}" if prefix else name
        leaves.update(_annotation_leaf_paths(field.annotation, path))
    return leaves


def _annotation_leaf_paths(annotation: Any, path: str) -> set[str]:
    origin = get_origin(annotation)
    if origin in (Union, types.UnionType):
        variants = tuple(value for value in get_args(annotation) if value is not type(None))
        nested = [value for value in variants if isinstance(value, type) and issubclass(value, BaseModel)]
        if len(nested) == 1:
            return _model_leaf_paths(nested[0], path)
        return {path}
    if origin in (tuple, list, set, frozenset):
        element = get_args(annotation)[0]
        item_path = f"{path}[*]"
        if isinstance(element, type) and issubclass(element, BaseModel):
            return _model_leaf_paths(element, item_path)
        return {item_path}
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return _model_leaf_paths(annotation, path)
    return {path}


CANONICAL_SEMANTIC_LEAF_PATHS = {
    "domain_id",
    "scene.scene_id",
    "scene.state_version",
    "scene.objects[*].object_id",
    "scene.objects[*].location_id",
    "scene.human_obstruction",
    "scene.safety_interlock_enabled",
    "requester.requester_id",
    "requester.role",
    "requested_inference_mode",
    "evaluation_mode",
    "benchmark_id",
    "benchmark_sha256",
    "oracle_version",
    "oracle_sha256",
    "expected_decision",
}
CANONICAL_MODALITY_PROVENANCE_LEAF_PATHS = {
    "input_mode",
    "typed_text",
    "transcription_id",
    "original_transcript_text",
    "transcript_text",
    "transcript_status",
    "transcript_backend",
    "transcript_confidence",
    "audio_sha256",
}

RESULT_P1_LEAF_PATHS = {
    f"canonical_result.request.{path}" for path in CANONICAL_SEMANTIC_LEAF_PATHS
}
RESULT_P2_LEAF_PATHS = {
    "canonical_result.raw_response_text",
    "canonical_result.proposal.actions[*].action",
    "canonical_result.proposal.actions[*].object_id",
    "canonical_result.proposal.actions[*].source_id",
    "canonical_result.proposal.actions[*].destination_id",
    "canonical_result.proposal.actions[*].duration_ms",
    "canonical_result.governance_record.routing.requested_mode",
    "canonical_result.governance_record.routing.selected_provider",
    "canonical_result.governance_record.routing.selected_model",
    "canonical_result.governance_record.routing.local_attempted",
    "canonical_result.governance_record.routing.cloud_attempted",
    "canonical_result.governance_record.routing.fallback_triggered",
    "canonical_result.governance_record.routing.fallback_reason",
    "canonical_result.governance_record.raw_response_sha256",
    "canonical_result.governance_record.raw_response_present",
    "canonical_result.governance_record.provenance.model_provider",
    "canonical_result.governance_record.provenance.model_id",
}
RESULT_P3_LEAF_PATHS = {
    "canonical_result.governance_record.evaluation_mode",
    "canonical_result.governance_record.normalised_command",
    "canonical_result.governance_record.domain_id",
    "canonical_result.governance_record.benchmark_id",
    "canonical_result.governance_record.policy_id",
    "canonical_result.governance_record.oracle_version",
    "canonical_result.governance_record.evidence_schema_version",
    "canonical_result.governance_record.parse_status",
    "canonical_result.governance_record.json_status",
    "canonical_result.governance_record.schema_status",
    "canonical_result.governance_record.plan_semantic_status",
    "canonical_result.governance_record.ambiguity_status",
    "canonical_result.governance_record.safety_status",
    "canonical_result.governance_record.authority_status",
    "canonical_result.governance_record.gate_reasons[*].gate",
    "canonical_result.governance_record.gate_reasons[*].reason_codes[*]",
    "canonical_result.governance_record.expected_decision",
    "canonical_result.governance_record.decision_correctness_status",
    "canonical_result.governance_record.final_decision",
    "canonical_result.governance_record.execution_eligible",
    "canonical_result.governance_record.decision_reason_codes[*]",
    "canonical_result.governance_record.provenance.source_repository",
    "canonical_result.governance_record.provenance.software_commit",
    "canonical_result.governance_record.provenance.prompt_id",
    "canonical_result.governance_record.provenance.prompt_version",
    "canonical_result.governance_record.provenance.benchmark_sha256",
    "canonical_result.governance_record.provenance.oracle_sha256",
    "canonical_result.governance_record.provenance.policy_sha256",
}
RESULT_P4_LEAF_PATHS = {
    "canonical_result.governance_record.execution_permit_id",
    "canonical_result.governance_record.simulation_status",
}
RESULT_P5_OPERATIONAL_LEAF_PATHS = {
    "routing_policy_id",
    "routing_policy_version",
    "routing_policy_sha256",
    "local_health.circuit_state",
    "local_health.local_available",
    "local_health.local_model_ready",
    "local_health.consecutive_failures",
    "local_health.rolling_sample_count",
    "local_health.rolling_structured_success_rate",
    "local_health.rolling_p50_latency_ms",
    "local_health.rolling_p95_latency_ms",
    "local_health.last_failure_reason",
    "local_health.last_circuit_transition",
    "canonical_result.governance_record.gate_latencies[*].gate",
}
RESULT_MODALITY_PROVENANCE_LEAF_PATHS = {
    *{
        f"canonical_result.request.{path}"
        for path in CANONICAL_MODALITY_PROVENANCE_LEAF_PATHS
    },
    "canonical_result.governance_record.input_mode",
    "canonical_result.governance_record.typed_text",
    "canonical_result.governance_record.transcription_id",
    "canonical_result.governance_record.original_transcript_text",
    "canonical_result.governance_record.transcript_text",
    "canonical_result.governance_record.transcript_status",
    "canonical_result.governance_record.transcript_backend",
    "canonical_result.governance_record.transcript_confidence",
    "canonical_result.governance_record.audio_sha256",
}
RESULT_VOLATILE_LEAF_PATHS = {
    "canonical_result.governance_record.record_id",
    "canonical_result.governance_record.trace_id",
    "canonical_result.governance_record.timestamp_utc",
    "canonical_result.governance_record.routing.local_latency_ms",
    "canonical_result.governance_record.routing.cloud_latency_ms",
    "canonical_result.governance_record.provider_latency_ms",
    "canonical_result.governance_record.gate_latencies[*].latency_ms",
    "canonical_result.governance_record.validation_latency_ms",
    "canonical_result.governance_record.total_pipeline_latency_ms",
}


def _differing_leaf_paths(left: Any, right: Any, prefix: str = "") -> set[str]:
    if isinstance(left, dict) and isinstance(right, dict):
        paths: set[str] = set()
        for key in sorted(set(left) | set(right)):
            path = f"{prefix}.{key}" if prefix else key
            if key not in left or key not in right:
                paths.add(path)
            else:
                paths.update(_differing_leaf_paths(left[key], right[key], path))
        return paths
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            return {f"{prefix}[*]"}
        paths: set[str] = set()
        for left_item, right_item in zip(left, right, strict=True):
            paths.update(_differing_leaf_paths(left_item, right_item, f"{prefix}[*]"))
        return paths
    return set() if left == right else {prefix}


def _register_controlled_transcript(harness: _Harness) -> RecordedTranscriptionResultV1:
    return harness.service.transcribe_recorded(
        b"D4.3 controlled transcription fixture",
        original_filename="d4_3_controlled.wav",
    )


def _typed_result(
    harness: _Harness, *, scenario_id: str, command: str, mode: str
) -> dict[str, Any]:
    result = harness.service.submit_typed(
        TypedCommandApiRequest(
            scenario_id=scenario_id,
            command=command,
            inference_mode=mode,
        )
    )
    return result.model_dump(mode="json")


def _voice_result(
    harness: _Harness, *, scenario_id: str, reviewed_command: str, mode: str
) -> dict[str, Any]:
    transcription = _register_controlled_transcript(harness)
    result = harness.service.submit_voice(
        VoiceCommandApiRequest(
            scenario_id=scenario_id,
            transcription_id=transcription.transcription_id,
            reviewed_transcript_text=reviewed_command,
            inference_mode=mode,
        )
    )
    return result.model_dump(mode="json")


def _provider_invocation_counts(harness: _Harness) -> tuple[int, int]:
    return harness.local_backend.invocation_count, harness.cloud_backend.invocation_count


def _validation_error_types(error: ValidationError) -> set[tuple[tuple[Any, ...], str]]:
    return {(tuple(item["loc"]), item["type"]) for item in error.errors()}


def test_d4_3_claim_boundary_is_explicit_and_bounded() -> None:
    assert MATRIX["claim_boundary"] == CLAIM_BOUNDARY


def test_dataset_expands_to_exact_balanced_18_pair_matrix() -> None:
    assert MATRIX["schema_version"] == "1.0.0"
    assert len(MATRIX["conditions"]) == 6
    assert MATRIX["routing_modes"] == ["LOCAL", "CLOUD", "AUTO"]
    assert len(PAIR_CASES) == 18
    assert len({case["pair_id"] for case in PAIR_CASES}) == 18
    assert {case["expected_decision"] for case in PAIR_CASES} == {
        "ACCEPT",
        "REJECT",
        "CLARIFY",
    }
    for mode in MATRIX["routing_modes"]:
        mode_cases = [case for case in PAIR_CASES if case["routing_mode"] == mode]
        assert len(mode_cases) == 6
        assert {case["review_stratum"] for case in mode_cases} == {
            "IDENTITY_REVIEW",
            "MATERIAL_OPERATOR_REVIEW",
        }
    for case in PAIR_CASES:
        assert case["scenario_id"] in SCENARIOS
        assert case["raw_transcript_scenario_id"] in SCENARIOS
        assert case["expected_decision"] == SCENARIOS[case["scenario_id"]][
            "expected_high_level_outcome"
        ]


def test_canonical_leaf_inventory_has_no_unknown_fields() -> None:
    known = CANONICAL_SEMANTIC_LEAF_PATHS | CANONICAL_MODALITY_PROVENANCE_LEAF_PATHS
    actual = _model_leaf_paths(CanonicalGovernanceRequestV2)
    assert actual - known == set(), f"unknown canonical fields: {sorted(actual - known)}"
    assert known - actual == set(), f"stale canonical classifications: {sorted(known - actual)}"


def test_result_leaf_inventory_has_no_unknown_fields() -> None:
    known = (
        RESULT_P1_LEAF_PATHS
        | RESULT_P2_LEAF_PATHS
        | RESULT_P3_LEAF_PATHS
        | RESULT_P4_LEAF_PATHS
        | RESULT_P5_OPERATIONAL_LEAF_PATHS
        | RESULT_MODALITY_PROVENANCE_LEAF_PATHS
        | RESULT_VOLATILE_LEAF_PATHS
    )
    actual = _model_leaf_paths(HybridGovernanceResultV1)
    assert actual - known == set(), f"unknown result fields: {sorted(actual - known)}"
    assert known - actual == set(), f"stale result classifications: {sorted(known - actual)}"


def test_p4_replay_access_is_bound_to_exact_scenario_identity() -> None:
    accept_id = "MANUFACTURING_TYPED_ACCEPT"
    observer_id = "MANUFACTURING_OBSERVER_ROLE_REJECT"
    frozen_replay_id = "FROZEN_B2_PICK_PLACE_EVIDENCE_REPLAY"
    assert SCENARIOS[accept_id]["command"] == SCENARIOS[observer_id]["command"]
    harness = _build_harness(
        raw_transcript=SCENARIOS[accept_id]["command"],
        transcription_id="d4-3-p4-scenario-binding",
    )
    assert _scenario_replay_projection(harness.service, accept_id) == {
        "replay_policy_scenario_id": accept_id,
        "qualification_replay_access": "PROHIBITED",
    }
    assert _scenario_replay_projection(harness.service, observer_id) == {
        "replay_policy_scenario_id": observer_id,
        "qualification_replay_access": "PROHIBITED",
    }
    assert _scenario_replay_projection(harness.service, frozen_replay_id) == {
        "replay_policy_scenario_id": frozen_replay_id,
        "qualification_replay_access": "SERVER_REGISTERED_ONLY",
    }


@pytest.mark.parametrize("mode", ("LOCAL", "CLOUD", "AUTO"))
def test_routing_mode_uses_only_controlled_network_free_providers(mode: str) -> None:
    scenario = SCENARIOS["MANUFACTURING_TYPED_ACCEPT"]
    harness = _build_harness(
        raw_transcript=scenario["command"],
        transcription_id=f"d4-3-routing-{mode.lower()}",
    )
    initial = harness.initial_operational_projection
    result = _typed_result(
        harness,
        scenario_id=scenario["scenario_id"],
        command=scenario["command"],
        mode=mode,
    )
    expected_counts = (0, 1) if mode == "CLOUD" else (1, 0)
    assert initial == {
        "circuit_state": "CLOSED",
        "local_available": True,
        "local_model_ready": True,
        "consecutive_failures": 0,
        "rolling_sample_count": 0,
        "rolling_structured_success_rate": None,
        "rolling_p50_latency_ms": None,
        "rolling_p95_latency_ms": None,
        "last_failure_reason": "NONE",
        "last_circuit_transition": None,
    }
    assert _provider_invocation_counts(harness) == expected_counts
    assert harness.local_backend.network_call_count == 0
    assert harness.cloud_backend.network_call_count == 0
    assert result["canonical_result"]["governance_record"]["final_decision"] == "ACCEPT"
    if mode == "AUTO":
        routing = result["canonical_result"]["governance_record"]["routing"]
        assert routing["selected_provider"] == "FOUNDRY_LOCAL"
        assert routing["fallback_triggered"] is False
        assert routing["fallback_reason"] == "NONE"


@pytest.mark.parametrize("case", PAIR_CASES, ids=lambda case: case["pair_id"])
def test_typed_and_operator_reviewed_voice_are_governance_invariant(
    case: dict[str, str],
) -> None:
    scenario = SCENARIOS[case["scenario_id"]]
    raw_scenario = SCENARIOS[case["raw_transcript_scenario_id"]]
    typed_command = scenario["command"]
    reviewed_command = scenario["command"]
    raw_transcript = raw_scenario["command"]
    assert typed_command == reviewed_command
    if case["review_stratum"] == "MATERIAL_OPERATOR_REVIEW":
        assert raw_transcript != reviewed_command
    else:
        assert raw_transcript == reviewed_command

    typed = _build_harness(
        raw_transcript=raw_transcript,
        transcription_id=f"d4-3-unused-typed-{case['pair_id'].lower()}",
    )
    voice = _build_harness(
        raw_transcript=raw_transcript,
        transcription_id=f"d4-3-voice-{case['pair_id'].lower()}",
    )
    assert typed.initial_operational_projection == voice.initial_operational_projection

    typed_result = _typed_result(
        typed,
        scenario_id=scenario["scenario_id"],
        command=typed_command,
        mode=case["routing_mode"],
    )
    voice_result = _voice_result(
        voice,
        scenario_id=scenario["scenario_id"],
        reviewed_command=reviewed_command,
        mode=case["routing_mode"],
    )

    p1_match = P1_CANONICAL_GOVERNANCE_INPUT_PROJECTION(typed_result) == P1_CANONICAL_GOVERNANCE_INPUT_PROJECTION(voice_result)
    p2_match = P2_PROVIDER_PROPOSAL_CONTROL_PROJECTION(typed_result) == P2_PROVIDER_PROPOSAL_CONTROL_PROJECTION(voice_result)
    p3_typed = P3_GOVERNANCE_OUTCOME_PROJECTION(typed_result)
    p3_voice = P3_GOVERNANCE_OUTCOME_PROJECTION(voice_result)
    p3_match = p3_typed == p3_voice
    p4_typed = P4_AUTHORITY_PROJECTION(
        typed_result, typed.service, scenario_id=case["scenario_id"]
    )
    p4_voice = P4_AUTHORITY_PROJECTION(
        voice_result, voice.service, scenario_id=case["scenario_id"]
    )
    assert p4_typed["replay_policy_scenario_id"] == case["scenario_id"]
    assert p4_voice["replay_policy_scenario_id"] == case["scenario_id"]
    p4_match = p4_typed == p4_voice

    observed_differences = _differing_leaf_paths(typed_result, voice_result)
    allowed_differences = RESULT_MODALITY_PROVENANCE_LEAF_PATHS | RESULT_VOLATILE_LEAF_PATHS
    unexpected_difference_paths = sorted(observed_differences - allowed_differences)
    typed_record = typed_result["canonical_result"]["governance_record"]
    voice_record = voice_result["canonical_result"]["governance_record"]

    assert p1_match, "CANONICAL_INPUT_MATCH=NO"
    assert p2_match, "CONTROLLED_PROPOSAL_MATCH=NO"
    assert p3_match, "GOVERNANCE_OUTCOME_MATCH=NO"
    assert typed_record["final_decision"] == voice_record["final_decision"]
    assert typed_record["gate_reasons"] == voice_record["gate_reasons"]
    assert typed_record["execution_eligible"] == voice_record["execution_eligible"]
    assert p4_match, "AUTHORITY_PROJECTION_MATCH=NO"
    assert unexpected_difference_paths == []
    assert voice_record["original_transcript_text"] == raw_transcript
    assert voice_record["normalised_command"] == " ".join(reviewed_command.split())
    assert voice_record["final_decision"] == case["expected_decision"]
    assert p4_voice["physical_execution_authority"] == "NOT_IMPLEMENTED"
    assert _provider_invocation_counts(typed) == _provider_invocation_counts(voice)
    assert typed.local_backend.network_call_count == voice.local_backend.network_call_count == 0
    assert typed.cloud_backend.network_call_count == voice.cloud_backend.network_call_count == 0


def test_n01_partial_transcript_cannot_enter_governance() -> None:
    scenario = SCENARIOS["MANUFACTURING_TYPED_ACCEPT"]
    harness = _build_harness(
        raw_transcript=scenario["command"],
        transcription_id="d4-3-n01-partial",
        transcript_status=TranscriptStatus.PARTIAL,
    )
    transcription = _register_controlled_transcript(harness)
    assert transcription.transcript_status is TranscriptStatus.PARTIAL
    with pytest.raises(TranscriptNotReadyError, match="^TRANSCRIPT_NOT_READY_OR_EXPIRED$"):
        harness.service.submit_voice(
            VoiceCommandApiRequest(
                scenario_id=scenario["scenario_id"],
                transcription_id=transcription.transcription_id,
                reviewed_transcript_text=scenario["command"],
                inference_mode="LOCAL",
            )
        )
    assert _provider_invocation_counts(harness) == (0, 0)


def test_n02_expired_ready_transcript_cannot_enter_governance() -> None:
    scenario = SCENARIOS["MANUFACTURING_TYPED_ACCEPT"]
    harness = _build_harness(
        raw_transcript=scenario["command"],
        transcription_id="d4-3-n02-expired",
        transcript_ttl_seconds=1,
    )
    transcription = _register_controlled_transcript(harness)
    harness.clock.now += timedelta(seconds=1)
    with pytest.raises(TranscriptNotReadyError, match="^TRANSCRIPT_NOT_READY_OR_EXPIRED$"):
        harness.service.submit_voice(
            VoiceCommandApiRequest(
                scenario_id=scenario["scenario_id"],
                transcription_id=transcription.transcription_id,
                reviewed_transcript_text=scenario["command"],
                inference_mode="LOCAL",
            )
        )
    assert _provider_invocation_counts(harness) == (0, 0)


def test_n03_unknown_transcript_identity_fails_closed() -> None:
    scenario = SCENARIOS["MANUFACTURING_TYPED_ACCEPT"]
    harness = _build_harness(
        raw_transcript=scenario["command"],
        transcription_id="d4-3-n03-unused",
    )
    with pytest.raises(TranscriptNotReadyError, match="^TRANSCRIPT_NOT_READY_OR_EXPIRED$"):
        harness.service.submit_voice(
            VoiceCommandApiRequest(
                scenario_id=scenario["scenario_id"],
                transcription_id="d4-3-n03-unknown",
                reviewed_transcript_text=scenario["command"],
                inference_mode="LOCAL",
            )
        )
    assert _provider_invocation_counts(harness) == (0, 0)


def test_n04_sequential_consumed_identity_reuse_fails() -> None:
    scenario = SCENARIOS["MANUFACTURING_TYPED_ACCEPT"]
    harness = _build_harness(
        raw_transcript=scenario["command"],
        transcription_id="d4-3-n04-consumed",
    )
    transcription = _register_controlled_transcript(harness)
    request = VoiceCommandApiRequest(
        scenario_id=scenario["scenario_id"],
        transcription_id=transcription.transcription_id,
        reviewed_transcript_text=scenario["command"],
        inference_mode="LOCAL",
    )
    first = harness.service.submit_voice(request)
    assert first.canonical_result.governance_record.final_decision.value == "ACCEPT"
    with pytest.raises(TranscriptNotReadyError, match="^TRANSCRIPT_NOT_READY_OR_EXPIRED$"):
        harness.service.submit_voice(request)
    assert _provider_invocation_counts(harness) == (1, 0)


def test_n05_concurrent_duplicate_claim_yields_exactly_one_winner() -> None:
    scenario = SCENARIOS["MANUFACTURING_TYPED_ACCEPT"]
    harness = _build_harness(
        raw_transcript=scenario["command"],
        transcription_id="d4-3-n05-concurrent",
    )
    transcription = _register_controlled_transcript(harness)
    request = VoiceCommandApiRequest(
        scenario_id=scenario["scenario_id"],
        transcription_id=transcription.transcription_id,
        reviewed_transcript_text=scenario["command"],
        inference_mode="LOCAL",
    )
    barrier = Barrier(2)

    def submit() -> str:
        barrier.wait()
        try:
            harness.service.submit_voice(request)
        except TranscriptNotReadyError as exc:
            return str(exc)
        return "WINNER"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(lambda _: submit(), range(2)))
    assert sorted(outcomes) == ["TRANSCRIPT_NOT_READY_OR_EXPIRED", "WINNER"]
    assert _provider_invocation_counts(harness) == (1, 0)


def test_n06_provider_failure_after_claim_never_restores_identity() -> None:
    scenario = SCENARIOS["MANUFACTURING_TYPED_ACCEPT"]
    harness = _build_harness(
        raw_transcript=scenario["command"],
        transcription_id="d4-3-n06-provider-failure",
        provider_failure=RuntimeError("D4_3_CONTROLLED_PROVIDER_FAILURE"),
    )
    transcription = _register_controlled_transcript(harness)
    request = VoiceCommandApiRequest(
        scenario_id=scenario["scenario_id"],
        transcription_id=transcription.transcription_id,
        reviewed_transcript_text=scenario["command"],
        inference_mode="LOCAL",
    )
    first = harness.service.submit_voice(request)
    first_record = first.canonical_result.governance_record
    assert first_record.parse_status.value == "ERROR"
    assert first_record.final_decision.value == "ERROR"
    assert first_record.execution_eligible is False
    assert first_record.decision_reason_codes == ("LOCAL_TRANSPORT_ERROR",)
    with pytest.raises(TranscriptNotReadyError, match="^TRANSCRIPT_NOT_READY_OR_EXPIRED$"):
        harness.service.submit_voice(request)
    assert _provider_invocation_counts(harness) == (1, 0)


def test_n07_raw_transcript_cannot_substitute_for_reviewed_text() -> None:
    scenario = SCENARIOS["MANUFACTURING_TYPED_ACCEPT"]
    harness = _build_harness(
        raw_transcript=scenario["command"],
        transcription_id="d4-3-n07-raw-substitution",
    )
    transcription = _register_controlled_transcript(harness)
    with pytest.raises(ValidationError) as caught:
        VoiceCommandApiRequest.model_validate(
            {
                "scenario_id": scenario["scenario_id"],
                "transcription_id": transcription.transcription_id,
                "original_transcript_text": scenario["command"],
                "inference_mode": "LOCAL",
            }
        )
    errors = _validation_error_types(caught.value)
    assert (("reviewed_transcript_text",), "missing") in errors
    assert (("original_transcript_text",), "extra_forbidden") in errors
    assert _provider_invocation_counts(harness) == (0, 0)
    valid = harness.service.submit_voice(
        VoiceCommandApiRequest(
            scenario_id=scenario["scenario_id"],
            transcription_id=transcription.transcription_id,
            reviewed_transcript_text=scenario["command"],
            inference_mode="LOCAL",
        )
    )
    assert valid.canonical_result.governance_record.final_decision.value == "ACCEPT"
    assert _provider_invocation_counts(harness) == (1, 0)


def test_n08_blank_reviewed_text_is_rejected_before_provider() -> None:
    scenario = SCENARIOS["MANUFACTURING_TYPED_ACCEPT"]
    harness = _build_harness(
        raw_transcript=scenario["command"],
        transcription_id="d4-3-n08-blank-review",
    )
    transcription = _register_controlled_transcript(harness)
    with pytest.raises(ValidationError) as caught:
        VoiceCommandApiRequest(
            scenario_id=scenario["scenario_id"],
            transcription_id=transcription.transcription_id,
            reviewed_transcript_text="   ",
            inference_mode="LOCAL",
        )
    assert (("reviewed_transcript_text",), "value_error") in _validation_error_types(caught.value)
    assert _provider_invocation_counts(harness) == (0, 0)
    harness.service.submit_voice(
        VoiceCommandApiRequest(
            scenario_id=scenario["scenario_id"],
            transcription_id=transcription.transcription_id,
            reviewed_transcript_text=scenario["command"],
            inference_mode="LOCAL",
        )
    )
    assert _provider_invocation_counts(harness) == (1, 0)


def test_n09_typed_client_authority_field_injection_is_rejected() -> None:
    scenario = SCENARIOS["MANUFACTURING_TYPED_ACCEPT"]
    harness = _build_harness(
        raw_transcript=scenario["command"],
        transcription_id="d4-3-n09-unused",
    )
    authority_fields: dict[str, Any] = {
        "domain_id": "MANUFACTURING",
        "requester": {"requester_id": "client", "role": "supervisor"},
        "scene": {"human_obstruction": False},
        "execution_eligible": True,
    }
    base = {
        "scenario_id": scenario["scenario_id"],
        "command": scenario["command"],
        "inference_mode": "LOCAL",
    }
    for field, value in authority_fields.items():
        with pytest.raises(ValidationError) as caught:
            TypedCommandApiRequest.model_validate({**base, field: value})
        assert ((field,), "extra_forbidden") in _validation_error_types(caught.value)
    assert _provider_invocation_counts(harness) == (0, 0)


def test_n10_voice_client_authority_field_injection_is_rejected() -> None:
    scenario = SCENARIOS["MANUFACTURING_TYPED_ACCEPT"]
    harness = _build_harness(
        raw_transcript=scenario["command"],
        transcription_id="d4-3-n10-authority",
    )
    transcription = _register_controlled_transcript(harness)
    authority_fields: dict[str, Any] = {
        "domain_id": "MANUFACTURING",
        "requester": {"requester_id": "client", "role": "supervisor"},
        "scene": {"human_obstruction": False},
        "execution_eligible": True,
    }
    base = {
        "scenario_id": scenario["scenario_id"],
        "transcription_id": transcription.transcription_id,
        "reviewed_transcript_text": scenario["command"],
        "inference_mode": "LOCAL",
    }
    for field, value in authority_fields.items():
        with pytest.raises(ValidationError) as caught:
            VoiceCommandApiRequest.model_validate({**base, field: value})
        assert ((field,), "extra_forbidden") in _validation_error_types(caught.value)
    assert _provider_invocation_counts(harness) == (0, 0)
    harness.service.submit_voice(VoiceCommandApiRequest.model_validate(base))
    assert _provider_invocation_counts(harness) == (1, 0)
