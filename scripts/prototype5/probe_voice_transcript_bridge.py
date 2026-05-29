from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.prototype5.foundry_sdk_backend import FoundrySDKBackend  # noqa: E402
from src.prototype5.foundry_sdk_client import FoundryLocalClient  # noqa: E402
from src.prototype5.voice_to_planner_bridge import bridge_transcript_to_planner  # noqa: E402


class MockBackendResponse:
    backend = "mock_voice_bridge_backend"
    model_alias = "mock"
    raw_text = '{"actions": []}'
    success = True
    latency_ms = 0.0
    error_type = None
    error_message = None


class MockBackend:
    def generate(self, command: str, context: dict | None = None) -> MockBackendResponse:
        self.command = command
        self.context = context or {}
        return MockBackendResponse()


def build_backend(use_live_sdk: bool):
    if not use_live_sdk:
        return MockBackend(), None

    base_url = os.getenv("FOUNDRY_LOCAL_BASE_URL", "").strip()
    model_alias = os.getenv("FOUNDRY_LOCAL_MODEL", "").strip()
    if not base_url or not model_alias:
        return None, "FOUNDRY_LOCAL_BASE_URL and FOUNDRY_LOCAL_MODEL must be set for --live-sdk."
    return FoundrySDKBackend(client=FoundryLocalClient(base_url=base_url, model_alias=model_alias)), None


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe the typed transcript bridge without audio input.")
    parser.add_argument("--text", required=True, help="Manual transcript text.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--mock-backend", action="store_true", help="Use the offline mock backend.")
    mode.add_argument("--live-sdk", action="store_true", help="Use the configured Foundry SDK backend.")
    args = parser.parse_args()

    backend, error = build_backend(use_live_sdk=args.live_sdk)
    if error:
        print(
            json.dumps(
                {
                    "status": "NOT_RUN_LIVE_SDK_ENV_MISSING",
                    "error": error,
                    "audio_runtime_used": False,
                    "microphone_used": False,
                },
                indent=2,
            )
        )
        return 0

    result = bridge_transcript_to_planner(args.text, planner_backend=backend or MockBackend())
    print(json.dumps(result.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
