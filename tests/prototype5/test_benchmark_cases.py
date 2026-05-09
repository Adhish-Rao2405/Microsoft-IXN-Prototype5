import json
import shutil
from pathlib import Path

from src.prototype5.benchmark_cases import load_benchmark_cases


TMP_ROOT = Path("tests/prototype5/_tmp_benchmark")


def test_load_benchmark_cases_normalises_id_and_command():
    shutil.rmtree(TMP_ROOT, ignore_errors=True)
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    path = TMP_ROOT / "benchmark_v1.json"
    path.write_text(
        json.dumps([{"id": "C01", "command": "Pick up the medicine cup"}]),
        encoding="utf-8",
    )

    result = load_benchmark_cases([path])

    assert result["status"] == "PRESENT"
    assert result["cases"] == [
        {
            "command_id": "C01",
            "command_text": "Pick up the medicine cup",
            "difficulty": "",
            "category": "",
        }
    ]
    shutil.rmtree(TMP_ROOT, ignore_errors=True)


def test_load_benchmark_cases_reports_missing():
    shutil.rmtree(TMP_ROOT, ignore_errors=True)
    result = load_benchmark_cases([TMP_ROOT / "missing.json"])
    assert result["status"] == "BENCHMARK_MISSING"
    assert result["cases"] == []
