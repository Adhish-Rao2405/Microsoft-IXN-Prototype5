import json
import shutil
from pathlib import Path

import pytest

from src.prototype5.quantisation_evidence import (
    classify_quantisation_evidence,
    precision_from_metadata,
    scan_custom_quantisation_metadata,
)


TMP_ROOT: Path


@pytest.fixture(autouse=True)
def isolated_tmp_root(tmp_path):
    global TMP_ROOT
    TMP_ROOT = tmp_path / "quantisation"


def _write_metadata(name: str, precision: str) -> None:
    (TMP_ROOT / name).write_text(
        json.dumps(
            {
                "Name": name,
                "precision": precision,
                "generated_by": "test",
                "model_output_path": str(TMP_ROOT / precision),
            }
        ),
        encoding="utf-8",
    )


def test_metadata_precision_fp16_int8_int4_is_detected():
    assert precision_from_metadata({"Name": "qwen-cpu", "precision": "fp16"}) == "fp16"
    assert precision_from_metadata({"Name": "qwen-gpu", "precision": "int8"}) == "int8"
    assert precision_from_metadata({"Name": "qwen-any", "precision": "int4"}) == "int4"


def test_all_three_precisions_produce_complete_custom_evidence():
    shutil.rmtree(TMP_ROOT, ignore_errors=True)
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    _write_metadata("fp16.json", "fp16")
    _write_metadata("int8.json", "int8")
    _write_metadata("int4.json", "int4")

    rows = scan_custom_quantisation_metadata(TMP_ROOT)
    summary = classify_quantisation_evidence(rows)

    assert summary["fp16_evidence"] == "PRESENT"
    assert summary["int8_evidence"] == "PRESENT"
    assert summary["int4_evidence"] == "PRESENT"
    assert summary["quantisation_overall"] == "COMPLETE_CUSTOM_EVIDENCE"
    assert summary["custom_precision_artifacts"] == "PRESENT"
    assert summary["built_in_foundry_precision_metadata"] == "MISSING"
    shutil.rmtree(TMP_ROOT, ignore_errors=True)


def test_cpu_gpu_only_model_ids_do_not_count_as_quantisation_evidence():
    assert precision_from_metadata({"Name": "foundry:qwen2.5-0.5b:cpu"}) is None
    assert precision_from_metadata({"Name": "foundry:qwen2.5-0.5b:gpu"}) is None
    assert precision_from_metadata({"Name": "qwen2.5-int4-in-name-only"}) is None
    summary = classify_quantisation_evidence(
        [
            {
                "precision": precision_from_metadata({"Name": "foundry:qwen2.5-0.5b:cpu"}),
                "metadata_path": "cpu.json",
            }
        ]
    )
    assert summary["quantisation_overall"] == "MISSING"


def test_run_recovery_prints_summary(capsys, monkeypatch):
    from src.prototype5 import run_recovery

    def fake_run_phi_recovery():
        return {
            "manifest": {
                "phi_status": "MISSING",
                "selected_model": None,
                "summary": {"successful_requests": 0},
            }
        }

    monkeypatch.setattr(run_recovery, "run_phi_recovery", fake_run_phi_recovery)
    monkeypatch.setattr(
        run_recovery,
        "run_local_cloud_comparison",
        lambda: {
            "summary": {
                "mode_c_status": "COMPLETE_WITH_CLOUD_NOT_RUN",
                "cloud_baseline_status": "NOT_RUN_API_KEY_MISSING",
            }
        },
    )
    recovery_main = run_recovery.main
    recovery_main()
    output = capsys.readouterr().out
    assert "Prototype 5 Mode B Recovery: COMPLETE" in output
    assert "Quantisation overall:" in output
