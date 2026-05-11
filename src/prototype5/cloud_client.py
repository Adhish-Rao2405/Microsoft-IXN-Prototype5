"""Cloud client abstraction for Prototype 5 Mode C."""

from __future__ import annotations

import json
import os
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .cloud_status import get_cloud_status


def _payload(command_text: str, model: str) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": "Return only valid JSON. Do not explain."},
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
        "max_tokens": int(os.environ.get("MODE_C_CLOUD_MAX_TOKENS", os.environ.get("OPENAI_MAX_TOKENS", "160"))),
    }


def _extract_content(payload: dict[str, Any]) -> str:
    choices = payload.get("choices", [])
    if not choices or not isinstance(choices[0], dict):
        return ""
    message = choices[0].get("message", {})
    if isinstance(message, dict):
        return str(message.get("content", ""))
    return ""


def run_cloud_completion(command_text: str, status: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run one cloud completion when available; otherwise return a safe failure row."""

    cloud_status = status or get_cloud_status()
    model = os.environ.get("MODE_C_CLOUD_MODEL", os.environ.get("OPENAI_MODEL", "gpt-4o-mini"))
    provider = cloud_status.get("provider", "openai")
    if not cloud_status.get("cloud_available"):
        return {
            "request_success": False,
            "raw_response": "",
            "latency_ms": "",
            "error": cloud_status.get("cloud_baseline_status") or cloud_status.get("reason", ""),
            "error_type": cloud_status.get("cloud_baseline_status", ""),
            "retry_after_seconds": "",
            "provider": provider,
            "model": model,
        }

    api_key = os.environ.get("OPENAI_API_KEY", "")
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    timeout_seconds = float(os.environ.get("OPENAI_TIMEOUT_SECONDS", "180"))
    request = Request(
        f"{base_url}/chat/completions",
        data=json.dumps(_payload(command_text, model)).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    start = time.perf_counter()
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            raw_payload = json.loads(response.read().decode("utf-8-sig"))
        return {
            "request_success": True,
            "raw_response": _extract_content(raw_payload),
            "latency_ms": round((time.perf_counter() - start) * 1000, 2),
            "error": "",
            "error_type": "",
            "retry_after_seconds": "",
            "provider": provider,
            "model": model,
        }
    except HTTPError as exc:
        retry_after = exc.headers.get("Retry-After", "") if exc.headers else ""
        error_type = "RATE_LIMITED_OR_QUOTA_EXCEEDED" if exc.code == 429 else "ERROR"
        return {
            "request_success": False,
            "raw_response": "",
            "latency_ms": "",
            "error": str(exc),
            "error_type": error_type,
            "retry_after_seconds": retry_after,
            "provider": provider,
            "model": model,
        }
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        return {
            "request_success": False,
            "raw_response": "",
            "latency_ms": "",
            "error": str(exc),
            "error_type": "ERROR",
            "retry_after_seconds": "",
            "provider": provider,
            "model": model,
        }
