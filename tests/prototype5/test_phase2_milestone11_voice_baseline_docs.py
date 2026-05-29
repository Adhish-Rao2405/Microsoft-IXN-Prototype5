import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

DOCS = [
    ROOT / "docs" / "prototype5" / "phase2_milestone11_voice_baseline_spec.md",
    ROOT / "docs" / "prototype5" / "phase2_milestone11_voice_safety_policy.md",
    ROOT / "docs" / "prototype5" / "phase2_milestone11_transcript_contract.md",
    ROOT / "docs" / "prototype5" / "phase2_milestone11_stop_proceed_policy.md",
    ROOT / "docs" / "prototype5" / "phase2_milestone11_non_goals_and_claim_boundaries.md",
]

EVIDENCE = [
    ROOT / "results" / "prototype5" / "mode_voice" / "phase2_milestone11_voice_risk_register.json",
    ROOT / "results" / "prototype5" / "mode_voice" / "phase2_milestone11_voice_claims_matrix.csv",
]

PROTECTED_DRAFT = "dissertation_drafts/DISS_DRAFT_cleaned.tex"


def _combined_doc_text() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in DOCS).lower()


def test_required_docs_and_optional_evidence_exist():
    assert [path for path in DOCS if not path.exists()] == []
    assert [path for path in EVIDENCE if not path.exists()] == []


def test_voice_is_input_modality_only():
    assert "voice is an input modality only" in _combined_doc_text()


def test_voice_never_bypasses_deterministic_validation():
    text = _combined_doc_text()

    assert "voice must never bypass" in text
    assert "deterministic validators" in text
    assert "voice must never bypass deterministic validation" in text


def test_voice_never_directly_triggers_execution():
    text = _combined_doc_text()

    assert "voice must never directly trigger execution" in text
    assert "voice commands cannot bypass deterministic validation or directly trigger execution" in text


def test_transcript_and_model_plan_are_untrusted():
    text = _combined_doc_text()

    assert "a transcript is untrusted input" in text
    assert "a model-generated plan remains an untrusted proposal" in text


def test_stop_proceed_policy_is_present():
    text = (ROOT / "docs" / "prototype5" / "phase2_milestone11_stop_proceed_policy.md").read_text(
        encoding="utf-8"
    ).lower()

    for phrase in [
        "stop",
        "abort",
        "cancel",
        "emergency stop",
        "halt",
        "proceed",
        "continue",
        "resume",
        "go ahead",
        "proceed commands must not override rejection",
        "proceed requires a valid pending context",
    ]:
        assert phrase in text


def test_strict_non_goals_are_present():
    text = (
        ROOT / "docs" / "prototype5" / "phase2_milestone11_non_goals_and_claim_boundaries.md"
    ).read_text(encoding="utf-8").lower()

    for phrase in [
        "no real robot execution",
        "no certified emergency-stop system",
        "no production voice-control claim",
        "no full speech benchmark",
        "no full 30-command sdk voice replay",
        "no physical microphone integration requirement",
        "no validator mutation",
        "no orchestrator mutation",
        "no safety policy weakening",
        "no dashboard/app work",
        "no phase f-j work",
        "no staging dissertation_drafts/diss_draft_cleaned.tex",
    ]:
        assert phrase in text


def test_claim_boundaries_reject_overclaims():
    text = _combined_doc_text()

    for phrase in [
        "no certified emergency-stop claim",
        "does not implement real robot execution",
        "does not implement real robot execution, certified emergency stop, production robot safety, or production voice control",
        "no production voice-control claim",
        "the following claims are forbidden",
        "the system supports safe voice-controlled robot execution",
        "the system implements emergency stop",
        "the system proves voice control is safe",
        "the system is ready for industrial deployment",
        "the voice interface improves robot autonomy",
    ]:
        assert phrase in text


def test_transcript_contract_defines_planning_not_execution_eligibility():
    text = (ROOT / "docs" / "prototype5" / "phase2_milestone11_transcript_contract.md").read_text(
        encoding="utf-8"
    ).lower()

    assert '"eligible_for_planning": false' in text
    assert "does not mean execution eligible" in text
    assert "detected_intent" in text
    assert "planning_command | stop_command | proceed_command" in text


def test_protected_dissertation_draft_is_not_staged():
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    staged_files = set(result.stdout.splitlines())
    assert PROTECTED_DRAFT not in staged_files
