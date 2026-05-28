"""
Planner backend adapter for the Foundry Local SDK/API client.

Scope:
- Translate Prototype 5 planner requests into FoundryLocalClient calls.
- Translate FoundryClientResponse into the internal ModelBackendResponse contract.
- Preserve raw model text exactly as returned by the SDK client.
- Do not parse, validate, repair, or assign execution eligibility.

Design rule:
This module is a transport adapter. It is not a decision layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .foundry_sdk_client import FoundryClientResponse, FoundryLocalClient


DEFAULT_PROMPT_ID = "prototype5_sdk_backend_default"


@dataclass(frozen=True)
class ModelBackendResponse:
    backend: str
    model_alias: str | None
    prompt_id: str
    raw_text: str | None
    success: bool
    latency_ms: float | None
    error_type: str | None
    error_message: str | None
    timestamp_utc: str


class PlannerBackend(Protocol):
    def generate(self, command: str, context: dict[str, Any] | None = None) -> ModelBackendResponse:
        ...


class FoundrySDKBackend:
    """Adapter from Prototype 5 planner calls to FoundryLocalClient."""

    def __init__(
        self,
        client: FoundryLocalClient | None = None,
        default_system_prompt: str | None = None,
        default_prompt_id: str = DEFAULT_PROMPT_ID,
        default_temperature: float = 0.0,
        default_max_tokens: int = 256,
    ) -> None:
        self.client = client or FoundryLocalClient()
        self.default_system_prompt = default_system_prompt
        self.default_prompt_id = default_prompt_id
        self.default_temperature = default_temperature
        self.default_max_tokens = default_max_tokens

    def generate(self, command: str, context: dict[str, Any] | None = None) -> ModelBackendResponse:
        """Return raw model output and metadata without downstream validation."""

        effective_context = context or {}
        response = self.client.chat_completion(
            user_prompt=command,
            system_prompt=self._context_str(effective_context, "system_prompt", self.default_system_prompt),
            temperature=self._context_float(effective_context, "temperature", self.default_temperature),
            max_tokens=self._context_int(effective_context, "max_tokens", self.default_max_tokens),
        )
        return self.from_client_response(
            response,
            prompt_id=self._context_str(effective_context, "prompt_id", self.default_prompt_id)
            or self.default_prompt_id,
        )

    @staticmethod
    def from_client_response(response: FoundryClientResponse, prompt_id: str) -> ModelBackendResponse:
        return ModelBackendResponse(
            backend=response.backend,
            model_alias=response.model_alias,
            prompt_id=prompt_id,
            raw_text=response.raw_text,
            success=response.success,
            latency_ms=response.latency_ms,
            error_type=response.error_type,
            error_message=response.error_message,
            timestamp_utc=response.timestamp_utc,
        )

    @staticmethod
    def _context_str(context: dict[str, Any], key: str, default: str | None) -> str | None:
        value = context.get(key, default)
        if value is None:
            return None
        return str(value)

    @staticmethod
    def _context_float(context: dict[str, Any], key: str, default: float) -> float:
        value = context.get(key, default)
        return float(value)

    @staticmethod
    def _context_int(context: dict[str, Any], key: str, default: int) -> int:
        value = context.get(key, default)
        return int(value)
