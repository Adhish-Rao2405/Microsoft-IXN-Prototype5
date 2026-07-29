"""Mode E0.3 full live pipeline repeatability gate.

This script intentionally does not improvise a new runner. It checks whether
Prototype 5 contains a repo-local callable implementation of the original
Prototype 3 action-envelope live benchmark path. If that integration point is
missing, it writes an explicit E0.3_NOT_RUN report with the exact interface
needed to make full live pipeline repeatability executable.
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODE_E0_DIR = REPO_ROOT / "results" / "prototype5" / "mode_e0"

LIVE_RUNS_CSV = MODE_E0_DIR / "full_pipeline_repeatability_live_runs.csv"
SUMMARY_JSON = MODE_E0_DIR / "full_pipeline_repeatability_summary.json"
SUMMARY_MD = MODE_E0_DIR / "full_pipeline_repeatability_summary.md"

CSV_COLUMNS = [
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

REQUIRED_REPO_LOCAL_INTERFACES = [
    "src/prototype5/full_pipeline_live_runner.py",
    "src/prototype5/prototype3_action_envelope_runner.py",
    "configs/prototype5/prototype3_action_envelope_prompt.md",
]

EXTERNAL_PROTOTYPE3_HINTS = [
    Path(r"C:\Users\reach\Microsoft-IXN-Prototype3\prototype3\src\eval\run_benchmark.py"),
    Path(r"C:\Users\reach\Microsoft-IXN-Prototype3\prototype3\src\brain\foundry_planner.py"),
    Path(r"C:\Users\reach\Microsoft-IXN-Prototype3\prototype3\datasets\benchmark_v1.json"),
]


def _repo_local_interfaces() -> dict[str, bool]:
    return {path: (REPO_ROOT / path).exists() for path in REQUIRED_REPO_LOCAL_INTERFACES}


def _external_hints() -> dict[str, bool]:
    return {str(path): path.exists() for path in EXTERNAL_PROTOTYPE3_HINTS}


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT).as_posix())
    except ValueError:
        return str(path)


def build_not_run_summary(output_dir: Path = MODE_E0_DIR) -> dict[str, object]:
    repo_local = _repo_local_interfaces()
    external = _external_hints()
    missing = [path for path, present in repo_local.items() if not present]
    return {
        "mode": "E0.3",
        "name": "Full Live Pipeline Repeatability Under Prototype 3 Prompt",
        "status": "E0_3_NOT_RUN",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "reason": (
            "Prototype 5 does not currently contain a repo-local callable live runner "
            "that combines the original Prototype 3 action-envelope prompt, fixed "
            "30-command benchmark and deterministic validation pipeline."
        ),
        "repo_local_interfaces_checked": repo_local,
        "repo_local_missing": missing,
        "external_prototype3_hints": external,
        "live_runs_csv": _display_path(output_dir / LIVE_RUNS_CSV.name),
        "required_command_interface": (
            "python scripts/prototype5/run_full_pipeline_repeatability_live.py --live "
            "--runs 3 --base-url <FOUNDRY_LOCAL_BASE_URL> --model <MODEL_ALIAS> "
            "--benchmark <repo-local benchmark_v1.json> --prompt <repo-local Prototype 3 action-envelope prompt>"
        ),
        "required_runner_contract": [
            "Use the original Prototype 3 action-envelope prompt/config.",
            "Run the same fixed 30-command benchmark three times.",
            "Call Foundry Local with temperature 0 and a fixed model alias/config.",
            "For each response, parse JSON, validate schema, score semantic validity, apply uncertainty handling, apply safety validation and decide execution eligibility.",
            "Write per-run metrics for schema_valid_rate, semantic_valid_rate, safety_valid_rate, execution_eligible_rate, model_false_accepts, pipeline_false_accepts and latency.",
        ],
        "claim_boundary": (
            "Schema-valid versus execution-eligible repeatability is not proven by E0.3 "
            "because the full action-envelope live runner is not available inside "
            "Prototype 5 yet."
        ),
    }


def write_outputs(
    summary: dict[str, object],
    output_dir: Path = MODE_E0_DIR,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    live_runs_csv = output_dir / LIVE_RUNS_CSV.name
    summary_json = output_dir / SUMMARY_JSON.name
    summary_md = output_dir / SUMMARY_MD.name
    row = {
        "run_id": "e0_3_full_live_pipeline",
        "model_alias": "not_run",
        "benchmark_id": "benchmark_v1",
        "config_id": "prototype3_action_envelope_prompt",
        "status": "E0_3_NOT_RUN",
        "request_success_rate": "NOT_EVALUATED",
        "parse_success_rate": "NOT_EVALUATED",
        "json_valid_rate": "NOT_EVALUATED",
        "schema_valid_rate": "NOT_EVALUATED",
        "semantic_valid_rate": "NOT_EVALUATED",
        "safety_valid_rate": "NOT_EVALUATED",
        "execution_eligible_rate": "NOT_EVALUATED",
        "model_false_accepts": "NOT_EVALUATED",
        "pipeline_false_accepts": "NOT_EVALUATED",
        "mean_latency_ms": "NOT_EVALUATED",
        "std_latency_ms": "NOT_EVALUATED",
        "notes": str(summary["reason"]),
    }
    with live_runs_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerow(row)

    summary_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    summary_md.write_text(build_markdown(summary), encoding="utf-8")


def build_markdown(summary: dict[str, object]) -> str:
    missing = summary.get("repo_local_missing", [])
    missing_lines = "\n".join(f"- `{path}`" for path in missing) or "- None"
    external = summary.get("external_prototype3_hints", {})
    external_lines = "\n".join(f"- `{path}`: {present}" for path, present in dict(external).items())
    contract_lines = "\n".join(f"- {item}" for item in summary["required_runner_contract"])
    return "\n".join(
        [
            "# Mode E0.3 Full Live Pipeline Repeatability Under Prototype 3 Prompt",
            "",
            f"- Status: {summary['status']}",
            f"- Reason: {summary['reason']}",
            "",
            "## Missing Repo-Local Integration Points",
            "",
            missing_lines,
            "",
            "## External Prototype 3 Hints Detected",
            "",
            external_lines,
            "",
            "## Required Command Interface",
            "",
            f"`{summary['required_command_interface']}`",
            "",
            "## Required Runner Contract",
            "",
            contract_lines,
            "",
            "## Claim Boundary",
            "",
            str(summary["claim_boundary"]),
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the Mode E0.3 not-run gate.")
    parser.add_argument("--output-dir", type=Path, default=MODE_E0_DIR)
    args = parser.parse_args()

    summary = build_not_run_summary(args.output_dir)
    write_outputs(summary, args.output_dir)
    print("Prototype 5 Mode E0.3 full live pipeline repeatability:", summary["status"])
    print(summary["reason"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
