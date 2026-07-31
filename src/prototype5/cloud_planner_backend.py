"""OpenAI-compatible cloud transport for the integrated demonstrator."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

from .foundry_sdk_backend import ModelBackendResponse


@dataclass(frozen=True)
class CloudPlannerConfiguration:
    base_url: str
    api_key: str
    model_id: str
    timeout_seconds: float
    system_prompt: str
    backend_name: str = "openai_compatible_cloud"

    def __post_init__(self) -> None:
        if not self.model_id.strip():
            raise ValueError("cloud model_id must not be blank")
        if self.timeout_seconds <= 0:
            raise ValueError("cloud timeout_seconds must be positive")


class CloudPlannerBackend:
    """Return raw cloud model text without making governance decisions."""

    def __init__(self, configuration: CloudPlannerConfiguration) -> None:
        self.configuration = configuration

    def generate(
        self, command: str, context: dict[str, Any] | None = None
    ) -> ModelBackendResponse:
        started = time.perf_counter()
        prompt_id = str((context or {}).get("prompt_id", "prototype5_demo_v2"))
        if not self.configuration.api_key:
            return self._failure(
                started=started,
                prompt_id=prompt_id,
                error_type="authentication_failed",
                error_message="Cloud API credentials are not configured.",
            )
        if not self.configuration.base_url:
            return self._failure(
                started=started,
                prompt_id=prompt_id,
                error_type="endpoint_unavailable",
                error_message="Cloud API base URL is not configured.",
            )

        payload = {
            "model": self.configuration.model_id,
            "messages": [
                {
                    "role": "system",
                    "content": self.configuration.system_prompt,
                },
                {
                    "role": "user",
                    "content": self._user_content(command, context or {}),
                },
            ],
            "temperature": 0,
            "max_tokens": 320,
            "stream": False,
        }
        api_request = urllib_request.Request(
            url=(
                f"{self.configuration.base_url.rstrip('/')}"
                "/chat/completions"
            ),
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.configuration.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urllib_request.urlopen(
                api_request, timeout=self.configuration.timeout_seconds
            ) as response:
                response_payload = json.loads(
                    response.read().decode("utf-8-sig")
                )
            raw_text = self._extract_text(response_payload)
            if raw_text is None or not raw_text.strip():
                return self._failure(
                    started=started,
                    prompt_id=prompt_id,
                    error_type="empty_model_response",
                    error_message="Cloud response contained no model text.",
                )
            return ModelBackendResponse(
                backend=self.configuration.backend_name,
                model_alias=self.configuration.model_id,
                prompt_id=prompt_id,
                raw_text=raw_text,
                success=True,
                latency_ms=self._elapsed_ms(started),
                error_type=None,
                error_message=None,
                timestamp_utc=self._timestamp(),
            )
        except TimeoutError as exc:
            return self._failure(
                started=started,
                prompt_id=prompt_id,
                error_type="timeout",
                error_message=str(exc),
            )
        except urllib_error.HTTPError as exc:
            error_type = (
                "authentication_failed"
                if exc.code in (401, 403)
                else "http_error"
            )
            return self._failure(
                started=started,
                prompt_id=prompt_id,
                error_type=error_type,
                error_message=f"HTTP {exc.code}: {exc.reason}",
            )
        except (urllib_error.URLError, OSError) as exc:
            return self._failure(
                started=started,
                prompt_id=prompt_id,
                error_type="endpoint_unavailable",
                error_message=str(exc),
            )
        except (json.JSONDecodeError, ValueError, KeyError, TypeError) as exc:
            return self._failure(
                started=started,
                prompt_id=prompt_id,
                error_type="malformed_cloud_response",
                error_message=f"{type(exc).__name__}: {exc}",
            )

    @staticmethod
    def _user_content(command: str, context: dict[str, Any]) -> str:
        scene = context.get("scene", {})
        domain = context.get("domain_id", "MANUFACTURING")
        return (
            f"Domain: {domain}\n"
            f"Scene state: {json.dumps(scene, sort_keys=True)}\n"
            f"Operator command: {command}\n"
            "Return only the structured proposal JSON object."
        )

    @staticmethod
    def _extract_text(payload: dict[str, Any]) -> str | None:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            return None
        first = choices[0]
        if not isinstance(first, dict):
            return None
        message = first.get("message")
        if not isinstance(message, dict):
            return None
        content = message.get("content")
        return content if isinstance(content, str) else None

    def _failure(
        self,
        *,
        started: float,
        prompt_id: str,
        error_type: str,
        error_message: str,
    ) -> ModelBackendResponse:
        return ModelBackendResponse(
            backend=self.configuration.backend_name,
            model_alias=self.configuration.model_id,
            prompt_id=prompt_id,
            raw_text=None,
            success=False,
            latency_ms=self._elapsed_ms(started),
            error_type=error_type,
            error_message=error_message,
            timestamp_utc=self._timestamp(),
        )

    @staticmethod
    def _elapsed_ms(started: float) -> float:
        return max(0.0, (time.perf_counter() - started) * 1000.0)

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()
