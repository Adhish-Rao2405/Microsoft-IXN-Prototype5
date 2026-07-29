"""Mode E0.4 repo-local full live pipeline repeatability adapter.

This runner uses only Prototype 5 repo-local inputs: the copied 30-command
benchmark, the action-envelope prompt, Foundry Local chat completions, and the
deterministic validation helpers used by Mode E0.2. It does not change locked
Prototype 3/4 metrics and it does not claim physical robot safety.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.prototype5.foundry_discovery import discover_foundry_models, select_phi_model

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from run_pipeline_repeatability_analysis import evaluate_record


MODE_E0_DIR = REPO_ROOT / "results" / "prototype5" / "mode_e0"
CONFIG_DIR = REPO_ROOT / "configs" / "prototype5"
DEFAULT_BENCHMARK_PATH = CONFIG_DIR / "benchmark_v1.json"
DEFAULT_PROMPT_PATH = CONFIG_DIR / "action_envelope_prompt.txt"

RUNS_CSV = MODE_E0_DIR / "full_pipeline_live_repeatability_runs.csv"
SUMMARY_JSON = MODE_E0_DIR / "full_pipeline_live_repeatability_summary.json"
SUMMARY_MD = MODE_E0_DIR / "full_pipeline_live_repeatability_summary.md"
RUN_SLOT_RE = re.compile(r"e0_4_full_pipeline_run_(\d{2})(?:_|_raw)")

RUN_COLUMNS = [
    "run_id",
    "model_alias",
    "benchmark_id",
    "config_id",
    "status",
    "commands_evaluated",
    "request_success_rate",
    "parse_success_rate",
    "json_valid_rate",
    "schema_valid_rate",
    "semantic_valid_rate",
    "safety_valid_rate",
    "execution_eligible_rate",
    "model_false_accepts",
    "pipeline_false_accepts",
    "correct_rejects",
    "mean_latency_ms",
    "std_latency_ms",
    "schema_valid_minus_execution_eligible_gap",
    "raw_output_file",
    "notes",
]

METRICS_FOR_VARIANCE = [
    "request_success_rate",
    "parse_success_rate",
    "json_valid_rate",
    "schema_valid_rate",
    "semantic_valid_rate",
    "safety_valid_rate",
    "execution_eligible_rate",
    "model_false_accepts",
    "pipeline_false_accepts",
    "correct_rejects",
    "mean_latency_ms",
    "std_latency_ms",
    "schema_valid_minus_execution_eligible_gap",
]

SCENE_STATE: dict[str, Any] = {}


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT).as_posix())
    except ValueError:
        return str(path)


def _configure_output_dir(output_dir: Path) -> None:
    global MODE_E0_DIR, RUNS_CSV, SUMMARY_JSON, SUMMARY_MD
    MODE_E0_DIR = output_dir
    RUNS_CSV = output_dir / "full_pipeline_live_repeatability_runs.csv"
    SUMMARY_JSON = output_dir / "full_pipeline_live_repeatability_summary.json"
    SUMMARY_MD = output_dir / "full_pipeline_live_repeatability_summary.md"


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


def _load_benchmark(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, list):
        raise ValueError(f"Benchmark must be a list: {path}")
    return payload


def _benchmark_by_id(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item["id"]): item for item in items}


def _chat_payload(command: str, model_id: str, prompt: str, max_tokens: int) -> dict[str, Any]:
    return {
        "model": model_id,
        "temperature": 0,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Command: {command}\nScene: {SCENE_STATE}"},
        ],
    }


def _call_foundry_action_envelope(
    base_url: str,
    model_id: str,
    command: str,
    prompt: str,
    timeout_seconds: float,
    max_tokens: int,
) -> dict[str, Any]:
    endpoint = f"{base_url.rstrip('/')}/v1/chat/completions"
    payload_bytes = json.dumps(_chat_payload(command, model_id, prompt, max_tokens)).encode("utf-8")
    request = Request(
        endpoint,
        data=payload_bytes,
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


def _write_jsonl(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def _stable_raw_path(slot: int) -> Path:
    return MODE_E0_DIR / f"e0_4_full_pipeline_run_{slot:02d}_raw.jsonl"


def _debug_raw_path(slot: int) -> Path:
    return MODE_E0_DIR / f"e0_4_full_pipeline_run_{slot:02d}_debug_raw.jsonl"


def _slot_from_path(path: Path) -> int | None:
    match = RUN_SLOT_RE.search(path.name)
    if not match:
        return None
    return int(match.group(1))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _migrate_timestamped_run_slots() -> None:
    """Copy legacy timestamped completed run files to stable slot names."""

    MODE_E0_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(MODE_E0_DIR.glob("e0_4_full_pipeline_run_*_raw.jsonl")):
        slot = _slot_from_path(path)
        if slot is None or path == _stable_raw_path(slot):
            continue
        stable_path = _stable_raw_path(slot)
        if stable_path.exists():
            continue
        try:
            records = _read_jsonl(path)
        except json.JSONDecodeError:
            continue
        if len(records) == 30:
            shutil.copy2(path, stable_path)


def _rate(count: int, total: int) -> float:
    return round(count / total, 4) if total else 0.0


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None


def _std(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    return round(math.sqrt(sum((value - mean) ** 2 for value in values) / (len(values) - 1)), 4)


def _row_float(row: dict[str, str], key: str) -> float | None:
    try:
        return float(row.get(key, ""))
    except ValueError:
        return None


def _summarise_evaluated_run(
    run_id: str,
    model_alias: str,
    evaluated: list[dict[str, Any]],
    raw_path: Path,
    benchmark_size: int = 30,
) -> dict[str, str]:
    total = len(evaluated)
    latencies = [
        float(row["latency_ms"])
        for row in evaluated
        if row.get("latency_ms") not in ("", None)
    ]
    schema_rate = _rate(sum(1 for row in evaluated if row["schema_valid"]), total)
    execution_rate = _rate(sum(1 for row in evaluated if row["execution_eligible"]), total)
    status = (
        "COMPLETE_FULL_LIVE_PIPELINE_REPEATABILITY"
        if total == benchmark_size
        else "DEBUG_PARTIAL_RUN"
    )
    return {
        "run_id": run_id,
        "model_alias": model_alias,
        "benchmark_id": "benchmark_v1",
        "config_id": "repo_local_action_envelope_temperature_0",
        "status": status,
        "commands_evaluated": str(total),
        "request_success_rate": str(_rate(sum(1 for row in evaluated if row["request_success"]), total)),
        "parse_success_rate": str(_rate(sum(1 for row in evaluated if row["parse_success"]), total)),
        "json_valid_rate": str(_rate(sum(1 for row in evaluated if row["json_valid"]), total)),
        "schema_valid_rate": str(schema_rate),
        "semantic_valid_rate": str(_rate(sum(1 for row in evaluated if row["semantic_valid"]), total)),
        "safety_valid_rate": str(_rate(sum(1 for row in evaluated if row["safety_valid"]), total)),
        "execution_eligible_rate": str(execution_rate),
        "model_false_accepts": str(sum(1 for row in evaluated if row["model_false_accept"])),
        "pipeline_false_accepts": str(sum(1 for row in evaluated if row["pipeline_false_accept"])),
        "correct_rejects": str(sum(1 for row in evaluated if row["correct_reject"])),
        "mean_latency_ms": str(round(sum(latencies) / len(latencies), 2)) if latencies else "",
        "std_latency_ms": str(round(math.sqrt(sum((value - (sum(latencies) / len(latencies))) ** 2 for value in latencies) / (len(latencies) - 1)), 2)) if len(latencies) > 1 else "",
        "schema_valid_minus_execution_eligible_gap": str(round(schema_rate - execution_rate, 4)),
        "raw_output_file": _display_path(raw_path),
        "notes": (
            "Live Foundry Local action-envelope run evaluated through deterministic schema, semantic, safety and execution-eligibility gates."
            if status == "COMPLETE_FULL_LIVE_PIPELINE_REPEATABILITY"
            else "Debug partial run; not counted toward completed repeatability."
        ),
    }


def _not_run_row(reason: str) -> dict[str, str]:
    row = {column: "" for column in RUN_COLUMNS}
    row.update(
        {
            "run_id": "e0_4_full_live_pipeline",
            "model_alias": "not_run",
            "benchmark_id": "benchmark_v1",
            "config_id": "repo_local_action_envelope_temperature_0",
            "status": "E0_4_NOT_RUN",
            "commands_evaluated": "0",
            "request_success_rate": "NOT_EVALUATED",
            "parse_success_rate": "NOT_EVALUATED",
            "json_valid_rate": "NOT_EVALUATED",
            "schema_valid_rate": "NOT_EVALUATED",
            "semantic_valid_rate": "NOT_EVALUATED",
            "safety_valid_rate": "NOT_EVALUATED",
            "execution_eligible_rate": "NOT_EVALUATED",
            "model_false_accepts": "NOT_EVALUATED",
            "pipeline_false_accepts": "NOT_EVALUATED",
            "correct_rejects": "NOT_EVALUATED",
            "mean_latency_ms": "NOT_EVALUATED",
            "std_latency_ms": "NOT_EVALUATED",
            "schema_valid_minus_execution_eligible_gap": "NOT_EVALUATED",
            "notes": reason,
        }
    )
    return row


def _write_runs_csv(rows: list[dict[str, str]]) -> None:
    MODE_E0_DIR.mkdir(parents=True, exist_ok=True)
    with RUNS_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RUN_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _read_runs_csv() -> list[dict[str, str]]:
    if not RUNS_CSV.exists():
        return []
    with RUNS_CSV.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _find_raw_paths() -> list[Path]:
    _migrate_timestamped_run_slots()
    stable_by_slot: dict[int, Path] = {}
    debug_paths: list[Path] = []
    timestamped_fallbacks: dict[int, Path] = {}
    for path in sorted(MODE_E0_DIR.glob("e0_4_full_pipeline_run_*_raw.jsonl")):
        slot = _slot_from_path(path)
        if slot is None:
            continue
        if path == _stable_raw_path(slot):
            stable_by_slot[slot] = path
        elif "_debug_raw" in path.name:
            debug_paths.append(path)
        else:
            timestamped_fallbacks.setdefault(slot, path)
    selected = [
        stable_by_slot.get(slot) or timestamped_fallbacks[slot]
        for slot in sorted(set(stable_by_slot) | set(timestamped_fallbacks))
    ]
    selected.extend(sorted(debug_paths))
    return selected


def _summarise_existing_raw(benchmark_path: Path) -> list[dict[str, str]]:
    benchmark_items = _load_benchmark(benchmark_path)
    benchmark_by_id = _benchmark_by_id(benchmark_items)
    rows: list[dict[str, str]] = []
    for raw_path in _find_raw_paths():
        raw_records = _read_jsonl(raw_path)
        evaluated = [evaluate_record(record, benchmark_by_id) for record in raw_records]
        run_id = raw_records[0].get("run_id", raw_path.stem) if raw_records else raw_path.stem
        model_alias = raw_records[0].get("model_id", "") if raw_records else ""
        rows.append(
            _summarise_evaluated_run(
                str(run_id),
                str(model_alias),
                evaluated,
                raw_path,
                benchmark_size=len(benchmark_items),
            )
        )
    return rows


def _metric_variance(rows: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    completed = [
        row
        for row in rows
        if row.get("status") == "COMPLETE_FULL_LIVE_PIPELINE_REPEATABILITY"
    ]
    summary: dict[str, dict[str, Any]] = {}
    for metric in METRICS_FOR_VARIANCE:
        values = [
            value
            for value in (_row_float(row, metric) for row in completed)
            if value is not None
        ]
        stable = "NOT_EVALUATED"
        if len(values) >= 3:
            stable = "STABLE" if max(values) == min(values) else "VARIABLE"
        summary[metric] = {
            "values": values,
            "mean": _mean(values),
            "std": _std(values),
            "stable": stable,
        }
    return summary


def _completed_count(rows: list[dict[str, str]]) -> int:
    return sum(1 for row in rows if row.get("status") == "COMPLETE_FULL_LIVE_PIPELINE_REPEATABILITY")


def _summary_status(rows: list[dict[str, str]]) -> str:
    completed_count = _completed_count(rows)
    if completed_count >= 3:
        return "COMPLETE_FULL_LIVE_PIPELINE_REPEATABILITY"
    if completed_count > 0:
        return "PARTIAL_FULL_LIVE_PIPELINE_REPEATABILITY"
    return "E0_4_NOT_RUN"


def _central_findings(rows: list[dict[str, str]]) -> dict[str, str]:
    completed = [
        row
        for row in rows
        if row.get("status") == "COMPLETE_FULL_LIVE_PIPELINE_REPEATABILITY"
    ]
    if len(completed) < 3:
        return {
            "schema_valid_greater_than_execution_eligible": "NOT_EVALUATED",
            "pipeline_false_accepts_bounded": "NOT_EVALUATED",
        }
    gaps = [_row_float(row, "schema_valid_minus_execution_eligible_gap") for row in completed]
    false_accepts = [_row_float(row, "pipeline_false_accepts") for row in completed]
    gap_status = (
        "STABLE_OBSERVED"
        if gaps and all(value is not None and value > 0 for value in gaps)
        else "NOT_OBSERVED_OR_VARIABLE"
    )
    false_accept_status = (
        "STABLE_ZERO"
        if false_accepts and all(value == 0 for value in false_accepts)
        else "VARIABLE_OR_NONZERO"
    )
    return {
        "schema_valid_greater_than_execution_eligible": gap_status,
        "pipeline_false_accepts_bounded": false_accept_status,
    }


def _write_summary(rows: list[dict[str, str]], benchmark_path: Path, prompt_path: Path, reason: str = "") -> dict[str, Any]:
    if not rows:
        rows = [_not_run_row(reason or "No E0.4 live raw outputs or run rows are available.")]
    completed_count = _completed_count(rows)
    status = _summary_status(rows)

    _write_runs_csv(rows)
    summary = {
        "mode": "E0.4",
        "name": "Repo-Local Full Pipeline Repeatability Adapter",
        "status": status,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "runs_evaluated": completed_count,
        "minimum_live_target": 3,
        "benchmark_path": str(benchmark_path.relative_to(REPO_ROOT).as_posix()),
        "prompt_path": str(prompt_path.relative_to(REPO_ROOT).as_posix()),
        "runs_csv": _display_path(RUNS_CSV),
        "raw_output_files": [
            row.get("raw_output_file", "")
            for row in rows
            if row.get("raw_output_file")
        ],
        "metric_variance": _metric_variance(rows),
        "central_findings": _central_findings(rows),
        "reason": reason,
        "claim_boundary": (
            "E0.4 measures full live pipeline repeatability only for the repo-local "
            "30-command benchmark, action-envelope prompt, selected Foundry Local model "
            "and deterministic validation policy. It does not change locked Prototype "
            "3/4 evidence and does not prove real-world robot safety or general model reliability."
        ),
    }
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    SUMMARY_MD.write_text(_build_markdown(summary, rows), encoding="utf-8")
    return summary


def _build_markdown(summary: dict[str, Any], rows: list[dict[str, str]]) -> str:
    lines = [
        "# Mode E0.4 Repo-Local Full Pipeline Repeatability Adapter",
        "",
        f"- Status: {summary['status']}",
        f"- Runs evaluated: {summary['runs_evaluated']}/{summary['minimum_live_target']}",
        f"- Benchmark: `{summary['benchmark_path']}`",
        f"- Prompt: `{summary['prompt_path']}`",
        f"- Runs CSV: `{summary['runs_csv']}`",
        "",
        "## Per-Run Metrics",
        "",
        "| Run | Request | JSON | Schema | Semantic | Safety | Execution eligible | Model false accepts | Pipeline false accepts | Gap | Mean latency ms |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| {run_id} | {request_success_rate} | {json_valid_rate} | {schema_valid_rate} | {semantic_valid_rate} | {safety_valid_rate} | {execution_eligible_rate} | {model_false_accepts} | {pipeline_false_accepts} | {gap} | {latency} |".format(
                run_id=row.get("run_id", ""),
                request_success_rate=row.get("request_success_rate", ""),
                json_valid_rate=row.get("json_valid_rate", ""),
                schema_valid_rate=row.get("schema_valid_rate", ""),
                semantic_valid_rate=row.get("semantic_valid_rate", ""),
                safety_valid_rate=row.get("safety_valid_rate", ""),
                execution_eligible_rate=row.get("execution_eligible_rate", ""),
                model_false_accepts=row.get("model_false_accepts", ""),
                pipeline_false_accepts=row.get("pipeline_false_accepts", ""),
                gap=row.get("schema_valid_minus_execution_eligible_gap", ""),
                latency=row.get("mean_latency_ms", ""),
            )
        )
    lines.extend(
        [
            "",
            "## Central Finding Stability",
            "",
            f"- Schema-valid greater than execution-eligible: {summary['central_findings']['schema_valid_greater_than_execution_eligible']}",
            f"- Pipeline false accepts bounded: {summary['central_findings']['pipeline_false_accepts_bounded']}",
            "",
            "## Boundary",
            "",
            summary["claim_boundary"],
            "",
        ]
    )
    if summary.get("reason"):
        lines.extend(["## Not-Run Or Partial Reason", "", summary["reason"], ""])
    return "\n".join(lines)


def _slot_from_row(row: dict[str, str]) -> int | None:
    raw_output = row.get("raw_output_file", "")
    if raw_output:
        slot = _slot_from_path(Path(raw_output))
        if slot is not None:
            return slot
    run_id = row.get("run_id", "")
    match = RUN_SLOT_RE.search(run_id)
    if match:
        return int(match.group(1))
    return None


def _existing_raw_slots() -> set[int]:
    _migrate_timestamped_run_slots()
    slots: set[int] = set()
    for path in MODE_E0_DIR.glob("e0_4_full_pipeline_run_*_raw.jsonl"):
        slot = _slot_from_path(path)
        if slot is not None:
            slots.add(slot)
    return slots


def _completed_slots(rows: list[dict[str, str]]) -> set[int]:
    slots: set[int] = set()
    for row in rows:
        if row.get("status") != "COMPLETE_FULL_LIVE_PIPELINE_REPEATABILITY":
            continue
        slot = _slot_from_row(row)
        if slot is not None:
            slots.add(slot)
    return slots


def _target_slots(
    runs: int,
    run_id: int | None,
    resume: bool,
    skip_existing: bool,
    existing_rows: list[dict[str, str]],
) -> list[int]:
    if run_id is not None:
        slots = [run_id]
    else:
        slots = list(range(1, runs + 1))
    if resume:
        completed = _completed_slots(existing_rows)
        slots = [slot for slot in slots if slot not in completed]
    if skip_existing:
        raw_slots = _existing_raw_slots()
        slots = [slot for slot in slots if slot not in raw_slots]
    return slots


def run_live(
    slots: list[int],
    base_url: str | None,
    requested_model: str | None,
    timeout_seconds: float,
    max_tokens: int,
    benchmark_path: Path,
    prompt_path: Path,
    max_commands: int | None,
) -> list[dict[str, str]]:
    if not benchmark_path.exists():
        raise FileNotFoundError(f"Repo-local benchmark missing: {benchmark_path}")
    if not prompt_path.exists():
        raise FileNotFoundError(f"Repo-local action-envelope prompt missing: {prompt_path}")

    discovery = discover_foundry_models(base_url=base_url, timeout_seconds=5.0)
    if not discovery.get("request_success"):
        raise RuntimeError(f"Foundry Local discovery failed: {discovery.get('error', '')}")
    selected_model = select_phi_model(discovery, requested_model)
    if not selected_model:
        raise RuntimeError("No suitable Phi-family Foundry Local model was discovered.")

    benchmark_items = _load_benchmark(benchmark_path)
    benchmark_size = len(benchmark_items)
    selected_items = benchmark_items[:max_commands] if max_commands is not None else benchmark_items
    debug_partial = max_commands is not None and max_commands < benchmark_size
    benchmark_by_id = _benchmark_by_id(benchmark_items)
    prompt = prompt_path.read_text(encoding="utf-8")
    rows: list[dict[str, str]] = []
    for run_number in slots:
        run_id = f"e0_4_full_pipeline_run_{run_number:02d}"
        raw_path = _debug_raw_path(run_number) if debug_partial else _stable_raw_path(run_number)
        if raw_path.exists():
            continue
        raw_rows: list[dict[str, Any]] = []
        evaluated_rows: list[dict[str, Any]] = []
        for item in selected_items:
            raw_row: dict[str, Any] = {
                "run_id": run_id,
                "command_id": item["id"],
                "command_text": item["command"],
                "model_id": selected_model,
                "request_success": False,
                "raw_response": "",
                "latency_ms": "",
                "error": "",
            }
            try:
                raw_row.update(
                    _call_foundry_action_envelope(
                        discovery["base_url"],
                        selected_model,
                        item["command"],
                        prompt,
                        timeout_seconds,
                        max_tokens,
                    )
                )
            except (OSError, URLError, TimeoutError, json.JSONDecodeError) as exc:
                raw_row["error"] = str(exc)
            raw_rows.append(raw_row)
            evaluated_rows.append(evaluate_record(raw_row, benchmark_by_id))
        _write_jsonl(raw_rows, raw_path)
        rows.append(
            _summarise_evaluated_run(
                run_id,
                selected_model,
                evaluated_rows,
                raw_path,
                benchmark_size=benchmark_size,
            )
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Mode E0.4 full live pipeline repeatability.")
    parser.add_argument("--live", action="store_true", help="Make live Foundry Local calls.")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--run-id", type=int, choices=range(1, 100), metavar="N", help="Run only one repeatability slot, for example 2 or 3.")
    parser.add_argument("--resume", action="store_true", help="With --live, skip completed run slots and run only missing slots.")
    parser.add_argument("--skip-existing", action="store_true", help="With --live, do not overwrite or rerun slots with existing raw JSONL evidence.")
    parser.add_argument("--max-commands", type=int, default=None, help="Debug only. Runs a prefix of the benchmark and marks the row DEBUG_PARTIAL_RUN.")
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK_PATH)
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT_PATH)
    parser.add_argument("--output-dir", type=Path, default=MODE_E0_DIR)
    args = parser.parse_args()

    _configure_output_dir(args.output_dir)

    if args.base_url:
        os.environ["FOUNDRY_LOCAL_BASE_URL"] = args.base_url

    reason = ""
    try:
        if args.live:
            existing_rows = _summarise_existing_raw(args.benchmark)
            slots = _target_slots(
                runs=args.runs,
                run_id=args.run_id,
                resume=args.resume,
                skip_existing=args.skip_existing,
                existing_rows=existing_rows,
            )
            run_live(
                slots=slots,
                base_url=args.base_url,
                requested_model=args.model,
                timeout_seconds=args.timeout_seconds,
                max_tokens=args.max_tokens,
                benchmark_path=args.benchmark,
                prompt_path=args.prompt,
                max_commands=args.max_commands,
            )
            rows = _summarise_existing_raw(args.benchmark)
            if not slots:
                reason = "No live slots were run because resume/skip-existing found no eligible missing slots."
        else:
            rows = _summarise_existing_raw(args.benchmark)
            if not rows:
                rows = _read_runs_csv()
            if not rows:
                reason = (
                    "Live mode was not requested and no existing E0.4 raw outputs "
                    "were found. Run with --live when Foundry Local and the selected "
                    "model are available."
                )
    except Exception as exc:
        rows = [_not_run_row(str(exc))]
        reason = str(exc)

    summary = _write_summary(rows, args.benchmark, args.prompt, reason)
    print("Prototype 5 Mode E0.4 full pipeline repeatability:", summary["status"])
    print(f"Runs evaluated: {summary['runs_evaluated']}/{summary['minimum_live_target']}")
    print(
        "Schema-valid > execution-eligible:",
        summary["central_findings"]["schema_valid_greater_than_execution_eligible"],
    )
    print(
        "Pipeline false accepts:",
        summary["central_findings"]["pipeline_false_accepts_bounded"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
