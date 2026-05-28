"""
Foundry Local SDK/API client wrapper for Prototype 5.

Scope:
- OpenAI-compatible Foundry Local API access.
- Non-streaming chat completions only.
- Fail-closed structured response object.
- No deterministic validator integration yet.
- No orchestrator integration yet.

Design rule:
Model outputs are untrusted proposals. This client only retrieves raw model text.
Execution eligibility remains controlled by downstream deterministic validators.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
import time
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request


DEFAULT_BASE_URL_ENV = "FOUNDRY_LOCAL_BASE_URL"
DEFAULT_MODEL_ENV = "FOUNDRY_LOCAL_MODEL"
DEFAULT_TIMEOUT_ENV = "FOUNDRY_LOCAL_TIMEOUT_SECONDS"

DEFAULT_MODEL_PREFERENCE_ORDER: tuple[str, ...] = (
    "qwen2.5-coder-0.5b-instruct-generic-cpu:4",
    "qwen2.5-0.5b-instruct-generic-cpu:4",
    "qwen2.5-coder-1.5b-instruct-generic-cpu:4",
    "qwen2.5-1.5b-instruct-generic-cpu:4",
    "Phi-3-mini-4k-instruct-generic-cpu:3",
)


@dataclass(frozen=True)
class FoundryClientResponse:
    success: bool
    backend: str
    base_url: str
    model_alias: str | None
    raw_text: str | None
    latency_ms: float | None
    error_type: str | None
    error_message: str | None
    response_payload: dict[str, Any] | None
    timestamp_utc: str


class FoundryLocalClient:
    """Small, dependency-light client for Foundry Local's OpenAI-compatible API."""

    backend_name = "foundry_local_openai_compatible"

    def __init__(
        self,
        base_url: str | None = None,
        model_alias: str | None = None,
        timeout_seconds: float | None = None,
        model_preference_order: tuple[str, ...] = DEFAULT_MODEL_PREFERENCE_ORDER,
    ) -> None:
        env_base_url = os.getenv(DEFAULT_BASE_URL_ENV)
        env_model_alias = os.getenv(DEFAULT_MODEL_ENV)
        env_timeout = os.getenv(DEFAULT_TIMEOUT_ENV)

        self.base_url = self._normalise_base_url(base_url or env_base_url or "")
        self.explicit_model_alias = model_alias or env_model_alias
        self.model_preference_order = model_preference_order

        if timeout_seconds is not None:
            self.timeout_seconds = float(timeout_seconds)
        elif env_timeout:
            self.timeout_seconds = float(env_timeout)
        else:
            self.timeout_seconds = 30.0

    def chat_completion(
        self,
        user_prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 256,
    ) -> FoundryClientResponse:
        """Call Foundry Local /v1/chat/completions and return raw text or structured failure."""

        started = time.perf_counter()

        if not self.base_url:
            return self._failure(
                error_type="missing_base_url",
                error_message=f"{DEFAULT_BASE_URL_ENV} is not set and no base_url was provided.",
                model_alias=self.explicit_model_alias,
                started=started,
            )

        model_resolution = self._resolve_model_alias(started=started)
        if isinstance(model_resolution, FoundryClientResponse):
            return model_resolution

        selected_model = model_resolution

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})

        payload = {
            "model": selected_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        try:
            response_payload = self._post_json("/v1/chat/completions", payload)
            raw_text = self._extract_text(response_payload)

            if raw_text is None or raw_text.strip() == "":
                return self._failure(
                    error_type="empty_model_response",
                    error_message="Chat completion response contained no extractable text.",
                    model_alias=selected_model,
                    started=started,
                    response_payload=response_payload,
                )

            return FoundryClientResponse(
                success=True,
                backend=self.backend_name,
                base_url=self.base_url,
                model_alias=selected_model,
                raw_text=raw_text,
                latency_ms=self._elapsed_ms(started),
                error_type=None,
                error_message=None,
                response_payload=response_payload,
                timestamp_utc=self._timestamp_utc(),
            )

        except TimeoutError as exc:
            return self._failure(
                error_type="timeout",
                error_message=str(exc),
                model_alias=selected_model,
                started=started,
            )
        except urllib_error.HTTPError as exc:
            return self._failure(
                error_type="http_error",
                error_message=f"HTTP {exc.code}: {exc.reason}",
                model_alias=selected_model,
                started=started,
            )
        except urllib_error.URLError as exc:
            return self._failure(
                error_type="endpoint_unavailable",
                error_message=str(exc.reason),
                model_alias=selected_model,
                started=started,
            )
        except json.JSONDecodeError as exc:
            return self._failure(
                error_type="malformed_json_response",
                error_message=str(exc),
                model_alias=selected_model,
                started=started,
            )
        except Exception as exc:  # defensive fail-closed boundary
            return self._failure(
                error_type="unknown_error",
                error_message=f"{type(exc).__name__}: {exc}",
                model_alias=selected_model,
                started=started,
            )

    def list_model_aliases(self) -> FoundryClientResponse:
        """Return available model aliases through the stable response object."""

        started = time.perf_counter()

        if not self.base_url:
            return self._failure(
                error_type="missing_base_url",
                error_message=f"{DEFAULT_BASE_URL_ENV} is not set and no base_url was provided.",
                model_alias=self.explicit_model_alias,
                started=started,
            )

        try:
            payload = self._get_json("/v1/models")
            aliases = self._extract_model_aliases(payload)

            return FoundryClientResponse(
                success=True,
                backend=self.backend_name,
                base_url=self.base_url,
                model_alias=None,
                raw_text=json.dumps(aliases),
                latency_ms=self._elapsed_ms(started),
                error_type=None,
                error_message=None,
                response_payload=payload,
                timestamp_utc=self._timestamp_utc(),
            )

        except TimeoutError as exc:
            return self._failure("timeout", str(exc), self.explicit_model_alias, started)
        except urllib_error.HTTPError as exc:
            return self._failure("http_error", f"HTTP {exc.code}: {exc.reason}", self.explicit_model_alias, started)
        except urllib_error.URLError as exc:
            return self._failure("endpoint_unavailable", str(exc.reason), self.explicit_model_alias, started)
        except json.JSONDecodeError as exc:
            return self._failure("malformed_json_response", str(exc), self.explicit_model_alias, started)
        except Exception as exc:
            return self._failure("unknown_error", f"{type(exc).__name__}: {exc}", self.explicit_model_alias, started)

    def _resolve_model_alias(self, started: float) -> str | FoundryClientResponse:
        try:
            model_payload = self._get_json("/v1/models")
            available_aliases = self._extract_model_aliases(model_payload)

            if not available_aliases:
                return self._failure(
                    error_type="empty_model_list",
                    error_message="/v1/models returned no usable model aliases.",
                    model_alias=self.explicit_model_alias,
                    started=started,
                    response_payload=model_payload,
                )

            if self.explicit_model_alias:
                if self.explicit_model_alias not in available_aliases:
                    return self._failure(
                        error_type="bad_model_alias",
                        error_message=(
                            f"Explicit model alias '{self.explicit_model_alias}' was not present "
                            "in /v1/models."
                        ),
                        model_alias=self.explicit_model_alias,
                        started=started,
                        response_payload=model_payload,
                    )
                return self.explicit_model_alias

            for preferred_model in self.model_preference_order:
                if preferred_model in available_aliases:
                    return preferred_model

            return self._failure(
                error_type="no_preferred_model_available",
                error_message=(
                    "No explicit model was provided and none of the safe preferred "
                    "CPU smoke-test models were available."
                ),
                model_alias=None,
                started=started,
                response_payload=model_payload,
            )

        except TimeoutError as exc:
            return self._failure("timeout", str(exc), self.explicit_model_alias, started)
        except urllib_error.HTTPError as exc:
            return self._failure("http_error", f"HTTP {exc.code}: {exc.reason}", self.explicit_model_alias, started)
        except urllib_error.URLError as exc:
            return self._failure("endpoint_unavailable", str(exc.reason), self.explicit_model_alias, started)
        except json.JSONDecodeError as exc:
            return self._failure("malformed_json_response", str(exc), self.explicit_model_alias, started)
        except Exception as exc:
            return self._failure("unknown_error", f"{type(exc).__name__}: {exc}", self.explicit_model_alias, started)

    def _get_json(self, path: str) -> dict[str, Any]:
        req = urllib_request.Request(
            url=f"{self.base_url}{path}",
            method="GET",
            headers={"Accept": "application/json"},
        )
        return self._open_and_decode(req)

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        req = urllib_request.Request(
            url=f"{self.base_url}{path}",
            data=body,
            method="POST",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )
        return self._open_and_decode(req)

    def _open_and_decode(self, req: urllib_request.Request) -> dict[str, Any]:
        with urllib_request.urlopen(req, timeout=self.timeout_seconds) as response:
            raw = response.read().decode("utf-8")
        decoded = json.loads(raw)
        if not isinstance(decoded, dict):
            raise ValueError("Expected JSON object response.")
        return decoded

    @staticmethod
    def _extract_model_aliases(payload: dict[str, Any]) -> list[str]:
        data = payload.get("data", [])
        if not isinstance(data, list):
            return []

        aliases: list[str] = []
        for item in data:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                aliases.append(item["id"])
        return aliases

    @staticmethod
    def _extract_text(payload: dict[str, Any]) -> str | None:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            return None

        first = choices[0]
        if not isinstance(first, dict):
            return None

        message = first.get("message")
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            return message["content"]

        if isinstance(first.get("text"), str):
            return first["text"]

        return None

    @staticmethod
    def _normalise_base_url(base_url: str) -> str:
        return base_url.strip().rstrip("/")

    @staticmethod
    def _timestamp_utc() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _elapsed_ms(started: float) -> float:
        return round((time.perf_counter() - started) * 1000.0, 3)

    def _failure(
        self,
        error_type: str,
        error_message: str,
        model_alias: str | None,
        started: float,
        response_payload: dict[str, Any] | None = None,
    ) -> FoundryClientResponse:
        return FoundryClientResponse(
            success=False,
            backend=self.backend_name,
            base_url=self.base_url,
            model_alias=model_alias,
            raw_text=None,
            latency_ms=self._elapsed_ms(started),
            error_type=error_type,
            error_message=error_message,
            response_payload=response_payload,
            timestamp_utc=self._timestamp_utc(),
        )
