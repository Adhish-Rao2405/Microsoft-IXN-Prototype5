import json

import pytest

from src.prototype5.voice_intent_policy import build_mock_voice_transcript
from src.prototype5.voice_transcript_contract import VoiceTranscript


def test_transcript_contract_serialises_to_dict_and_json():
    transcript = build_mock_voice_transcript(
        "Move the red block to the inspection zone",
        voice_input_id="voice_test_001",
        timestamp_utc="2026-05-29T00:00:00+00:00",
    )

    payload = transcript.to_dict()
    encoded = json.dumps(payload)

    assert json.loads(encoded)["voice_input_id"] == "voice_test_001"
    assert payload["audio_source_type"] == "mocked_transcript"
    assert payload["transcription_backend"] == "mock"
    assert payload["normalised_transcript"] == "Move the red block to the inspection zone"
    assert payload["eligible_for_planning"] is True


def test_contract_rejects_unknown_source_backend_and_intent():
    base = {
        "voice_input_id": "voice_test_002",
        "timestamp_utc": "2026-05-29T00:00:00+00:00",
        "audio_source_type": "mocked_transcript",
        "transcription_backend": "mock",
        "raw_transcript": "hello",
        "normalised_transcript": "hello",
        "transcript_confidence": 1.0,
        "language": "en",
        "is_partial": False,
        "detected_intent": "non_command",
        "voice_risk_flags": ["non_command"],
        "eligible_for_planning": False,
        "rejection_reason": "non_command",
    }

    with pytest.raises(ValueError):
        VoiceTranscript(**{**base, "audio_source_type": "stream"})
    with pytest.raises(ValueError):
        VoiceTranscript(**{**base, "transcription_backend": "whisper_runtime"})
    with pytest.raises(ValueError):
        VoiceTranscript(**{**base, "detected_intent": "execute_now"})


def test_contract_rejects_confidence_outside_unit_interval():
    with pytest.raises(ValueError):
        build_mock_voice_transcript("Move the red block", transcript_confidence=1.5)


def test_normalisation_collapses_whitespace_without_removing_negation():
    transcript = build_mock_voice_transcript("  Do   not   move outside the safety zone  ")

    assert transcript.normalised_transcript == "Do not move outside the safety zone"
    assert "negation_detected" in transcript.voice_risk_flags
    assert transcript.eligible_for_planning is False


def test_m12_uses_mocked_transcripts_only_for_actual_policy_output():
    transcript = build_mock_voice_transcript("Move the red block to the inspection zone")

    assert transcript.audio_source_type == "mocked_transcript"
    assert transcript.transcription_backend == "mock"
