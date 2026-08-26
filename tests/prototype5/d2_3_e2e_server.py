"""Deterministic D2.3 browser-to-governance test server.

Only the model-provider port is substituted. The adapter returns raw model
text; the production router, canonical governance runner, policies, service,
FastAPI response models, and built frontend remain authoritative.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from itertools import count
from pathlib import Path

import uvicorn
from fastapi import FastAPI


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.prototype5.canonical_governance_runner import (  # noqa: E402
    CanonicalGovernanceRunner,
    CanonicalRunnerConfigurationV2,
)
from src.prototype5.demo_api import create_demo_app  # noqa: E402
from src.prototype5.demo_runtime import build_replay_coordinator  # noqa: E402
from src.prototype5.demo_service import DemoApplicationService  # noqa: E402
from src.prototype5.foundry_sdk_backend import ModelBackendResponse  # noqa: E402
from src.prototype5.governance_contract_v2 import ProviderId  # noqa: E402
from src.prototype5.hybrid_inference_router import (  # noqa: E402
    HybridInferenceRouter,
    InferenceProviderBinding,
    ProviderAvailabilityV2,
    load_hybrid_routing_policy,
)
from src.prototype5.manufacturing_policy_v2 import (  # noqa: E402
    load_manufacturing_policy,
)
from src.prototype5.replay_coordinator import ReplayCoordinator  # noqa: E402


FIXED_TIME = datetime(2026, 8, 12, 12, 0, tzinfo=timezone.utc)
RAW_MOVE_RESPONSE = json.dumps(
    {
        "actions": [
            {
                "action": "MOVE",
                "object_id": "blue_component",
                "source_id": "input_tray_a",
                "destination_id": "assembly_fixture_b",
                "duration_ms": None,
            }
        ]
    },
    separators=(",", ":"),
)


class DeterministicRawProposalBackend:
    """Return raw proposal text without assigning any governance outcome."""

    def __init__(self, provider: ProviderId, model_id: str) -> None:
        self.provider = provider
        self.model_id = model_id

    def generate(
        self,
        command: str,
        context: dict[str, object] | None = None,
    ) -> ModelBackendResponse:
        del command, context
        return ModelBackendResponse(
            backend=self.provider.value,
            model_alias=self.model_id,
            prompt_id="prototype5_integrated_demo_v2",
            raw_text=RAW_MOVE_RESPONSE,
            success=True,
            latency_ms=10.0,
            error_type=None,
            error_message=None,
            timestamp_utc=FIXED_TIME.isoformat(),
        )


def _software_commit() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=5,
    )
    return completed.stdout.strip().lower()


def _build_direct_replay_coordinator() -> ReplayCoordinator:
    """Capture the production replay composition in deterministic DIRECT mode."""

    variable = "PROTOTYPE5_REPLAY_MODE"
    previous = os.environ.get(variable)
    os.environ[variable] = "DIRECT"
    try:
        return build_replay_coordinator(ROOT)
    finally:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous


def create_d2_3_app() -> FastAPI:
    sequence = count(1)
    software_commit = _software_commit()
    local_model = "d2-3-deterministic-local-model"
    cloud_model = "d2-3-deterministic-cloud-model"
    governance_runner = CanonicalGovernanceRunner(
        policy=load_manufacturing_policy(
            ROOT / "configs" / "prototype5" / "manufacturing_policy_v2.json"
        ),
        configuration=CanonicalRunnerConfigurationV2(
            source_repository="Adhish-Rao2405/Microsoft-IXN-Prototype5",
            software_commit=software_commit,
            prompt_id="prototype5_integrated_demo_v2",
            prompt_version="2.0.0",
        ),
        clock=lambda: FIXED_TIME,
        id_factory=lambda: f"d2-3-{next(sequence)}",
    )
    router = HybridInferenceRouter(
        local=InferenceProviderBinding(
            provider_id=ProviderId.FOUNDRY_LOCAL,
            model_id=local_model,
            backend=DeterministicRawProposalBackend(
                ProviderId.FOUNDRY_LOCAL,
                local_model,
            ),
            availability_probe=lambda: ProviderAvailabilityV2(
                available=True,
                model_ready=True,
                detail_code="READY",
            ),
        ),
        cloud=InferenceProviderBinding(
            provider_id=ProviderId.CLOUD,
            model_id=cloud_model,
            backend=DeterministicRawProposalBackend(
                ProviderId.CLOUD,
                cloud_model,
            ),
        ),
        governance_runner=governance_runner,
        routing_policy=load_hybrid_routing_policy(
            ROOT / "configs" / "prototype5" / "hybrid_routing_policy_v1.json"
        ),
        utc_clock=lambda: FIXED_TIME,
    )
    service = DemoApplicationService(
        router=router,
        software_commit=software_commit,
        cloud_configured=True,
        speech_transcriber=None,
        utc_clock=lambda: FIXED_TIME,
    )
    replay_coordinator = _build_direct_replay_coordinator()
    return create_demo_app(
        service,
        frontend_dist=ROOT / "frontend" / "dist",
        replay_coordinator=replay_coordinator,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the D2.3 governed test stack.")
    parser.add_argument("--port", type=int, default=8001)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    uvicorn.run(
        create_d2_3_app(),
        host="127.0.0.1",
        port=args.port,
        log_level="warning",
    )


if __name__ == "__main__":
    main()
