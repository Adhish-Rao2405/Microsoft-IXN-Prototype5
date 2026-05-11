"""Final dissertation claims matrix."""

from __future__ import annotations

from typing import Any

from .simple_table import Table, numeric


def _present(status: dict[str, dict[str, str]], *names: str) -> bool:
    return any(status.get(name, {}).get("status") == "PRESENT" for name in names)


def create_claims_matrix(
    input_status: dict[str, dict[str, str]] | None = None,
    metric_tables: dict[str, Table] | None = None,
    quantisation_summary: dict[str, Any] | None = None,
    phi_summary: dict[str, Any] | None = None,
    mode_c_summary: dict[str, Any] | None = None,
    mode_d_summary: dict[str, Any] | None = None,
) -> Table:
    status = input_status or {}
    tables = metric_tables or {}
    model_table = tables.get("model_comparison", Table())
    zero_trust_table = tables.get("zero_trust_comparison", Table())

    p1_status = "PROVEN" if _present(status, "prototype1_audit_summary_json") else "PARTIAL"
    p2_status = "PROVEN" if _present(status, "prototype2_audit_summary_json") else "PARTIAL"
    p3_status = (
        "PROVEN"
        if not model_table.empty or _present(status, "prototype3_rq5_comparison_csv")
        else "MISSING"
    )
    p4_status = (
        "PROVEN"
        if not zero_trust_table.empty
        or _present(status, "prototype4_execution_comparison_csv")
        else "MISSING"
    )
    p47_status = (
        "PROVEN"
        if _present(status, "prototype4_phase_4_7_ambiguity_gate_summary_json")
        else "MISSING"
    )
    p48_status = (
        "PROVEN"
        if _present(status, "prototype4_phase_4_8_clarification_recovery_summary_json")
        else "MISSING"
    )
    p49_status = (
        "PROVEN"
        if _present(status, "prototype4_phase_4_9_formal_safety_audit_summary_json")
        else "MISSING"
    )

    false_accept_reduction_status = "NEEDS_REVIEW"
    if not zero_trust_table.empty and {"pipeline_mode", "unsafe_false_accepts"}.issubset(
        set(zero_trust_table.columns)
    ):
        baseline = [
            row
            for row in zero_trust_table.rows
            if "baseline" in str(row.get("pipeline_mode", "")).lower()
        ]
        zt = [
            row
            for row in zero_trust_table.rows
            if "zero_trust" in str(row.get("pipeline_mode", "")).lower()
        ]
        if baseline and zt:
            baseline_fa = sum(numeric(row.get("unsafe_false_accepts")) or 0 for row in baseline)
            zt_fa = sum(numeric(row.get("unsafe_false_accepts")) or 0 for row in zt)
            false_accept_reduction_status = (
                "PROVEN" if baseline_fa > zt_fa and zt_fa == 0 else "PARTIAL"
            )
    elif p4_status == "MISSING":
        false_accept_reduction_status = "MISSING"

    quantisation = quantisation_summary or {
        "quantisation_overall": "MISSING",
        "custom_precision_metadata_files": [],
    }
    phi = phi_summary or {"phi_status": "MISSING", "output_files_present": []}
    mode_c = mode_c_summary or {"cloud_baseline_status": "MISSING", "output_files_present": []}
    mode_d = mode_d_summary or {"mode_d_status": "MISSING", "output_files_present": []}

    rows: list[dict[str, Any]] = [
        {
            "claim": "Prototype 1 established baseline planner-validator-executor architecture.",
            "status": p1_status,
            "evidence_source": "Prototype 1 audit summary/table, where present.",
            "safe_dissertation_wording": "Prototype 1 documents the baseline planner-validator-executor architecture used as the starting point for later prototypes.",
            "unsafe_wording_to_avoid": "Prototype 1 proves final robot safety or deployment readiness.",
        },
        {
            "claim": "Prototype 2 established deterministic schema and safety foundation.",
            "status": p2_status,
            "evidence_source": "Prototype 2 audit summary/table, where present.",
            "safe_dissertation_wording": "Prototype 2 documents deterministic schema and safety checks that informed later validation stages.",
            "unsafe_wording_to_avoid": "Prototype 2 alone proves semantic safety under all robot tasks.",
        },
        {
            "claim": "Prototype 3 provides Qwen-family CPU model-comparison evidence.",
            "status": p3_status,
            "evidence_source": "Prototype 3 rq5_comparison.csv and evidence pack.",
            "safe_dissertation_wording": "Prototype 3 compares available Qwen-family CPU model variants on the benchmark evidence set.",
            "unsafe_wording_to_avoid": "Prototype 3 compares every local SLM family or hardware target.",
        },
        {
            "claim": "Prototype 3 provides semantic validity, false accept, false reject, and latency evidence.",
            "status": p3_status,
            "evidence_source": "Prototype 3 RQ5 summaries and run evidence.",
            "safe_dissertation_wording": "Prototype 3 reports schema validity, execution eligibility, false accepts, false rejects, correct rejects, and latency for the evaluated Qwen CPU runs.",
            "unsafe_wording_to_avoid": "Prototype 3 proves production-grade semantic correctness.",
        },
        {
            "claim": "Prototype 4 provides execution-grounded zero-trust evaluation evidence.",
            "status": p4_status,
            "evidence_source": "Prototype 4 execution comparison and summary files.",
            "safe_dissertation_wording": "Prototype 4 provides execution-record evidence comparing baseline trust and zero-trust pipeline modes.",
            "unsafe_wording_to_avoid": "Prototype 4 proves physical robot deployment safety.",
        },
        {
            "claim": "Prototype 4 shows unsafe false accepts reduced from baseline to zero-trust pipeline.",
            "status": false_accept_reduction_status,
            "evidence_source": "Prototype 4 execution comparison grouped by pipeline mode.",
            "safe_dissertation_wording": "In the available Prototype 4 execution records, unsafe false accepts are reduced from the baseline trust mode to zero in the zero-trust pipeline.",
            "unsafe_wording_to_avoid": "Zero-trust eliminates every possible unsafe robot action.",
        },
        {
            "claim": "Phase 4.7 provides ambiguity-adaptive gating evidence.",
            "status": p47_status,
            "evidence_source": "Phase 4.7 ambiguity_gate_summary.json.",
            "safe_dissertation_wording": "Phase 4.7 reports ambiguity-adaptive EXECUTE, CLARIFY, and REJECT decisions for the evaluated command set.",
            "unsafe_wording_to_avoid": "Phase 4.7 proves natural-language ambiguity is solved generally.",
        },
        {
            "claim": "Phase 4.8 provides simulated clarification recovery evidence.",
            "status": p48_status,
            "evidence_source": "Phase 4.8 clarification_recovery_summary.json.",
            "safe_dissertation_wording": "Phase 4.8 reports simulated clarification recovery on the evaluated clarification cases.",
            "unsafe_wording_to_avoid": "Phase 4.8 proves live human-dialogue recovery.",
        },
        {
            "claim": "Phase 4.9 provides formal safety specification evidence.",
            "status": p49_status,
            "evidence_source": "Phase 4.9 formal_safety_audit_summary.json.",
            "safe_dissertation_wording": "Phase 4.9 reports formal safety cases and unsafe-case rejection evidence.",
            "unsafe_wording_to_avoid": "Phase 4.9 is a complete formal proof of robot safety.",
        },
    ]

    if quantisation.get("quantisation_overall") == "COMPLETE_CUSTOM_EVIDENCE":
        rows.append(
            {
                "claim": "FP16/INT8/INT4 custom precision artifact evidence is present.",
                "status": "PROVEN",
                "evidence_source": "; ".join(
                    quantisation.get("custom_precision_metadata_files", [])
                ),
                "safe_dissertation_wording": "Complete custom precision evidence was recovered for FP16, INT8 and INT4 using explicit Prototype 5 metadata precision fields.",
                "unsafe_wording_to_avoid": "Do not describe this as built-in Foundry Local catalogue precision metadata or infer precision from CPU/GPU model labels.",
            }
        )
        rows.append(
            {
                "claim": "Built-in Foundry Local precision metadata is missing.",
                "status": "MISSING",
                "evidence_source": "No built-in Foundry catalogue precision field was available in the loaded evidence.",
                "safe_dissertation_wording": "Built-in Foundry Local catalogue metadata did not expose explicit precision fields; the precision claim is based on custom Prototype 5 artifacts.",
                "unsafe_wording_to_avoid": "Built-in Foundry Local CPU/GPU model labels prove FP16, INT8, or INT4 precision.",
            }
        )
    else:
        rows.append(
            {
                "claim": "FP16/INT8/INT4 quantisation comparison is missing.",
                "status": "MISSING",
                "evidence_source": "No complete explicit Prototype 5 custom precision metadata set found.",
                "safe_dissertation_wording": "FP16/INT8/INT4 quantisation evidence is missing or incomplete.",
                "unsafe_wording_to_avoid": "Do not claim quantisation comparison results without explicit evidence.",
            }
        )

    phi_status = str(phi.get("phi_status", "MISSING"))
    if phi_status in {"PRESENT", "PARTIAL"}:
        rows.append(
            {
                "claim": "Phi-family evaluation evidence is present.",
                "status": phi_status,
                "evidence_source": "; ".join(phi.get("output_files_present", [])),
                "safe_dissertation_wording": (
                    "Prototype 5 recovered Phi-family Foundry Local response evidence. "
                    "Semantic validity remains NOT_EVALUATED."
                ),
                "unsafe_wording_to_avoid": "Do not claim semantic validity, safety performance, or full Phi evaluation beyond recorded Foundry Local responses.",
            }
        )
    elif phi_status == "FAILED":
        rows.append(
            {
                "claim": "Phi-family recovery was attempted but failed.",
                "status": "NEEDS_REVIEW",
                "evidence_source": "; ".join(phi.get("output_files_present", [])),
                "safe_dissertation_wording": "Phi-family recovery was attempted, but no usable real Phi response evidence was recovered.",
                "unsafe_wording_to_avoid": "Do not claim Phi-family evaluation evidence.",
            }
        )
    else:
        rows.append(
            {
                "claim": "Phi-family evaluation is missing.",
                "status": "MISSING",
                "evidence_source": "No real Phi-family Foundry Local response evidence found.",
                "safe_dissertation_wording": "Phi-family evaluation is missing.",
                "unsafe_wording_to_avoid": "Do not claim Phi-family model evaluation.",
            }
        )

    cloud_status = str(mode_c.get("cloud_baseline_status", "MISSING"))
    if cloud_status == "NOT_RUN_API_KEY_MISSING":
        rows.append(
            {
                "claim": "Cloud baseline was not run because OPENAI_API_KEY was missing.",
                "status": "FUTURE_WORK",
                "evidence_source": "; ".join(mode_c.get("output_files_present", [])),
                "safe_dissertation_wording": "Prototype 5 Mode C generated local-vs-cloud fallback outputs, but cloud baseline execution was not run because no API key was present.",
                "unsafe_wording_to_avoid": "Do not claim cloud-vs-local performance comparison from the fallback run.",
            }
        )
    elif cloud_status in {"PRESENT", "PARTIAL", "COMPLETE"}:
        rows.append(
            {
                "claim": "Cloud baseline request-level evidence is available.",
                "status": "PROVEN" if cloud_status == "COMPLETE" else cloud_status,
                "evidence_source": "; ".join(mode_c.get("output_files_present", [])),
                "safe_dissertation_wording": "Prototype 5 Mode C records request-level cloud baseline evidence with semantic validity marked NOT_EVALUATED.",
                "unsafe_wording_to_avoid": "Do not claim semantic equivalence or safety superiority from request-level cloud outputs alone.",
            }
        )
    else:
        rows.append(
            {
                "claim": "cloud-vs-local comparison is missing.",
                "status": "MISSING",
                "evidence_source": "; ".join(mode_c.get("output_files_present", [])),
                "safe_dissertation_wording": "cloud-vs-local comparison is missing.",
                "unsafe_wording_to_avoid": "Do not claim cloud-vs-local performance or safety comparison.",
            }
        )

    if mode_d.get("mode_d_status") == "COMPLETE_LIVE_PROFILE":
        rows.append(
            {
                "claim": "Live Foundry Local resource profiling completed",
                "status": "PROVEN",
                "evidence_source": "mode_d_final_evidence_summary.json",
                "safe_dissertation_wording": (
                    "Prototype 5 Mode D completed live Foundry Local resource profiling, "
                    f"with {mode_d.get('live_foundry_successful_requests', 'NOT_AVAILABLE')}/"
                    f"{mode_d.get('live_foundry_total_commands', 'NOT_AVAILABLE')} successful requests, "
                    f"JSON-valid rate {mode_d.get('live_foundry_json_valid_rate', 'NOT_AVAILABLE')}, "
                    f"mean latency {mode_d.get('live_foundry_mean_latency_ms', 'NOT_AVAILABLE')} ms, "
                    "and normalized mean CPU "
                    f"{mode_d.get('live_foundry_normalized_mean_cpu_percent', 'NOT_AVAILABLE')}%."
                ),
                "unsafe_wording_to_avoid": "Do not generalise Mode D live profiling beyond the measured local machine, Foundry process, and command set.",
            }
        )
    else:
        rows.append(
            {
                "claim": "Live Foundry Local resource profiling is missing.",
                "status": "MISSING",
                "evidence_source": "; ".join(mode_d.get("output_files_present", [])),
                "safe_dissertation_wording": "Live Foundry Local resource profiling is missing.",
                "unsafe_wording_to_avoid": "Do not claim live local resource utilisation evidence.",
            }
        )

    missing_claims = [
        ("physical robot execution is not proven.", "Do not claim physical robot execution or deployment validation."),
    ]
    if mode_d.get("mode_d_status") != "COMPLETE_LIVE_PROFILE":
        missing_claims = [
            ("GPU/NPU profiling is missing.", "Do not claim GPU or NPU profiling evidence."),
            ("memory footprint measurement is missing.", "Do not claim measured memory footprint."),
            *missing_claims,
        ]
    for claim, unsafe in missing_claims:
        rows.append(
            {
                "claim": claim,
                "status": "MISSING",
                "evidence_source": "No explicit Prototype 5 input evidence found.",
                "safe_dissertation_wording": claim,
                "unsafe_wording_to_avoid": unsafe,
            }
        )

    return Table(
        rows,
        [
            "claim",
            "status",
            "evidence_source",
            "safe_dissertation_wording",
            "unsafe_wording_to_avoid",
        ],
    )
