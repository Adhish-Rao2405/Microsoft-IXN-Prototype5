"""Foundry Local Phi-family recovery runner for Prototype 5."""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from .benchmark_cases import load_benchmark_cases
from .evidence_paths import DOCS_DIR, PHI_RECOVERY_DIR
from .foundry_discovery import discover_foundry_models, select_phi_model
from .phi_recovery_metrics import phi_summary_table, summarise_phi_results
from .report_exports import write_csv, write_json, write_markdown


def _extract_response_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices", [])
    if not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message", {})
    if isinstance(message, dict):
        content = message.get("content")
        if content not in (None, ""):
            return str(content)
    delta = first.get("delta", {})
    if isinstance(delta, dict):
        content = delta.get("content")
        if content not in (None, ""):
            return str(content)
    return str(first.get("text", ""))


def strip_json_fences(text: str) -> str:
    stripped = text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()
    return stripped


def _parse_json_response(text: str) -> tuple[bool, bool, str]:
    try:
        parsed = json.loads(strip_json_fences(text))
    except json.JSONDecodeError:
        return False, False, ""
    return True, True, json.dumps(parsed, sort_keys=True)


def _chat_payload(command_text: str, model_id: str, max_tokens: int = 128) -> dict[str, Any]:
    return {
        "model": model_id,
        "messages": [
            {
                "role": "system",
                "content": "Return only valid JSON. Do not explain.",
            },
            {
                "role": "user",
                "content": (
                    "Convert this robot command into a minimal JSON action object:\n"
                    f"\"{command_text}\"\n"
                    "Return only JSON."
                ),
            },
        ],
        "temperature": 0,
        "max_tokens": max_tokens,
    }


def call_foundry_chat(
    base_url: str,
    model_id: str,
    command_text: str,
    timeout_seconds: float = 180.0,
    max_tokens: int = 128,
) -> dict[str, Any]:
    endpoint = f"{base_url.rstrip('/')}/v1/chat/completions"
    payload_bytes = json.dumps(_chat_payload(command_text, model_id, max_tokens)).encode("utf-8")
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
    response_text = _extract_response_text(raw_payload)
    parse_success, json_valid, parsed_json = _parse_json_response(response_text)
    return {
        "raw_response": response_text,
        "raw_payload": raw_payload,
        "latency_ms": latency_ms,
        "request_success": True,
        "parse_success": parse_success,
        "json_valid": json_valid,
        "parsed_json": parsed_json,
        "error": "",
    }


def _write_jsonl(rows: list[dict[str, Any]], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
    return path


def _append_jsonl(row: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="") as handle:
        handle.write(json.dumps(row) + "\n")


def run_phi_recovery(
    output_dir: Path = PHI_RECOVERY_DIR,
    base_url: str | None = None,
    requested_model: str | None = None,
    timeout_seconds: float | None = None,
    max_tokens: int | None = None,
    limit_commands: int | None = None,
) -> dict[str, Any]:
    if timeout_seconds is None:
        timeout_seconds = float(os.environ.get("FOUNDRY_LOCAL_TIMEOUT_SECONDS", "180"))
    if max_tokens is None:
        max_tokens = int(os.environ.get("FOUNDRY_LOCAL_MAX_TOKENS", "128"))
    if limit_commands is None:
        env_limit = os.environ.get("FOUNDRY_LOCAL_LIMIT_COMMANDS")
        limit_commands = int(env_limit) if env_limit else None
    output_dir.mkdir(parents=True, exist_ok=True)
    discovery = discover_foundry_models(base_url=base_url)
    selected_model = select_phi_model(discovery, requested_model)
    benchmark = load_benchmark_cases()

    inventory_path = write_json(discovery, output_dir / "foundry_model_inventory.json")
    results_path = output_dir / "phi_recovery_results.jsonl"
    temp_results_path = output_dir / "phi_recovery_results.tmp.jsonl"
    summary_path = output_dir / "phi_recovery_summary.csv"
    manifest_path = output_dir / "phi_recovery_manifest.json"
    doc_path = DOCS_DIR / "prototype5_phi_evidence_summary.md"

    failure_reason = ""
    rows: list[dict[str, Any]] = []
    if benchmark["status"] != "PRESENT":
        failure_reason = benchmark["status"]
    elif not selected_model:
        failure_reason = "PHI_MODEL_MISSING"
    elif not discovery.get("request_success"):
        failure_reason = "FOUNDRY_DISCOVERY_FAILED"
    else:
        cases = benchmark["cases"][:limit_commands] if limit_commands else benchmark["cases"]
        temp_results_path.write_text("", encoding="utf-8")
        for case in cases:
            result = {
                "command_id": case["command_id"],
                "command_text": case["command_text"],
                "model_id": selected_model,
                "raw_response": "",
                "latency_ms": "",
                "request_success": False,
                "parse_success": False,
                "json_valid": False,
                "error": "",
                "semantic_validity": "NOT_EVALUATED",
            }
            try:
                result.update(
                    call_foundry_chat(
                        discovery["base_url"],
                        selected_model,
                        case["command_text"],
                        timeout_seconds=timeout_seconds,
                        max_tokens=max_tokens,
                    )
                )
            except (OSError, URLError, TimeoutError, json.JSONDecodeError) as exc:
                result["error"] = str(exc)
            rows.append(result)
            _append_jsonl(result, temp_results_path)

    new_successes = [row for row in rows if row.get("request_success") is True]
    if rows and (new_successes or not results_path.exists()):
        temp_results_path.replace(results_path)
    elif temp_results_path.exists():
        temp_results_path.unlink()

    if (not rows or (rows and not new_successes and results_path.exists())) and results_path.exists():
        from .phi_recovery_metrics import load_phi_results

        rows = load_phi_results(results_path)
        failure_reason = ""
    elif not results_path.exists():
        _write_jsonl(rows, results_path)
    summary = summarise_phi_results(
        rows,
        expected_commands=len(benchmark.get("cases", [])) or 30,
        failure_reason=failure_reason,
        model_id=selected_model or os.environ.get("FOUNDRY_LOCAL_MODEL", ""),
    )
    write_csv(phi_summary_table(summary), summary_path)
    manifest = {
        "phi_status": summary["evidence_status"],
        "selected_model": selected_model,
        "benchmark_status": benchmark["status"],
        "benchmark_path": benchmark["path"],
        "foundry_discovery_success": discovery.get("request_success", False),
        "foundry_base_url": discovery.get("base_url", ""),
        "base_url": discovery.get("base_url", ""),
        "timeout_seconds": timeout_seconds,
        "max_tokens": max_tokens,
        "limit_commands": limit_commands,
        "successful_requests": summary["successful_requests"],
        "failed_requests": summary["failed_requests"],
        "evidence_status": summary["evidence_status"],
        "phi_model_ids": discovery.get("phi_model_ids", []),
        "outputs": {
            "foundry_model_inventory": str(inventory_path),
            "phi_recovery_results": str(results_path),
            "phi_recovery_summary": str(summary_path),
        },
        "summary": summary,
        "safe_scope": (
            "Phi-family evidence is based only on real Foundry Local chat completion "
            "responses recorded in phi_recovery_results.jsonl. Semantic validity is "
            "not evaluated by this recovery layer."
        ),
    }
    write_json(manifest, manifest_path)
    write_markdown(build_phi_evidence_doc(manifest), doc_path)
    return {"manifest": manifest, "summary": summary, "results": rows}


def build_phi_evidence_doc(manifest: dict[str, Any]) -> str:
    summary = manifest.get("summary", {})
    return "\n".join(
        [
            "# Prototype 5 Phi Evidence Summary",
            "",
            "Phi-family evidence is counted only when real Foundry Local Phi responses are recorded. Semantic validity remains NOT_EVALUATED.",
            "",
            f"- Phi evidence status: {manifest.get('phi_status', 'MISSING')}",
            f"- Selected model: {manifest.get('selected_model') or ''}",
            f"- Base URL: {manifest.get('base_url') or manifest.get('foundry_base_url') or ''}",
            f"- Timeout seconds: {manifest.get('timeout_seconds', '')}",
            f"- Max tokens: {manifest.get('max_tokens', '')}",
            f"- Limit commands: {manifest.get('limit_commands', '')}",
            f"- Benchmark status: {manifest.get('benchmark_status', '')}",
            f"- Successful requests: {summary.get('successful_requests', 0)}",
            f"- Failed requests: {summary.get('failed_requests', 0)}",
            f"- Parse success rate: {summary.get('parse_success_rate', 0.0)}",
            f"- JSON valid rate: {summary.get('json_valid_rate', 0.0)}",
            "",
            "## Outputs",
            "",
            f"- {manifest.get('outputs', {}).get('foundry_model_inventory', '')}",
            f"- {manifest.get('outputs', {}).get('phi_recovery_results', '')}",
            f"- {manifest.get('outputs', {}).get('phi_recovery_summary', '')}",
            "",
        ]
    )
