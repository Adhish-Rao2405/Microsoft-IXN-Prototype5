from copy import deepcopy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.prototype5.governance_contract_v2 import (
    CorrectnessStatus,
    DomainId,
    EvaluationMode,
    FallbackReason,
    FinalDecision,
    GateStatus,
    GovernanceRecordV2,
    InferenceMode,
    InputMode,
    LegacyMetricReference,
    PlanSemanticStatus,
    ProviderId,
    RoutingRecordV2,
    SimulationStatus,
    TranscriptStatus,
    build_legacy_metric_reference,
)


SHA_A = "a" * 64
SHA_B = "b" * 64
COMMIT = "7" * 40
ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas/prototype5/governance_record_v2.schema.json"


def local_route() -> dict:
    return {
        "requested_mode": "LOCAL",
        "selected_provider": "FOUNDRY_LOCAL",
        "selected_model": "phi-local-test",
        "local_attempted": True,
        "cloud_attempted": False,
        "fallback_triggered": False,
        "fallback_reason": "NONE",
        "local_latency_ms": 12.0,
        "cloud_latency_ms": None,
    }


def local_provenance() -> dict:
    return {
        "source_repository": "Adhish-Rao2405/Microsoft-IXN-Prototype5",
        "software_commit": COMMIT,
        "prompt_id": "manufacturing_planner",
        "prompt_version": "2.0.0",
        "model_provider": "FOUNDRY_LOCAL",
        "model_id": "phi-local-test",
        "benchmark_sha256": None,
        "oracle_sha256": None,
        "policy_sha256": SHA_B,
    }


def accepted_live_record() -> dict:
    return {
        "record_id": "REC-001",
        "trace_id": "TRACE-001",
        "timestamp_utc": "2026-07-30T12:00:00+00:00",
        "evaluation_mode": "LIVE",
        "input_mode": "TYPED",
        "normalised_command": "Move the blue component to fixture B.",
        "typed_text": "Move the blue component to fixture B.",
        "transcript_text": None,
        "transcript_status": "NOT_APPLICABLE",
        "transcript_backend": None,
        "transcript_confidence": None,
        "audio_sha256": None,
        "domain_id": "MANUFACTURING",
        "benchmark_id": None,
        "policy_id": "manufacturing_policy_v2",
        "oracle_version": None,
        "evidence_schema_version": "2.0.0",
        "routing": local_route(),
        "raw_response_sha256": SHA_A,
        "raw_response_present": True,
        "provider_latency_ms": 12.0,
        "parse_status": "PASSED",
        "json_status": "PASSED",
        "schema_status": "PASSED",
        "plan_semantic_status": "VALID",
        "ambiguity_status": "PASSED",
        "safety_status": "PASSED",
        "authority_status": "PASSED",
        "gate_reasons": [],
        "gate_latencies": [
            {"gate": "PARSE", "latency_ms": 0.2},
            {"gate": "JSON", "latency_ms": 0.1},
            {"gate": "SCHEMA", "latency_ms": 0.3},
            {"gate": "SEMANTICS", "latency_ms": 0.6},
            {"gate": "AMBIGUITY", "latency_ms": 0.1},
            {"gate": "SAFETY", "latency_ms": 0.2},
            {"gate": "AUTHORITY", "latency_ms": 0.1},
        ],
        "expected_decision": None,
        "decision_correctness_status": "NOT_EVALUATED",
        "final_decision": "ACCEPT",
        "execution_eligible": True,
        "decision_reason_codes": ["ALL_MANDATORY_GATES_PASSED"],
        "validation_latency_ms": 2.0,
        "total_pipeline_latency_ms": 14.0,
        "execution_permit_id": None,
        "simulation_status": "NOT_REQUESTED",
        "provenance": local_provenance(),
    }


def build_record(**updates) -> GovernanceRecordV2:
    payload = accepted_live_record()
    payload.update(updates)
    return GovernanceRecordV2.model_validate(payload)


def test_valid_live_record_serialises_with_v2_schema():
    record = build_record()

    assert record.evidence_schema_version == "2.0.0"
    assert record.final_decision is FinalDecision.ACCEPT
    assert record.execution_eligible is True
    assert record.decision_correctness_status is CorrectnessStatus.NOT_EVALUATED
    assert "semantic_valid" not in record.model_dump()
    assert "semantic_score" not in record.model_dump()


def test_committed_json_schema_matches_the_pydantic_contract():
    committed = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert committed == GovernanceRecordV2.model_json_schema()
    assert "semantic_valid" not in committed["properties"]
    assert "semantic_score" not in committed["properties"]
    assert set(
        (
            "plan_semantic_status",
            "decision_correctness_status",
            "final_decision",
            "execution_eligible",
        )
    ).issubset(committed["required"])


def test_contract_rejects_unknown_fields_and_is_frozen():
    with pytest.raises(ValidationError, match="extra_forbidden"):
        build_record(semantic_valid=True)

    record = build_record()
    with pytest.raises(ValidationError, match="frozen"):
        record.execution_eligible = False
    with pytest.raises(ValidationError, match="frozen"):
        record.gate_latencies[0].latency_ms = 99


def test_gate_records_reject_duplicate_gate_entries():
    with pytest.raises(ValidationError, match="one gate latency record"):
        build_record(
            gate_latencies=[
                {"gate": "PARSE", "latency_ms": 0.2},
                {"gate": "PARSE", "latency_ms": 0.3},
            ]
        )


def test_schema_failure_can_never_be_semantically_valid():
    with pytest.raises(
        ValidationError, match="non-passing schema cannot produce semantic VALID"
    ):
        build_record(schema_status="FAILED")


def test_parse_failure_can_never_produce_passing_downstream_structure():
    with pytest.raises(
        ValidationError, match="non-passing parse cannot produce passing JSON or schema"
    ):
        build_record(parse_status="FAILED")


def test_schema_invalid_correct_rejection_is_decision_correctness_only():
    payload = accepted_live_record()
    payload.update(
        {
            "evaluation_mode": "EVALUATION",
            "benchmark_id": "manufacturing_v2",
            "oracle_version": "2.0.0",
            "expected_decision": "REJECT",
            "decision_correctness_status": "CORRECT",
            "parse_status": "PASSED",
            "json_status": "PASSED",
            "schema_status": "FAILED",
            "plan_semantic_status": "NOT_ASSESSABLE_SCHEMA_INVALID",
            "ambiguity_status": "NOT_ASSESSABLE",
            "safety_status": "NOT_ASSESSABLE",
            "authority_status": "NOT_ASSESSABLE",
            "final_decision": "REJECT",
            "execution_eligible": False,
            "decision_reason_codes": ["SCHEMA_INVALID"],
        }
    )

    record = GovernanceRecordV2.model_validate(payload)

    assert record.decision_correctness_status is CorrectnessStatus.CORRECT
    assert (
        record.plan_semantic_status
        is PlanSemanticStatus.NOT_ASSESSABLE_SCHEMA_INVALID
    )
    assert record.execution_eligible is False


def test_safety_not_assessable_is_not_safety_failed_or_execution_eligible():
    record = build_record(
        safety_status="NOT_ASSESSABLE",
        final_decision="REJECT",
        execution_eligible=False,
        decision_reason_codes=["SAFETY_NOT_ASSESSABLE"],
    )

    assert record.safety_status is GateStatus.NOT_ASSESSABLE
    assert record.safety_status is not GateStatus.FAILED


def test_accept_requires_every_mandatory_gate():
    with pytest.raises(ValidationError, match="execution_eligible must equal"):
        build_record(
            ambiguity_status="FAILED",
            final_decision="REJECT",
            execution_eligible=True,
            decision_reason_codes=["AMBIGUOUS_COMMAND"],
        )

    with pytest.raises(ValidationError, match="ACCEPT requires execution eligibility"):
        build_record(
            safety_status="FAILED",
            final_decision="ACCEPT",
            execution_eligible=False,
            decision_reason_codes=["SAFETY_POLICY_REJECTED"],
        )


def test_live_mode_never_invents_oracle_decision_correctness():
    with pytest.raises(ValidationError, match="live mode cannot invent"):
        build_record(
            expected_decision="ACCEPT",
            decision_correctness_status="CORRECT",
        )


def test_evaluation_mode_requires_benchmark_oracle_and_expected_decision():
    with pytest.raises(ValidationError, match="requires benchmark_id and oracle_version"):
        build_record(evaluation_mode="EVALUATION")


def test_auto_fallback_accepts_only_operational_structural_reason():
    route = RoutingRecordV2.model_validate(
        {
            "requested_mode": "AUTO",
            "selected_provider": "CLOUD",
            "selected_model": "qualified-cloud-model",
            "local_attempted": True,
            "cloud_attempted": True,
            "fallback_triggered": True,
            "fallback_reason": "LOCAL_SCHEMA_FAILURE",
            "local_latency_ms": 100.0,
            "cloud_latency_ms": 50.0,
        }
    )

    assert route.fallback_reason is FallbackReason.LOCAL_SCHEMA_FAILURE

    with pytest.raises(ValidationError, match="Input should be"):
        RoutingRecordV2.model_validate(
            {
                **route.model_dump(mode="json"),
                "fallback_reason": "SAFETY_REJECTED",
            }
        )


def test_local_and_cloud_modes_cannot_cross_route():
    with pytest.raises(ValidationError, match="LOCAL mode cannot attempt cloud"):
        RoutingRecordV2.model_validate(
            {
                "requested_mode": "LOCAL",
                "selected_provider": "CLOUD",
                "selected_model": "cloud",
                "local_attempted": True,
                "cloud_attempted": True,
            }
        )

    with pytest.raises(ValidationError, match="CLOUD mode cannot attempt local"):
        RoutingRecordV2.model_validate(
            {
                "requested_mode": "CLOUD",
                "selected_provider": "FOUNDRY_LOCAL",
                "selected_model": "local",
                "local_attempted": True,
                "cloud_attempted": True,
            }
        )


def test_direct_mode_can_record_pre_provider_unavailability_without_false_attempt():
    local = RoutingRecordV2.model_validate(
        {
            "requested_mode": "LOCAL",
            "selected_provider": "NONE",
            "selected_model": None,
            "local_attempted": False,
            "cloud_attempted": False,
        }
    )
    cloud = RoutingRecordV2.model_validate(
        {
            "requested_mode": "CLOUD",
            "selected_provider": "NONE",
            "selected_model": None,
            "local_attempted": False,
            "cloud_attempted": False,
        }
    )

    assert local.selected_provider is ProviderId.NONE
    assert cloud.selected_provider is ProviderId.NONE


def test_auto_can_fallback_after_pre_attempt_local_health_failure():
    route = RoutingRecordV2.model_validate(
        {
            "requested_mode": "AUTO",
            "selected_provider": "CLOUD",
            "selected_model": "qualified-cloud-model",
            "local_attempted": False,
            "cloud_attempted": True,
            "fallback_triggered": True,
            "fallback_reason": "LOCAL_UNAVAILABLE",
            "cloud_latency_ms": 40.0,
        }
    )

    assert route.fallback_triggered is True
    assert route.local_attempted is False

    with pytest.raises(
        ValidationError, match="pre-attempt local health reason"
    ):
        RoutingRecordV2.model_validate(
            {
                **route.model_dump(mode="json"),
                "fallback_reason": "LOCAL_SCHEMA_FAILURE",
            }
        )


def test_voice_ready_record_requires_real_transcript_provenance():
    payload = accepted_live_record()
    payload.update(
        {
            "input_mode": "VOICE",
            "typed_text": None,
            "normalised_command": "Move the blue component to fixture B.",
            "transcript_text": "Move the blue component to fixture B.",
            "transcript_status": "READY",
            "transcript_backend": "nemotron-speech-streaming-en-0.6b",
            "transcript_confidence": 0.91,
            "audio_sha256": SHA_B,
        }
    )

    record = GovernanceRecordV2.model_validate(payload)

    assert record.input_mode is InputMode.VOICE
    assert record.transcript_status is TranscriptStatus.READY
    assert record.audio_sha256 == SHA_B


def test_partial_voice_transcript_cannot_call_planner_or_be_eligible():
    payload = accepted_live_record()
    payload.update(
        {
            "input_mode": "VOICE",
            "typed_text": None,
            "normalised_command": "Move the part",
            "transcript_text": "Move the part",
            "transcript_status": "PARTIAL",
            "transcript_backend": "nemotron-speech-streaming-en-0.6b",
            "transcript_confidence": 0.4,
            "audio_sha256": SHA_B,
            "routing": {
                "requested_mode": "AUTO",
                "selected_provider": "NONE",
                "selected_model": None,
                "local_attempted": False,
                "cloud_attempted": False,
            },
            "raw_response_sha256": None,
            "raw_response_present": False,
            "provider_latency_ms": None,
            "parse_status": "NOT_ASSESSABLE",
            "json_status": "NOT_ASSESSABLE",
            "schema_status": "NOT_ASSESSABLE",
            "plan_semantic_status": "NOT_ASSESSABLE_NO_PROPOSAL",
            "ambiguity_status": "FAILED",
            "safety_status": "NOT_ASSESSABLE",
            "authority_status": "NOT_ASSESSABLE",
            "final_decision": "CLARIFY",
            "execution_eligible": False,
            "decision_reason_codes": ["TRANSCRIPT_PARTIAL"],
            "provenance": {
                **local_provenance(),
                "model_provider": "NONE",
                "model_id": None,
            },
        }
    )

    record = GovernanceRecordV2.model_validate(payload)

    assert record.execution_eligible is False
    assert record.final_decision is FinalDecision.CLARIFY
    assert record.routing.selected_provider is ProviderId.NONE


def test_non_ready_voice_transcript_cannot_call_provider():
    payload = accepted_live_record()
    payload.update(
        {
            "input_mode": "VOICE",
            "typed_text": None,
            "normalised_command": None,
            "transcript_text": None,
            "transcript_status": "BACKEND_UNAVAILABLE",
            "transcript_backend": None,
        }
    )

    with pytest.raises(ValidationError, match="non-ready transcript cannot select"):
        GovernanceRecordV2.model_validate(payload)


def test_voice_backend_unavailable_is_recorded_without_fabricated_command():
    payload = accepted_live_record()
    payload.update(
        {
            "input_mode": "VOICE",
            "typed_text": None,
            "normalised_command": None,
            "transcript_text": None,
            "transcript_status": "BACKEND_UNAVAILABLE",
            "transcript_backend": "nemotron-speech-streaming-en-0.6b",
            "transcript_confidence": None,
            "audio_sha256": None,
            "routing": {
                "requested_mode": "AUTO",
                "selected_provider": "NONE",
                "selected_model": None,
                "local_attempted": False,
                "cloud_attempted": False,
            },
            "raw_response_sha256": None,
            "raw_response_present": False,
            "provider_latency_ms": None,
            "parse_status": "NOT_ASSESSABLE",
            "json_status": "NOT_ASSESSABLE",
            "schema_status": "NOT_ASSESSABLE",
            "plan_semantic_status": "NOT_ASSESSABLE_NO_PROPOSAL",
            "ambiguity_status": "NOT_ASSESSABLE",
            "safety_status": "NOT_ASSESSABLE",
            "authority_status": "NOT_ASSESSABLE",
            "final_decision": "ERROR",
            "execution_eligible": False,
            "decision_reason_codes": ["VOICE_BACKEND_UNAVAILABLE"],
            "provenance": {
                **local_provenance(),
                "model_provider": "NONE",
                "model_id": None,
            },
        }
    )

    record = GovernanceRecordV2.model_validate(payload)

    assert record.normalised_command is None
    assert record.transcript_text is None
    assert record.final_decision is FinalDecision.ERROR
    assert record.routing.selected_provider is ProviderId.NONE


def test_raw_response_hash_and_provider_metadata_are_consistent():
    with pytest.raises(ValidationError, match="raw response requires raw_response_sha256"):
        build_record(raw_response_sha256=None)

    provenance = local_provenance()
    provenance["model_id"] = "different-model"
    with pytest.raises(
        ValidationError, match="routing and provenance model identifiers must match"
    ):
        build_record(provenance=provenance)

    with pytest.raises(
        ValidationError, match="provider latency must match selected local latency"
    ):
        build_record(provider_latency_ms=99.0)


def test_missing_raw_response_cannot_pass_structural_or_semantic_gates():
    with pytest.raises(
        ValidationError, match="missing raw response cannot pass structural gates"
    ):
        build_record(
            raw_response_present=False,
            raw_response_sha256=None,
        )


def test_simulation_requires_eligibility_and_execution_permit():
    with pytest.raises(
        ValidationError, match="queued or executed simulation requires eligibility and a permit"
    ):
        build_record(simulation_status="QUEUED")

    record = build_record(
        execution_permit_id="PERMIT-001",
        simulation_status="QUEUED",
    )
    assert record.simulation_status is SimulationStatus.QUEUED


def test_latency_accounting_is_bounded():
    with pytest.raises(ValidationError, match="total latency cannot be less"):
        build_record(total_pipeline_latency_ms=1.0)

    with pytest.raises(ValidationError, match="gate latency total cannot exceed"):
        build_record(validation_latency_ms=0.1)


def test_timestamp_and_reason_codes_are_strict():
    with pytest.raises(ValidationError, match="UTC offset"):
        build_record(timestamp_utc="2026-07-30T12:00:00+01:00")

    with pytest.raises(ValidationError, match="invalid decision reason code"):
        build_record(decision_reason_codes=["free form reason"])


def test_legacy_adapter_preserves_fields_without_inventing_v2_meanings():
    payload = {
        "semantic_score": 1.0,
        "semantic_valid": True,
        "safety_valid": False,
        "false_accept": True,
    }
    original = deepcopy(payload)

    reference = build_legacy_metric_reference(
        payload,
        source_repository="Adhish-Rao2405/Microsoft-IXN-Prototype3",
        source_commit="3" * 40,
        source_path="prototype3/results/runs/rq5_comparison.jsonl",
        source_sha256=SHA_A,
    )

    assert payload == original
    assert isinstance(reference, LegacyMetricReference)
    assert reference.legacy_semantic_score == 1.0
    assert reference.semantic_metric_classification == "LEGACY_HYBRID_DECISION_SCORE"
    assert (
        reference.v2_plan_semantic_status
        == "NOT_ASSESSABLE_MISSING_ORACLE"
    )
    assert reference.v2_safety_status == "NOT_ASSESSABLE"
    assert "LEGACY_SEMANTIC_FIELD_NOT_CONVERTED" in reference.migration_warnings


def test_legacy_reference_rejects_personal_or_escaping_source_paths():
    common = {
        "payload": {},
        "source_repository": "Adhish-Rao2405/Microsoft-IXN-Prototype3",
        "source_commit": "3" * 40,
        "source_sha256": SHA_A,
    }

    with pytest.raises(ValidationError, match="repository-relative"):
        build_legacy_metric_reference(
            **common,
            source_path=r"C:\Users\developer\results.jsonl",
        )

    with pytest.raises(ValidationError, match="cannot escape"):
        build_legacy_metric_reference(
            **common,
            source_path="../results.jsonl",
        )
