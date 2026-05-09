"""Defensive evidence loaders for Prototype 5."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .evidence_paths import EXPECTED_INPUT_PATHS
from .simple_table import Table, read_csv_table


def load_csv(path: str | Path) -> Table:
    return read_csv_table(path)


def load_json(path: str | Path) -> dict[str, Any] | list[Any] | None:
    path = Path(path)
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    path = Path(path)
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_markdown(path: str | Path) -> str:
    path = Path(path)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def load_evidence(
    expected_paths: dict[str, Path] | None = None,
) -> dict[str, Table | dict[str, Any] | list[Any] | str | None]:
    """Load every known evidence file that is present.

    Missing optional files are represented by empty objects appropriate to their
    extension, so downstream reporting can continue and mark gaps explicitly.
    """

    paths = expected_paths or EXPECTED_INPUT_PATHS
    evidence: dict[str, Table | dict[str, Any] | list[Any] | str | None] = {}
    for name, path in paths.items():
        suffix = path.suffix.lower()
        if suffix == ".csv":
            evidence[name] = load_csv(path)
        elif suffix == ".json":
            evidence[name] = load_json(path)
        elif suffix == ".jsonl":
            evidence[name] = load_jsonl(path)
        elif suffix == ".md":
            evidence[name] = load_markdown(path)
        else:
            evidence[name] = path.read_text(encoding="utf-8") if path.exists() else None
    return evidence
