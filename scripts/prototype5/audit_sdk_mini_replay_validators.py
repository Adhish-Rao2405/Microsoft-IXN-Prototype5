from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.prototype5.run_pipeline_repeatability_analysis import (  # noqa: E402
    SafetyValidationResult,
    SchemaValidationResult,
    assess_uncertainty,
    parse_raw_response,
    score_semantics,
    validate_action_plan,
    validate_safety,
)


INPUT_JSON = Path("results/prototype5/mode_sdk/sdk_mini_replay_results.json")
OUTPUT_JSON = Path("results/prototype5/mode_sdk/sdk_mini_replay_validator_audit.json")
OUTPUT_MD = Path("results/prototype5/mode_sdk/sdk_mini_replay_validator_audit.md")

ARCHITECTURAL_BOUNDARY = {
    "uses_existing_validators": True,
    "modifies_validators": False,
    "repairs_model_output": False,
    "infers_missing_model_fields": False,
    "runs_full_benchmark": False,
    "calls_orchestrator": False,
    "starts_voice_control": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_json_parse(raw_text: str | None) -> tuple[bool, Any, str | None]:
    if raw_text is None or not str(raw_text).strip():
        return False, None, "empty_raw_text"

    parsed_payload, parse_success = parse_raw_response(str(raw_text))
    if parse_success:
        return True, parsed_payload, None
    try:
        json.loads(str(raw_text))
    except json.JSONDecodeError as exc:
        return False, None, f"json_decode_error: {exc}"
    return False, None, "json_decode_error"


def normalise_bool(value: Any) -> bool:
    return bool(value)


def benchmark_item_for_case(case: dict[str, Any]) -> dict[str, Any]:
    risk_type = str(case.get("risk_type", ""))
    if risk_type == "ambiguous":
        gold_label = "REJECT_UNCERTAIN"
    elif risk_type in {"unsafe", "unsupported"}:
        gold_label = "REJECT_UNSUPPORTED"
    else:
        gold_label = "EXECUTE_FLEXIBLE"
    return {
        "id": case.get("case_id", ""),
        "command": case.get("user_command", ""),
        "category": case.get("category", ""),
        "difficulty": risk_type,
        "gold_label": gold_label,
        "gold_intent": {"actions": []},
    }


def run_existing_validation(raw_text: str | None, case: dict[str, Any]) -> dict[str, Any]:
    """
    Audit wrapper around the existing validation path.

    Critical rule:
    This function imports and calls existing validators, but does not modify validators,
    repair model output, infer missing fields, or invent execution eligibility.
    """

    json_valid, parsed_payload, parse_error = safe_json_parse(raw_text)

    schema_valid = False
    semantic_valid = False
    safety_valid = False
    execution_eligible = False
    failure_mode = None
    validation_notes: list[str] = []
    schema_errors: list[str] = []
    semantic_failure_mode: str | None = None
    safety_violations: list[str] = []

    if not json_valid:
        failure_mode = "json_invalid"
        validation_notes.append("Raw SDK proposal could not be parsed as JSON.")
        return {
            "json_valid": False,
            "schema_valid": False,
            "semantic_valid": False,
            "safety_valid": False,
            "execution_eligible": False,
            "failure_mode": failure_mode,
            "parse_error": parse_error,
            "validation_notes": validation_notes,
            "parsed_payload": None,
            "schema_errors": schema_errors,
            "semantic_failure_mode": semantic_failure_mode,
            "safety_violations": safety_violations,
        }

    try:
        schema = validate_action_plan(parsed_payload)
        schema_valid = normalise_bool(schema.valid)
        schema_errors = list(schema.errors)
        planned_actions = schema.normalized_actions if schema_valid else None

        uncertainty = assess_uncertainty(str(case.get("user_command", "")))
        semantic = score_semantics(benchmark_item_for_case(case), planned_actions, uncertainty)
        semantic_valid = normalise_bool(semantic.passed)
        semantic_failure_mode = semantic.failure_mode

        if schema_valid and semantic_valid and not uncertainty.uncertain:
            safety = validate_safety(planned_actions)
        else:
            safety = SafetyValidationResult(False, [])
        safety_valid = normalise_bool(safety.safe)
        safety_violations = list(safety.violations)

    except Exception as exc:
        failure_mode = "validator_exception"
        validation_notes.append(f"Existing validator raised exception: {type(exc).__name__}: {exc}")

    execution_eligible = bool(schema_valid and semantic_valid and safety_valid)

    if execution_eligible:
        failure_mode = None
    elif failure_mode is None:
        if not schema_valid:
            failure_mode = "schema_invalid"
        elif not semantic_valid:
            failure_mode = "semantic_invalid"
        elif not safety_valid:
            failure_mode = "safety_invalid"
        else:
            failure_mode = "not_execution_eligible"

    return {
        "json_valid": json_valid,
        "schema_valid": schema_valid,
        "semantic_valid": semantic_valid,
        "safety_valid": safety_valid,
        "execution_eligible": execution_eligible,
        "failure_mode": failure_mode,
        "parse_error": parse_error,
        "validation_notes": validation_notes,
        "parsed_payload": parsed_payload,
        "schema_errors": schema_errors,
        "semantic_failure_mode": semantic_failure_mode,
        "safety_violations": safety_violations,
    }


def audit_case(case: dict[str, Any]) -> dict[str, Any]:
    validation = run_existing_validation(case.get("raw_text"), case)

    return {
        "case_id": case.get("case_id"),
        "category": case.get("category"),
        "risk_type": case.get("risk_type"),
        "user_command": case.get("user_command"),
        "sdk_success": case.get("success"),
        "sdk_latency_ms": case.get("latency_ms"),
        "sdk_error_type": case.get("error_type"),
        "json_valid": validation["json_valid"],
        "schema_valid": validation["schema_valid"],
        "semantic_valid": validation["semantic_valid"],
        "safety_valid": validation["safety_valid"],
        "execution_eligible": validation["execution_eligible"],
        "failure_mode": validation["failure_mode"],
        "parse_error": validation["parse_error"],
        "validation_notes": validation["validation_notes"],
        "schema_errors": validation["schema_errors"],
        "semantic_failure_mode": validation["semantic_failure_mode"],
        "safety_violations": validation["safety_violations"],
    }


def write_markdown(summary: dict[str, Any]) -> None:
    lines = [
        "# SDK Mini Replay Validator Audit",
        "",
        f"Status: `{summary['status']}`",
        "",
        "## Scope",
        "",
        "This audit passes the five SDK mini-replay raw proposals through the existing unchanged deterministic validation boundary. "
        "It does not modify validators, does not repair model output, does not run the full benchmark, and does not call the final orchestrator.",
        "",
        "## Summary Metrics",
        "",
        f"- Case count: `{summary['case_count']}`",
        f"- SDK success count: `{summary['sdk_success_count']}`",
        f"- JSON-valid count: `{summary['json_valid_count']}`",
        f"- Schema-valid count: `{summary['schema_valid_count']}`",
        f"- Semantic-valid count: `{summary['semantic_valid_count']}`",
        f"- Safety-valid count: `{summary['safety_valid_count']}`",
        f"- Execution-eligible count: `{summary['execution_eligible_count']}`",
        "",
        "## Architectural Boundary",
        "",
    ]

    for key, value in summary["architectural_boundary"].items():
        lines.append(f"- {key}: `{str(value).lower()}`")

    lines.extend(
        [
            "",
            "## Result Rows",
            "",
            "| Case ID | Risk Type | SDK Success | JSON Valid | Schema Valid | Semantic Valid | Safety Valid | Execution Eligible | Failure Mode |",
            "|---|---|---:|---:|---:|---:|---:|---:|---|",
        ]
    )

    for row in summary["audit_rows"]:
        lines.append(
            f"| {row['case_id']} | {row['risk_type']} | {row['sdk_success']} | "
            f"{row['json_valid']} | {row['schema_valid']} | {row['semantic_valid']} | "
            f"{row['safety_valid']} | {row['execution_eligible']} | {row['failure_mode']} |"
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "SDK success is not execution eligibility. A raw proposal is not a validated plan. "
            "This mini audit is not a full benchmark.",
            "",
            "This audit distinguishes raw SDK proposal generation from execution eligibility. "
            "A successful SDK response is not treated as safe or executable unless it survives the existing deterministic validation stages.",
            "",
        ]
    )

    OUTPUT_MD.write_text("\n".join(lines), encoding="utf-8")


def build_summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    audit_rows = [audit_case(case) for case in cases]
    return {
        "status": "COMPLETE_SDK_MINI_REPLAY_VALIDATOR_AUDIT",
        "timestamp_utc": utc_now(),
        "scope": "existing_validator_audit_over_sdk_mini_replay_only",
        "source_input": str(INPUT_JSON),
        "case_count": len(audit_rows),
        "sdk_success_count": sum(1 for row in audit_rows if row["sdk_success"]),
        "json_valid_count": sum(1 for row in audit_rows if row["json_valid"]),
        "schema_valid_count": sum(1 for row in audit_rows if row["schema_valid"]),
        "semantic_valid_count": sum(1 for row in audit_rows if row["semantic_valid"]),
        "safety_valid_count": sum(1 for row in audit_rows if row["safety_valid"]),
        "execution_eligible_count": sum(1 for row in audit_rows if row["execution_eligible"]),
        "audit_rows": audit_rows,
        "architectural_boundary": ARCHITECTURAL_BOUNDARY,
        "interpretation_boundary": (
            "This evidence audits the same five SDK mini-replay outputs against existing validation logic. "
            "It is not full benchmark evidence and does not replace locked Prototype 3/4/5 evidence."
        ),
    }


def main() -> int:
    if not INPUT_JSON.exists():
        raise FileNotFoundError(f"Missing Milestone 6 input evidence: {INPUT_JSON}")

    source = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    cases = source.get("cases", [])
    summary = build_summary(cases)

    OUTPUT_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_markdown(summary)

    print(summary["status"])
    print(f"Case count: {summary['case_count']}")
    print(f"SDK success count: {summary['sdk_success_count']}")
    print(f"JSON-valid count: {summary['json_valid_count']}")
    print(f"Schema-valid count: {summary['schema_valid_count']}")
    print(f"Semantic-valid count: {summary['semantic_valid_count']}")
    print(f"Safety-valid count: {summary['safety_valid_count']}")
    print(f"Execution-eligible count: {summary['execution_eligible_count']}")
    print(f"JSON: {OUTPUT_JSON}")
    print(f"Markdown: {OUTPUT_MD}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
