"""Cloud baseline availability detection for Prototype 5 Mode C."""

from __future__ import annotations

import os
from typing import Any


READY = "READY"
NOT_RUN_API_KEY_MISSING = "NOT_RUN_API_KEY_MISSING"
NOT_RUN_CLIENT_UNAVAILABLE = "NOT_RUN_CLIENT_UNAVAILABLE"
NOT_RUN_CONFIG_MISSING = "NOT_RUN_CONFIG_MISSING"
ERROR = "ERROR"


def get_cloud_status(env: dict[str, str] | None = None) -> dict[str, Any]:
    """Return structured cloud availability without exposing secrets."""

    source = os.environ if env is None else env
    provider = source.get("CLOUD_PROVIDER", "openai")
    if provider != "openai":
        return {
            "cloud_available": False,
            "cloud_baseline_status": NOT_RUN_CONFIG_MISSING,
            "provider": provider,
            "reason": "Only the OpenAI-compatible cloud provider is configured for Mode C.",
        }
    if not source.get("OPENAI_API_KEY"):
        return {
            "cloud_available": False,
            "cloud_baseline_status": NOT_RUN_API_KEY_MISSING,
            "provider": provider,
            "reason": "OPENAI_API_KEY is missing.",
        }
    return {
        "cloud_available": True,
        "cloud_baseline_status": READY,
        "provider": provider,
        "reason": "OPENAI_API_KEY is present in the local environment.",
    }
