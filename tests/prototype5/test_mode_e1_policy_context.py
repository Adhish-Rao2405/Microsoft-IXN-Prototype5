import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VOCABULARY = ROOT / "configs" / "prototype5" / "mode_e_industrial_vocabulary.json"
POLICY = ROOT / "configs" / "prototype5" / "mode_e_industrial_policy_rules.json"
AUDIT_SCRIPT = ROOT / "scripts" / "prototype5" / "run_mode_e_policy_audit.py"


def test_mode_e1_required_files_exist():
    assert VOCABULARY.exists()
    assert POLICY.exists()
    assert AUDIT_SCRIPT.exists()


def test_mode_e1_vocabulary_has_required_sections():
    payload = json.loads(VOCABULARY.read_text(encoding="utf-8"))
    assert payload["vocabulary_id"] == "prototype5_mode_e_industrial_vocabulary_v1"
    assert "entities" in payload
    assert "policy_terms" in payload
    for section in ["components", "locations", "restricted_locations", "systems", "actors"]:
        assert section in payload["entities"]
        assert payload["entities"][section]
    for term in ["conveyor", "human work area", "inspection station", "restricted zone"]:
        assert term in json.dumps(payload).lower()


def test_mode_e1_policy_has_required_reject_and_clarify_rules():
    payload = json.loads(POLICY.read_text(encoding="utf-8"))
    rules = payload["rules"]
    decisions = {rule["decision"] for rule in rules}
    names = {rule["name"] for rule in rules}
    assert "reject_before_execution" in decisions
    assert "requires_clarification" in decisions
    assert "execution_eligible_candidate" in decisions
    assert "reject_human_proximity_motion" in names
    assert "reject_restricted_zone_entry" in names
    assert "reject_hazardous_action" in names
    assert "clarify_ambiguous_reference" in names


def test_mode_e1_policy_audit_outputs_are_complete(tmp_path):
    output_dir = tmp_path / "mode_e"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/prototype5/run_mode_e_policy_audit.py",
            "--output-dir",
            str(output_dir),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    audit_json = output_dir / "mode_e_policy_audit.json"
    audit_md = output_dir / "mode_e_policy_audit.md"
    assert audit_json.exists()
    assert audit_md.exists()

    audit = json.loads(audit_json.read_text(encoding="utf-8"))
    assert audit["audit_status"] == "COMPLETE_POLICY_CONTEXT"
    assert audit["total_cases"] == 30
    assert audit["covered_cases"] == 30
    assert audit["coverage_rate"] == 1.0
    assert audit["policy_rules_count"] >= 5
    assert audit["mismatched_expected_decisions"] == []
    assert audit["clear_cases_blocked"] == []
    assert audit["unsafe_cases_not_blocked"] == []
    assert audit["ambiguous_cases_not_clarified"] == []
    assert {path.name for path in output_dir.iterdir()} == {
        "mode_e_policy_audit.json",
        "mode_e_policy_audit.md",
    }


def test_mode_e1_docs_contain_bounded_language():
    docs = [
        ROOT / "docs" / "prototype5" / "mode_e1_industrial_policy_context.md",
        ROOT / "docs" / "prototype5" / "mode_e1_evidence_summary.md",
    ]
    assert [path for path in docs if not path.exists()] == []
    combined = "\n".join(path.read_text(encoding="utf-8") for path in docs).lower()
    assert "the purpose is to avoid evaluating industrial commands against undefined vocabulary" in combined
    assert "not a certified industrial robot safety system" in combined
    assert "not prove industrial safety" in combined
    assert "e.2 should not be run" in combined
