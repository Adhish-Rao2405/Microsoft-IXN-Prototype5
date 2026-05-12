import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BENCHMARK = ROOT / "configs" / "prototype5" / "mode_e_industrial_benchmark.json"


def load_cases():
    payload = json.loads(BENCHMARK.read_text(encoding="utf-8"))
    return payload, payload["cases"]


def test_mode_e_benchmark_file_exists_and_has_required_shape():
    payload, cases = load_cases()
    assert payload["benchmark_id"] == "prototype5_mode_e_industrial_v1"
    assert len(cases) == 30
    assert "does not claim comprehensive industrial robotics coverage" in payload["scope_boundary"]

    required_fields = {
        "id",
        "scenario_family",
        "difficulty",
        "command",
        "expected_risk_class",
        "expected_issue",
        "notes",
    }
    for case in cases:
        assert required_fields.issubset(case)
        assert case["command"].strip()


def test_mode_e_benchmark_distribution_is_balanced():
    _, cases = load_cases()
    assert Counter(case["difficulty"] for case in cases) == {
        "clear": 10,
        "ambiguous": 10,
        "unsafe_or_invalid": 10,
    }
    assert Counter(case["scenario_family"] for case in cases) == {
        "pick_and_place": 5,
        "conveyor_sorting": 5,
        "inspection_quality": 5,
        "warehouse_transfer": 5,
        "human_proximity": 5,
        "restricted_zone": 5,
    }


def test_mode_e_ids_commands_and_labels_are_valid():
    _, cases = load_cases()
    expected_ids = [f"E{index:03d}" for index in range(1, 31)]
    ids = [case["id"] for case in cases]
    commands = [case["command"] for case in cases]

    assert ids == expected_ids
    assert len(set(ids)) == 30
    assert len(set(commands)) == 30

    assert {case["expected_risk_class"] for case in cases}.issubset(
        {
            "execution_eligible_candidate",
            "requires_clarification",
            "reject_before_execution",
        }
    )
    assert {case["expected_issue"] for case in cases}.issubset(
        {
            "none",
            "ambiguous_reference",
            "missing_target",
            "missing_location",
            "unsafe_human_proximity",
            "restricted_zone",
            "hazardous_action",
            "out_of_scope_action",
            "insufficient_clearance",
        }
    )
