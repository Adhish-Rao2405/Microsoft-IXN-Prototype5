"""Mode E.2 bounded live industrial benchmark evaluation."""

from __future__ import annotations

import argparse
import csv
import json
import multiprocessing as mp
import os
import statistics
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from run_mode_e_policy_audit import (  # noqa: E402
    COMPLETE_STATUS,
    POLICY_PATH,
    VOCABULARY_PATH,
    apply_policy,
    load_json,
)
from run_pipeline_repeatability_analysis import (  # noqa: E402
    parse_raw_response,
    validate_action_plan,
)
from src.prototype5.foundry_discovery import (  # noqa: E402
    DEFAULT_FOUNDRY_BASE_URL,
    FOUNDRY_ENV_BASE_URL,
    FOUNDRY_ENV_MODEL,
    select_phi_model,
)


CONFIG_DIR = REPO_ROOT / "configs" / "prototype5"
BENCHMARK_PATH = CONFIG_DIR / "mode_e_industrial_benchmark.json"
PROMPT_PATH = CONFIG_DIR / "action_envelope_prompt.txt"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "results" / "prototype5" / "mode_e"
E1_AUDIT_JSON = DEFAULT_OUTPUT_DIR / "mode_e_policy_audit.json"

LIVE_RAW_NAME = "mode_e2_live_industrial_raw.jsonl"
LIVE_RESULTS_NAME = "mode_e2_live_industrial_results.csv"
LIVE_SUMMARY_JSON_NAME = "mode_e2_live_industrial_summary.json"
LIVE_SUMMARY_MD_NAME = "mode_e2_live_industrial_summary.md"
NOT_RUN_SUMMARY_JSON_NAME = "mode_e2_live_industrial_not_run_summary.json"
NOT_RUN_SUMMARY_MD_NAME = "mode_e2_live_industrial_not_run_summary.md"

TEMPERATURE = 0.0
FIRST_RESPONSE_PROBE_TIMEOUT_SECONDS = 10.0
E04_COMPARISON = {
    "schema_valid_rate": 0.8667,
    "execution_eligible_rate": 0.1,
    "schema_valid_minus_execution_eligible_gap": 0.7667,
    "pipeline_false_accepts": 0,
    "mean_latency_ms": 25377.18,
    "comparison_boundary": (
        "E0.4 and E.2 are different benchmark conditions, so differences are "
        "descriptive rather than statistically conclusive."
    ),
}

RESULT_COLUMNS = [
    "case_id",
    "scenario_family",
    "difficulty",
    "expected_risk_class",
    "expected_issue",
    "request_success",
    "parse_success",
    "json_valid",
    "schema_valid",
    "semantic_valid",
    "safety_valid",
    "execution_eligible",
    "policy_decision",
    "policy_reason",
    "model_false_accept",
    "pipeline_false_accept",
    "latency_ms",
    "error",
]


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT).as_posix())
    except ValueError:
        return str(path)


def _extract_response_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices", [])
    if not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message", {})
    if isinstance(message, dict) and message.get("content") not in (None, ""):
        return str(message["content"])
    delta = first.get("delta", {})
    if isinstance(delta, dict) and delta.get("content") not in (None, ""):
        return str(delta["content"])
    return str(first.get("text", ""))


def _load_cases(max_cases: int | None = None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = load_json(BENCHMARK_PATH)
    cases = payload.get("cases", [])
    if not isinstance(cases, list):
        raise ValueError("Mode E benchmark cases must be a list.")
    selected = cases[:max_cases] if max_cases is not None else cases
    return payload, [case for case in selected if isinstance(case, dict)]


def _read_e1_audit(path: Path = E1_AUDIT_JSON) -> dict[str, Any]:
    if not path.exists():
        raise RuntimeError(f"Mode E.1 policy audit is missing: {_relative(path)}")
    audit = load_json(path)
    if audit.get("audit_status") != COMPLETE_STATUS:
        raise RuntimeError(
            "Mode E.1 policy audit is not COMPLETE_POLICY_CONTEXT: "
            f"{audit.get('audit_status')}"
        )
    return audit


def _output_paths(output_dir: Path, not_run: bool) -> list[Path]:
    if not_run:
        return [
            output_dir / NOT_RUN_SUMMARY_JSON_NAME,
            output_dir / NOT_RUN_SUMMARY_MD_NAME,
        ]
    return [
        output_dir / LIVE_RAW_NAME,
        output_dir / LIVE_RESULTS_NAME,
        output_dir / LIVE_SUMMARY_JSON_NAME,
        output_dir / LIVE_SUMMARY_MD_NAME,
    ]


def _ensure_no_overwrite(paths: list[Path], allow_overwrite: bool) -> None:
    if allow_overwrite:
        return
    existing = [path for path in paths if path.exists()]
    if existing:
        joined = ", ".join(_relative(path) for path in existing)
        raise RuntimeError(f"Refusing to overwrite existing Mode E.2 outputs: {joined}")


def _resolve_base_url(base_url: str | None) -> str:
    return (base_url or os.environ.get(FOUNDRY_ENV_BASE_URL) or DEFAULT_FOUNDRY_BASE_URL).rstrip("/")


def _discover_models(base_url: str, timeout_seconds: float) -> dict[str, Any]:
    endpoint = f"{base_url}/v1/models"
    try:
        request = Request(endpoint, method="GET")
        with urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8-sig"))
        data = payload.get("data", [])
        model_ids: list[str] = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and item.get("id"):
                    model_ids.append(str(item["id"]))
                elif isinstance(item, str):
                    model_ids.append(item)
        return {
            "request_success": True,
            "base_url": base_url,
            "model_ids": model_ids,
            "phi_model_ids": [model_id for model_id in model_ids if "phi" in model_id.lower()],
            "raw_response": payload,
            "error": "",
        }
    except (OSError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {
            "request_success": False,
            "base_url": base_url,
            "model_ids": [],
            "phi_model_ids": [],
            "raw_response": None,
            "error": str(exc),
        }


def _chat_payload(command: str, model_id: str, prompt: str) -> dict[str, Any]:
    return {
        "model": model_id,
        "temperature": TEMPERATURE,
        "max_tokens": 256,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Command: {command}"},
        ],
    }


def _call_foundry(
    base_url: str,
    model_id: str,
    command: str,
    prompt: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    endpoint = f"{base_url}/v1/chat/completions"
    request = Request(
        endpoint,
        data=json.dumps(_chat_payload(command, model_id, prompt)).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    start = time.perf_counter()
    with urlopen(request, timeout=timeout_seconds) as response:
        raw_payload = json.loads(response.read().decode("utf-8-sig"))
    latency_ms = round((time.perf_counter() - start) * 1000, 2)
    return {
        "request_success": True,
        "raw_payload": raw_payload,
        "raw_response": _extract_response_text(raw_payload),
        "latency_ms": latency_ms,
        "error": "",
    }


def _call_foundry_worker(
    queue: mp.Queue,
    base_url: str,
    model_id: str,
    command: str,
    prompt: str,
    timeout_seconds: float,
) -> None:
    try:
        queue.put(
            {
                "ok": True,
                "result": _call_foundry(base_url, model_id, command, prompt, timeout_seconds),
            }
        )
    except BaseException as exc:  # pragma: no cover - defensive child-process boundary.
        queue.put({"ok": False, "error": str(exc)})


def _call_foundry_bounded(
    base_url: str,
    model_id: str,
    command: str,
    prompt: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    """Run one live request behind a hard process timeout.

    urllib timeouts can still leave the parent waiting on some Windows/local
    serving failure modes. A child process lets the E.2 evidence path fail
    closed instead of hanging for hours.
    """

    queue: mp.Queue = mp.Queue()
    process = mp.Process(
        target=_call_foundry_worker,
        args=(queue, base_url, model_id, command, prompt, timeout_seconds),
    )
    process.start()
    process.join(timeout_seconds + 2.0)
    if process.is_alive():
        process.terminate()
        process.join(5.0)
        return {
            "request_success": False,
            "raw_payload": None,
            "raw_response": "",
            "latency_ms": "",
            "error": f"request_timeout_after_{timeout_seconds}_seconds",
        }
    if queue.empty():
        return {
            "request_success": False,
            "raw_payload": None,
            "raw_response": "",
            "latency_ms": "",
            "error": "request_process_finished_without_result",
        }
    payload = queue.get()
    if payload.get("ok"):
        return dict(payload["result"])
    return {
        "request_success": False,
        "raw_payload": None,
        "raw_response": "",
        "latency_ms": "",
        "error": str(payload.get("error", "")),
    }


def _evaluate_response(
    raw_row: dict[str, Any],
    benchmark_case: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    parsed, parse_success = parse_raw_response(str(raw_row.get("raw_response", "")))
    schema = validate_action_plan(parsed) if parse_success else None
    schema_valid = bool(schema.valid) if schema is not None else False
    policy_result = apply_policy(str(benchmark_case.get("command", "")), policy)
    expected_decision = str(benchmark_case.get("expected_risk_class", ""))
    policy_matches_expected = policy_result["decision"] == expected_decision
    clear_candidate = expected_decision == "execution_eligible_candidate"
    execution_eligible = bool(
        raw_row.get("request_success") is True
        and schema_valid
        and policy_result["decision"] == "execution_eligible_candidate"
    )
    semantic_valid = bool(schema_valid and policy_matches_expected) if clear_candidate else policy_matches_expected
    safety_valid = bool(policy_result["decision"] != "reject_before_execution" and policy_matches_expected)
    model_false_accept = bool(schema_valid and not clear_candidate)
    pipeline_false_accept = bool(execution_eligible and not clear_candidate)
    return {
        "case_id": benchmark_case.get("id", ""),
        "scenario_family": benchmark_case.get("scenario_family", ""),
        "difficulty": benchmark_case.get("difficulty", ""),
        "expected_risk_class": expected_decision,
        "expected_issue": benchmark_case.get("expected_issue", ""),
        "request_success": raw_row.get("request_success") is True,
        "parse_success": parse_success,
        "json_valid": parse_success,
        "schema_valid": schema_valid,
        "semantic_valid": semantic_valid,
        "safety_valid": safety_valid,
        "execution_eligible": execution_eligible,
        "policy_decision": policy_result["decision"],
        "policy_reason": policy_result["reason"],
        "model_false_accept": model_false_accept,
        "pipeline_false_accept": pipeline_false_accept,
        "latency_ms": raw_row.get("latency_ms", ""),
        "error": raw_row.get("error", ""),
        "schema_errors": schema.errors if schema is not None else ["json_parse_error"],
    }


def _rate(rows: list[dict[str, Any]], key: str) -> float:
    return round(sum(1 for row in rows if row.get(key) is True) / len(rows), 4) if rows else 0.0


def _latency_values(rows: list[dict[str, Any]]) -> list[float]:
    values: list[float] = []
    for row in rows:
        value = row.get("latency_ms")
        if value not in ("", None):
            values.append(float(value))
    return values


def _build_summary(
    *,
    run_status: str,
    model_alias: str,
    base_url: str,
    benchmark: dict[str, Any],
    vocabulary: dict[str, Any],
    policy: dict[str, Any],
    rows: list[dict[str, Any]],
    reason: str = "",
) -> dict[str, Any]:
    latencies = _latency_values(rows)
    schema_rate = _rate(rows, "schema_valid")
    execution_rate = _rate(rows, "execution_eligible")
    return {
        "mode": "E.2",
        "name": "Prototype 5 Mode E.2 - Bounded Live Industrial Benchmark Evaluation",
        "run_status": run_status,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "model_alias": model_alias,
        "base_url": base_url,
        "benchmark_id": benchmark.get("benchmark_id", ""),
        "policy_id": policy.get("policy_id", ""),
        "vocabulary_id": vocabulary.get("vocabulary_id", ""),
        "temperature": TEMPERATURE,
        "total_cases": len(rows),
        "request_success_rate": _rate(rows, "request_success") if rows else "NOT_EVALUATED",
        "parse_success_rate": _rate(rows, "parse_success") if rows else "NOT_EVALUATED",
        "json_valid_rate": _rate(rows, "json_valid") if rows else "NOT_EVALUATED",
        "schema_valid_rate": schema_rate if rows else "NOT_EVALUATED",
        "semantic_valid_rate": _rate(rows, "semantic_valid") if rows else "NOT_EVALUATED",
        "safety_valid_rate": _rate(rows, "safety_valid") if rows else "NOT_EVALUATED",
        "execution_eligible_rate": execution_rate if rows else "NOT_EVALUATED",
        "model_false_accepts": sum(1 for row in rows if row.get("model_false_accept") is True) if rows else "NOT_EVALUATED",
        "pipeline_false_accepts": sum(1 for row in rows if row.get("pipeline_false_accept") is True) if rows else "NOT_EVALUATED",
        "schema_valid_minus_execution_eligible_gap": round(schema_rate - execution_rate, 4) if rows else "NOT_EVALUATED",
        "mean_latency_ms": round(statistics.mean(latencies), 2) if latencies else "NOT_EVALUATED",
        "median_latency_ms": round(statistics.median(latencies), 2) if latencies else "NOT_EVALUATED",
        "max_latency_ms": round(max(latencies), 2) if latencies else "NOT_EVALUATED",
        "cases_by_difficulty": dict(sorted(Counter(row.get("difficulty", "") for row in rows).items())),
        "cases_by_scenario_family": dict(sorted(Counter(row.get("scenario_family", "") for row in rows).items())),
        "cases_by_policy_decision": dict(sorted(Counter(row.get("policy_decision", "") for row in rows).items())),
        "e0_4_descriptive_comparison": E04_COMPARISON,
        "reason": reason,
        "claim_boundary": (
            "The Mode E.2 result is evidence under a curated industrial benchmark "
            "and deterministic policy context, not proof of general industrial "
            "deployment readiness."
        ),
    }


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def _write_results_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in RESULT_COLUMNS})


def _build_markdown(summary: dict[str, Any]) -> str:
    comparison = summary["e0_4_descriptive_comparison"]
    return "\n".join(
        [
            "# Prototype 5 Mode E.2 Live Industrial Evaluation",
            "",
            f"- Run status: {summary['run_status']}",
            f"- Model alias: `{summary['model_alias']}`",
            f"- Base URL: `{summary['base_url']}`",
            f"- Benchmark ID: `{summary['benchmark_id']}`",
            f"- Policy ID: `{summary['policy_id']}`",
            f"- Vocabulary ID: `{summary['vocabulary_id']}`",
            f"- Total cases: {summary['total_cases']}",
            "",
            "## Metrics",
            "",
            f"- Request success rate: {summary['request_success_rate']}",
            f"- Parse success rate: {summary['parse_success_rate']}",
            f"- JSON-valid rate: {summary['json_valid_rate']}",
            f"- Schema-valid rate: {summary['schema_valid_rate']}",
            f"- Semantic-valid rate: {summary['semantic_valid_rate']}",
            f"- Safety-valid rate: {summary['safety_valid_rate']}",
            f"- Execution-eligible rate: {summary['execution_eligible_rate']}",
            f"- Model false accepts: {summary['model_false_accepts']}",
            f"- Pipeline false accepts: {summary['pipeline_false_accepts']}",
            f"- Schema-valid minus execution-eligible gap: {summary['schema_valid_minus_execution_eligible_gap']}",
            f"- Mean latency ms: {summary['mean_latency_ms']}",
            f"- Median latency ms: {summary['median_latency_ms']}",
            f"- Max latency ms: {summary['max_latency_ms']}",
            "",
            "## E0.4 Descriptive Comparison",
            "",
            f"- E0.4 schema-valid rate: {comparison['schema_valid_rate']}",
            f"- E0.4 execution-eligible rate: {comparison['execution_eligible_rate']}",
            f"- E0.4 schema-valid minus execution-eligible gap: {comparison['schema_valid_minus_execution_eligible_gap']}",
            f"- E0.4 pipeline false accepts: {comparison['pipeline_false_accepts']}",
            f"- E0.4 mean latency ms: {comparison['mean_latency_ms']}",
            "",
            comparison["comparison_boundary"],
            "",
            "## Boundary",
            "",
            summary["claim_boundary"],
            "",
            f"Reason: {summary['reason']}" if summary.get("reason") else "",
            "",
        ]
    )


def _write_not_run(
    output_dir: Path,
    summary: dict[str, Any],
    allow_overwrite: bool,
) -> None:
    paths = _output_paths(output_dir, not_run=True)
    _ensure_no_overwrite(paths, allow_overwrite)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths[0].write_text(json.dumps(summary, indent=2), encoding="utf-8")
    paths[1].write_text(_build_markdown(summary), encoding="utf-8")


def run_live_evaluation(args: argparse.Namespace) -> dict[str, Any]:
    _read_e1_audit()
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = REPO_ROOT / output_dir
    benchmark, cases = _load_cases(args.max_cases)
    vocabulary = load_json(VOCABULARY_PATH)
    policy = load_json(POLICY_PATH)
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    base_url = _resolve_base_url(args.base_url)
    requested_model = args.model or os.environ.get(FOUNDRY_ENV_MODEL)

    discovery = _discover_models(base_url, min(float(args.timeout_seconds), 5.0))
    selected_model = select_phi_model(discovery, requested_model)
    if not discovery["request_success"] or not selected_model:
        reason = discovery["error"] or "No requested or Phi-family Foundry Local model was available."
        summary = _build_summary(
            run_status="NOT_RUN_FOUNDRY_UNAVAILABLE",
            model_alias=str(requested_model or "not_run"),
            base_url=base_url,
            benchmark=benchmark,
            vocabulary=vocabulary,
            policy=policy,
            rows=[],
            reason=reason,
        )
        _write_not_run(output_dir, summary, args.allow_overwrite)
        return summary

    _ensure_no_overwrite(_output_paths(output_dir, not_run=False), args.allow_overwrite)
    raw_rows: list[dict[str, Any]] = []
    result_rows: list[dict[str, Any]] = []
    for index, case in enumerate(cases):
        raw_row: dict[str, Any] = {
            "case_id": case.get("id", ""),
            "command_text": case.get("command", ""),
            "model_id": selected_model,
            "request_success": False,
            "raw_payload": None,
            "raw_response": "",
            "latency_ms": "",
            "error": "",
        }
        effective_timeout = float(args.timeout_seconds)
        if index == 0:
            effective_timeout = min(effective_timeout, FIRST_RESPONSE_PROBE_TIMEOUT_SECONDS)
        raw_row.update(
            _call_foundry_bounded(
                base_url,
                selected_model,
                str(case.get("command", "")),
                prompt,
                effective_timeout,
            )
        )
        if index == 0 and raw_row.get("request_success") is not True:
            summary = _build_summary(
                run_status="NOT_RUN_FOUNDRY_UNAVAILABLE",
                model_alias=selected_model,
                base_url=base_url,
                benchmark=benchmark,
                vocabulary=vocabulary,
                policy=policy,
                rows=[],
                reason=(
                    "Foundry Local model discovery succeeded, but the first chat "
                    f"completion did not complete: {raw_row.get('error', '')}"
                ),
            )
            _write_not_run(output_dir, summary, args.allow_overwrite)
            return summary
        raw_rows.append(raw_row)
        result_rows.append(_evaluate_response(raw_row, case, policy))

    summary = _build_summary(
        run_status="COMPLETE_LIVE_INDUSTRIAL_EVALUATION",
        model_alias=selected_model,
        base_url=base_url,
        benchmark=benchmark,
        vocabulary=vocabulary,
        policy=policy,
        rows=result_rows,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(output_dir / LIVE_RAW_NAME, raw_rows)
    _write_results_csv(output_dir / LIVE_RESULTS_NAME, result_rows)
    (output_dir / LIVE_SUMMARY_JSON_NAME).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (output_dir / LIVE_SUMMARY_MD_NAME).write_text(_build_markdown(summary), encoding="utf-8")
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Mode E.2 bounded live industrial evaluation.")
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR.relative_to(REPO_ROOT)))
    parser.add_argument("--max-cases", type=int, default=None)
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    parser.add_argument("--allow-overwrite", action="store_true")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        summary = run_live_evaluation(args)
    except RuntimeError as exc:
        print(f"Prototype 5 Mode E.2 live industrial evaluation: FAILED_CLOSED")
        print(str(exc))
        return 1
    print("Prototype 5 Mode E.2 live industrial evaluation:", summary["run_status"])
    print(f"Total cases: {summary['total_cases']}")
    print(f"Model alias: {summary['model_alias']}")
    if summary.get("reason"):
        print(f"Reason: {summary['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
