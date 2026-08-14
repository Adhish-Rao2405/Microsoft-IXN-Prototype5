"""Runtime composition for the integrated demonstrator.

Construction is side-effect free. Foundry Local and cloud calls occur only
after a user submits a request or a local availability probe is evaluated.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pybullet as pb

from .canonical_governance_runner import (
    CanonicalGovernanceRunner,
    CanonicalRunnerConfigurationV2,
)
from .cloud_planner_backend import (
    CloudPlannerBackend,
    CloudPlannerConfiguration,
)
from .demo_service import DemoApplicationService
from .final_demo_contract import load_final_demo_contract
from .final_demo_presentation import FinalDemoPresentationRegistry
from .foundry_sdk_backend import FoundrySDKBackend
from .foundry_sdk_client import FoundryLocalClient
from .governance_contract_v2 import ProviderId
from .hybrid_inference_router import (
    HybridInferenceRouter,
    InferenceProviderBinding,
    ProviderAvailabilityV2,
    load_hybrid_routing_policy,
)
from .manufacturing_policy_v2 import load_manufacturing_policy
from .recorded_speech import (
    NemotronRecordedAudioClient,
    RecordedSpeechClientConfiguration,
)
from .pybullet_evidence_replay import PyBulletEvidenceReplaySession
from .replay_coordinator import ReplayCoordinator


DEFAULT_LOCAL_MODEL = "qwen2.5-coder-0.5b-instruct-generic-cpu:4"
DEFAULT_CLOUD_MODEL = "gpt-4o-mini"

STRUCTURED_PROPOSAL_SYSTEM_PROMPT = """You generate untrusted robot task proposals.
Return exactly one JSON object with an actions array and no markdown.
Allowed actions are MOVE, PICK, PLACE, WAIT, STOP, and INSPECT.
MOVE requires object_id, source_id, and destination_id.
PICK requires object_id and source_id.
PLACE requires object_id and destination_id.
WAIT requires duration_ms. STOP has no other fields.
INSPECT requires object_id.
All entity identifiers must use lower_snake_case.
Never claim that a proposal is safe, authorised, or execution eligible."""


def build_demo_service(repo_root: Path | None = None) -> DemoApplicationService:
    root = repo_root or Path(__file__).resolve().parents[2]
    routing_policy = load_hybrid_routing_policy(
        root / "configs" / "prototype5" / "hybrid_routing_policy_v1.json"
    )
    manufacturing_policy = load_manufacturing_policy(
        root / "configs" / "prototype5" / "manufacturing_policy_v2.json"
    )
    final_demo_presentation = FinalDemoPresentationRegistry.from_contract(
        load_final_demo_contract(
            root / "configs" / "prototype5" / "final_demo_scenarios_v1.json"
        )
    )
    software_commit = _resolve_software_commit(root)

    local_model = os.getenv("FOUNDRY_LOCAL_MODEL", DEFAULT_LOCAL_MODEL)
    local_client = FoundryLocalClient(
        base_url=os.getenv("FOUNDRY_LOCAL_BASE_URL"),
        model_alias=local_model,
        timeout_seconds=routing_policy.config.local_timeout_ms / 1000,
    )
    local_backend = FoundrySDKBackend(
        client=local_client,
        default_system_prompt=STRUCTURED_PROPOSAL_SYSTEM_PROMPT,
        default_prompt_id="prototype5_integrated_demo_v2",
    )

    cloud_api_key = os.getenv("OPENAI_API_KEY", "")
    cloud_model = os.getenv("OPENAI_MODEL", DEFAULT_CLOUD_MODEL)
    cloud_backend = CloudPlannerBackend(
        CloudPlannerConfiguration(
            base_url=os.getenv(
                "OPENAI_BASE_URL", "https://api.openai.com/v1"
            ),
            api_key=cloud_api_key,
            model_id=cloud_model,
            timeout_seconds=float(os.getenv("OPENAI_TIMEOUT_SECONDS", "30")),
            system_prompt=STRUCTURED_PROPOSAL_SYSTEM_PROMPT,
        )
    )
    governance_runner = CanonicalGovernanceRunner(
        policy=manufacturing_policy,
        configuration=CanonicalRunnerConfigurationV2(
            source_repository="Adhish-Rao2405/Microsoft-IXN-Prototype5",
            software_commit=software_commit,
            prompt_id="prototype5_integrated_demo_v2",
            prompt_version="2.0.0",
        ),
    )

    def local_availability() -> ProviderAvailabilityV2:
        result = local_client.list_model_aliases()
        if not result.success:
            return ProviderAvailabilityV2(
                available=False,
                model_ready=False,
                detail_code=_normalise_detail_code(result.error_type),
            )
        aliases = json.loads(result.raw_text or "[]")
        model_ready = local_model in aliases
        return ProviderAvailabilityV2(
            available=True,
            model_ready=model_ready,
            detail_code="READY" if model_ready else "MODEL_NOT_READY",
        )

    router = HybridInferenceRouter(
        local=InferenceProviderBinding(
            provider_id=ProviderId.FOUNDRY_LOCAL,
            model_id=local_model,
            backend=local_backend,
            availability_probe=local_availability,
        ),
        cloud=InferenceProviderBinding(
            provider_id=ProviderId.CLOUD,
            model_id=cloud_model,
            backend=cloud_backend,
        ),
        governance_runner=governance_runner,
        routing_policy=routing_policy,
    )
    speech_python = Path(
        os.getenv("PROTOTYPE5_SPEECH_PYTHON", sys.executable)
    ).expanduser()
    speech_temp_root_value = os.getenv("PROTOTYPE5_SPEECH_TEMP_ROOT")
    speech_transcriber = NemotronRecordedAudioClient(
        RecordedSpeechClientConfiguration(
            repository_root=root,
            speech_python_executable=speech_python,
            process_timeout_seconds=float(
                os.getenv("PROTOTYPE5_SPEECH_TIMEOUT_SECONDS", "120")
            ),
            allow_model_download=(
                os.getenv("PROTOTYPE5_SPEECH_ALLOW_MODEL_DOWNLOAD", "0")
                == "1"
            ),
            temporary_root=(
                Path(speech_temp_root_value).expanduser()
                if speech_temp_root_value
                else None
            ),
        )
    )
    return DemoApplicationService(
        router=router,
        software_commit=software_commit,
        cloud_configured=bool(cloud_api_key),
        speech_transcriber=speech_transcriber,
        final_demo_presentation=final_demo_presentation,
    )


def build_replay_coordinator(repo_root: Path | None = None) -> ReplayCoordinator:
    """Compose replay ownership without loading evidence or connecting PyBullet."""

    root = repo_root or Path(__file__).resolve().parents[2]
    mode_name = os.getenv("PROTOTYPE5_REPLAY_MODE", "GUI")
    modes = {"GUI": pb.GUI, "DIRECT": pb.DIRECT}
    if mode_name not in modes:
        raise ValueError("PROTOTYPE5_REPLAY_MODE must be GUI or DIRECT")
    contract = load_final_demo_contract(
        root / "configs" / "prototype5" / "final_demo_scenarios_v1.json"
    )
    known_scenario_ids = frozenset(
        scenario.scenario_id for scenario in contract.scenario_contract.scenarios
    )
    connection_mode = modes[mode_name]

    def session_factory() -> PyBulletEvidenceReplaySession:
        return PyBulletEvidenceReplaySession(connection_mode=connection_mode)

    return ReplayCoordinator(
        session_factory,
        known_scenario_ids=known_scenario_ids,
    )


def _resolve_software_commit(repo_root: Path) -> str:
    override = os.getenv("PROTOTYPE5_SOFTWARE_COMMIT")
    if override:
        commit = override
    else:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        commit = completed.stdout.strip()
    if not re.fullmatch(r"[0-9a-fA-F]{40}", commit):
        raise ValueError("software commit must be a full 40-character Git SHA")
    return commit.lower()


def _normalise_detail_code(value: str | None) -> str:
    if not value:
        return "LOCAL_UNAVAILABLE"
    return "".join(
        character if character.isalnum() else "_" for character in value.upper()
    )
