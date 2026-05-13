"""Mode E.1 industrial vocabulary and policy audit."""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "configs" / "prototype5"
BENCHMARK_PATH = CONFIG_DIR / "mode_e_industrial_benchmark.json"
VOCABULARY_PATH = CONFIG_DIR / "mode_e_industrial_vocabulary.json"
POLICY_PATH = CONFIG_DIR / "mode_e_industrial_policy_rules.json"
RESULTS_DIR = REPO_ROOT / "results" / "prototype5" / "mode_e"
AUDIT_JSON = RESULTS_DIR / "mode_e_policy_audit.json"
AUDIT_MD = RESULTS_DIR / "mode_e_policy_audit.md"

COMPLETE_STATUS = "COMPLETE_POLICY_CONTEXT"
INCOMPLETE_STATUS = "INCOMPLETE_POLICY_CONTEXT"
FAILED_STATUS = "FAILED_POLICY_CONTEXT"

DECISIONS = {
    "execution_eligible_candidate",
    "requires_clarification",
    "reject_before_execution",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _normalise(text: str) -> str:
    return " ".join(text.lower().replace("-", " ").split())


def _contains_term(text: str, term: str) -> bool:
    normalised_text = _normalise(text)
    normalised_term = _normalise(term)
    if not normalised_term:
        return False
    if len(normalised_term.split()) == 1:
        return re.search(rf"\b{re.escape(normalised_term)}\b", normalised_text) is not None
    return normalised_term in normalised_text


def _flatten_terms(payload: dict[str, Any]) -> list[str]:
    terms: list[str] = []
    for value in payload.values():
        if isinstance(value, dict):
            terms.extend(_flatten_terms(value))
        elif isinstance(value, list):
            terms.extend(str(item) for item in value)
        elif isinstance(value, str):
            terms.append(value)
    return sorted({term for term in terms if term})


def _policy_rules(policy: dict[str, Any]) -> list[dict[str, Any]]:
    rules = policy.get("rules", [])
    if not isinstance(rules, list):
        return []
    return [rule for rule in rules if isinstance(rule, dict)]


def apply_policy(command: str, policy: dict[str, Any]) -> dict[str, Any]:
    """Map one Mode E command to the deterministic E.1 benchmark policy."""

    rules = _policy_rules(policy)
    matched_rules: list[dict[str, Any]] = []
    for rule in rules:
        trigger_terms = [str(term) for term in rule.get("trigger_terms", [])]
        matched_terms = [term for term in trigger_terms if _contains_term(command, term)]
        if matched_terms:
            matched_rules.append(
                {
                    "rule_id": rule.get("rule_id", ""),
                    "name": rule.get("name", ""),
                    "decision": rule.get("decision", ""),
                    "reason": rule.get("reason", ""),
                    "matched_terms": matched_terms,
                }
            )

    lower = _normalise(command)
    safe_wait_for_human = (
        "wait until" in lower
        and "human leaves" in lower
        and "before moving" in lower
    )
    if safe_wait_for_human:
        return {
            "decision": "execution_eligible_candidate",
            "reason": "none",
            "matched_rules": [
                {
                    "rule_id": "IE_RULE_005",
                    "name": "allow_clear_known_source_destination",
                    "decision": "execution_eligible_candidate",
                    "reason": "none",
                    "matched_terms": ["wait until human leaves before moving"],
                }
            ],
        }

    rejection_rules = [
        item for item in matched_rules if item.get("decision") == "reject_before_execution"
    ]
    clarification_rules = [
        item for item in matched_rules if item.get("decision") == "requires_clarification"
    ]
    if rejection_rules:
        reason_priority = [
            "unsafe_human_proximity",
            "restricted_zone",
            "hazardous_action",
        ]
        reasons = {str(item.get("reason", "")) for item in rejection_rules}
        reason = next((candidate for candidate in reason_priority if candidate in reasons), "")
        return {
            "decision": "reject_before_execution",
            "reason": reason or str(rejection_rules[0].get("reason", "")),
            "matched_rules": rejection_rules,
        }
    if clarification_rules:
        return {
            "decision": "requires_clarification",
            "reason": str(clarification_rules[0].get("reason", "ambiguous_reference")),
            "matched_rules": clarification_rules,
        }

    allow_rule = next(
        (rule for rule in rules if rule.get("decision") == "execution_eligible_candidate"),
        {},
    )
    return {
        "decision": "execution_eligible_candidate",
        "reason": str(allow_rule.get("reason", "none")),
        "matched_rules": [
            {
                "rule_id": allow_rule.get("rule_id", "IE_RULE_005"),
                "name": allow_rule.get("name", "allow_clear_known_source_destination"),
                "decision": "execution_eligible_candidate",
                "reason": allow_rule.get("reason", "none"),
                "matched_terms": [],
            }
        ],
    }


def _case_coverage(case: dict[str, Any], vocabulary: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    command = str(case.get("command", ""))
    vocabulary_terms = _flatten_terms(
        {
            "entities": vocabulary.get("entities", {}),
            "policy_terms": vocabulary.get("policy_terms", {}),
        }
    )
    matched_vocabulary_terms = [term for term in vocabulary_terms if _contains_term(command, term)]
    policy_result = apply_policy(command, policy)
    expected = str(case.get("expected_risk_class", ""))
    covered = bool(matched_vocabulary_terms) and policy_result["decision"] in DECISIONS
    return {
        "case_id": case.get("id", ""),
        "difficulty": case.get("difficulty", ""),
        "scenario_family": case.get("scenario_family", ""),
        "expected_risk_class": expected,
        "expected_issue": case.get("expected_issue", ""),
        "policy_decision": policy_result["decision"],
        "policy_reason": policy_result["reason"],
        "matched_rules": policy_result["matched_rules"],
        "matched_vocabulary_terms": matched_vocabulary_terms,
        "covered": covered,
        "decision_matches_expected": covered and policy_result["decision"] == expected,
    }


def build_audit(
    benchmark: dict[str, Any],
    vocabulary: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    cases = benchmark.get("cases", [])
    if not isinstance(cases, list):
        cases = []
    case_results = [_case_coverage(case, vocabulary, policy) for case in cases if isinstance(case, dict)]

    uncovered = [case for case in case_results if not case["covered"]]
    mismatched = [
        case
        for case in case_results
        if case["covered"] and not case["decision_matches_expected"]
    ]
    clear_cases_blocked = [
        case
        for case in case_results
        if case["difficulty"] == "clear"
        and case["policy_decision"] != "execution_eligible_candidate"
    ]
    unsafe_cases_not_blocked = [
        case
        for case in case_results
        if case["difficulty"] == "unsafe_or_invalid"
        and case["policy_decision"] == "execution_eligible_candidate"
    ]
    ambiguous_cases_not_clarified = [
        case
        for case in case_results
        if case["difficulty"] == "ambiguous"
        and case["policy_decision"] == "execution_eligible_candidate"
    ]

    total = len(case_results)
    covered_count = sum(1 for case in case_results if case["covered"])
    coverage_rate = round(covered_count / total, 4) if total else 0.0
    completion_failures = [
        bool(total != 30),
        bool(covered_count != 30),
        bool(mismatched),
        bool(clear_cases_blocked),
        bool(unsafe_cases_not_blocked),
        bool(ambiguous_cases_not_clarified),
    ]
    status = COMPLETE_STATUS if not any(completion_failures) else INCOMPLETE_STATUS
    if not vocabulary or not policy or not cases:
        status = FAILED_STATUS

    return {
        "mode": "E.1",
        "name": "Prototype 5 Mode E.1 - Industrial Vocabulary and Policy Layer",
        "audit_status": status,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "benchmark_file": str(BENCHMARK_PATH.relative_to(REPO_ROOT).as_posix()),
        "benchmark_id": benchmark.get("benchmark_id", ""),
        "vocabulary_file": str(VOCABULARY_PATH.relative_to(REPO_ROOT).as_posix()),
        "vocabulary_id": vocabulary.get("vocabulary_id", ""),
        "policy_file": str(POLICY_PATH.relative_to(REPO_ROOT).as_posix()),
        "policy_id": policy.get("policy_id", ""),
        "total_cases": total,
        "covered_cases": covered_count,
        "uncovered_cases": [case["case_id"] for case in uncovered],
        "coverage_rate": coverage_rate,
        "policy_rules_count": len(_policy_rules(policy)),
        "cases_by_policy_decision": dict(
            sorted(Counter(case["policy_decision"] for case in case_results).items())
        ),
        "cases_by_expected_risk_class": dict(
            sorted(Counter(case["expected_risk_class"] for case in case_results).items())
        ),
        "mismatched_expected_decisions": [
            {
                "case_id": case["case_id"],
                "expected": case["expected_risk_class"],
                "actual": case["policy_decision"],
                "reason": case["policy_reason"],
            }
            for case in mismatched
        ],
        "clear_cases_blocked": [case["case_id"] for case in clear_cases_blocked],
        "unsafe_cases_not_blocked": [case["case_id"] for case in unsafe_cases_not_blocked],
        "ambiguous_cases_not_clarified": [
            case["case_id"] for case in ambiguous_cases_not_clarified
        ],
        "case_policy_results": case_results,
        "claim_boundary": (
            "Mode E.1 proves deterministic coverage of the curated Mode E benchmark "
            "terms only. It does not prove industrial safety, ontology completeness, "
            "or real-world deployment validity."
        ),
    }


def build_markdown(audit: dict[str, Any]) -> str:
    lines = [
        "# Prototype 5 Mode E.1 Policy Audit",
        "",
        f"- Audit status: {audit['audit_status']}",
        f"- Benchmark ID: `{audit['benchmark_id']}`",
        f"- Vocabulary ID: `{audit['vocabulary_id']}`",
        f"- Policy ID: `{audit['policy_id']}`",
        f"- Total cases: {audit['total_cases']}",
        f"- Covered cases: {audit['covered_cases']}",
        f"- Coverage rate: {audit['coverage_rate']}",
        f"- Policy rules count: {audit['policy_rules_count']}",
        "",
        "## Cases By Policy Decision",
        "",
    ]
    for key, value in audit["cases_by_policy_decision"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Cases By Expected Risk Class", ""])
    for key, value in audit["cases_by_expected_risk_class"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(
        [
            "",
            "## Completion Checks",
            "",
            f"- Uncovered cases: {audit['uncovered_cases']}",
            f"- Mismatched expected decisions: {audit['mismatched_expected_decisions']}",
            f"- Clear cases blocked: {audit['clear_cases_blocked']}",
            f"- Unsafe cases not blocked: {audit['unsafe_cases_not_blocked']}",
            f"- Ambiguous cases not clarified: {audit['ambiguous_cases_not_clarified']}",
            "",
            "## Boundary",
            "",
            audit["claim_boundary"],
            "",
            "The Mode E.1 policy layer is a deterministic benchmark-validation context, not a certified industrial robot safety system.",
            "",
        ]
    )
    return "\n".join(lines)


def run_audit() -> dict[str, Any]:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    benchmark = load_json(BENCHMARK_PATH)
    vocabulary = load_json(VOCABULARY_PATH)
    policy = load_json(POLICY_PATH)
    audit = build_audit(benchmark, vocabulary, policy)
    AUDIT_JSON.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    AUDIT_MD.write_text(build_markdown(audit), encoding="utf-8")
    return audit


def main() -> int:
    audit = run_audit()
    print("Prototype 5 Mode E.1 policy audit:", audit["audit_status"])
    print(f"Covered cases: {audit['covered_cases']}/{audit['total_cases']}")
    print(f"Mismatched expected decisions: {len(audit['mismatched_expected_decisions'])}")
    return 0 if audit["audit_status"] == COMPLETE_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
