"""Small table helper used to keep Prototype 5 standard-library only."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Iterable


class Table:
    def __init__(self, rows: Iterable[dict[str, Any]] | None = None, columns: list[str] | None = None):
        self.rows = list(rows or [])
        if columns is not None:
            self.columns = list(columns)
        else:
            seen: list[str] = []
            for row in self.rows:
                for key in row:
                    if key not in seen:
                        seen.append(key)
            self.columns = seen

    @property
    def empty(self) -> bool:
        return len(self.rows) == 0

    def __len__(self) -> int:
        return len(self.rows)

    def head(self, max_rows: int | None = None) -> "Table":
        if max_rows is None:
            return self
        return Table(self.rows[:max_rows], self.columns)

    def to_csv(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=self.columns, extrasaction="ignore")
            writer.writeheader()
            for row in self.rows:
                writer.writerow({column: row.get(column, "") for column in self.columns})


def read_csv_table(path: str | Path) -> Table:
    path = Path(path)
    if not path.exists():
        return Table()
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return Table(list(reader), reader.fieldnames or [])


def numeric(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def integer(value: Any) -> int | None:
    number = numeric(value)
    return int(number) if number is not None else None


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def group_rows(rows: Iterable[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(str(row.get(key, "")), []).append(row)
    return groups
