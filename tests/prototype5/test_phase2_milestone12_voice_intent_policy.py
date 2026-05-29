from src.prototype5.voice_intent_policy import build_mock_voice_transcript


def test_clear_planning_command_is_eligible_for_planning():
    transcript = build_mock_voice_transcript("Move the red block to the inspection zone")

    assert transcript.detected_intent == "planning_command"
    assert transcript.eligible_for_planning is True


def test_stop_command_is_not_eligible():
    transcript = build_mock_voice_transcript("Stop the robot")

    assert transcript.detected_intent == "stop_command"
    assert transcript.eligible_for_planning is False
    assert {"stop_intent", "safety_critical_intent"}.issubset(transcript.voice_risk_flags)


def test_proceed_command_is_not_eligible_without_context():
    transcript = build_mock_voice_transcript("Proceed")

    assert transcript.detected_intent == "proceed_command"
    assert transcript.eligible_for_planning is False
    assert {"context_required", "proceed_intent"}.issubset(transcript.voice_risk_flags)


def test_ambiguous_command_fails_closed():
    transcript = build_mock_voice_transcript("Move it over there")

    assert transcript.eligible_for_planning is False
    assert "ambiguous_reference" in transcript.voice_risk_flags


def test_negation_sensitive_command_fails_closed():
    transcript = build_mock_voice_transcript("Do not move outside the safety zone")

    assert transcript.eligible_for_planning is False
    assert "negation_detected" in transcript.voice_risk_flags


def test_unsafe_command_fails_closed():
    transcript = build_mock_voice_transcript("Move the arm outside the safety zone")

    assert transcript.eligible_for_planning is False
    assert "unsafe_keyword" in transcript.voice_risk_flags


def test_non_command_does_not_enter_planner():
    transcript = build_mock_voice_transcript("Can you hear me")

    assert transcript.detected_intent == "non_command"
    assert transcript.eligible_for_planning is False
    assert "non_command" in transcript.voice_risk_flags


def test_low_confidence_transcript_fails_closed():
    transcript = build_mock_voice_transcript(
        "Move the red block to the inspection zone",
        transcript_confidence=0.5,
    )

    assert transcript.eligible_for_planning is False
    assert "low_confidence" in transcript.voice_risk_flags


def test_partial_transcript_fails_closed():
    transcript = build_mock_voice_transcript("Move the red", is_partial=True)

    assert transcript.eligible_for_planning is False
    assert "partial_transcript" in transcript.voice_risk_flags


def test_empty_transcript_fails_closed():
    transcript = build_mock_voice_transcript("")

    assert transcript.detected_intent == "unknown"
    assert transcript.eligible_for_planning is False
    assert "empty_transcript" in transcript.voice_risk_flags


def test_stop_proceed_conflict_fails_closed():
    transcript = build_mock_voice_transcript("Stop the robot and proceed")

    assert transcript.eligible_for_planning is False
    assert "stop_proceed_conflict" in transcript.voice_risk_flags
    assert transcript.detected_intent in {"stop_command", "unknown"}


def test_clarification_requires_context_and_is_not_planning_eligible():
    transcript = build_mock_voice_transcript("Actually use the red block")

    assert transcript.detected_intent == "clarification"
    assert transcript.eligible_for_planning is False
    assert {"context_required", "clarification_without_context"}.issubset(transcript.voice_risk_flags)
