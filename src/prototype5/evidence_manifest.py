"""Evidence manifest generation for Prototype 5."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .evidence_paths import missing_input_names, present_input_names

OPTIONAL_CONTEXT_INPUT_PREFIXES = ("prototype1_",)


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


def _is_optional_context_input(name: str) -> bool:
    return any(name.startswith(prefix) for prefix in OPTIONAL_CONTEXT_INPUT_PREFIXES)


def _core_missing_input_names(input_status: dict[str, dict[str, str]]) -> list[str]:
    return [name for name in missing_input_names(input_status) if not _is_optional_context_input(name)]


def _optional_context_missing_input_names(
    input_status: dict[str, dict[str, str]],
) -> list[str]:
    return [name for name in missing_input_names(input_status) if _is_optional_context_input(name)]


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
    mode_c_summary: dict[str, Any] | None = None,
    mode_d_summary: dict[str, Any] | None = None,
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
    mode_c = mode_c_summary or {
        "mode_c_status": "MISSING",
        "cloud_baseline_status": "MISSING",
        "output_files_present": [],
    }
    mode_d = mode_d_summary or {
        "mode_d_status": "MISSING",
        "output_files_present": [],
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
    if mode_c.get("mode_c_status") not in {"COMPLETE", "COMPLETE_WITH_CLOUD_NOT_RUN"}:
        pass
    else:
        missing_limitations = [
            item for item in missing_limitations if item != "cloud-vs-local comparison evidence is missing."
        ]
    if mode_d.get("mode_d_status") in {
        "COMPLETE_LIVE_PROFILE",
        "COMPLETE_REPLAY_PROFILE",
        "COMPLETE_WITH_LIMITED_HARDWARE_VISIBILITY",
        "COMPLETE_WITH_PROFILER_LIMITED",
    }:
        missing_limitations = [
            item
            for item in missing_limitations
            if item
            not in {
                "GPU/NPU profiling evidence is missing.",
                "memory footprint measurement evidence is missing.",
            }
        ]
        hardware = mode_d.get("hardware_visibility", {})
        if hardware.get("gpu_status") in {"NOT_DETECTED", "NOT_AVAILABLE"} or hardware.get(
            "npu_status"
        ) in {"NOT_DETECTED", "NOT_AVAILABLE"}:
            missing_limitations.insert(
                2,
                "GPU/NPU counters were not detected in Mode D, so no hardware acceleration claim is made.",
            )
    return {
        "input_files_present": present_input_names(input_status),
        "input_files_missing": _core_missing_input_names(input_status),
        "optional_context_files_missing": _optional_context_missing_input_names(input_status),
        "optional_context_evidence": {
            "prototype_1": {
                "status": (
                    "OPTIONAL_CONTEXT_PRESENT"
                    if _prototype_status(input_status, "prototype1_") == "PRESENT"
                    else "OPTIONAL_CONTEXT_MISSING"
                ),
                "role": "early feasibility/context only",
                "core_claim_dependency": False,
                "safe_interpretation": (
                    "Prototype 1 audit files are optional project-history context. "
                    "Their absence does not affect the core final claims, which are supported by "
                    "Prototype 3, Prototype 4, and Prototype 5 evidence."
                ),
                "note_file": "docs/prototype1_context_note.md",
            }
        },
        "generated_outputs": [str(path) for path in generated_outputs],
        "prototype_statuses": {
            "prototype_1_audit": (
                "OPTIONAL_CONTEXT_PRESENT"
                if _prototype_status(input_status, "prototype1_") == "PRESENT"
                else "OPTIONAL_CONTEXT_MISSING"
            ),
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
        "mode_c_status": mode_c.get("mode_c_status", "MISSING"),
        "cloud_baseline_status": mode_c.get("cloud_baseline_status", "MISSING"),
        "mode_c_evidence": mode_c,
        "mode_c_output_files": mode_c.get("output_files_present", []),
        "mode_d_status": mode_d.get("mode_d_status", "MISSING"),
        "mode_d_evidence": mode_d,
        "mode_d_output_files": mode_d.get("output_files_present", []),
        "live_foundry_profile_status": mode_d.get("live_foundry_profile_status", "MISSING"),
        "live_foundry_successful_requests": mode_d.get(
            "live_foundry_successful_requests", "NOT_AVAILABLE"
        ),
        "live_foundry_total_commands": mode_d.get("live_foundry_total_commands", "NOT_AVAILABLE"),
        "live_foundry_json_valid_rate": mode_d.get("live_foundry_json_valid_rate", "NOT_AVAILABLE"),
        "live_foundry_mean_latency_ms": mode_d.get(
            "live_foundry_mean_latency_ms", "NOT_AVAILABLE"
        ),
        "live_foundry_normalized_mean_cpu_percent": mode_d.get(
            "live_foundry_normalized_mean_cpu_percent", "NOT_AVAILABLE"
        ),
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
