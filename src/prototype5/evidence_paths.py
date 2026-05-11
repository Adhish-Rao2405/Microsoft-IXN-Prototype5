"""Input and output paths for Prototype 5 evidence orchestration."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]

PROTOTYPE_1_ROOT = Path(r"C:\Users\reach\Microsoft-IXN-Prototype1")
PROTOTYPE_2_ROOT = Path(r"C:\Users\reach\Microsoft-IXN-Prototype2")
PROTOTYPE_3_ROOT = Path(r"C:\Users\reach\Microsoft-IXN-Prototype3")
PROTOTYPE_4_ROOT = Path(r"C:\Users\reach\zero-trust-local-slm-robotics")
PROTOTYPE_5_ROOT = REPO_ROOT

RESULTS_DIR = PROTOTYPE_5_ROOT / "results" / "prototype5"
DOCS_DIR = PROTOTYPE_5_ROOT / "docs" / "prototype5"
CUSTOM_QUANTISATION_DIR = RESULTS_DIR / "recovery" / "custom_quantisation"
PHI_RECOVERY_DIR = RESULTS_DIR / "recovery" / "phi"
MODE_C_DIR = RESULTS_DIR / "mode_c"


EXPECTED_INPUT_PATHS: dict[str, Path] = {
    "prototype3_rq5_comparison_csv": PROTOTYPE_3_ROOT
    / "prototype3"
    / "results"
    / "summaries"
    / "rq5_comparison.csv",
    "prototype3_rq5_comparison_jsonl": PROTOTYPE_3_ROOT
    / "prototype3"
    / "results"
    / "runs"
    / "rq5_comparison.jsonl",
    "prototype3_evidence_pack_json": PROTOTYPE_3_ROOT
    / "prototype3"
    / "results"
    / "summaries"
    / "rq5_comparison_evidence"
    / "evidence_pack.json",
    "prototype3_evidence_by_difficulty_csv": PROTOTYPE_3_ROOT
    / "prototype3"
    / "results"
    / "summaries"
    / "rq5_comparison_evidence"
    / "evidence_by_difficulty.csv",
    "prototype3_evidence_by_category_csv": PROTOTYPE_3_ROOT
    / "prototype3"
    / "results"
    / "summaries"
    / "rq5_comparison_evidence"
    / "evidence_by_category.csv",
    "prototype3_benchmark_json": PROTOTYPE_3_ROOT
    / "prototype3"
    / "datasets"
    / "benchmark_v1.json",
    "prototype3_audit_summary_json": PROTOTYPE_3_ROOT
    / "prototype3"
    / "results"
    / "prototype_audit"
    / "prototype_3_audit_summary.json",
    "prototype3_quantisation_coverage_table_csv": PROTOTYPE_3_ROOT
    / "prototype3"
    / "results"
    / "prototype_audit"
    / "prototype_3_quantisation_coverage_table.csv",
    "prototype4_execution_comparison_csv": PROTOTYPE_4_ROOT
    / "results"
    / "summaries"
    / "prototype4_execution_comparison.csv",
    "prototype4_by_model_csv": PROTOTYPE_4_ROOT
    / "results"
    / "summaries"
    / "prototype4_by_model.csv",
    "prototype4_by_ambiguity_csv": PROTOTYPE_4_ROOT
    / "results"
    / "summaries"
    / "prototype4_by_ambiguity.csv",
    "prototype4_false_accepts_csv": PROTOTYPE_4_ROOT
    / "results"
    / "summaries"
    / "prototype4_false_accepts.csv",
    "prototype4_key_metrics_md": PROTOTYPE_4_ROOT
    / "results"
    / "summaries"
    / "prototype4_key_metrics.md",
    "prototype4_safety_latency_frontier_csv": PROTOTYPE_4_ROOT
    / "results"
    / "summaries"
    / "safety_latency_frontier.csv",
    "prototype4_metrics_manifest_json": PROTOTYPE_4_ROOT
    / "results"
    / "evidence_pack"
    / "metrics_manifest.json",
    "prototype4_phase_4_7_ambiguity_gate_summary_json": PROTOTYPE_4_ROOT
    / "results"
    / "prototype4_extensions"
    / "phase_4_7"
    / "ambiguity_gate_summary.json",
    "prototype4_phase_4_8_clarification_recovery_summary_json": PROTOTYPE_4_ROOT
    / "results"
    / "prototype4_extensions"
    / "phase_4_8"
    / "clarification_recovery_summary.json",
    "prototype4_phase_4_9_formal_safety_audit_summary_json": PROTOTYPE_4_ROOT
    / "results"
    / "prototype4_extensions"
    / "phase_4_9"
    / "formal_safety_audit_summary.json",
    "prototype4_phase_4_10_extension_audit_summary_json": PROTOTYPE_4_ROOT
    / "results"
    / "prototype4_extensions"
    / "phase_4_10"
    / "extension_audit_summary.json",
    "prototype4_audit_summary_json": PROTOTYPE_4_ROOT
    / "results"
    / "prototype_audit"
    / "prototype_4_audit_summary.json",
    "prototype4_audit_table_csv": PROTOTYPE_4_ROOT
    / "results"
    / "prototype_audit"
    / "prototype_4_audit_table.csv",
    "prototype1_audit_summary_json": PROTOTYPE_1_ROOT
    / "results"
    / "prototype_audit"
    / "prototype_1_audit_summary.json",
    "prototype1_audit_table_csv": PROTOTYPE_1_ROOT
    / "results"
    / "prototype_audit"
    / "prototype_1_audit_table.csv",
    "prototype2_audit_summary_json": PROTOTYPE_2_ROOT
    / "results"
    / "prototype_audit"
    / "prototype_2_audit_summary.json",
    "prototype2_audit_table_csv": PROTOTYPE_2_ROOT
    / "results"
    / "prototype_audit"
    / "prototype_2_audit_table.csv",
}


EXPECTED_RESULT_FILES = [
    "final_model_comparison.csv",
    "final_zero_trust_comparison.csv",
    "final_safety_latency_summary.csv",
    "final_extension_summary.csv",
    "final_claims_matrix.csv",
    "final_limitations_matrix.csv",
    "final_dissertation_metrics.md",
    "final_evidence_manifest.json",
]

EXPECTED_DOC_FILES = [
    "prototype5_final_evaluation_protocol.md",
    "prototype5_dissertation_results_summary.md",
    "prototype5_limitations_and_scope.md",
    "prototype5_quantisation_metadata_check.md",
    "prototype5_phi_evidence_summary.md",
]


def path_exists(path: str | Path) -> bool:
    """Return whether a path exists without mutating any source repository."""

    return Path(path).exists()


def collect_input_status(
    expected_paths: dict[str, Path] | None = None,
) -> dict[str, dict[str, str]]:
    """Return PRESENT/MISSING status for each expected evidence file."""

    paths = expected_paths or EXPECTED_INPUT_PATHS
    return {
        name: {"path": str(path), "status": "PRESENT" if path_exists(path) else "MISSING"}
        for name, path in paths.items()
    }


def present_input_names(status: dict[str, dict[str, str]]) -> list[str]:
    return [name for name, item in status.items() if item["status"] == "PRESENT"]


def missing_input_names(status: dict[str, dict[str, str]]) -> list[str]:
    return [name for name, item in status.items() if item["status"] == "MISSING"]
