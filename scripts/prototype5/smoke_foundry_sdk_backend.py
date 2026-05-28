"""Bounded smoke runner for the Foundry SDK planner backend.

This script records adapter-level evidence only. It does not parse model
output, call validators, infer safety, infer semantic validity, or assign
execution eligibility.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.prototype5.foundry_sdk_backend import FoundrySDKBackend, ModelBackendResponse  # noqa: E402
from src.prototype5.foundry_sdk_client import FoundryLocalClient  # noqa: E402


BASE_URL_ENV = "FOUNDRY_LOCAL_BASE_URL"
MODEL_ENV = "FOUNDRY_LOCAL_MODEL"
OUTPUT_DIR = REPO_ROOT / "results" / "prototype5" / "mode_sdk"
SUMMARY_JSON = OUTPUT_DIR / "backend_smoke_summary.json"
SUMMARY_MD = OUTPUT_DIR / "backend_smoke_summary.md"
STATUS_COMPLETE = "COMPLETE_BACKEND_SMOKE"
SCOPE = "bounded_sdk_backend_smoke_only"

ARCHITECTURAL_BOUNDARY = {
    "parses_json": False,
    "validates_schema": False,
    "repairs_model_output": False,
    "infers_execution_eligibility": False,
    "calls_orchestrator": False,
    "runs_benchmark": False,
}

SMOKE_PROMPTS = [
    {
        "case_id": "smoke_001",
        "prompt_id": "phase1_m5_backend_smoke_prompt",
        "command": 'Return exactly this JSON object and nothing else: {"status":"ok","action":"noop"}',
    }
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def failure_response(
    *,
    backend: str,
    model_alias: str | None,
    prompt_id: str,
    error_type: str,
    error_message: str,
) -> ModelBackendResponse:
    return ModelBackendResponse(
        backend=backend,
        model_alias=model_alias,
        prompt_id=prompt_id,
        raw_text=None,
        success=False,
        latency_ms=None,
        error_type=error_type,
        error_message=error_message,
        timestamp_utc=utc_now(),
    )


def response_to_row(case_id: str, response: ModelBackendResponse) -> dict[str, Any]:
    row = asdict(response)
    row["case_id"] = case_id
    return {
        "case_id": row["case_id"],
        "success": row["success"],
        "backend": row["backend"],
        "model_alias": row["model_alias"],
        "prompt_id": row["prompt_id"],
        "latency_ms": row["latency_ms"],
        "raw_text": row["raw_text"],
        "error_type": row["error_type"],
        "error_message": row["error_message"],
        "timestamp_utc": row["timestamp_utc"],
    }


def run_smoke(
    *,
    backend: FoundrySDKBackend | None = None,
    base_url: str | None = None,
    model_alias: str | None = None,
    prompts: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    effective_base_url = base_url if base_url is not None else os.getenv(BASE_URL_ENV, "")
    effective_model_alias = model_alias if model_alias is not None else os.getenv(MODEL_ENV, "")
    smoke_prompts = prompts or SMOKE_PROMPTS

    if backend is None and effective_base_url and effective_model_alias:
        client = FoundryLocalClient(
            base_url=effective_base_url,
            model_alias=effective_model_alias,
        )
        backend = FoundrySDKBackend(client=client)

    rows: list[dict[str, Any]] = []
    for prompt in smoke_prompts:
        case_id = prompt["case_id"]
        prompt_id = prompt["prompt_id"]

        if not effective_base_url:
            response = failure_response(
                backend="foundry_local_openai_compatible",
                model_alias=effective_model_alias or None,
                prompt_id=prompt_id,
                error_type="missing_base_url_env",
                error_message=f"{BASE_URL_ENV} must be set explicitly for the backend smoke runner.",
            )
        elif not effective_model_alias:
            response = failure_response(
                backend="foundry_local_openai_compatible",
                model_alias=None,
                prompt_id=prompt_id,
                error_type="missing_model_env",
                error_message=f"{MODEL_ENV} must be set explicitly for the backend smoke runner.",
            )
        elif backend is None:
            response = failure_response(
                backend="foundry_local_openai_compatible",
                model_alias=effective_model_alias,
                prompt_id=prompt_id,
                error_type="backend_initialisation_failed",
                error_message="Backend was not available after configuration checks.",
            )
        else:
            response = backend.generate(
                prompt["command"],
                {
                    "prompt_id": prompt_id,
                    "system_prompt": "Return only the requested text. Do not explain.",
                    "temperature": 0,
                    "max_tokens": 64,
                },
            )

        rows.append(response_to_row(case_id, response))

    success_count = sum(1 for row in rows if row["success"])
    failure_count = len(rows) - success_count

    return {
        "status": STATUS_COMPLETE,
        "timestamp_utc": utc_now(),
        "scope": SCOPE,
        "strict_scope_note": (
            "Bounded SDK backend smoke only. This is not benchmark evidence and does not perform "
            "schema, semantic, safety, or execution validation."
        ),
        "base_url": effective_base_url,
        "model_alias": effective_model_alias or None,
        "prompt_count": len(rows),
        "success_count": success_count,
        "failure_count": failure_count,
        "results": rows,
        "architectural_boundary": ARCHITECTURAL_BOUNDARY,
    }


def write_json_summary(summary: dict[str, Any], path: Path = SUMMARY_JSON) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return path


def write_markdown_summary(summary: dict[str, Any], path: Path = SUMMARY_MD) -> Path:
    boundary = summary["architectural_boundary"]
    lines = [
        "# Foundry SDK Backend Smoke Summary",
        "",
        f"Status: {summary['status']}",
        "",
        "## Scope",
        "",
        (
            "This is a bounded adapter smoke test only. It does not replace Prototype 3/4/5 "
            "evidence and does not perform schema, semantic, safety, or execution validation."
        ),
        "",
        "## Configuration",
        "",
        f"- Base URL: `{summary['base_url']}`",
        f"- Model alias: `{summary['model_alias']}`",
        f"- Prompt count: `{summary['prompt_count']}`",
        f"- Success count: `{summary['success_count']}`",
        f"- Failure count: `{summary['failure_count']}`",
        "",
        "## Architectural Boundary",
        "",
        f"- Parses JSON: `{str(boundary['parses_json']).lower()}`",
        f"- Validates schema: `{str(boundary['validates_schema']).lower()}`",
        f"- Repairs model output: `{str(boundary['repairs_model_output']).lower()}`",
        f"- Infers execution eligibility: `{str(boundary['infers_execution_eligibility']).lower()}`",
        f"- Calls orchestrator: `{str(boundary['calls_orchestrator']).lower()}`",
        f"- Runs benchmark: `{str(boundary['runs_benchmark']).lower()}`",
        "",
        "## Result Rows",
        "",
        "| Case ID | Success | Backend | Model alias | Latency ms | Error type |",
        "|---|---:|---|---|---:|---|",
    ]
    for row in summary["results"]:
        lines.append(
            "| {case_id} | {success} | {backend} | {model_alias} | {latency_ms} | {error_type} |".format(
                case_id=row["case_id"],
                success=str(row["success"]).lower(),
                backend=row["backend"],
                model_alias=row["model_alias"],
                latency_ms=row["latency_ms"],
                error_type=row["error_type"],
            )
        )
    lines.extend(
        [
            "",
            "## Raw Text",
            "",
        ]
    )
    for row in summary["results"]:
        lines.extend(
            [
                f"### {row['case_id']}",
                "",
                "````text",
                row["raw_text"] or "<NO RAW TEXT>",
                "````",
                "",
            ]
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> int:
    summary = run_smoke()
    json_path = write_json_summary(summary)
    md_path = write_markdown_summary(summary)
    print(f"Foundry SDK backend smoke: {summary['status']}")
    print(f"Prompt count: {summary['prompt_count']}")
    print(f"Success count: {summary['success_count']}")
    print(f"Failure count: {summary['failure_count']}")
    print(f"Wrote: {json_path}")
    print(f"Wrote: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
