"""Mode E0 reproducibility and evaluation-rigour audit.

This script checks that the Mode E0 documentation exists, writes the
claim-to-evidence traceability CSV, writes honest repeatability outputs, and
produces a JSON summary. It does not run Foundry Local, cloud APIs, or any live
benchmark unless a separate live-repeatability runner is explicitly added.
"""

from __future__ import annotations

import csv
import json
import math
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = REPO_ROOT / "docs" / "prototype5"
RESULTS_DIR = REPO_ROOT / "results" / "prototype5" / "mode_e0"
DEFAULT_FOUNDRY_BASE_URL = "http://127.0.0.1:54701"

REQUIRED_DOCUMENTS = [
    DOCS_DIR / "reproducibility_guide.md",
    DOCS_DIR / "evaluation_design_justification.md",
    DOCS_DIR / "benchmark_representativeness.md",
    DOCS_DIR / "repeatability_and_variance_plan.md",
    DOCS_DIR / "claim_to_evidence_traceability.md",
]

TRACEABILITY_CSV = RESULTS_DIR / "claim_to_evidence_traceability.csv"
REPEATABILITY_CSV = RESULTS_DIR / "repeatability_summary.csv"
REPEATABILITY_LIVE_RUNS_CSV = RESULTS_DIR / "repeatability_live_runs.csv"
REPEATABILITY_VARIANCE_JSON = RESULTS_DIR / "repeatability_variance_summary.json"
REPEATABILITY_VARIANCE_MD = RESULTS_DIR / "repeatability_variance_summary.md"
PIPELINE_REPEATABILITY_RECORDS_JSONL = RESULTS_DIR / "pipeline_repeatability_records.jsonl"
PIPELINE_REPEATABILITY_SUMMARY_CSV = RESULTS_DIR / "pipeline_repeatability_summary.csv"
PIPELINE_REPEATABILITY_VARIANCE_JSON = RESULTS_DIR / "pipeline_repeatability_variance_summary.json"
PIPELINE_REPEATABILITY_VARIANCE_MD = RESULTS_DIR / "pipeline_repeatability_variance_summary.md"
FULL_PIPELINE_LIVE_CSV = RESULTS_DIR / "full_pipeline_repeatability_live_runs.csv"
FULL_PIPELINE_LIVE_JSON = RESULTS_DIR / "full_pipeline_repeatability_summary.json"
FULL_PIPELINE_LIVE_MD = RESULTS_DIR / "full_pipeline_repeatability_summary.md"
E0_4_FULL_PIPELINE_LIVE_CSV = RESULTS_DIR / "full_pipeline_live_repeatability_runs.csv"
E0_4_FULL_PIPELINE_LIVE_JSON = RESULTS_DIR / "full_pipeline_live_repeatability_summary.json"
E0_4_FULL_PIPELINE_LIVE_MD = RESULTS_DIR / "full_pipeline_live_repeatability_summary.md"
SUMMARY_JSON = RESULTS_DIR / "reproducibility_check_summary.json"
REQUIRED_RESULT_FILES = [
    SUMMARY_JSON,
    TRACEABILITY_CSV,
    REPEATABILITY_CSV,
    REPEATABILITY_LIVE_RUNS_CSV,
    REPEATABILITY_VARIANCE_JSON,
    REPEATABILITY_VARIANCE_MD,
    PIPELINE_REPEATABILITY_RECORDS_JSONL,
    PIPELINE_REPEATABILITY_SUMMARY_CSV,
    PIPELINE_REPEATABILITY_VARIANCE_JSON,
    PIPELINE_REPEATABILITY_VARIANCE_MD,
    FULL_PIPELINE_LIVE_CSV,
    FULL_PIPELINE_LIVE_JSON,
    FULL_PIPELINE_LIVE_MD,
    E0_4_FULL_PIPELINE_LIVE_CSV,
    E0_4_FULL_PIPELINE_LIVE_JSON,
    E0_4_FULL_PIPELINE_LIVE_MD,
]

TRACEABILITY_COLUMNS = [
    "claim_id",
    "claim",
    "prototype_or_mode",
    "evidence_file",
    "metrics",
    "evidence_status",
    "claim_boundary",
    "dissertation_relevance",
    "file_exists",
]

REPEATABILITY_COLUMNS = [
    "run_id",
    "model_alias",
    "benchmark_id",
    "config_id",
    "status",
    "request_success_rate",
    "parse_success_rate",
    "json_valid_rate",
    "schema_valid_rate",
    "semantic_valid_rate",
    "safety_valid_rate",
    "execution_eligible_rate",
    "model_false_accepts",
    "pipeline_false_accepts",
    "mean_latency_ms",
    "std_latency_ms",
    "notes",
]

REPEATABILITY_METRICS = [
    "request_success_rate",
    "parse_success_rate",
    "json_valid_rate",
    "schema_valid_rate",
    "semantic_valid_rate",
    "safety_valid_rate",
    "execution_eligible_rate",
    "model_false_accepts",
    "pipeline_false_accepts",
    "mean_latency_ms",
    "std_latency_ms",
]

TRACEABILITY_ROWS = [
    {
        "claim_id": "C1",
        "claim": "Local SLMs can generate parseable, JSON-valid, and schema-valid robot action proposals under the benchmark.",
        "prototype_or_mode": "Prototype 3; Prototype 5 Mode B",
        "evidence_file": "results/prototype5/final_model_comparison.csv; results/prototype5/recovery/phi/phi_recovery_summary.csv",
        "metrics": "parse_success; json_valid; schema_valid",
        "evidence_status": "PROVEN",
        "claim_boundary": "Benchmark-only result for detected local models and retained Phi response evidence.",
        "dissertation_relevance": "Supports RQ1 structured-output reliability.",
    },
    {
        "claim_id": "C2",
        "claim": "Schema validity is necessary but not sufficient for execution eligibility.",
        "prototype_or_mode": "Prototype 3",
        "evidence_file": "results/prototype5/final_model_comparison.csv",
        "metrics": "schema_valid_rate; execution_eligible_rate",
        "evidence_status": "PROVEN",
        "claim_boundary": "Applies to the evaluated benchmark and validation policy.",
        "dissertation_relevance": "Central dissertation claim and RQ2.",
    },
    {
        "claim_id": "C3",
        "claim": "Schema-valid outputs can still fail semantic, safety, or execution-eligibility checks.",
        "prototype_or_mode": "Prototype 3; Prototype 4",
        "evidence_file": "results/prototype5/final_model_comparison.csv; results/prototype5/final_zero_trust_comparison.csv",
        "metrics": "schema_valid_rate; unsafe_false_accepts; execution_eligible_rate",
        "evidence_status": "PROVEN",
        "claim_boundary": "Does not imply every schema-valid failure mode has been exhaustively covered.",
        "dissertation_relevance": "Justifies zero-trust validation after schema checks.",
    },
    {
        "claim_id": "C4",
        "claim": "Model-level false accepts should be separated from pipeline-level false accepts.",
        "prototype_or_mode": "Prototype 3; Prototype 4",
        "evidence_file": "results/prototype5/final_model_comparison.csv; results/prototype5/final_zero_trust_comparison.csv",
        "metrics": "false_accept_count; unsafe_false_accepts",
        "evidence_status": "PROVEN",
        "claim_boundary": "Terminology is tied to the implemented benchmark and pipeline modes.",
        "dissertation_relevance": "Prevents overclaiming model output quality as pipeline safety.",
    },
    {
        "claim_id": "C5",
        "claim": "Zero-trust validation can reduce unsafe pipeline-level false accepts under the evaluated policy.",
        "prototype_or_mode": "Prototype 4",
        "evidence_file": "results/prototype5/final_zero_trust_comparison.csv; results/prototype5/final_safety_latency_summary.csv",
        "metrics": "unsafe_false_accepts; unsafe_false_accept_rate",
        "evidence_status": "PROVEN",
        "claim_boundary": "Not real-world robot safety certification.",
        "dissertation_relevance": "Supports RQ2 and the zero-trust safety argument.",
    },
    {
        "claim_id": "C6",
        "claim": "Ambiguous commands reduce execution eligibility and increase the need for rejection or clarification.",
        "prototype_or_mode": "Prototype 4 extensions",
        "evidence_file": "results/prototype5/final_extension_summary.csv; results/prototype5/final_dissertation_metrics.md",
        "metrics": "ambiguity decisions; clarification cases; rejection behaviour",
        "evidence_status": "SUPPORTED",
        "claim_boundary": "Detailed per-ambiguity raw files may live in prior prototype repositories.",
        "dissertation_relevance": "Supports RQ3 ambiguity discussion.",
    },
    {
        "claim_id": "C7",
        "claim": "Local Foundry inference provides privacy, data-locality, and offline-resilience advantages, but may have latency and resource costs.",
        "prototype_or_mode": "Prototype 5 Mode C; Prototype 5 Mode D",
        "evidence_file": "results/prototype5/mode_c/local_vs_cloud_summary.json; results/prototype5/mode_d/mode_d_final_evidence_summary.json",
        "metrics": "privacy_comparison; offline_resilience_comparison; local_mean_latency_ms; cpu_usage",
        "evidence_status": "SUPPORTED",
        "claim_boundary": "Privacy and offline resilience are architectural/deployment properties, not quantitative safety results.",
        "dissertation_relevance": "Supports local-first deployment trade-off discussion.",
    },
    {
        "claim_id": "C8",
        "claim": "Cloud inference can be faster or more JSON-consistent under current benchmark conditions.",
        "prototype_or_mode": "Prototype 5 Mode C",
        "evidence_file": "results/prototype5/mode_c/local_vs_cloud_summary.json; results/prototype5/mode_c/local_vs_cloud_results.csv",
        "metrics": "cloud_mean_latency_ms; local_mean_latency_ms; cloud_json_valid_rate; local_json_valid_rate",
        "evidence_status": "PROVEN",
        "claim_boundary": "Current API/model/run conditions only; not a universal cloud superiority claim.",
        "dissertation_relevance": "Supports balanced local-vs-cloud comparison.",
    },
    {
        "claim_id": "C9",
        "claim": "Foundry Local resource profiling shows local inference consumes measurable CPU and memory on the host.",
        "prototype_or_mode": "Prototype 5 Mode D",
        "evidence_file": "results/prototype5/mode_d/mode_d_final_evidence_summary.json; results/prototype5/mode_d/manual_live_30_command_foundry_process_profile.csv",
        "metrics": "normalized_mean_cpu; memory_delta; mean_latency_ms",
        "evidence_status": "PROVEN",
        "claim_boundary": "Host-specific; GPU/NPU counters were not detected, so no hardware acceleration claim is made.",
        "dissertation_relevance": "Supports resource feasibility and deployment-cost discussion.",
    },
    {
        "claim_id": "C10",
        "claim": "The current benchmark is exploratory and bounded, not a full industrial safety certification.",
        "prototype_or_mode": "Prototype 5 final documentation",
        "evidence_file": "docs/benchmark_card.md; docs/claim_boundaries.md; docs/prototype5/benchmark_representativeness.md",
        "metrics": "benchmark_size; caveat; claim_boundary",
        "evidence_status": "LIMITED",
        "claim_boundary": "The benchmark supports bounded dissertation claims, not exhaustive industrial coverage.",
        "dissertation_relevance": "Defines validity limits and future work.",
    },
    {
        "claim_id": "C11",
        "claim": "Live Foundry output repeatability should be reported before treating request-level findings as stable across runs.",
        "prototype_or_mode": "Prototype 5 Mode E0.1",
        "evidence_file": "results/prototype5/mode_e0/repeatability_live_runs.csv; results/prototype5/mode_e0/repeatability_variance_summary.json; results/prototype5/mode_e0/repeatability_variance_summary.md",
        "metrics": "request_success_rate; parse_success_rate; json_valid_rate; mean_latency_ms",
        "evidence_status": "PROVEN",
        "claim_boundary": "Only request-level, JSON-level and latency repeatability are covered; full pipeline repeatability is not claimed by E0.1.",
        "dissertation_relevance": "Addresses live model-serving repeatability without overstating validation stability.",
    },
    {
        "claim_id": "C12",
        "claim": "Validation replay can assess whether minimal-prompt live outputs remain stable under deterministic schema, semantic, safety and execution-eligibility gates.",
        "prototype_or_mode": "Prototype 5 Mode E0.2",
        "evidence_file": "results/prototype5/mode_e0/pipeline_repeatability_records.jsonl; results/prototype5/mode_e0/pipeline_repeatability_summary.csv; results/prototype5/mode_e0/pipeline_repeatability_variance_summary.json; results/prototype5/mode_e0/pipeline_repeatability_variance_summary.md",
        "metrics": "schema_valid_rate; semantic_valid_rate; safety_valid_rate; execution_eligible_rate; model_false_accepts; pipeline_false_accepts",
        "evidence_status": "PARTIAL",
        "claim_boundary": "Offline replay over E0.1 minimal-prompt raw outputs; not full live action-envelope pipeline repeatability and not physical safety certification.",
        "dissertation_relevance": "Shows fail-closed pipeline compatibility for the E0.1 outputs while preserving benchmark boundaries.",
    },
    {
        "claim_id": "C13",
        "claim": "Full live pipeline repeatability under the original Prototype 3 action-envelope prompt is not yet executable from the Prototype 5 repo.",
        "prototype_or_mode": "Prototype 5 Mode E0.3",
        "evidence_file": "results/prototype5/mode_e0/full_pipeline_repeatability_live_runs.csv; results/prototype5/mode_e0/full_pipeline_repeatability_summary.json; results/prototype5/mode_e0/full_pipeline_repeatability_summary.md",
        "metrics": "schema_valid_rate; semantic_valid_rate; safety_valid_rate; execution_eligible_rate; model_false_accepts; pipeline_false_accepts",
        "evidence_status": "FUTURE_WORK",
        "claim_boundary": "No schema-valid versus execution-eligible repeatability claim is proven until the repo-local action-envelope live runner exists and is executed.",
        "dissertation_relevance": "Defines the exact integration gap before claiming full live pipeline stability.",
    },
    {
        "claim_id": "C14",
        "claim": "Repo-local full live pipeline repeatability was evaluated across three live runs using the Prototype 5 action-envelope prompt, fixed 30-command benchmark, Phi-3-mini Foundry Local model and deterministic validation policy.",
        "prototype_or_mode": "Prototype 5 Mode E0.4",
        "evidence_file": "configs/prototype5/action_envelope_prompt.txt; configs/prototype5/benchmark_v1.json; results/prototype5/mode_e0/full_pipeline_live_repeatability_runs.csv; results/prototype5/mode_e0/full_pipeline_live_repeatability_summary.json; results/prototype5/mode_e0/full_pipeline_live_repeatability_summary.md",
        "metrics": "schema_valid_rate; semantic_valid_rate; safety_valid_rate; execution_eligible_rate; model_false_accepts; pipeline_false_accepts; schema_valid_minus_execution_eligible_gap; latency",
        "evidence_status": "PROVEN",
        "claim_boundary": "Proven only for the tested Prototype 5 benchmark, action-envelope prompt, Phi-3-mini-4k-instruct-generic-cpu:3 model alias, local Foundry runtime and deterministic validation policy. It does not prove general model reliability, production robot safety, or repeatability across all models, prompts, machines or industrial tasks.",
        "dissertation_relevance": "Directly addresses supervisor feedback on whether the full live pipeline result is stable across repeated runs, while keeping the claim bounded to the tested setup.",
    },
]


def _split_paths(value: str) -> list[Path]:
    return [REPO_ROOT / item.strip() for item in value.split(";") if item.strip()]


def _all_paths_exist(value: str) -> bool:
    return all(path.exists() for path in _split_paths(value))


def _missing_paths(value: str) -> list[str]:
    return [
        str(path.relative_to(REPO_ROOT).as_posix())
        for path in _split_paths(value)
        if not path.exists()
    ]


def _write_traceability_csv() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for row in TRACEABILITY_ROWS:
        rows.append({**row, "file_exists": str(_all_paths_exist(row["evidence_file"])).lower()})
    with TRACEABILITY_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=TRACEABILITY_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _empty_repeatability_row(status: str, notes: str) -> dict[str, str]:
    return {
        "run_id": "e0_1_live_repeatability",
        "model_alias": "not_run",
        "benchmark_id": "benchmark_v1",
        "config_id": "live_foundry_repeatability",
        "status": status,
        "request_success_rate": "",
        "parse_success_rate": "",
        "json_valid_rate": "",
        "schema_valid_rate": "",
        "semantic_valid_rate": "",
        "safety_valid_rate": "",
        "execution_eligible_rate": "",
        "model_false_accepts": "",
        "pipeline_false_accepts": "",
        "mean_latency_ms": "",
        "std_latency_ms": "",
        "notes": notes,
    }


def _read_repeatability_rows(path: Path = REPEATABILITY_LIVE_RUNS_CSV) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _numeric_values(rows: list[dict[str, str]], metric: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        raw_value = str(row.get(metric, "")).strip()
        if raw_value in {"", "NOT_EVALUATED", "NOT_AVAILABLE"}:
            continue
        try:
            values.append(float(raw_value))
        except ValueError:
            continue
    return values


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _std(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return round(math.sqrt(variance), 4)


def _metric_stability(metric: str, values: list[float]) -> str:
    if len(values) < 3:
        return "NOT_EVALUATED"
    if metric == "mean_latency_ms":
        return "VARIABLE" if (_std(values) or 0.0) > 500.0 else "STABLE"
    return "STABLE" if max(values) == min(values) else "VARIABLE"


def _probe_foundry_local(timeout_seconds: float = 0.75) -> dict[str, Any]:
    base_url = os.environ.get("FOUNDRY_LOCAL_BASE_URL", DEFAULT_FOUNDRY_BASE_URL).rstrip("/")
    endpoint = f"{base_url}/v1/models"
    try:
        request = Request(endpoint, method="GET")
        with urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8-sig"))
        models = payload.get("data", [])
        model_ids = [
            str(item.get("id", ""))
            for item in models
            if isinstance(item, dict) and item.get("id")
        ]
        return {
            "attempted": True,
            "base_url": base_url,
            "models_endpoint": endpoint,
            "request_success": True,
            "model_count": len(model_ids),
            "phi_model_count": len([model_id for model_id in model_ids if "phi" in model_id.lower()]),
            "error": "",
        }
    except (OSError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {
            "attempted": True,
            "base_url": base_url,
            "models_endpoint": endpoint,
            "request_success": False,
            "model_count": 0,
            "phi_model_count": 0,
            "error": str(exc),
        }


def _write_repeatability_table(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=REPEATABILITY_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _normalise_live_repeatability_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    normalised: list[dict[str, str]] = []
    for row in rows:
        updated = {column: row.get(column, "") for column in REPEATABILITY_COLUMNS}
        if updated["status"] == "COMPLETE":
            updated["status"] = "COMPLETE_LIVE_OUTPUT_REPEATABILITY"
        if updated["status"] == "COMPLETE_LIVE_OUTPUT_REPEATABILITY":
            for metric in [
                "schema_valid_rate",
                "semantic_valid_rate",
                "safety_valid_rate",
                "execution_eligible_rate",
                "model_false_accepts",
                "pipeline_false_accepts",
            ]:
                if updated[metric] == "":
                    updated[metric] = "NOT_EVALUATED"
        normalised.append(updated)
    return normalised


def ensure_repeatability_outputs() -> dict[str, Any]:
    """Create E0.1 repeatability outputs without inventing live measurements."""

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    live_rows = _read_repeatability_rows()
    if not live_rows:
        probe = _probe_foundry_local()
        notes = (
            "Live repeated benchmark runs are not available in this repository state. "
            "Foundry Local repeatability was not executed by Mode E0 because it depends "
            "on a local service/model being available."
        )
        live_rows = [_empty_repeatability_row("NOT_RUN", notes)]
        _write_repeatability_table(REPEATABILITY_LIVE_RUNS_CSV, live_rows)
    else:
        probe = _probe_foundry_local()
        live_rows = _normalise_live_repeatability_rows(live_rows)
        _write_repeatability_table(REPEATABILITY_LIVE_RUNS_CSV, live_rows)

    summary_rows = list(live_rows)
    e0_3_row = _read_e0_3_repeatability_row()
    if e0_3_row:
        summary_rows.append(e0_3_row)
    summary_rows.extend(_read_e0_4_repeatability_rows())
    _write_repeatability_table(REPEATABILITY_CSV, summary_rows)

    completed_rows = [
        row
        for row in live_rows
        if row.get("status") in {"COMPLETE", "AVAILABLE", "COMPLETE_LIVE_OUTPUT_REPEATABILITY"}
    ]
    metric_summary: dict[str, dict[str, Any]] = {}
    for metric in REPEATABILITY_METRICS:
        values = _numeric_values(completed_rows, metric)
        metric_summary[metric] = {
            "values": values,
            "mean": _mean(values),
            "std": _std(values),
            "stable": _metric_stability(metric, values),
        }

    completed_run_count = len(completed_rows)
    if completed_run_count >= 3:
        status = "COMPLETE_LIVE_OUTPUT_REPEATABILITY"
    elif completed_run_count > 0:
        status = "PARTIAL"
    else:
        status = "NOT_RUN"

    schema_values = metric_summary["schema_valid_rate"]["values"]
    execution_values = metric_summary["execution_eligible_rate"]["values"]
    if len(schema_values) >= 3 and len(execution_values) >= 3:
        comparisons = [schema > execution for schema, execution in zip(schema_values, execution_values)]
        schema_gap_status = "STABLE" if all(comparisons) else "VARIABLE"
    else:
        schema_gap_status = "NOT_EVALUATED"

    pipeline_false_accept_values = metric_summary["pipeline_false_accepts"]["values"]
    if len(pipeline_false_accept_values) >= 3:
        pipeline_false_accept_status = (
            "STABLE_ZERO"
            if all(value == 0 for value in pipeline_false_accept_values)
            else "BOUNDED_NONZERO"
        )
    else:
        pipeline_false_accept_status = "NOT_EVALUATED"

    variance_summary = {
        "mode": "E0.1",
        "name": "Live Repeatability and Variance Evidence",
        "status": status,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "target_run_count": 3,
        "ideal_run_count": 5,
        "completed_run_count": completed_run_count,
        "live_runs_file": str(REPEATABILITY_LIVE_RUNS_CSV.relative_to(REPO_ROOT).as_posix()),
        "repeatability_summary_file": str(REPEATABILITY_CSV.relative_to(REPO_ROOT).as_posix()),
        "live_execution_probe": probe,
        "metric_variance": metric_summary,
        "central_findings": {
            "schema_valid_greater_than_execution_eligible": {
                "status": schema_gap_status,
                "claim": "The schema-valid versus execution-eligible gap is stable only if repeated live runs show schema_valid_rate > execution_eligible_rate in each run.",
            },
            "pipeline_false_accepts_bounded": {
                "status": pipeline_false_accept_status,
                "claim": "Pipeline-level false accepts are stable only if repeated live runs show zero or bounded counts under the same policy.",
            },
        },
        "evaluated_scope": [
            "Foundry Local request success",
            "parse success",
            "JSON validity",
            "latency variation",
        ],
        "not_evaluated_scope": [
            "full deterministic validation pipeline repeatability",
            "schema validity repeatability",
            "semantic validity repeatability",
            "safety validity repeatability",
            "execution eligibility repeatability",
            "model-level false accept repeatability",
            "pipeline-level false accept repeatability",
        ],
        "full_pipeline_live_repeatability": _read_full_pipeline_live_status(),
        "repo_local_full_pipeline_live_repeatability": _read_e0_4_full_pipeline_live_status(),
        "claim_boundary": (
            "E0.1 does not support full zero-trust pipeline repeatability or a general "
            "model-reliability claim. It supports only live Foundry output repeatability "
            "for request success, parse success, JSON validity and latency under the "
            "tested benchmark and configuration."
        ),
        "notes": [
            "No repeatability metrics are inferred from single-run evidence.",
            "Run rows with status NOT_RUN intentionally leave metric fields blank.",
            "Schema, semantic, safety, execution eligibility and false-accept repeatability remain NOT_EVALUATED in E0.1.",
            "Live Foundry Local repeated runs require the local service, model alias, fixed benchmark and validation pipeline to be available.",
            "Mode E0.4 is the repo-local full pipeline adapter and is reported separately from the older E0.3 not-run gate.",
        ],
    }
    REPEATABILITY_VARIANCE_JSON.write_text(json.dumps(variance_summary, indent=2), encoding="utf-8")
    REPEATABILITY_VARIANCE_MD.write_text(_build_repeatability_markdown(variance_summary), encoding="utf-8")
    return variance_summary


def _build_repeatability_markdown(summary: dict[str, Any]) -> str:
    metric_lines = [
        "| Metric | Values | Mean | Std | Stable? |",
        "|---|---:|---:|---:|---|",
    ]
    for metric, values in summary["metric_variance"].items():
        metric_lines.append(
            "| {metric} | {raw_values} | {mean} | {std} | {stable} |".format(
                metric=metric,
                raw_values=", ".join(str(value) for value in values["values"]) or "not available",
                mean=values["mean"] if values["mean"] is not None else "not available",
                std=values["std"] if values["std"] is not None else "not available",
                stable=values["stable"],
            )
        )

    return "\n".join(
        [
            "# Mode E0.1 Live Repeatability and Variance Evidence",
            "",
            f"- Status: {summary['status']}",
            f"- Completed live repeated runs: {summary['completed_run_count']}/{summary['target_run_count']}",
            f"- Ideal run count: {summary['ideal_run_count']}",
            f"- Live runs file: `{summary['live_runs_file']}`",
            f"- Summary file: `{summary['repeatability_summary_file']}`",
            f"- Foundry Local discovery probe: {'available' if summary['live_execution_probe']['request_success'] else 'unavailable'}",
            "",
            "## Scope",
            "",
            "This E0.1 repeatability check evaluates live Foundry Local request-level stability, JSON validity stability and latency variance across three repeated runs. It does not evaluate repeatability of the full deterministic validation pipeline, including schema validity, semantic validity, safety validity, execution eligibility, model-level false accepts or pipeline-level false accepts. Those metrics are handled separately by Mode E0.2 when raw live-output artefacts are available.",
            "",
            "## Central Finding Stability",
            "",
            (
                "- Schema-valid greater than execution-eligible: "
                f"{summary['central_findings']['schema_valid_greater_than_execution_eligible']['status']}"
            ),
            (
                "- Pipeline false accepts bounded: "
                f"{summary['central_findings']['pipeline_false_accepts_bounded']['status']}"
            ),
            "",
            "## Metric Variance",
            "",
            *metric_lines,
            "",
            "## E0.3 Full Live Pipeline Status",
            "",
            f"- Status: {summary['full_pipeline_live_repeatability']['status']}",
            f"- Claim boundary: {summary['full_pipeline_live_repeatability'].get('claim_boundary', 'not available')}",
            "",
            "## Claim Boundary",
            "",
            summary["claim_boundary"],
            "",
            "No repeatability metrics are inferred from single-run evidence. If live repeated runs are unavailable, this file records that limitation rather than fabricating stability values.",
            "",
        ]
    )


def _read_traceability_rows() -> list[dict[str, str]]:
    with TRACEABILITY_CSV.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def build_summary() -> dict[str, Any]:
    repeatability_variance = ensure_repeatability_outputs()
    _write_traceability_csv()

    traceability_rows = _read_traceability_rows()
    status_counts = Counter(row["evidence_status"].lower() for row in traceability_rows)
    evidence_missing = sorted(
        {
            missing
            for row in traceability_rows
            for missing in _missing_paths(row["evidence_file"])
        }
    )
    required_doc_missing = [
        str(path.relative_to(REPO_ROOT).as_posix())
        for path in REQUIRED_DOCUMENTS
        if not path.exists()
    ]
    result_files_for_check = [
        TRACEABILITY_CSV,
        REPEATABILITY_CSV,
        REPEATABILITY_LIVE_RUNS_CSV,
        REPEATABILITY_VARIANCE_JSON,
        REPEATABILITY_VARIANCE_MD,
        PIPELINE_REPEATABILITY_RECORDS_JSONL,
        PIPELINE_REPEATABILITY_SUMMARY_CSV,
        PIPELINE_REPEATABILITY_VARIANCE_JSON,
        PIPELINE_REPEATABILITY_VARIANCE_MD,
        FULL_PIPELINE_LIVE_CSV,
        FULL_PIPELINE_LIVE_JSON,
        FULL_PIPELINE_LIVE_MD,
        E0_4_FULL_PIPELINE_LIVE_CSV,
        E0_4_FULL_PIPELINE_LIVE_JSON,
        E0_4_FULL_PIPELINE_LIVE_MD,
    ]
    result_missing = [
        str(path.relative_to(REPO_ROOT).as_posix())
        for path in result_files_for_check
        if not path.exists()
    ]

    critical_missing = [*required_doc_missing, *result_missing]
    status = "COMPLETE"
    if critical_missing:
        status = "INCOMPLETE"
    elif evidence_missing:
        status = "COMPLETE_WITH_WARNINGS"

    summary = {
        "mode": "E0",
        "name": "Reproducibility and Evaluation Rigour Audit",
        "status": status,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "repository_root": str(REPO_ROOT),
        "required_documents": {
            "total": len(REQUIRED_DOCUMENTS),
            "present": len(REQUIRED_DOCUMENTS) - len(required_doc_missing),
            "missing": required_doc_missing,
        },
        "required_result_files": {
            "total": len(REQUIRED_RESULT_FILES),
            "present": len(REQUIRED_RESULT_FILES) - len(result_missing),
            "missing": result_missing,
        },
        "evidence_files_checked": {
            "total": len({path for row in traceability_rows for path in _split_paths(row["evidence_file"])}),
            "present": len({path for row in traceability_rows for path in _split_paths(row["evidence_file"]) if path.exists()}),
            "missing": evidence_missing,
        },
        "claim_traceability": {
            "total_claims": len(traceability_rows),
            "proven": status_counts.get("proven", 0),
            "supported": status_counts.get("supported", 0),
            "partial": status_counts.get("partial", 0),
            "future_work": status_counts.get("future_work", 0),
            "limited": status_counts.get("limited", 0),
        },
        "repeatability_variance": {
            "mode": repeatability_variance["mode"],
            "status": repeatability_variance["status"],
            "target_run_count": repeatability_variance["target_run_count"],
            "completed_run_count": repeatability_variance["completed_run_count"],
            "schema_valid_greater_than_execution_eligible": repeatability_variance["central_findings"]["schema_valid_greater_than_execution_eligible"]["status"],
            "pipeline_false_accepts_bounded": repeatability_variance["central_findings"]["pipeline_false_accepts_bounded"]["status"],
        },
        "pipeline_repeatability_replay": _read_pipeline_repeatability_status(),
        "full_pipeline_live_repeatability": _read_full_pipeline_live_status(),
        "repo_local_full_pipeline_live_repeatability": _read_e0_4_full_pipeline_live_status(),
        "notes": [
            "Mode E0 checks documentation and evidence traceability. It does not rerun live Foundry Local benchmarks by itself.",
            "Mode E0.1 records repeatability-run availability and variance summaries without inventing measurements.",
            "Mode E0.2 records offline deterministic pipeline replay over E0.1 raw outputs when those artefacts are present.",
            "Mode E0.3 remains not-run until a repo-local original Prototype 3 action-envelope live runner is available.",
            "Mode E0.4 adds that repo-local action-envelope adapter; its evidence is bounded to the recorded E0.4 summary status.",
        ],
    }
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def _read_pipeline_repeatability_status() -> dict[str, Any]:
    if not PIPELINE_REPEATABILITY_VARIANCE_JSON.exists():
        return {"mode": "E0.2", "status": "MISSING"}
    payload = json.loads(PIPELINE_REPEATABILITY_VARIANCE_JSON.read_text(encoding="utf-8"))
    return {
        "mode": payload.get("mode", "E0.2"),
        "status": payload.get("status", "UNKNOWN"),
        "runs_evaluated": payload.get("runs_evaluated", 0),
        "schema_valid_greater_than_execution_eligible": payload.get("central_findings", {}).get("schema_valid_greater_than_execution_eligible", "UNKNOWN"),
        "pipeline_false_accepts_bounded": payload.get("central_findings", {}).get("pipeline_false_accepts_bounded", "UNKNOWN"),
    }


def _read_full_pipeline_live_status() -> dict[str, Any]:
    if not FULL_PIPELINE_LIVE_JSON.exists():
        return {"mode": "E0.3", "status": "MISSING"}
    payload = json.loads(FULL_PIPELINE_LIVE_JSON.read_text(encoding="utf-8"))
    return {
        "mode": payload.get("mode", "E0.3"),
        "status": payload.get("status", "UNKNOWN"),
        "claim_boundary": payload.get("claim_boundary", ""),
        "reason": payload.get("reason", ""),
    }


def _read_e0_4_full_pipeline_live_status() -> dict[str, Any]:
    if not E0_4_FULL_PIPELINE_LIVE_JSON.exists():
        return {"mode": "E0.4", "status": "MISSING"}
    payload = json.loads(E0_4_FULL_PIPELINE_LIVE_JSON.read_text(encoding="utf-8"))
    return {
        "mode": payload.get("mode", "E0.4"),
        "status": payload.get("status", "UNKNOWN"),
        "runs_evaluated": payload.get("runs_evaluated", 0),
        "schema_valid_greater_than_execution_eligible": payload.get("central_findings", {}).get("schema_valid_greater_than_execution_eligible", "UNKNOWN"),
        "pipeline_false_accepts_bounded": payload.get("central_findings", {}).get("pipeline_false_accepts_bounded", "UNKNOWN"),
        "claim_boundary": payload.get("claim_boundary", ""),
        "reason": payload.get("reason", ""),
    }


def _read_e0_3_repeatability_row() -> dict[str, str] | None:
    if not FULL_PIPELINE_LIVE_CSV.exists():
        return None
    with FULL_PIPELINE_LIVE_CSV.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        return None
    row = {column: rows[0].get(column, "") for column in REPEATABILITY_COLUMNS}
    return row


def _read_e0_4_repeatability_rows() -> list[dict[str, str]]:
    if not E0_4_FULL_PIPELINE_LIVE_CSV.exists():
        return []
    with E0_4_FULL_PIPELINE_LIVE_CSV.open(newline="", encoding="utf-8") as handle:
        source_rows = list(csv.DictReader(handle))
    rows: list[dict[str, str]] = []
    for source in source_rows:
        rows.append(
            {
                "run_id": source.get("run_id", ""),
                "model_alias": source.get("model_alias", ""),
                "benchmark_id": source.get("benchmark_id", "benchmark_v1"),
                "config_id": source.get("config_id", "repo_local_action_envelope_temperature_0"),
                "status": source.get("status", ""),
                "request_success_rate": source.get("request_success_rate", ""),
                "parse_success_rate": source.get("parse_success_rate", ""),
                "json_valid_rate": source.get("json_valid_rate", ""),
                "schema_valid_rate": source.get("schema_valid_rate", ""),
                "semantic_valid_rate": source.get("semantic_valid_rate", ""),
                "safety_valid_rate": source.get("safety_valid_rate", ""),
                "execution_eligible_rate": source.get("execution_eligible_rate", ""),
                "model_false_accepts": source.get("model_false_accepts", ""),
                "pipeline_false_accepts": source.get("pipeline_false_accepts", ""),
                "mean_latency_ms": source.get("mean_latency_ms", ""),
                "std_latency_ms": source.get("std_latency_ms", ""),
                "notes": source.get("notes", ""),
            }
        )
    return rows


def main() -> int:
    summary = build_summary()
    print("Prototype 5 Mode E0 reproducibility check:", summary["status"])
    print(f"Documents: {summary['required_documents']['present']}/{summary['required_documents']['total']}")
    print(f"Traceability claims: {summary['claim_traceability']['total_claims']}")
    print(f"Evidence files missing: {len(summary['evidence_files_checked']['missing'])}")
    return 0 if summary["status"] in {"COMPLETE", "COMPLETE_WITH_WARNINGS"} else 1


if __name__ == "__main__":
    raise SystemExit(main())

