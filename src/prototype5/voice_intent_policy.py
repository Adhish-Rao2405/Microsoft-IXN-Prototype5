"""
Deterministic mocked transcript policy for Prototype 5 Phase 2 Milestone 12.

The policy treats transcript text as untrusted input and conservatively decides
whether it may be passed to a future planner stage. It does not call an LLM,
SDK backend, deterministic validators, audio runtime, or benchmark runner.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Iterable
from uuid import uuid4

from .voice_transcript_contract import VoiceTranscript, utc_now


LOW_CONFIDENCE_THRESHOLD = 0.75

STOP_PHRASES = (
    "emergency stop",
    "e-stop",
    "stop the robot",
    "stop robot",
    "stop",
    "halt",
    "abort task",
    "abort",
    "cancel task",
    "cancel",
    "shut down the task",
)

PROCEED_PHRASES = (
    "okay proceed",
    "yes continue",
    "go ahead",
    "carry on",
    "proceed",
    "continue",
    "resume",
)

CLARIFICATION_PHRASES = (
    "i mean",
    "no the other one",
    "use the left object",
    "actually use",
    "not that zone",
    "instead",
)

NON_COMMAND_PHRASES = (
    "can you hear me",
    "what happened",
    "this is slow",
    "hello",
    "testing",
    "is this working",
    "thank you",
    "that was good",
)

TASK_VERBS = (
    "move",
    "pick",
    "pick up",
    "place",
    "put",
    "inspect",
    "open",
    "close",
    "reset",
)

AMBIGUOUS_REFERENTS = (
    "it",
    "that",
    "this",
    "there",
    "over there",
    "the other one",
    "that one",
    "this one",
    "left one",
    "right one",
)

NEGATION_TERMS = ("do not", "don't", "cannot", "can't", "not", "never", "no")

UNSAFE_PHRASES = (
    "outside the safety zone",
    "outside safety zone",
    "ignore safety",
    "disable safety",
    "maximum speed",
    "fast as possible",
)

UNSAFE_TERMS = ("unsafe", "danger", "collision", "human", "person", "emergency", "force", "override", "bypass", "crash")

ZONE_TERMS = ("zone", "area", "position", "home")
OBJECT_TERMS = ("block", "object", "component", "arm", "robot", "cube")
BACKGROUND_NOISE_MARKERS = ("[noise]", "(noise)", "background noise", "[inaudible]", "(inaudible)")

DISQUALIFYING_FLAGS = {
    "low_confidence",
    "partial_transcript",
    "empty_transcript",
    "ambiguous_reference",
    "negation_detected",
    "unsafe_keyword",
    "stop_intent",
    "proceed_intent",
    "context_required",
    "stop_proceed_conflict",
    "unknown_intent",
    "non_command",
}


def normalise_transcript(raw_transcript: str) -> str:
    """Apply whitespace-only normalisation without rewriting command meaning."""

    return re.sub(r"\s+", " ", str(raw_transcript)).strip()


def phrase_present(text: str, phrases: Iterable[str]) -> bool:
    return any(re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text) for phrase in phrases)


def classify_intent(normalised_transcript: str, risk_flags: set[str] | None = None) -> str:
    text = normalised_transcript.lower()
    flags = risk_flags or set()

    if not text:
        return "unknown"
    if "stop_proceed_conflict" in flags:
        return "stop_command" if "stop_intent" in flags else "unknown"
    if phrase_present(text, STOP_PHRASES):
        return "stop_command"
    if phrase_present(text, PROCEED_PHRASES):
        return "proceed_command"
    if phrase_present(text, CLARIFICATION_PHRASES):
        return "clarification"
    if phrase_present(text, NON_COMMAND_PHRASES):
        return "non_command"
    if len(text) < 3:
        return "unknown"
    if phrase_present(text, TASK_VERBS):
        return "planning_command"
    return "unknown"


def detect_risk_flags(
    normalised_transcript: str,
    *,
    transcript_confidence: float,
    is_partial: bool,
) -> list[str]:
    text = normalised_transcript.lower()
    flags: set[str] = set()

    has_stop = phrase_present(text, STOP_PHRASES)
    has_proceed = phrase_present(text, PROCEED_PHRASES)

    if transcript_confidence < LOW_CONFIDENCE_THRESHOLD:
        flags.add("low_confidence")
    if is_partial:
        flags.add("partial_transcript")
    if not text:
        flags.add("empty_transcript")
        flags.add("unknown_intent")
    if phrase_present(text, AMBIGUOUS_REFERENTS):
        flags.add("ambiguous_reference")
    if phrase_present(text, NEGATION_TERMS):
        flags.add("negation_detected")
    if phrase_present(text, UNSAFE_PHRASES) or phrase_present(text, UNSAFE_TERMS):
        flags.add("unsafe_keyword")
    if phrase_present(text, BACKGROUND_NOISE_MARKERS):
        flags.add("background_noise_marker")
    if has_stop:
        flags.add("stop_intent")
        flags.add("safety_critical_intent")
    if has_proceed:
        flags.add("proceed_intent")
        flags.add("context_required")
    if has_stop and has_proceed:
        flags.add("stop_proceed_conflict")
    if re.search(r"[-+]?\d+(\.\d+)?", text):
        flags.add("coordinate_or_number_present")
    if phrase_present(text, ZONE_TERMS):
        flags.add("zone_reference_present")
    if phrase_present(text, OBJECT_TERMS):
        flags.add("object_reference_present")

    intent = classify_intent(normalised_transcript, flags)
    if intent == "clarification":
        flags.add("context_required")
        flags.add("clarification_without_context")
    elif intent == "non_command":
        flags.add("non_command")
    elif intent == "unknown":
        flags.add("unknown_intent")

    return sorted(flags)


def rejection_reason_for(intent: str, risk_flags: list[str]) -> str | None:
    if intent != "planning_command":
        if intent == "stop_command":
            return "stop_intent_not_planning_command"
        if intent == "proceed_command":
            return "proceed_requires_valid_pending_context"
        if intent == "clarification":
            return "clarification_requires_valid_pending_context"
        if intent == "non_command":
            return "non_command"
        return "unknown_intent"

    for flag in sorted(DISQUALIFYING_FLAGS):
        if flag in risk_flags:
            return flag
    return None


def is_eligible_for_planning(intent: str, risk_flags: list[str]) -> bool:
    return intent == "planning_command" and DISQUALIFYING_FLAGS.isdisjoint(risk_flags)


def build_mock_voice_transcript(
    raw_transcript: str,
    *,
    transcript_confidence: float = 1.0,
    is_partial: bool = False,
    voice_input_id: str | None = None,
    timestamp_utc: str | None = None,
    language: str = "en",
) -> VoiceTranscript:
    normalised = normalise_transcript(raw_transcript)
    risk_flags = detect_risk_flags(
        normalised,
        transcript_confidence=float(transcript_confidence),
        is_partial=bool(is_partial),
    )
    intent = classify_intent(normalised, set(risk_flags))
    eligible = is_eligible_for_planning(intent, risk_flags)
    rejection_reason = None if eligible else rejection_reason_for(intent, risk_flags)

    return VoiceTranscript(
        voice_input_id=voice_input_id or f"mock_voice_{uuid4().hex}",
        timestamp_utc=timestamp_utc or utc_now(),
        audio_source_type="mocked_transcript",
        transcription_backend="mock",
        raw_transcript=str(raw_transcript),
        normalised_transcript=normalised,
        transcript_confidence=float(transcript_confidence),
        language=language,
        is_partial=bool(is_partial),
        detected_intent=intent,
        voice_risk_flags=risk_flags,
        eligible_for_planning=eligible,
        rejection_reason=rejection_reason,
    )


def summarise_transcripts(transcripts: list[VoiceTranscript]) -> dict[str, object]:
    intent_counts = Counter(item.detected_intent for item in transcripts)
    risk_flag_counts = Counter(flag for item in transcripts for flag in item.voice_risk_flags)
    return {
        "cases_total": len(transcripts),
        "cases_eligible_for_planning": sum(1 for item in transcripts if item.eligible_for_planning),
        "cases_rejected": sum(1 for item in transcripts if not item.eligible_for_planning),
        "intent_counts": dict(sorted(intent_counts.items())),
        "risk_flag_counts": dict(sorted(risk_flag_counts.items())),
    }
