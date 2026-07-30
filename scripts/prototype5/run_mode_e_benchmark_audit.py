"""Mode E industrial benchmark representativeness audit."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_PATH = REPO_ROOT / "configs" / "prototype5" / "mode_e_industrial_benchmark.json"
RESULTS_DIR = REPO_ROOT / "results" / "prototype5" / "mode_e"
AUDIT_JSON = RESULTS_DIR / "mode_e_benchmark_audit.json"
AUDIT_MD = RESULTS_DIR / "mode_e_benchmark_audit.md"

ALLOWED_DIFFICULTIES = {"clear", "ambiguous", "unsafe_or_invalid"}
ALLOWED_FAMILIES = {
    "pick_and_place",
    "conveyor_sorting",
    "inspection_quality",
    "warehouse_transfer",
    "human_proximity",
    "restricted_zone",
}
ALLOWED_RISK_CLASSES = {
    "execution_eligible_candidate",
    "requires_clarification",
    "reject_before_execution",
}
ALLOWED_ISSUES = {
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
REQUIRED_CASE_FIELDS = {
    "id",
    "scenario_family",
    "difficulty",
    "command",
    "expected_risk_class",
    "expected_issue",
    "notes",
}


def load_benchmark(path: Path = BENCHMARK_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def validate_benchmark(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
    cases = payload.get("cases", [])
    errors: list[str] = []
    if not isinstance(cases, list):
        return [], ["cases_not_list"], {}

    ids = [str(case.get("id", "")) for case in cases if isinstance(case, dict)]
    commands = [str(case.get("command", "")).strip() for case in cases if isinstance(case, dict)]
    difficulty_counts = Counter(str(case.get("difficulty", "")) for case in cases if isinstance(case, dict))
    family_counts = Counter(str(case.get("scenario_family", "")) for case in cases if isinstance(case, dict))
    risk_counts = Counter(str(case.get("expected_risk_class", "")) for case in cases if isinstance(case, dict))
    issue_counts = Counter(str(case.get("expected_issue", "")) for case in cases if isinstance(case, dict))

    if len(cases) != 30:
        errors.append(f"expected_30_cases_found_{len(cases)}")
    expected_ids = [f"E{index:03d}" for index in range(1, 31)]
    if ids != expected_ids:
        errors.append("ids_must_match_E001_to_E030_in_order")
    if len(set(ids)) != len(ids):
        errors.append("duplicate_ids")
    if any(not command for command in commands):
        errors.append("empty_command")
    if len(set(commands)) != len(commands):
        errors.append("duplicate_commands")
    if difficulty_counts != {"clear": 10, "ambiguous": 10, "unsafe_or_invalid": 10}:
        errors.append(f"invalid_difficulty_distribution:{dict(difficulty_counts)}")
    if set(family_counts) != ALLOWED_FAMILIES or any(count != 5 for count in family_counts.values()):
        errors.append(f"invalid_scenario_family_distribution:{dict(family_counts)}")

    for index, case in enumerate(cases, start=1):
        if not isinstance(case, dict):
            errors.append(f"case_{index}_not_object")
            continue
        missing = REQUIRED_CASE_FIELDS - set(case)
        if missing:
            errors.append(f"{case.get('id', index)}_missing_fields:{sorted(missing)}")
        if case.get("difficulty") not in ALLOWED_DIFFICULTIES:
            errors.append(f"{case.get('id', index)}_invalid_difficulty:{case.get('difficulty')}")
        if case.get("scenario_family") not in ALLOWED_FAMILIES:
            errors.append(f"{case.get('id', index)}_invalid_scenario_family:{case.get('scenario_family')}")
        if case.get("expected_risk_class") not in ALLOWED_RISK_CLASSES:
            errors.append(f"{case.get('id', index)}_invalid_expected_risk_class:{case.get('expected_risk_class')}")
        if case.get("expected_issue") not in ALLOWED_ISSUES:
            errors.append(f"{case.get('id', index)}_invalid_expected_issue:{case.get('expected_issue')}")

    metrics = {
        "total_cases": len(cases),
        "cases_by_difficulty": dict(sorted(difficulty_counts.items())),
        "cases_by_scenario_family": dict(sorted(family_counts.items())),
        "expected_risk_class_distribution": dict(sorted(risk_counts.items())),
        "expected_issue_distribution": dict(sorted(issue_counts.items())),
    }
    return cases, errors, metrics


def build_audit(payload: dict[str, Any]) -> dict[str, Any]:
    cases, errors, metrics = validate_benchmark(payload)
    coverage_status = "COMPLETE_BALANCED_EXTENSION" if not errors else "INVALID_BENCHMARK"
    return {
        "mode": "E",
        "name": "Industrial Scenario Benchmark Expansion and Representativeness Audit",
        "status": coverage_status,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "benchmark_file": str(BENCHMARK_PATH.relative_to(REPO_ROOT).as_posix()),
        "benchmark_id": payload.get("benchmark_id", ""),
        "purpose": payload.get("purpose", ""),
        "scope_boundary": payload.get("scope_boundary", ""),
        "metrics": metrics,
        "validation_errors": errors,
        "case_ids": [case.get("id", "") for case in cases],
        "claim_boundary": (
            "Mode E improves benchmark scenario coverage but does not prove production robot safety, "
            "full industrial generalisation, or general local SLM reliability."
        ),
    }


def build_markdown(audit: dict[str, Any]) -> str:
    metrics = audit["metrics"]
    lines = [
        "# Prototype 5 Mode E Benchmark Audit",
        "",
        f"- Status: {audit['status']}",
        f"- Benchmark ID: `{audit['benchmark_id']}`",
        f"- Benchmark file: `{audit['benchmark_file']}`",
        f"- Total cases: {metrics.get('total_cases', 0)}",
        "",
        "## Coverage Summary",
        "",
        "### Difficulty",
        "",
    ]
    for key, value in metrics.get("cases_by_difficulty", {}).items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "### Scenario Family", ""])
    for key, value in metrics.get("cases_by_scenario_family", {}).items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "### Expected Risk Class", ""])
    for key, value in metrics.get("expected_risk_class_distribution", {}).items():
        lines.append(f"- {key}: {value}")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            audit["claim_boundary"],
            "",
            "This extension improves scenario coverage but does not make the benchmark comprehensive.",
            "",
        ]
    )
    if audit["validation_errors"]:
        lines.extend(["## Validation Errors", ""])
        lines.extend(f"- {error}" for error in audit["validation_errors"])
        lines.append("")
    return "\n".join(lines)


def run_audit(output_dir: Path = RESULTS_DIR) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = load_benchmark()
    audit = build_audit(payload)
    (output_dir / AUDIT_JSON.name).write_text(
        json.dumps(audit, indent=2),
        encoding="utf-8",
    )
    (output_dir / AUDIT_MD.name).write_text(build_markdown(audit), encoding="utf-8")
    return audit


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the Mode E benchmark.")
    parser.add_argument("--output-dir", type=Path, default=RESULTS_DIR)
    args = parser.parse_args()

    audit = run_audit(args.output_dir)
    print("Prototype 5 Mode E benchmark audit:", audit["status"])
    print(f"Total cases: {audit['metrics'].get('total_cases', 0)}")
    print(f"Validation errors: {len(audit['validation_errors'])}")
    return 0 if audit["status"] == "COMPLETE_BALANCED_EXTENSION" else 1


if __name__ == "__main__":
    raise SystemExit(main())
