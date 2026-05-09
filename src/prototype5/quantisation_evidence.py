"""Mode B custom precision evidence recovery for Prototype 5."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .evidence_paths import CUSTOM_QUANTISATION_DIR


REQUIRED_PRECISIONS = ("fp16", "int8", "int4")


def normalize_precision(value: Any) -> str | None:
    if value is None:
        return None
    precision = str(value).strip().lower().replace("-", "").replace("_", "")
    return precision if precision in REQUIRED_PRECISIONS else None


def precision_from_metadata(metadata: dict[str, Any]) -> str | None:
    """Return precision only from explicit metadata fields.

    Model IDs, names, CPU/GPU labels, and other route labels are deliberately
    ignored so device placement cannot be misclassified as quantisation evidence.
    """

    return normalize_precision(metadata.get("precision"))


def scan_custom_quantisation_metadata(
    directory: str | Path = CUSTOM_QUANTISATION_DIR,
) -> list[dict[str, Any]]:
    directory = Path(directory)
    if not directory.exists():
        return []

    rows: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        try:
            metadata = json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError:
            continue
        precision = precision_from_metadata(metadata)
        if precision is None:
            continue
        model_output_path = metadata.get("model_output_path", "")
        rows.append(
            {
                "precision": precision,
                "metadata_path": str(path),
                "name": metadata.get("Name", ""),
                "source_model": metadata.get("source_model", ""),
                "generated_by": metadata.get("generated_by", ""),
                "generation_route": metadata.get("olive_command")
                or metadata.get("quantization_method", ""),
                "model_output_path": model_output_path,
                "model_output_exists": Path(model_output_path).exists()
                if model_output_path
                else False,
                "important_scope_note": metadata.get("important_scope_note", ""),
            }
        )
    return rows


def classify_quantisation_evidence(
    metadata_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    present_by_precision: dict[str, list[dict[str, Any]]] = {
        precision: [] for precision in REQUIRED_PRECISIONS
    }
    for row in metadata_rows:
        precision = normalize_precision(row.get("precision"))
        if precision in present_by_precision:
            present_by_precision[precision].append(row)

    statuses = {
        f"{precision}_evidence": "PRESENT" if present_by_precision[precision] else "MISSING"
        for precision in REQUIRED_PRECISIONS
    }
    all_present = all(status == "PRESENT" for status in statuses.values())
    if all_present:
        overall = "COMPLETE_CUSTOM_EVIDENCE"
    elif any(status == "PRESENT" for status in statuses.values()):
        overall = "PARTIAL_CUSTOM_EVIDENCE"
    else:
        overall = "MISSING"

    return {
        **statuses,
        "quantisation_overall": overall,
        "built_in_foundry_precision_metadata": "MISSING",
        "custom_precision_artifacts": "PRESENT" if metadata_rows else "MISSING",
        "custom_precision_metadata_files": [
            row["metadata_path"] for row in metadata_rows if row.get("metadata_path")
        ],
        "precision_sources": {
            precision: present_by_precision[precision] for precision in REQUIRED_PRECISIONS
        },
        "safe_scope": (
            "Complete custom precision evidence was recovered for FP16, INT8 and INT4. "
            "Built-in Foundry Local catalogue metadata did not expose explicit precision fields; "
            "therefore the precision claim is based on custom Prototype 5 artifacts, "
            "not inferred CPU/GPU model labels."
        )
        if all_present
        else (
            "Custom precision evidence is incomplete. Do not infer quantisation from "
            "CPU/GPU labels or model IDs."
        ),
    }


def collect_quantisation_evidence(
    directory: str | Path = CUSTOM_QUANTISATION_DIR,
) -> dict[str, Any]:
    return classify_quantisation_evidence(scan_custom_quantisation_metadata(directory))
