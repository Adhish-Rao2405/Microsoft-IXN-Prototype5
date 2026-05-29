"""
Voice transcript contract for Prototype 5 Phase 2.

This module defines the data shape for future voice-derived transcript input.
It does not process audio, call a planner, call validators, or assign execution
eligibility. ``eligible_for_planning`` only means the transcript may enter a
planner stage; it never means execution eligible.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


ALLOWED_AUDIO_SOURCE_TYPES = ("microphone", "audio_file", "mocked_transcript")
ALLOWED_TRANSCRIPTION_BACKENDS = ("mock", "foundry_whisper", "other_local_stt")
ALLOWED_DETECTED_INTENTS = (
    "planning_command",
    "stop_command",
    "proceed_command",
    "clarification",
    "non_command",
    "unknown",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class VoiceTranscript:
    voice_input_id: str
    timestamp_utc: str
    audio_source_type: str
    transcription_backend: str
    raw_transcript: str
    normalised_transcript: str
    transcript_confidence: float
    language: str
    is_partial: bool
    detected_intent: str
    voice_risk_flags: list[str]
    eligible_for_planning: bool
    rejection_reason: str | None

    def __post_init__(self) -> None:
        if self.audio_source_type not in ALLOWED_AUDIO_SOURCE_TYPES:
            raise ValueError(f"Unsupported audio_source_type: {self.audio_source_type}")
        if self.transcription_backend not in ALLOWED_TRANSCRIPTION_BACKENDS:
            raise ValueError(f"Unsupported transcription_backend: {self.transcription_backend}")
        if self.detected_intent not in ALLOWED_DETECTED_INTENTS:
            raise ValueError(f"Unsupported detected_intent: {self.detected_intent}")
        if not 0.0 <= float(self.transcript_confidence) <= 1.0:
            raise ValueError("transcript_confidence must be between 0.0 and 1.0")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
