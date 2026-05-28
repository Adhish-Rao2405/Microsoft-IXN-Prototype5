import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


BASE_URL = os.environ.get("FOUNDRY_LOCAL_BASE_URL", "http://127.0.0.1:53402").rstrip("/")
MODEL_ALIAS = os.environ.get("FOUNDRY_LOCAL_MODEL", "")
OUTPUT_DIR = Path("results/prototype5/mode_sdk")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def http_get_json(url: str, timeout: int = 20):
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def http_post_json(url: str, payload: dict, timeout: int = 120):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def extract_model_alias(models_payload: dict) -> str:
    if MODEL_ALIAS:
        return MODEL_ALIAS

    models = models_payload.get("data", [])
    if not models:
        raise RuntimeError("No models returned from /v1/models")

    first = models[0]
    model_id = first.get("id")
    if not model_id:
        raise RuntimeError(f"First model entry has no id: {first}")

    return model_id


def extract_text(response_payload: dict) -> str | None:
    choices = response_payload.get("choices", [])
    if not choices:
        return None

    first = choices[0]

    message = first.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str):
            return content

    text = first.get("text")
    if isinstance(text, str):
        return text

    return None


def main():
    summary = {
        "status": "UNKNOWN",
        "timestamp_utc": utc_now(),
        "base_url": BASE_URL,
        "model_alias": None,
        "models_endpoint": f"{BASE_URL}/v1/models",
        "chat_endpoint": f"{BASE_URL}/v1/chat/completions",
        "latency_ms": None,
        "response_text_found": False,
        "error_type": None,
        "error_message": None,
    }

    try:
        models_payload = http_get_json(f"{BASE_URL}/v1/models")
        (OUTPUT_DIR / "spike_foundry_models.json").write_text(
            json.dumps(models_payload, indent=2),
            encoding="utf-8",
        )

        model_alias = extract_model_alias(models_payload)
        summary["model_alias"] = model_alias

        payload = {
            "model": model_alias,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a robot task planner. Return only valid JSON. "
                        "Do not include Markdown."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Convert this command into a minimal robot action plan: "
                        "Move the red block to the inspection zone."
                    ),
                },
            ],
            "temperature": 0,
            "stream": False,
        }

        start = time.perf_counter()
        response_payload = http_post_json(
            f"{BASE_URL}/v1/chat/completions",
            payload,
            timeout=180,
        )
        end = time.perf_counter()

        latency_ms = round((end - start) * 1000, 2)
        text = extract_text(response_payload)

        summary["latency_ms"] = latency_ms
        summary["response_text_found"] = text is not None
        summary["status"] = "SUCCESS" if text else "SUCCESS_NO_TEXT_EXTRACTED"

        (OUTPUT_DIR / "spike_foundry_sdk_response.json").write_text(
            json.dumps(response_payload, indent=2),
            encoding="utf-8",
        )

        (OUTPUT_DIR / "spike_foundry_sdk_summary.json").write_text(
            json.dumps(summary, indent=2),
            encoding="utf-8",
        )

        md = [
            "# Phase 1 SDK/API Discovery Spike Summary",
            "",
            f"- Status: {summary['status']}",
            f"- Base URL: `{BASE_URL}`",
            f"- Model alias: `{model_alias}`",
            f"- Latency ms: `{latency_ms}`",
            f"- Response text found: `{summary['response_text_found']}`",
            "",
            "## Extracted response text",
            "",
            "```text",
            text or "<NO TEXT EXTRACTED>",
            "```",
            "",
        ]

        (OUTPUT_DIR / "spike_foundry_sdk_summary.md").write_text(
            "\n".join(md),
            encoding="utf-8",
        )

        print(json.dumps(summary, indent=2))

    except urllib.error.URLError as exc:
        summary["status"] = "FAILED"
        summary["error_type"] = "url_error"
        summary["error_message"] = str(exc)
        (OUTPUT_DIR / "spike_foundry_sdk_summary.json").write_text(
            json.dumps(summary, indent=2),
            encoding="utf-8",
        )
        print(json.dumps(summary, indent=2))
        raise SystemExit(1)

    except Exception as exc:
        summary["status"] = "FAILED"
        summary["error_type"] = type(exc).__name__
        summary["error_message"] = str(exc)
        (OUTPUT_DIR / "spike_foundry_sdk_summary.json").write_text(
            json.dumps(summary, indent=2),
            encoding="utf-8",
        )
        print(json.dumps(summary, indent=2))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
