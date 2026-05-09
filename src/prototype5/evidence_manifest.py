"""Evidence manifest generation for Prototype 5."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .evidence_paths import missing_input_names, present_input_names


def _prototype_status(input_status: dict[str, dict[str, str]], prefix: str) -> str:
    relevant = [item for name, item in input_status.items() if name.startswith(prefix)]
    if not relevant:
        return "MISSING"
    present = [item for item in relevant if item["status"] == "PRESENT"]
    if len(present) == len(relevant):
        return "PRESENT"
    if present:
        return "PARTIAL"
    return "MISSING"


def _detect_quantisation_status(input_status: dict[str, dict[str, str]]) -> str:
    """Return MISSING unless explicit coverage exists and proves compared variants."""

    _ = input_status
    return "MISSING"


def generate_evidence_manifest(
    input_status: dict[str, dict[str, str]],
    generated_outputs: list[str | Path],
    claims_summary: dict[str, Any] | None = None,
    quantisation_summary: dict[str, Any] | None = None,
    phi_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    quantisation = quantisation_summary or {
        "fp16_evidence": "MISSING",
        "int8_evidence": "MISSING",
        "int4_evidence": "MISSING",
        "quantisation_overall": _detect_quantisation_status(input_status),
        "built_in_foundry_precision_metadata": "MISSING",
        "custom_precision_artifacts": "MISSING",
        "custom_precision_metadata_files": [],
    }
    phi = phi_summary or {
        "phi_status": "MISSING",
        "output_files_present": [],
        "real_output_count": 0,
        "summary": {},
    }
    missing_limitations = [
        "Built-in Foundry Local catalogue precision metadata is missing.",
        "cloud-vs-local comparison evidence is missing.",
        "GPU/NPU profiling evidence is missing.",
        "memory footprint measurement evidence is missing.",
        "physical robot execution is not proven.",
    ]
    if phi.get("phi_status") not in {"PRESENT", "PARTIAL"}:
        missing_limitations.insert(1, "Phi-family evaluation evidence is missing.")
    return {
        "input_files_present": present_input_names(input_status),
        "input_files_missing": missing_input_names(input_status),
        "generated_outputs": [str(path) for path in generated_outputs],
        "prototype_statuses": {
            "prototype_1_audit": _prototype_status(input_status, "prototype1_"),
            "prototype_2_audit": _prototype_status(input_status, "prototype2_"),
            "prototype_3_model_evidence": _prototype_status(input_status, "prototype3_"),
            "prototype_4_zero_trust_evidence": _prototype_status(input_status, "prototype4_"),
        },
        "quantisation_status": quantisation["quantisation_overall"],
        "quantisation_evidence": quantisation,
        "fp16_evidence": quantisation["fp16_evidence"],
        "int8_evidence": quantisation["int8_evidence"],
        "int4_evidence": quantisation["int4_evidence"],
        "quantisation_overall": quantisation["quantisation_overall"],
        "built_in_foundry_precision_metadata": quantisation[
            "built_in_foundry_precision_metadata"
        ],
        "custom_precision_artifacts": quantisation["custom_precision_artifacts"],
        "custom_precision_metadata_files": quantisation["custom_precision_metadata_files"],
        "phi_status": phi["phi_status"],
        "phi_evidence": phi,
        "phi_output_files": phi.get("output_files_present", []),
        "final_safe_scope": (
            "Prototype 5 is an orchestration/reporting layer. It consolidates "
            "available Prototype 3 model-comparison evidence, Prototype 4 "
            "zero-trust execution evidence, extension summaries, and audit "
            "references. It does not run new inference, introduce robot planning "
            "logic, or modify earlier prototype repositories."
        ),
        "final_limitations": missing_limitations,
        "claims_summary": claims_summary or {},
    }
