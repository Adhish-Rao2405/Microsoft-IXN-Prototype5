"""Benchmark loading for Prototype 5 Phi recovery."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


BENCHMARK_PATHS = [
    Path(r"C:\Users\reach\Microsoft-IXN-Prototype3\prototype3\datasets\benchmark_v1.json"),
    Path(r"C:\Users\reach\Microsoft-IXN-Prototype3\datasets\benchmark_v1.json"),
]


def load_benchmark_cases(paths: list[Path] | None = None) -> dict[str, Any]:
    candidates = paths or BENCHMARK_PATHS
    for path in candidates:
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, list):
            return {
                "status": "BENCHMARK_INVALID",
                "path": str(path),
                "cases": [],
                "error": "Benchmark JSON is not a list.",
            }
        cases = []
        for index, item in enumerate(payload, start=1):
            if not isinstance(item, dict):
                continue
            command = item.get("command") or item.get("command_text")
            if not command:
                continue
            cases.append(
                {
                    "command_id": str(item.get("id") or item.get("command_id") or f"C{index:02d}"),
                    "command_text": str(command),
                    "difficulty": item.get("difficulty", ""),
                    "category": item.get("category", ""),
                }
            )
        return {"status": "PRESENT", "path": str(path), "cases": cases, "error": ""}
    return {
        "status": "BENCHMARK_MISSING",
        "path": "",
        "cases": [],
        "error": "No benchmark_v1.json found in expected Prototype 3 paths.",
    }
