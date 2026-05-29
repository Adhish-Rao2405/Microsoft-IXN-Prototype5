"""
Typed transcript bridge from M12 voice policy into the existing planner/validator path.

This module does not process audio, load speech models, call a microphone, run a
benchmark, or execute robot actions. Voice policy eligibility only controls
planner handoff. Execution eligibility is derived only from the existing
deterministic validation wrapper.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from typing import Any

from scripts.prototype5.audit_sdk_mini_replay_validators import run_existing_validation

from .voice_intent_policy import build_mock_voice_transcript


@dataclass(frozen=True)
class VoicePlannerBridgeResult:
    voice_input_id: str
    timestamp_utc: str
    raw_transcript: str
    normalised_transcript: str
    detected_intent: str
    voice_risk_flags: list[str]
    voice_eligible_for_planning: bool
    voice_rejection_reason: str | None
    planner_backend: str | None
    planner_called: bool
    planner_success: bool
    planner_latency_ms: float | None
    raw_planner_response: str | None
    json_valid: bool
    schema_valid: bool
    semantic_valid: bool
    safety_valid: bool
    execution_eligible: bool
    pipeline_false_accept: bool | None
    rejection_stage: str | None
    rejection_reason: str | None
    error: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def response_to_dict(response: Any) -> dict[str, Any]:
    if is_dataclass(response):
        return asdict(response)
    if isinstance(response, dict):
        return dict(response)
    if hasattr(response, "__dict__"):
        return dict(response.__dict__)
    return {"raw_response_repr": repr(response)}


def get_field(payload: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in payload:
            return payload[name]
    return default


def validation_case_for(transcript_text: str, voice_input_id: str) -> dict[str, str]:
    return {
        "case_id": voice_input_id,
        "category": "voice_transcript_bridge",
        "risk_type": "standard",
        "user_command": transcript_text,
    }


def _voice_policy_rejection(transcript: Any) -> VoicePlannerBridgeResult:
    return VoicePlannerBridgeResult(
        voice_input_id=transcript.voice_input_id,
        timestamp_utc=transcript.timestamp_utc,
        raw_transcript=transcript.raw_transcript,
        normalised_transcript=transcript.normalised_transcript,
        detected_intent=transcript.detected_intent,
        voice_risk_flags=transcript.voice_risk_flags,
        voice_eligible_for_planning=transcript.eligible_for_planning,
        voice_rejection_reason=transcript.rejection_reason,
        planner_backend=None,
        planner_called=False,
        planner_success=False,
        planner_latency_ms=None,
        raw_planner_response=None,
        json_valid=False,
        schema_valid=False,
        semantic_valid=False,
        safety_valid=False,
        execution_eligible=False,
        pipeline_false_accept=None,
        rejection_stage="voice_policy",
        rejection_reason=transcript.rejection_reason,
        error=None,
    )


def bridge_transcript_to_planner(
    raw_transcript: str,
    *,
    planner_backend: Any,
    transcript_confidence: float = 1.0,
    is_partial: bool = False,
    voice_input_id: str | None = None,
) -> VoicePlannerBridgeResult:
    transcript = build_mock_voice_transcript(
        raw_transcript,
        transcript_confidence=transcript_confidence,
        is_partial=is_partial,
        voice_input_id=voice_input_id,
    )

    if not transcript.eligible_for_planning:
        return _voice_policy_rejection(transcript)

    try:
        response = planner_backend.generate(
            transcript.normalised_transcript,
            {
                "prompt_id": f"voice_bridge_{transcript.voice_input_id}",
                "temperature": 0,
            },
        )
    except Exception as exc:
        return VoicePlannerBridgeResult(
            voice_input_id=transcript.voice_input_id,
            timestamp_utc=transcript.timestamp_utc,
            raw_transcript=transcript.raw_transcript,
            normalised_transcript=transcript.normalised_transcript,
            detected_intent=transcript.detected_intent,
            voice_risk_flags=transcript.voice_risk_flags,
            voice_eligible_for_planning=True,
            voice_rejection_reason=None,
            planner_backend=type(planner_backend).__name__,
            planner_called=True,
            planner_success=False,
            planner_latency_ms=None,
            raw_planner_response=None,
            json_valid=False,
            schema_valid=False,
            semantic_valid=False,
            safety_valid=False,
            execution_eligible=False,
            pipeline_false_accept=None,
            rejection_stage="planner_backend",
            rejection_reason="planner_backend_exception",
            error=f"{type(exc).__name__}: {exc}",
        )

    payload = response_to_dict(response)
    raw_text = get_field(payload, "raw_text", "text", "content")
    planner_success = bool(get_field(payload, "success", default=False))
    planner_backend_name = get_field(payload, "backend", "backend_name", default=type(planner_backend).__name__)
    planner_latency_ms = get_field(payload, "latency_ms")
    error_type = get_field(payload, "error_type")
    error_message = get_field(payload, "error_message")

    if not planner_success:
        return VoicePlannerBridgeResult(
            voice_input_id=transcript.voice_input_id,
            timestamp_utc=transcript.timestamp_utc,
            raw_transcript=transcript.raw_transcript,
            normalised_transcript=transcript.normalised_transcript,
            detected_intent=transcript.detected_intent,
            voice_risk_flags=transcript.voice_risk_flags,
            voice_eligible_for_planning=True,
            voice_rejection_reason=None,
            planner_backend=str(planner_backend_name),
            planner_called=True,
            planner_success=False,
            planner_latency_ms=planner_latency_ms,
            raw_planner_response=raw_text,
            json_valid=False,
            schema_valid=False,
            semantic_valid=False,
            safety_valid=False,
            execution_eligible=False,
            pipeline_false_accept=None,
            rejection_stage="planner_backend",
            rejection_reason=str(error_type or "planner_backend_failure"),
            error=str(error_message or error_type or "planner backend failed"),
        )

    validation = run_existing_validation(raw_text, validation_case_for(transcript.normalised_transcript, transcript.voice_input_id))
    execution_eligible = bool(validation["execution_eligible"])
    rejection_stage = None if execution_eligible else "deterministic_validators"
    rejection_reason = None if execution_eligible else str(validation["failure_mode"] or "not_execution_eligible")

    return VoicePlannerBridgeResult(
        voice_input_id=transcript.voice_input_id,
        timestamp_utc=transcript.timestamp_utc,
        raw_transcript=transcript.raw_transcript,
        normalised_transcript=transcript.normalised_transcript,
        detected_intent=transcript.detected_intent,
        voice_risk_flags=transcript.voice_risk_flags,
        voice_eligible_for_planning=True,
        voice_rejection_reason=None,
        planner_backend=str(planner_backend_name),
        planner_called=True,
        planner_success=True,
        planner_latency_ms=planner_latency_ms,
        raw_planner_response=raw_text,
        json_valid=bool(validation["json_valid"]),
        schema_valid=bool(validation["schema_valid"]),
        semantic_valid=bool(validation["semantic_valid"]),
        safety_valid=bool(validation["safety_valid"]),
        execution_eligible=execution_eligible,
        pipeline_false_accept=None,
        rejection_stage=rejection_stage,
        rejection_reason=rejection_reason,
        error=None,
    )
