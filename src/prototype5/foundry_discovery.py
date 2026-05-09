"""Foundry Local model discovery for Prototype 5 Phi recovery."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen


DEFAULT_FOUNDRY_BASE_URL = "http://127.0.0.1:54701"
FOUNDRY_ENV_BASE_URL = "FOUNDRY_LOCAL_BASE_URL"
FOUNDRY_ENV_MODEL = "FOUNDRY_LOCAL_MODEL"


def _normalise_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def _extract_model_ids(payload: dict[str, Any]) -> list[str]:
    data = payload.get("data", [])
    ids: list[str] = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and item.get("id"):
                ids.append(str(item["id"]))
            elif isinstance(item, str):
                ids.append(item)
    return ids


def is_phi_model(model_id: str | None) -> bool:
    return "phi" in str(model_id or "").lower()


def discover_foundry_models(
    base_url: str | None = None,
    timeout_seconds: float = 5.0,
) -> dict[str, Any]:
    """Discover Foundry Local models without crashing when the service is absent."""

    requested_base = base_url or os.environ.get(FOUNDRY_ENV_BASE_URL) or DEFAULT_FOUNDRY_BASE_URL
    candidate_urls = [_normalise_base_url(requested_base)]
    fallback_url = _normalise_base_url(DEFAULT_FOUNDRY_BASE_URL)
    if fallback_url not in candidate_urls:
        candidate_urls.append(fallback_url)

    attempts: list[dict[str, Any]] = []
    for candidate in candidate_urls:
        endpoint = f"{candidate}/v1/models"
        try:
            request = Request(endpoint, method="GET")
            with urlopen(request, timeout=timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8-sig"))
            model_ids = _extract_model_ids(payload)
            return {
                "base_url": candidate,
                "models_endpoint": endpoint,
                "request_success": True,
                "model_ids": model_ids,
                "phi_model_ids": [model_id for model_id in model_ids if is_phi_model(model_id)],
                "raw_response": payload,
                "attempts": attempts,
                "error": "",
            }
        except (OSError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            attempts.append({"base_url": candidate, "endpoint": endpoint, "error": str(exc)})

    return {
        "base_url": candidate_urls[0],
        "models_endpoint": f"{candidate_urls[0]}/v1/models",
        "request_success": False,
        "model_ids": [],
        "phi_model_ids": [],
        "raw_response": None,
        "attempts": attempts,
        "error": "; ".join(item["error"] for item in attempts),
    }


def select_phi_model(discovery: dict[str, Any], requested_model: str | None = None) -> str | None:
    requested = requested_model or os.environ.get(FOUNDRY_ENV_MODEL)
    if is_phi_model(requested):
        return str(requested)
    phi_models = discovery.get("phi_model_ids", [])
    return str(phi_models[0]) if phi_models else None
