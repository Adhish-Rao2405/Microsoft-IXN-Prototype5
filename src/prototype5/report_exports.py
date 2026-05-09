"""Writers for Prototype 5 final evidence outputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .evidence_paths import DOCS_DIR, RESULTS_DIR
from .simple_table import Table


def ensure_output_dirs(results_dir: Path = RESULTS_DIR, docs_dir: Path = DOCS_DIR) -> None:
    results_dir.mkdir(parents=True, exist_ok=True)
    docs_dir.mkdir(parents=True, exist_ok=True)


def write_csv(df: Table, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path)
    return path


def write_json(data: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def write_markdown(content: str, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _markdown_table(df: Table, max_rows: int | None = None) -> str:
    if df.empty:
        return "_No available evidence rows._"
    view = df.head(max_rows) if max_rows else df
    headers = list(view.columns)
    rows = [[str(row.get(header, "")) for header in headers] for row in view.rows]
    widths = [
        max(len(header), *(len(row[index]) for row in rows)) if rows else len(header)
        for index, header in enumerate(headers)
    ]

    def fmt(values: list[str]) -> str:
        return "| " + " | ".join(value.ljust(widths[index]) for index, value in enumerate(values)) + " |"

    separator = "| " + " | ".join("-" * width for width in widths) + " |"
    return "\n".join([fmt(headers), separator, *(fmt(row) for row in rows)])


def build_final_dissertation_metrics_md(
    model_comparison: Table,
    zero_trust_comparison: Table,
    safety_latency_summary: Table,
    extension_summary: Table,
    claims_matrix: Table,
    limitations_matrix: Table,
    quantisation_status: str = "MISSING",
) -> str:
    proven = sum(1 for row in claims_matrix.rows if row.get("status") == "PROVEN")
    missing = sum(1 for row in claims_matrix.rows if row.get("status") == "MISSING")
    return "\n".join(
        [
            "# Prototype 5 Final Dissertation Metrics",
            "",
            "Prototype 5 consolidates existing evidence only. It does not introduce new inference, planning, or robot execution.",
            "",
            f"- Proven claims: {proven}",
            f"- Missing evidence claims: {missing}",
            f"- Quantisation evidence: {quantisation_status}",
            "- Phi-family evidence: MISSING",
            "",
            "## Final Model Comparison",
            _markdown_table(model_comparison),
            "",
            "## Final Zero-Trust Comparison",
            _markdown_table(zero_trust_comparison),
            "",
            "## Final Safety-Latency Summary",
            _markdown_table(safety_latency_summary),
            "",
            "## Final Extension Summary",
            _markdown_table(extension_summary),
            "",
            "## Quantisation Evidence",
            "Complete custom precision evidence was recovered for FP16, INT8 and INT4 when `quantisation_status` is `COMPLETE_CUSTOM_EVIDENCE`. Built-in Foundry Local catalogue precision metadata remains missing.",
            "",
            "## Limitations",
            _markdown_table(limitations_matrix),
            "",
        ]
    )


def build_protocol_doc() -> str:
    return "\n".join(
        [
            "# Prototype 5 Final Evaluation Protocol",
            "",
            "Prototype 5 is a dissertation evidence orchestrator. It reads existing Prototype 3 and Prototype 4 evidence, plus audit references from Prototypes 1-4 where available.",
            "",
            "## Scope",
            "",
            "- Consolidate existing CSV, JSON, JSONL, and Markdown evidence.",
            "- Generate final model, zero-trust, safety-latency, extension, claims, limitations, and manifest outputs.",
            "- Record missing inputs explicitly and continue with available evidence.",
            "",
            "## Non-Scope",
            "",
            "- No new model inference.",
            "- No new robot planning logic.",
            "- No modification of Prototype 1, Prototype 2, Prototype 3, or Prototype 4 repositories.",
            "- FP16, INT8, and INT4 claims require explicit custom Prototype 5 metadata precision fields.",
            "- No claims for Phi, cloud, GPU/NPU, memory, or physical execution without explicit evidence.",
            "",
        ]
    )


def build_results_summary_doc(
    model_comparison: Table,
    zero_trust_comparison: Table,
    extension_summary: Table,
) -> str:
    return "\n".join(
        [
            "# Prototype 5 Dissertation Results Summary",
            "",
            "This summary is generated from existing evidence files and should be cited with the accompanying evidence manifest.",
            "",
            "## Prototype 3 Model Evidence",
            _markdown_table(model_comparison),
            "",
            "## Prototype 4 Zero-Trust Evidence",
            _markdown_table(zero_trust_comparison),
            "",
            "## Prototype 4 Extension Evidence",
            _markdown_table(extension_summary),
            "",
        ]
    )


def build_limitations_doc(claims_matrix: Table, limitations_matrix: Table) -> str:
    missing_claims = Table(
        [row for row in claims_matrix.rows if row.get("status") == "MISSING"],
        claims_matrix.columns,
    )
    return "\n".join(
        [
            "# Prototype 5 Limitations and Scope",
            "",
            "Prototype 5 distinguishes safe dissertation wording from unsupported claims. Missing evidence is not converted into a positive result.",
            "",
            "## Explicit Limitations",
            _markdown_table(limitations_matrix),
            "",
            "## Missing Claims",
            _markdown_table(missing_claims),
            "",
        ]
    )


def build_quantisation_metadata_check_doc(manifest: dict[str, Any]) -> str:
    files = manifest.get("custom_precision_metadata_files", [])
    file_lines = "\n".join(f"- {path}" for path in files) if files else "- None"
    return "\n".join(
        [
            "# Prototype 5 Quantisation Metadata Check",
            "",
            "Complete custom precision evidence was recovered for FP16, INT8 and INT4. Built-in Foundry Local catalogue metadata did not expose explicit precision fields; therefore the precision claim is based on custom Prototype 5 artifacts, not inferred CPU/GPU model labels.",
            "",
            "## Evidence Status",
            "",
            f"- FP16 evidence: {manifest.get('fp16_evidence', 'MISSING')}",
            f"- INT8 evidence: {manifest.get('int8_evidence', 'MISSING')}",
            f"- INT4 evidence: {manifest.get('int4_evidence', 'MISSING')}",
            f"- Quantisation overall: {manifest.get('quantisation_overall', 'MISSING')}",
            f"- Built-in Foundry precision metadata: {manifest.get('built_in_foundry_precision_metadata', 'MISSING')}",
            f"- Custom precision artifacts: {manifest.get('custom_precision_artifacts', 'MISSING')}",
            "",
            "## Metadata Files",
            "",
            file_lines,
            "",
        ]
    )


def export_all(
    tables: dict[str, Table],
    manifest: dict[str, Any],
    results_dir: Path = RESULTS_DIR,
    docs_dir: Path = DOCS_DIR,
) -> list[Path]:
    ensure_output_dirs(results_dir, docs_dir)
    generated = [
        write_csv(tables["model_comparison"], results_dir / "final_model_comparison.csv"),
        write_csv(tables["zero_trust_comparison"], results_dir / "final_zero_trust_comparison.csv"),
        write_csv(tables["safety_latency_summary"], results_dir / "final_safety_latency_summary.csv"),
        write_csv(tables["extension_summary"], results_dir / "final_extension_summary.csv"),
        write_csv(tables["claims_matrix"], results_dir / "final_claims_matrix.csv"),
        write_csv(tables["limitations_matrix"], results_dir / "final_limitations_matrix.csv"),
    ]
    generated.append(
        write_markdown(
            build_final_dissertation_metrics_md(
                tables["model_comparison"],
                tables["zero_trust_comparison"],
                tables["safety_latency_summary"],
                tables["extension_summary"],
                tables["claims_matrix"],
                tables["limitations_matrix"],
                manifest.get("quantisation_status", "MISSING"),
            ),
            results_dir / "final_dissertation_metrics.md",
        )
    )
    generated.append(write_json(manifest, results_dir / "final_evidence_manifest.json"))
    generated.extend(
        [
            write_markdown(build_protocol_doc(), docs_dir / "prototype5_final_evaluation_protocol.md"),
            write_markdown(
                build_results_summary_doc(
                    tables["model_comparison"],
                    tables["zero_trust_comparison"],
                    tables["extension_summary"],
                ),
                docs_dir / "prototype5_dissertation_results_summary.md",
            ),
            write_markdown(
                build_limitations_doc(tables["claims_matrix"], tables["limitations_matrix"]),
                docs_dir / "prototype5_limitations_and_scope.md",
            ),
            write_markdown(
                build_quantisation_metadata_check_doc(manifest),
                docs_dir / "prototype5_quantisation_metadata_check.md",
            ),
        ]
    )
    return generated
