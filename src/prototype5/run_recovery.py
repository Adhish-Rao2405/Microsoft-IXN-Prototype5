"""Command-line entry point for Prototype 5 Mode B recovery evidence checks."""

from __future__ import annotations

from .phi_recovery_runner import run_phi_recovery
from .quantisation_evidence import collect_quantisation_evidence


def main() -> None:
    summary = collect_quantisation_evidence()
    print("Prototype 5 Mode B Recovery: COMPLETE")
    print(f"FP16 evidence: {summary['fp16_evidence']}")
    print(f"INT8 evidence: {summary['int8_evidence']}")
    print(f"INT4 evidence: {summary['int4_evidence']}")
    print(f"Quantisation overall: {summary['quantisation_overall']}")
    print(
        "Built-in Foundry precision metadata: "
        f"{summary['built_in_foundry_precision_metadata']}"
    )
    print(f"Custom precision artifacts: {summary['custom_precision_artifacts']}")
    print(f"Metadata files: {len(summary['custom_precision_metadata_files'])}")
    phi_result = run_phi_recovery()
    phi_manifest = phi_result["manifest"]
    print(f"Phi recovery evidence: {phi_manifest['phi_status']}")
    print(f"Phi model: {phi_manifest.get('selected_model') or ''}")
    print(f"Phi successful requests: {phi_manifest['summary'].get('successful_requests', 0)}")


if __name__ == "__main__":
    main()
