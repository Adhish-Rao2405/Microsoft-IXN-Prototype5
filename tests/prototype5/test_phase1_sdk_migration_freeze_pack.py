import json
from pathlib import Path


REPORT = Path("docs/prototype5/phase1_sdk_migration_completion_report.md")
CLAIMS = Path("docs/prototype5/phase1_sdk_claims_and_evidence_matrix.md")
LIMITATIONS = Path("docs/prototype5/phase1_sdk_limitations_and_next_steps.md")
SUMMARY = Path("results/prototype5/mode_sdk/phase1_sdk_migration_summary.json")


def test_phase1_freeze_pack_files_exist():
    assert REPORT.exists()
    assert CLAIMS.exists()
    assert LIMITATIONS.exists()
    assert SUMMARY.exists()


def test_summary_json_lists_m3_to_m9_commits_and_evidence():
    payload = json.loads(SUMMARY.read_text(encoding="utf-8"))

    assert payload["status"] == "PHASE1_SDK_MIGRATION_COMPLETE"
    assert set(payload["latest_commits"]) == {"m3", "m4", "m5", "m6", "m7", "m8", "m9"}
    assert "results/prototype5/mode_sdk/sdk_mini_replay_validator_audit.json" in payload["evidence_files"]
    assert "results/prototype5/mode_sdk/sdk_action_envelope_mini_replay_results.json" in payload["evidence_files"]


def test_phase1_decision_and_phase2_readiness_are_present():
    payload = json.loads(SUMMARY.read_text(encoding="utf-8"))

    assert payload["phase1_decision"] == "COMPLETE"
    assert payload["phase2_readiness"]["voice_control_ready_to_start"] is True
    assert len(payload["phase2_readiness"]["conditions"]) >= 3
    assert any("must not bypass deterministic validators" in item for item in payload["phase2_readiness"]["conditions"])


def test_freeze_pack_does_not_overclaim_safety_or_voice_implementation():
    combined = "\n".join(
        [
            REPORT.read_text(encoding="utf-8"),
            CLAIMS.read_text(encoding="utf-8"),
            LIMITATIONS.read_text(encoding="utf-8"),
            SUMMARY.read_text(encoding="utf-8"),
        ]
    ).lower()

    forbidden_phrases = [
        "production-safe",
        "robot-certified",
        "voice is implemented",
    ]
    for phrase in forbidden_phrases:
        assert phrase not in combined


def test_claims_matrix_contains_required_sdk_claims():
    text = CLAIMS.read_text(encoding="utf-8")

    for claim_id in ["SDK-C1", "SDK-C2", "SDK-C3", "SDK-C4", "SDK-C5", "SDK-C6", "SDK-C7"]:
        assert claim_id in text
    assert "Deterministic validators remain the execution authority" in text


def test_completion_report_states_bounded_phase1_decision():
    text = REPORT.read_text(encoding="utf-8")

    assert "Phase 1 SDK migration is complete as a bounded integration and evidence path." in text
    assert "does not prove production robot safety" in text
    assert "does not implement voice control" in text
