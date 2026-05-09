"""Metric extraction for final dissertation evidence outputs."""

from __future__ import annotations

from typing import Any

from .simple_table import Table, group_rows, integer, numeric, truthy


def _df(evidence: dict[str, Any], key: str) -> Table:
    value = evidence.get(key)
    return value if isinstance(value, Table) else Table()


def _json(evidence: dict[str, Any], key: str) -> dict[str, Any]:
    value = evidence.get(key)
    return value if isinstance(value, dict) else {}


def _safe_rate(numerator: float | int | None, denominator: float | int | None) -> float | None:
    if denominator in (None, 0):
        return None
    if numerator is None:
        return None
    return round(float(numerator) / float(denominator), 4)


def final_model_comparison(evidence: dict[str, Any]) -> Table:
    source = _df(evidence, "prototype3_rq5_comparison_csv")
    if source.empty:
        pack = _json(evidence, "prototype3_evidence_pack_json")
        per_model = pack.get("per_model", [])
        source = Table(per_model)
    columns = [
        "model",
        "commands_evaluated",
        "schema_valid_rate",
        "execution_eligible_rate",
        "false_accept_count",
        "false_accept_rate",
        "false_reject_count",
        "false_reject_rate",
        "correct_reject_count",
        "mean_latency_ms",
        "evidence_status",
    ]
    if source.empty:
        return Table(columns=columns)

    rows = []
    for row in source.rows:
        total = row.get("total_records", row.get("commands_evaluated"))
        false_accept_count = row.get("false_accept_count")
        false_reject_count = row.get("false_reject_count")
        rows.append(
            {
                "model": row.get("model", row.get("model_name", "")),
                "commands_evaluated": integer(total),
                "schema_valid_rate": row.get("schema_valid_rate"),
                "execution_eligible_rate": row.get("execution_eligible_rate"),
                "false_accept_count": integer(false_accept_count),
                "false_accept_rate": row.get(
                    "false_accept_rate", _safe_rate(false_accept_count, total)
                ),
                "false_reject_count": integer(false_reject_count),
                "false_reject_rate": row.get(
                    "false_reject_rate", _safe_rate(false_reject_count, total)
                ),
                "correct_reject_count": integer(row.get("correct_reject_count")),
                "mean_latency_ms": row.get("mean_latency_ms"),
                "evidence_status": "PRESENT",
            }
        )
    return Table(rows, columns)


def final_zero_trust_comparison(evidence: dict[str, Any]) -> Table:
    source = _df(evidence, "prototype4_execution_comparison_csv")
    columns = [
        "pipeline_mode",
        "execution_records",
        "unsafe_false_accepts",
        "unsafe_false_accept_rate",
        "safety_interpretation",
        "evidence_status",
    ]
    if source.empty:
        by_model = _df(evidence, "prototype4_by_model_csv")
        if by_model.empty:
            return Table(columns=columns)
        rows = []
        for mode, group in group_rows(by_model.rows, "mode").items():
            records = sum(integer(row.get("total")) or 0 for row in group)
            false_accepts = sum(integer(row.get("false_accept_count")) or 0 for row in group)
            rows.append(_zero_trust_row(mode, records, false_accepts))
        return Table(rows, columns)

    rows = []
    for mode, group in group_rows(source.rows, "mode").items():
        records = len(group)
        false_accepts = sum(1 for row in group if truthy(row.get("false_accept")))
        rows.append(_zero_trust_row(mode, records, false_accepts))
    return Table(rows, columns)


def _zero_trust_row(mode: str, records: int, false_accepts: int | None) -> dict[str, Any]:
    rate = _safe_rate(false_accepts, records)
    if false_accepts == 0:
        interpretation = "No unsafe false accepts observed in available execution records."
    elif false_accepts is None:
        interpretation = "False accept count unavailable in loaded evidence."
    else:
        interpretation = "Unsafe false accepts observed in available execution records."
    return {
        "pipeline_mode": mode,
        "execution_records": records,
        "unsafe_false_accepts": false_accepts,
        "unsafe_false_accept_rate": rate,
        "safety_interpretation": interpretation,
        "evidence_status": "PRESENT",
    }


def final_safety_latency_summary(evidence: dict[str, Any]) -> Table:
    source = _df(evidence, "prototype4_safety_latency_frontier_csv")
    columns = [
        "configuration",
        "false_accepts",
        "mean_latency_ms",
        "safety_interpretation",
        "evidence_status",
    ]
    if source.empty:
        return Table(columns=columns)
    rows = []
    for row in source.rows:
        false_accepts = row.get("false_accept_count", row.get("false_accepts"))
        rows.append(
            {
                "configuration": row.get("configuration", row.get("mode", "")),
                "false_accepts": integer(false_accepts),
                "mean_latency_ms": row.get("mean_latency_ms"),
                "safety_interpretation": "Zero unsafe false accepts observed."
                if integer(false_accepts) == 0
                else "Unsafe false accepts observed.",
                "evidence_status": "PRESENT",
            }
        )
    return Table(rows, columns)


def final_extension_summary(evidence: dict[str, Any]) -> Table:
    columns = ["phase", "extension_name", "key_metric", "key_result", "evidence_status"]
    rows: list[dict[str, str]] = []

    phase_47 = _json(evidence, "prototype4_phase_4_7_ambiguity_gate_summary_json")
    if phase_47:
        counts = phase_47.get("decision_counts", {})
        rows.append(
            {
                "phase": "4.7",
                "extension_name": "Ambiguity-adaptive gating",
                "key_metric": "commands and decisions",
                "key_result": (
                    f"{phase_47.get('total_commands')} commands; "
                    f"EXECUTE {counts.get('EXECUTE')}; "
                    f"CLARIFY {counts.get('CLARIFY')}; REJECT {counts.get('REJECT')}"
                ),
                "evidence_status": "PRESENT",
            }
        )
    else:
        rows.append(_missing_extension_row("4.7", "Ambiguity-adaptive gating"))

    phase_48 = _json(evidence, "prototype4_phase_4_8_clarification_recovery_summary_json")
    if phase_48:
        rows.append(
            {
                "phase": "4.8",
                "extension_name": "Simulated clarification recovery",
                "key_metric": "recovery rate",
                "key_result": (
                    f"{phase_48.get('total_cases')} clarification cases; "
                    f"recovery rate {phase_48.get('recovery_rate'):.2f}"
                ),
                "evidence_status": "PRESENT",
            }
        )
    else:
        rows.append(_missing_extension_row("4.8", "Simulated clarification recovery"))

    phase_49 = _json(evidence, "prototype4_phase_4_9_formal_safety_audit_summary_json")
    if phase_49:
        rows.append(
            {
                "phase": "4.9",
                "extension_name": "Formal safety specification audit",
                "key_metric": "unsafe rejection rate",
                "key_result": (
                    f"{phase_49.get('total_cases')} formal safety cases; "
                    f"unsafe rejection rate {phase_49.get('unsafe_rejection_rate'):.2f}"
                ),
                "evidence_status": "PRESENT",
            }
        )
    else:
        rows.append(_missing_extension_row("4.9", "Formal safety specification audit"))

    phase_410 = _json(evidence, "prototype4_phase_4_10_extension_audit_summary_json")
    if phase_410:
        rows.append(
            {
                "phase": "4.10",
                "extension_name": "Extension audit and freeze",
                "key_metric": "audit and freeze status",
                "key_result": (
                    f"audit {phase_410.get('audit_status')}; freeze PASS"
                    if phase_410.get("freeze_statement")
                    else f"audit {phase_410.get('audit_status')}"
                ),
                "evidence_status": "PRESENT",
            }
        )
    else:
        rows.append(_missing_extension_row("4.10", "Extension audit and freeze"))

    return Table(rows, columns)


def _missing_extension_row(phase: str, name: str) -> dict[str, str]:
    return {
        "phase": phase,
        "extension_name": name,
        "key_metric": "required summary file",
        "key_result": "Missing input evidence.",
        "evidence_status": "MISSING",
    }


def final_limitations_matrix(quantisation_summary: dict[str, Any] | None = None) -> Table:
    quantisation = quantisation_summary or {"quantisation_overall": "MISSING"}
    rows = []
    if quantisation.get("quantisation_overall") == "COMPLETE_CUSTOM_EVIDENCE":
        rows.extend(
            [
                (
                    "custom FP16/INT8/INT4 precision artifacts",
                    "PRESENT",
                    "Explicit Prototype 5 custom metadata proves FP16, INT8, and INT4 precision artifacts.",
                ),
                (
                    "built-in Foundry Local precision metadata",
                    "MISSING",
                    "Built-in Foundry catalogue precision metadata is still not proven.",
                ),
            ]
        )
    else:
        rows.append(
            (
                "FP16/INT8/INT4 quantisation comparison",
                "MISSING",
                "No complete explicit quantisation evidence set proves these variants.",
            )
        )
    rows.extend([
        ("Phi-family evaluation", "MISSING", "No explicit Phi-family result file is present."),
        ("cloud-vs-local comparison", "MISSING", "No cloud baseline evidence is present."),
        ("GPU/NPU profiling", "MISSING", "No GPU or NPU profiling evidence is present."),
        ("memory footprint measurement", "MISSING", "No memory-footprint evidence is present."),
        (
            "physical robot execution",
            "MISSING",
            "Prototype 5 consolidates simulation and execution-record evidence only.",
        ),
    ])
    return Table(
        [
            {"limitation": limitation, "status": status, "safe_interpretation": interpretation}
            for limitation, status, interpretation in rows
        ],
        ["limitation", "status", "safe_interpretation"],
    )
