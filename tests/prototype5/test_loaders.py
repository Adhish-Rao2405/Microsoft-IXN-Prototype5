import json
import shutil
from pathlib import Path

import pytest

from src.prototype5.loaders import load_csv, load_evidence, load_json, load_jsonl, load_markdown

TMP_ROOT: Path


@pytest.fixture(autouse=True)
def isolated_tmp_root(tmp_path):
    global TMP_ROOT
    TMP_ROOT = tmp_path / "loaders"


def test_loaders_handle_missing_optional_files():
    shutil.rmtree(TMP_ROOT, ignore_errors=True)
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    assert load_csv(TMP_ROOT / "missing.csv").empty
    assert load_json(TMP_ROOT / "missing.json") is None
    assert load_jsonl(TMP_ROOT / "missing.jsonl") == []
    assert load_markdown(TMP_ROOT / "missing.md") == ""
    shutil.rmtree(TMP_ROOT, ignore_errors=True)


def test_load_evidence_uses_file_extensions():
    shutil.rmtree(TMP_ROOT, ignore_errors=True)
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    csv_path = TMP_ROOT / "evidence.csv"
    json_path = TMP_ROOT / "evidence.json"
    jsonl_path = TMP_ROOT / "evidence.jsonl"
    md_path = TMP_ROOT / "evidence.md"
    csv_path.write_text("model,total_records\nm1,1\n", encoding="utf-8")
    json_path.write_text(json.dumps({"ok": True}), encoding="utf-8")
    jsonl_path.write_text('{"a": 1}\n{"a": 2}\n', encoding="utf-8")
    md_path.write_text("# Evidence", encoding="utf-8")

    evidence = load_evidence(
        {
            "csv": csv_path,
            "json": json_path,
            "jsonl": jsonl_path,
            "md": md_path,
            "missing": TMP_ROOT / "missing.csv",
        }
    )

    assert evidence["csv"].rows[0]["model"] == "m1"
    assert evidence["json"]["ok"] is True
    assert len(evidence["jsonl"]) == 2
    assert evidence["md"] == "# Evidence"
    assert evidence["missing"].empty
    shutil.rmtree(TMP_ROOT, ignore_errors=True)
