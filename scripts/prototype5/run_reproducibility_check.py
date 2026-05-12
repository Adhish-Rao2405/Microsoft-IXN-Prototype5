"""Mode E0 reproducibility and evaluation-rigour audit.

This script checks that the Mode E0 documentation exists, writes the
claim-to-evidence traceability CSV, writes an honest repeatability placeholder,
and produces a JSON summary. It does not run Foundry Local, cloud APIs, or any
live benchmark.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = REPO_ROOT / "docs" / "prototype5"
RESULTS_DIR = REPO_ROOT / "results" / "prototype5" / "mode_e0"

REQUIRED_DOCUMENTS = [
    DOCS_DIR / "reproducibility_guide.md",
    DOCS_DIR / "evaluation_design_justification.md",
    DOCS_DIR / "benchmark_representativeness.md",
    DOCS_DIR / "repeatability_and_variance_plan.md",
    DOCS_DIR / "claim_to_evidence_traceability.md",
]

TRACEABILITY_CSV = RESULTS_DIR / "claim_to_evidence_traceability.csv"
REPEATABILITY_CSV = RESULTS_DIR / "repeatability_summary.csv"
SUMMARY_JSON = RESULTS_DIR / "reproducibility_check_summary.json"
REQUIRED_RESULT_FILES = [SUMMARY_JSON, TRACEABILITY_CSV, REPEATABILITY_CSV]

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


def _write_repeatability_csv() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    row = {
        "run_id": "repeatability_protocol",
        "model_alias": "not_run",
        "benchmark_id": "benchmark_v1",
        "config_id": "planned",
        "status": "PLANNED",
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
        "notes": "Protocol defined; live repeated runs not yet executed.",
    }
    with REPEATABILITY_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=REPEATABILITY_COLUMNS)
        writer.writeheader()
        writer.writerow(row)


def _read_traceability_rows() -> list[dict[str, str]]:
    with TRACEABILITY_CSV.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def build_summary() -> dict[str, Any]:
    _write_traceability_csv()
    _write_repeatability_csv()

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
    result_files_for_check = [TRACEABILITY_CSV, REPEATABILITY_CSV]
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
        "notes": [
            "Mode E0 checks documentation and evidence traceability. It does not rerun live Foundry Local benchmarks by itself.",
            "Repeatability is defined as a protocol until live repeated runs are intentionally executed.",
        ],
    }
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> int:
    summary = build_summary()
    print("Prototype 5 Mode E0 reproducibility check:", summary["status"])
    print(f"Documents: {summary['required_documents']['present']}/{summary['required_documents']['total']}")
    print(f"Traceability claims: {summary['claim_traceability']['total_claims']}")
    print(f"Evidence files missing: {len(summary['evidence_files_checked']['missing'])}")
    return 0 if summary["status"] in {"COMPLETE", "COMPLETE_WITH_WARNINGS"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
