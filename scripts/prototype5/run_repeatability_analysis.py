"""Mode E0.1 repeatability and variance summary generator.

This script updates the Mode E0.1 repeatability artefacts from any recorded
repeatability rows under results/prototype5/mode_e0. It intentionally does not
start Foundry Local or make cloud calls by default. If ``--live`` is passed, it
runs repeated Foundry Local calls against the fixed benchmark and writes only
Mode E0.1 artefacts.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError

REPO_ROOT_FOR_IMPORTS = Path(__file__).resolve().parents[2]
if str(REPO_ROOT_FOR_IMPORTS) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT_FOR_IMPORTS))

from src.prototype5.benchmark_cases import load_benchmark_cases
from src.prototype5.foundry_discovery import discover_foundry_models, select_phi_model
from src.prototype5.phi_recovery_runner import call_foundry_chat

import run_reproducibility_check as reproducibility
from run_reproducibility_check import (
    REPEATABILITY_COLUMNS,
    REPEATABILITY_LIVE_RUNS_CSV,
    REPO_ROOT,
    RESULTS_DIR,
    ensure_repeatability_outputs,
)


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT).as_posix())
    except ValueError:
        return str(path)


def _configure_output_dir(output_dir: Path) -> None:
    global RESULTS_DIR, REPEATABILITY_LIVE_RUNS_CSV
    RESULTS_DIR = output_dir
    REPEATABILITY_LIVE_RUNS_CSV = output_dir / "repeatability_live_runs.csv"
    reproducibility.configure_output_dir(output_dir)


def _write_jsonl(rows: list[dict[str, object]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def _rate(count: int, total: int) -> str:
    if total == 0:
        return ""
    return str(round(count / total, 4))


def _latency_mean(latencies: list[float]) -> str:
    if not latencies:
        return ""
    return str(round(sum(latencies) / len(latencies), 2))


def _latency_std(latencies: list[float]) -> str:
    if len(latencies) < 2:
        return ""
    return str(round(statistics.stdev(latencies), 2))


def _summarise_live_run(
    run_id: str,
    model_alias: str,
    rows: list[dict[str, object]],
    benchmark_size: int,
    raw_path: Path,
) -> dict[str, str]:
    successful = [row for row in rows if row.get("request_success") is True]
    parse_success = [row for row in rows if row.get("parse_success") is True]
    json_valid = [row for row in rows if row.get("json_valid") is True]
    latencies = [
        float(row["latency_ms"])
        for row in successful
        if row.get("latency_ms") not in (None, "")
    ]
    if len(successful) == benchmark_size and benchmark_size > 0:
        status = "COMPLETE_LIVE_OUTPUT_REPEATABILITY"
    elif successful:
        status = "PARTIAL"
    else:
        status = "FAILED"
    return {
        "run_id": run_id,
        "model_alias": model_alias,
        "benchmark_id": "benchmark_v1",
        "config_id": "foundry_phi_temperature_0_json_prompt",
        "status": status,
        "request_success_rate": _rate(len(successful), benchmark_size),
        "parse_success_rate": _rate(len(parse_success), benchmark_size),
        "json_valid_rate": _rate(len(json_valid), benchmark_size),
        "schema_valid_rate": "NOT_EVALUATED",
        "semantic_valid_rate": "NOT_EVALUATED",
        "safety_valid_rate": "NOT_EVALUATED",
        "execution_eligible_rate": "NOT_EVALUATED",
        "model_false_accepts": "NOT_EVALUATED",
        "pipeline_false_accepts": "NOT_EVALUATED",
        "mean_latency_ms": _latency_mean(latencies),
        "std_latency_ms": _latency_std(latencies),
        "notes": (
            "Live Foundry Local repeatability run. Schema, semantic, safety and "
            "execution-eligibility metrics are not evaluated by this E0.1 runner. "
            f"Raw rows: {_display_path(raw_path)}"
        ),
    }


def _write_live_summary(rows: list[dict[str, str]]) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with REPEATABILITY_LIVE_RUNS_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=REPEATABILITY_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def run_live_repeatability(
    runs: int,
    base_url: str | None,
    requested_model: str | None,
    timeout_seconds: float,
    max_tokens: int,
) -> list[dict[str, str]]:
    discovery = discover_foundry_models(base_url=base_url, timeout_seconds=5.0)
    selected_model = select_phi_model(discovery, requested_model)
    benchmark = load_benchmark_cases()
    if benchmark["status"] != "PRESENT":
        raise RuntimeError(f"Benchmark unavailable: {benchmark['status']}")
    if not discovery.get("request_success"):
        raise RuntimeError(f"Foundry discovery failed: {discovery.get('error', '')}")
    if not selected_model:
        raise RuntimeError("No Phi-family model found for repeatability run.")

    cases = benchmark["cases"]
    summary_rows: list[dict[str, str]] = []
    for run_number in range(1, runs + 1):
        run_id = f"e0_1_live_run_{run_number:02d}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        raw_rows: list[dict[str, object]] = []
        raw_path = RESULTS_DIR / f"{run_id}_raw.jsonl"
        for case in cases:
            row: dict[str, object] = {
                "run_id": run_id,
                "command_id": case["command_id"],
                "command_text": case["command_text"],
                "model_id": selected_model,
                "request_success": False,
                "parse_success": False,
                "json_valid": False,
                "latency_ms": "",
                "raw_response": "",
                "parsed_json": "",
                "error": "",
                "semantic_validity": "NOT_EVALUATED",
                "schema_valid": "NOT_EVALUATED",
                "safety_valid": "NOT_EVALUATED",
                "execution_eligible": "NOT_EVALUATED",
            }
            try:
                result = call_foundry_chat(
                    discovery["base_url"],
                    selected_model,
                    case["command_text"],
                    timeout_seconds=timeout_seconds,
                    max_tokens=max_tokens,
                )
                row.update(result)
            except (OSError, URLError, TimeoutError, json.JSONDecodeError) as exc:
                row["error"] = str(exc)
            raw_rows.append(row)
        _write_jsonl(raw_rows, raw_path)
        summary_rows.append(
            _summarise_live_run(
                run_id,
                selected_model,
                raw_rows,
                len(cases),
                raw_path,
            )
        )

    _write_live_summary(summary_rows)
    return summary_rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Mode E0.1 repeatability artefacts.")
    parser.add_argument("--live", action="store_true", help="Run live Foundry Local repeatability calls.")
    parser.add_argument("--runs", type=int, default=3, help="Number of live repeated runs.")
    parser.add_argument("--base-url", default=None, help="Foundry Local base URL.")
    parser.add_argument("--model", default=None, help="Requested Foundry Local model alias.")
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument("--max-tokens", type=int, default=128)
    parser.add_argument("--output-dir", type=Path, default=RESULTS_DIR)
    parser.add_argument(
        "--skip-foundry-probe",
        action="store_true",
        help="Do not query the local Foundry service while regenerating summaries.",
    )
    args = parser.parse_args()

    _configure_output_dir(args.output_dir)

    if args.base_url:
        os.environ["FOUNDRY_LOCAL_BASE_URL"] = args.base_url

    if args.live:
        rows = run_live_repeatability(
            runs=args.runs,
            base_url=args.base_url,
            requested_model=args.model,
            timeout_seconds=args.timeout_seconds,
            max_tokens=args.max_tokens,
        )
        print(f"Recorded live repeatability runs: {len(rows)}")

    probe_fn = (
        reproducibility._not_assessed_foundry_probe
        if args.skip_foundry_probe
        else reproducibility._probe_foundry_local
    )
    summary = ensure_repeatability_outputs(probe_fn=probe_fn)
    print("Prototype 5 Mode E0.1 repeatability analysis:", summary["status"])
    print(f"Completed repeated runs: {summary['completed_run_count']}/{summary['target_run_count']}")
    print(
        "Schema-valid > execution-eligible stability:",
        summary["central_findings"]["schema_valid_greater_than_execution_eligible"]["status"],
    )
    print(
        "Pipeline false-accept stability:",
        summary["central_findings"]["pipeline_false_accepts_bounded"]["status"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
