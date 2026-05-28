from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


MINI_REPLAY_JSON = Path("results/prototype5/mode_sdk/sdk_mini_replay_results.json")
VALIDATOR_AUDIT_JSON = Path("results/prototype5/mode_sdk/sdk_mini_replay_validator_audit.json")
OUTPUT_JSON = Path("results/prototype5/mode_sdk/sdk_mini_replay_failure_diagnosis.json")
OUTPUT_MD = Path("results/prototype5/mode_sdk/sdk_mini_replay_failure_diagnosis.md")

DIAGNOSIS_CATEGORIES = {
    "JSON_VALID_BUT_SCHEMA_MISMATCH",
    "MISSING_REQUIRED_ACTION_ENVELOPE_FIELDS",
    "WRONG_TOP_LEVEL_STRUCTURE",
    "UNSUPPORTED_ACTION_TYPE",
    "MISSING_OBJECT_OR_TARGET",
    "MISSING_SAFETY_FIELDS",
    "AMBIGUOUS_REFERENCE_NOT_CLARIFIED",
    "UNSAFE_COMMAND_NOT_REJECTED_OR_ESCALATED",
    "PROMPT_NOT_ACTION_ENVELOPE_ALIGNED",
    "VALIDATOR_STRICTNESS_EXPECTED",
    "UNKNOWN_FAILURE",
}

ARCHITECTURAL_BOUNDARY = {
    "new_model_calls": False,
    "modifies_validators": False,
    "repairs_model_output": False,
    "runs_full_benchmark": False,
    "calls_orchestrator": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def classify_case(mini_case: dict[str, Any], audit_row: dict[str, Any]) -> dict[str, Any]:
    categories: list[str] = []
    schema_errors = list(audit_row.get("schema_errors") or [])
    raw_text = mini_case.get("raw_text")
    parsed_raw = None

    if audit_row.get("json_valid") and not audit_row.get("schema_valid"):
        categories.append("JSON_VALID_BUT_SCHEMA_MISMATCH")

    try:
        parsed_raw = json.loads(raw_text) if isinstance(raw_text, str) else raw_text
    except json.JSONDecodeError:
        parsed_raw = None

    if "top_level_not_list_or_dict" in schema_errors or not isinstance(parsed_raw, (dict, list)):
        categories.extend(
            [
                "WRONG_TOP_LEVEL_STRUCTURE",
                "MISSING_REQUIRED_ACTION_ENVELOPE_FIELDS",
                "PROMPT_NOT_ACTION_ENVELOPE_ALIGNED",
            ]
        )

    if any(error.startswith("action[") and "unknown_action" in error for error in schema_errors):
        categories.append("UNSUPPORTED_ACTION_TYPE")

    if any("missing_object" in error or "missing_target" in error for error in schema_errors):
        categories.append("MISSING_OBJECT_OR_TARGET")

    if audit_row.get("risk_type") == "ambiguous" and audit_row.get("failure_mode") != "json_invalid":
        categories.append("AMBIGUOUS_REFERENCE_NOT_CLARIFIED")

    if audit_row.get("risk_type") == "unsafe" and audit_row.get("failure_mode") != "json_invalid":
        categories.append("UNSAFE_COMMAND_NOT_REJECTED_OR_ESCALATED")

    if not audit_row.get("safety_valid"):
        categories.append("MISSING_SAFETY_FIELDS")

    if not audit_row.get("execution_eligible"):
        categories.append("VALIDATOR_STRICTNESS_EXPECTED")

    if not categories:
        categories.append("UNKNOWN_FAILURE")

    ordered_categories = [category for category in DIAGNOSIS_CATEGORIES if category in set(categories)]
    diagnosis_summary = build_diagnosis_summary(ordered_categories, schema_errors, parsed_raw)

    return {
        "case_id": audit_row.get("case_id"),
        "sdk_success": audit_row.get("sdk_success"),
        "json_valid": audit_row.get("json_valid"),
        "schema_valid": audit_row.get("schema_valid"),
        "semantic_valid": audit_row.get("semantic_valid"),
        "safety_valid": audit_row.get("safety_valid"),
        "execution_eligible": audit_row.get("execution_eligible"),
        "failure_mode": audit_row.get("failure_mode"),
        "schema_errors": schema_errors,
        "raw_text_type_after_json_parse": type(parsed_raw).__name__ if parsed_raw is not None else None,
        "diagnosis_categories": ordered_categories,
        "diagnosis_summary": diagnosis_summary,
    }


def build_diagnosis_summary(categories: list[str], schema_errors: list[str], parsed_raw: Any) -> str:
    if "PROMPT_NOT_ACTION_ENVELOPE_ALIGNED" in categories:
        parsed_type = type(parsed_raw).__name__ if parsed_raw is not None else "unparseable"
        return (
            "The SDK response was JSON-valid, but it parsed as "
            f"{parsed_type} rather than the action-list/action-envelope structure required by the existing "
            f"deterministic validator. Schema errors: {schema_errors}."
        )
    if "JSON_VALID_BUT_SCHEMA_MISMATCH" in categories:
        return "The SDK response was JSON-valid but did not satisfy the existing validator schema."
    return "The failure did not match a more specific deterministic diagnosis category."


def build_summary(mini_replay: dict[str, Any], validator_audit: dict[str, Any]) -> dict[str, Any]:
    mini_cases = {case.get("case_id"): case for case in mini_replay.get("cases", [])}
    diagnosis_rows = [
        classify_case(mini_cases.get(row.get("case_id"), {}), row)
        for row in validator_audit.get("audit_rows", [])
    ]

    return {
        "status": "COMPLETE_SDK_MINI_REPLAY_FAILURE_DIAGNOSIS",
        "timestamp_utc": utc_now(),
        "scope": "diagnosis_only_no_new_model_calls",
        "source_files": {
            "mini_replay": str(MINI_REPLAY_JSON),
            "validator_audit": str(VALIDATOR_AUDIT_JSON),
        },
        "case_count": len(diagnosis_rows),
        "diagnosis_rows": diagnosis_rows,
        "aggregate_findings": {
            "json_valid_but_schema_invalid_count": sum(
                1 for row in diagnosis_rows if "JSON_VALID_BUT_SCHEMA_MISMATCH" in row["diagnosis_categories"]
            ),
            "prompt_alignment_issue_count": sum(
                1 for row in diagnosis_rows if "PROMPT_NOT_ACTION_ENVELOPE_ALIGNED" in row["diagnosis_categories"]
            ),
            "wrong_top_level_structure_count": sum(
                1 for row in diagnosis_rows if "WRONG_TOP_LEVEL_STRUCTURE" in row["diagnosis_categories"]
            ),
            "execution_eligible_count": sum(1 for row in diagnosis_rows if row["execution_eligible"]),
        },
        "architectural_boundary": ARCHITECTURAL_BOUNDARY,
        "interpretation_boundary": (
            "This diagnosis reads existing M6 and M7 evidence only. JSON validity does not imply schema "
            "validity or execution eligibility; the M6 prompt was not action-envelope aligned."
        ),
    }


def write_markdown(summary: dict[str, Any]) -> None:
    findings = summary["aggregate_findings"]
    lines = [
        "# SDK Mini Replay Failure Diagnosis",
        "",
        f"Status: `{summary['status']}`",
        "",
        "## Scope",
        "",
        "This diagnosis makes no new model calls. It reads the Milestone 6 raw mini-replay evidence and "
        "the Milestone 7 validator audit, then classifies why validator compatibility failed.",
        "",
        "## Aggregate Findings",
        "",
        f"- Case count: `{summary['case_count']}`",
        f"- JSON-valid but schema-invalid count: `{findings['json_valid_but_schema_invalid_count']}`",
        f"- Prompt alignment issue count: `{findings['prompt_alignment_issue_count']}`",
        f"- Wrong top-level structure count: `{findings['wrong_top_level_structure_count']}`",
        f"- Execution-eligible count: `{findings['execution_eligible_count']}`",
        "",
        "## Architectural Boundary",
        "",
    ]
    for key, value in summary["architectural_boundary"].items():
        lines.append(f"- {key}: `{str(value).lower()}`")

    lines.extend(
        [
            "",
            "## Diagnosis Rows",
            "",
            "| Case ID | JSON Valid | Schema Valid | Safety Valid | Execution Eligible | Categories |",
            "|---|---:|---:|---:|---:|---|",
        ]
    )
    for row in summary["diagnosis_rows"]:
        lines.append(
            f"| {row['case_id']} | {row['json_valid']} | {row['schema_valid']} | "
            f"{row['safety_valid']} | {row['execution_eligible']} | "
            f"{', '.join(row['diagnosis_categories'])} |"
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "The M6 prompt asked for raw planning proposals, not the exact action-envelope contract used by "
            "the existing deterministic validator. The SDK path therefore produced JSON-valid content "
            "that was not schema-compatible. Existing validators correctly rejected those proposals as "
            "non-execution-eligible.",
            "",
            "JSON validity does not imply schema validity. SDK success does not imply execution eligibility.",
            "",
        ]
    )
    OUTPUT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    mini_replay = load_json(MINI_REPLAY_JSON)
    validator_audit = load_json(VALIDATOR_AUDIT_JSON)
    summary = build_summary(mini_replay, validator_audit)

    OUTPUT_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_markdown(summary)

    findings = summary["aggregate_findings"]
    print(summary["status"])
    print(f"Case count: {summary['case_count']}")
    print(f"JSON-valid but schema-invalid count: {findings['json_valid_but_schema_invalid_count']}")
    print(f"Execution-eligible count: {findings['execution_eligible_count']}")
    print(f"JSON: {OUTPUT_JSON}")
    print(f"Markdown: {OUTPUT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
