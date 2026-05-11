"""Command-line entry point for Prototype 5 Mode A."""

from __future__ import annotations

from .claims_matrix import create_claims_matrix
from .evidence_manifest import generate_evidence_manifest
from .evidence_paths import collect_input_status
from .loaders import load_evidence
from .metrics import (
    final_extension_summary,
    final_limitations_matrix,
    final_model_comparison,
    final_safety_latency_summary,
    final_zero_trust_comparison,
)
from .local_cloud_comparison import collect_mode_c_evidence
from .mode_d_summary import collect_mode_d_evidence
from .phi_recovery_metrics import collect_phi_evidence
from .quantisation_evidence import collect_quantisation_evidence
from .report_exports import export_all


def _status_from_table(table) -> str:
    if table.empty:
        return "MISSING"
    if "evidence_status" not in table.columns:
        return "PRESENT"
    statuses = {str(row.get("evidence_status")) for row in table.rows if row.get("evidence_status")}
    if statuses == {"PRESENT"}:
        return "PRESENT"
    if "PRESENT" in statuses:
        return "PARTIAL"
    return "MISSING"


def run() -> tuple[dict[str, object], list[object]]:
    input_status = collect_input_status()
    evidence = load_evidence()
    quantisation_summary = collect_quantisation_evidence()
    phi_summary = collect_phi_evidence()
    mode_c_summary = collect_mode_c_evidence()
    mode_d_summary = collect_mode_d_evidence()

    tables = {
        "model_comparison": final_model_comparison(evidence),
        "zero_trust_comparison": final_zero_trust_comparison(evidence),
        "safety_latency_summary": final_safety_latency_summary(evidence),
        "extension_summary": final_extension_summary(evidence),
    }
    tables["limitations_matrix"] = final_limitations_matrix(
        quantisation_summary, phi_summary, mode_c_summary, mode_d_summary
    )
    tables["claims_matrix"] = create_claims_matrix(
        input_status, tables, quantisation_summary, phi_summary, mode_c_summary, mode_d_summary
    )

    claims_summary: dict[str, int] = {}
    for row in tables["claims_matrix"].rows:
        status = str(row.get("status", ""))
        claims_summary[status] = claims_summary.get(status, 0) + 1
    provisional_manifest = generate_evidence_manifest(
        input_status,
        [],
        claims_summary,
        quantisation_summary,
        phi_summary,
        mode_c_summary,
        mode_d_summary,
    )
    generated = export_all(tables, provisional_manifest)
    final_manifest = generate_evidence_manifest(
        input_status,
        generated,
        claims_summary,
        quantisation_summary,
        phi_summary,
        mode_c_summary,
        mode_d_summary,
    )
    generated = export_all(tables, final_manifest)
    return {"tables": tables, "manifest": final_manifest}, generated


def main() -> None:
    result, generated = run()
    tables = result["tables"]
    manifest = result["manifest"]
    model_status = _status_from_table(tables["model_comparison"])
    p4_status = _status_from_table(tables["zero_trust_comparison"])
    extension_status = _status_from_table(tables["extension_summary"])
    print("Prototype 5 Final Evidence Orchestrator: COMPLETE")
    print(f"Prototype 3 model evidence: {model_status}")
    print(f"Prototype 4 zero-trust evidence: {p4_status}")
    print(f"Prototype 4 extension evidence: {extension_status}")
    print(f"Quantisation evidence: {manifest['quantisation_status']}")
    print(f"Phi evidence: {manifest['phi_status']}")
    print(f"Mode C status: {manifest['mode_c_status']}")
    print(f"Cloud baseline status: {manifest['cloud_baseline_status']}")
    print(f"Mode D status: {manifest['mode_d_status']}")
    print(f"Live Foundry profile: {manifest['live_foundry_profile_status']}")
    print(
        "Live Foundry successful requests: "
        f"{manifest['live_foundry_successful_requests']}/{manifest['live_foundry_total_commands']}"
    )
    print(f"Live Foundry JSON-valid rate: {manifest['live_foundry_json_valid_rate']}")
    print(f"Live Foundry mean latency: {manifest['live_foundry_mean_latency_ms']} ms")
    print(
        "Live Foundry normalized mean CPU: "
        f"{manifest['live_foundry_normalized_mean_cpu_percent']}%"
    )
    print(f"Generated outputs: {len(generated)}")


if __name__ == "__main__":
    main()
