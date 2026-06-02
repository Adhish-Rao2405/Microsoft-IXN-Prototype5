from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.prototype5.voice_to_planner_bridge import bridge_transcript_to_planner  # noqa: E402


DEFAULT_CASES = REPO_ROOT / "data" / "prototype5" / "mode_voice" / "manual_voice_transcript_cases.csv"
DEFAULT_RESULTS_CSV = (
    REPO_ROOT / "results" / "prototype5" / "mode_voice" / "phase2_milestone14a_manual_voice_transcript_results.csv"
)
DEFAULT_SUMMARY_JSON = (
    REPO_ROOT / "results" / "prototype5" / "mode_voice" / "phase2_milestone14a_manual_voice_transcript_summary.json"
)
DEFAULT_SUMMARY_MD = (
    REPO_ROOT / "results" / "prototype5" / "mode_voice" / "phase2_milestone14a_manual_voice_transcript_summary.md"
)

MILESTONE = "Phase 2 Milestone 14A"
MODE = "manual_recorded_voice_transcript_evaluation"

REQUIRED_COLUMNS = {
    "case_id",
    "scenario_family",
    "spoken_command",
    "manual_transcript",
    "transcript_confidence",
    "is_partial",
    "expected_intent",
    "expected_voice_eligible_for_planning",
    "expected_planner_called",
    "expected_rejection_stage",
    "expected_primary_risk_flag",
    "notes",
}

PRIMARY_RISK_PRIORITY = (
    "stop_proceed_conflict",
    "low_confidence",
    "partial_transcript",
    "empty_transcript",
    "stop_intent",
    "context_required",
    "ambiguous_reference",
    "negation_detected",
    "unsafe_keyword",
    "non_command",
    "unknown_intent",
)

RESULT_FIELDS = (
    "case_id",
    "scenario_family",
    "spoken_command",
    "manual_transcript",
    "transcript_confidence",
    "is_partial",
    "expected_intent",
    "actual_intent",
    "expected_voice_eligible_for_planning",
    "actual_voice_eligible_for_planning",
    "expected_planner_called",
    "actual_planner_called",
    "expected_rejection_stage",
    "actual_rejection_stage",
    "expected_primary_risk_flag",
    "actual_risk_flags",
    "execution_eligible",
    "passed_expectations",
    "notes",
    "json_valid",
    "schema_valid",
    "semantic_valid",
    "safety_valid",
    "raw_planner_response_present",
    "voice_rejection_reason",
    "bridge_rejection_stage",
    "bridge_rejection_reason",
)


@dataclass(frozen=True)
class MockBackendResponse:
    raw_text: str = '{"actions": []}'
    success: bool = True
    backend: str = "mock_manual_voice_transcript_backend"
    model_alias: str = "mock"
    latency_ms: float = 0.0
    error_type: str | None = None
    error_message: str | None = None


class MockBackend:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    def generate(self, command: str, context: dict[str, Any] | None = None) -> MockBackendResponse:
        self.calls.append((command, context))
        return MockBackendResponse()


def parse_bool(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    normalised = str(value).strip().lower()
    if normalised in {"true", "1", "yes", "y"}:
        return True
    if normalised in {"false", "0", "no", "n"}:
        return False
    raise ValueError(f"Cannot parse boolean value: {value!r}")


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def load_cases(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - columns
        if missing:
            raise ValueError(f"Case CSV is missing required columns: {sorted(missing)}")
        return [dict(row) for row in reader]


def primary_risk_flag(risk_flags: list[str]) -> str:
    for flag in PRIMARY_RISK_PRIORITY:
        if flag in risk_flags:
            return flag
    return "none"


def actual_voice_rejection_stage(result: Any) -> str:
    if result.rejection_stage == "voice_policy" and not result.planner_called:
        return "voice_policy"
    return "none"


def evaluate_case(row: dict[str, str]) -> dict[str, str]:
    confidence = float(row.get("transcript_confidence", "1.0") or "1.0")
    is_partial = parse_bool(row.get("is_partial", "false"))
    backend = MockBackend()
    result = bridge_transcript_to_planner(
        row["manual_transcript"],
        planner_backend=backend,
        transcript_confidence=confidence,
        is_partial=is_partial,
        voice_input_id=row["case_id"],
    )

    actual_primary_risk = primary_risk_flag(result.voice_risk_flags)
    actual_stage = actual_voice_rejection_stage(result)
    expected_voice_eligible = parse_bool(row["expected_voice_eligible_for_planning"])
    expected_planner_called = parse_bool(row["expected_planner_called"])
    expected_stage = row["expected_rejection_stage"].strip() or "none"
    expected_primary_risk = row["expected_primary_risk_flag"].strip() or "none"

    passed = (
        result.detected_intent == row["expected_intent"]
        and result.voice_eligible_for_planning is expected_voice_eligible
        and result.planner_called is expected_planner_called
        and actual_stage == expected_stage
        and actual_primary_risk == expected_primary_risk
    )

    return {
        "case_id": row["case_id"],
        "scenario_family": row["scenario_family"],
        "spoken_command": row["spoken_command"],
        "manual_transcript": row["manual_transcript"],
        "transcript_confidence": f"{confidence:g}",
        "is_partial": bool_text(is_partial),
        "expected_intent": row["expected_intent"],
        "actual_intent": result.detected_intent,
        "expected_voice_eligible_for_planning": bool_text(expected_voice_eligible),
        "actual_voice_eligible_for_planning": bool_text(result.voice_eligible_for_planning),
        "expected_planner_called": bool_text(expected_planner_called),
        "actual_planner_called": bool_text(result.planner_called),
        "expected_rejection_stage": expected_stage,
        "actual_rejection_stage": actual_stage,
        "expected_primary_risk_flag": expected_primary_risk,
        "actual_risk_flags": "|".join(result.voice_risk_flags) if result.voice_risk_flags else "none",
        "execution_eligible": bool_text(result.execution_eligible),
        "passed_expectations": bool_text(passed),
        "notes": row.get("notes", ""),
        "json_valid": bool_text(result.json_valid),
        "schema_valid": bool_text(result.schema_valid),
        "semantic_valid": bool_text(result.semantic_valid),
        "safety_valid": bool_text(result.safety_valid),
        "raw_planner_response_present": bool_text(result.raw_planner_response is not None),
        "voice_rejection_reason": result.voice_rejection_reason or "none",
        "bridge_rejection_stage": result.rejection_stage or "none",
        "bridge_rejection_reason": result.rejection_reason or "none",
    }


def build_summary(results: list[dict[str, str]]) -> dict[str, Any]:
    scenario_family_counts = Counter(row["scenario_family"] for row in results)
    intent_counts = Counter(row["actual_intent"] for row in results)
    risk_flag_counts: Counter[str] = Counter()
    for row in results:
        for flag in row["actual_risk_flags"].split("|"):
            if flag and flag != "none":
                risk_flag_counts[flag] += 1

    case_count = len(results)
    passed_count = sum(parse_bool(row["passed_expectations"]) for row in results)
    failed_count = case_count - passed_count
    planner_called_count = sum(parse_bool(row["actual_planner_called"]) for row in results)
    voice_policy_rejection_count = sum(row["actual_rejection_stage"] == "voice_policy" for row in results)
    execution_eligible_count = sum(parse_bool(row["execution_eligible"]) for row in results)
    unexpected_planner_call_count = sum(
        parse_bool(row["actual_planner_called"]) and not parse_bool(row["expected_planner_called"]) for row in results
    )

    return {
        "status": "COMPLETE_MANUAL_TRANSCRIPT_EVALUATION"
        if failed_count == 0
        else "COMPLETE_WITH_EXPECTATION_FAILURES",
        "timestamp_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "milestone": MILESTONE,
        "mode": MODE,
        "case_count": case_count,
        "passed_expectation_count": passed_count,
        "failed_expectation_count": failed_count,
        "pass_rate": round(passed_count / case_count, 4) if case_count else 0.0,
        "scenario_family_counts": dict(sorted(scenario_family_counts.items())),
        "intent_counts": dict(sorted(intent_counts.items())),
        "voice_eligible_for_planning_count": sum(
            parse_bool(row["actual_voice_eligible_for_planning"]) for row in results
        ),
        "voice_policy_rejection_count": voice_policy_rejection_count,
        "planner_called_count": planner_called_count,
        "planner_not_called_count": case_count - planner_called_count,
        "execution_eligible_count": execution_eligible_count,
        "risk_flag_counts": dict(sorted(risk_flag_counts.items())),
        "fail_closed_count": sum(not parse_bool(row["execution_eligible"]) for row in results),
        "unexpected_planner_call_count": unexpected_planner_call_count,
        "unexpected_execution_eligible_count": execution_eligible_count,
        "dependency_changes": False,
        "audio_runtime_used": False,
        "live_microphone_used": False,
        "speech_to_text_used": False,
        "notes": (
            "Manual transcript evaluation uses controlled text transcripts with the existing M12 policy "
            "and M13 bridge. It does not load audio or speech-to-text runtime components."
        ),
    }


def write_results_csv(path: Path, results: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(results)


def write_summary_json(path: Path, summary: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_summary_md(path: Path, summary: dict[str, Any]) -> None:
    families = ", ".join(summary["scenario_family_counts"].keys())
    text = f"""# Phase 2 Milestone 14A Manual Voice Transcript Evaluation

## Purpose

Phase 2 Milestone 14A evaluates manually transcribed spoken-command scenarios using the existing voice transcript policy and typed transcript bridge. It provides bounded evidence that voice-derived transcript candidates can be risk-classified, failed closed, or routed into the zero-trust planner/validator path without bypassing deterministic validation.

This milestone evaluates manually transcribed spoken-command scenarios, not live speech recognition. The evaluation is intended to test the zero-trust voice-intake pathway under controlled transcript inputs before introducing audio-runtime complexity.

## Method

The evaluation loads curated spoken-command scenarios from `data/prototype5/mode_voice/manual_voice_transcript_cases.csv`. Each manual transcript is processed by the existing M12 transcript policy and then passed through the existing M13 typed transcript bridge with the offline mock backend.

RQ-M14A: Can manually transcribed spoken-command scenarios be evaluated through the existing zero-trust voice-intake pathway such that risky, ambiguous, or context-dependent utterances fail closed before planning, while clear candidate commands remain subject to downstream deterministic validation?

## Key Results

- Case count: {summary["case_count"]}
- Scenario families: {families}
- Passed expectations: {summary["passed_expectation_count"]}/{summary["case_count"]}
- Voice-policy rejections before planning: {summary["voice_policy_rejection_count"]}
- Planner calls: {summary["planner_called_count"]}
- Execution-eligible cases: {summary["execution_eligible_count"]}
- Unexpected planner calls: {summary["unexpected_planner_call_count"]}
- Unexpected execution-eligible cases: {summary["unexpected_execution_eligible_count"]}

## Fail-Closed Findings

Stop, proceed, ambiguous-reference, negation-sensitive, unsafe, non-command, clarification-without-context, conflict, low-confidence, and partial transcript cases were expected to fail closed before planner invocation. Clear planning transcripts were allowed to reach the bridge, where the mock planner output remained subject to downstream deterministic validation.

## What This Proves

M14A shows that manually transcribed spoken-command candidates can be evaluated through the existing zero-trust voice-intake pathway. Risky or context-dependent transcripts can be rejected before planner calls, while clear planning transcripts can enter the planner pathway without receiving execution authority from the voice layer.

## What This Does Not Prove

M14A does not prove live voice control, speech recognition accuracy, audio capture reliability, emergency-stop capability, production safety, real robot readiness, or deployment readiness.

## Next Possible Step

A later bounded milestone could compare intended spoken commands with transcript text produced by a controlled speech-to-text adapter. That should remain separate from this manual transcript evaluation and should preserve the same zero-trust execution boundary.
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run_evaluation(cases_path: Path, results_csv: Path, summary_json: Path, summary_md: Path) -> dict[str, Any]:
    cases = load_cases(cases_path)
    results = [evaluate_case(row) for row in cases]
    summary = build_summary(results)
    write_results_csv(results_csv, results)
    write_summary_json(summary_json, summary)
    write_summary_md(summary_md, summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the M14A manual voice transcript evaluation.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--results-csv", type=Path, default=DEFAULT_RESULTS_CSV)
    parser.add_argument("--summary-json", type=Path, default=DEFAULT_SUMMARY_JSON)
    parser.add_argument("--summary-md", type=Path, default=DEFAULT_SUMMARY_MD)
    parser.add_argument("--mock-backend", action="store_true", help="Use the offline mock backend. This is the default.")
    args = parser.parse_args()

    summary = run_evaluation(args.cases, args.results_csv, args.summary_json, args.summary_md)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
