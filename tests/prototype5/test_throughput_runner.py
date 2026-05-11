import csv
import json
import shutil
from pathlib import Path

from src.prototype5.throughput_runner import run_throughput_profile


TMP_ROOT = Path("tests/prototype5/_tmp_mode_d_runner")


def _write_phi_rows(path: Path) -> str:
    rows = [
        {
            "command_id": "C01",
            "command_text": "Pick up the medicine cup",
            "model_id": "Phi-3-mini-4k-instruct-generic-cpu:3",
            "request_success": True,
            "json_valid": True,
            "latency_ms": 1000,
        },
        {
            "command_id": "C02",
            "command_text": "Place the pill box on the tray",
            "model_id": "Phi-3-mini-4k-instruct-generic-cpu:3",
            "request_success": True,
            "json_valid": False,
            "latency_ms": 2000,
        },
    ]
    content = "\n".join(json.dumps(row) for row in rows) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return content


def test_throughput_runner_generates_mode_d_outputs_without_cloud_or_foundry(monkeypatch):
    from src.prototype5 import throughput_runner

    shutil.rmtree(TMP_ROOT, ignore_errors=True)
    phi_path = TMP_ROOT / "phi" / "phi_recovery_results.jsonl"
    phi_contents = _write_phi_rows(phi_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("MODE_D_LIVE_LOCAL_RUN", raising=False)

    result = run_throughput_profile(
        output_dir=TMP_ROOT / "mode_d",
        docs_dir=TMP_ROOT / "docs",
        phi_results_path=phi_path,
    )

    throughput_path = TMP_ROOT / "mode_d" / "throughput_stability.csv"
    samples_path = TMP_ROOT / "mode_d" / "resource_profile_samples.csv"
    summary_csv_path = TMP_ROOT / "mode_d" / "resource_profile_summary.csv"
    summary_json_path = TMP_ROOT / "mode_d" / "mode_d_summary.json"
    docs_path = TMP_ROOT / "docs" / "prototype5_resource_profile.md"

    assert result["summary"]["workload_mode"] == "evidence_replay"
    assert result["summary"]["live_local_status"] == "NOT_REQUESTED"
    assert result["summary"]["total_commands"] == 2
    assert throughput_path.exists()
    assert samples_path.exists()
    assert summary_csv_path.exists()
    assert summary_json_path.exists()
    assert docs_path.exists()
    assert "evidence replay workload; no new model call performed" in throughput_path.read_text(encoding="utf-8")
    assert phi_path.read_text(encoding="utf-8") == phi_contents
    assert not (TMP_ROOT / "mode_c").exists()
    shutil.rmtree(TMP_ROOT, ignore_errors=True)


def test_throughput_csv_has_one_row_per_replay_unit(monkeypatch):
    shutil.rmtree(TMP_ROOT, ignore_errors=True)
    phi_path = TMP_ROOT / "phi" / "phi_recovery_results.jsonl"
    _write_phi_rows(phi_path)
    monkeypatch.delenv("MODE_D_LIVE_LOCAL_RUN", raising=False)
    run_throughput_profile(
        output_dir=TMP_ROOT / "mode_d",
        docs_dir=TMP_ROOT / "docs",
        phi_results_path=phi_path,
    )
    with (TMP_ROOT / "mode_d" / "throughput_stability.csv").open("r", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 2
    assert rows[0]["workload_mode"] == "evidence_replay"
    assert rows[0]["latency_ms"] == "1000"
    assert rows[1]["json_valid"] == "False"
    shutil.rmtree(TMP_ROOT, ignore_errors=True)


def test_live_local_request_records_not_implemented_and_uses_replay(monkeypatch):
    shutil.rmtree(TMP_ROOT, ignore_errors=True)
    phi_path = TMP_ROOT / "phi" / "phi_recovery_results.jsonl"
    _write_phi_rows(phi_path)
    monkeypatch.setenv("MODE_D_LIVE_LOCAL_RUN", "true")
    result = run_throughput_profile(
        output_dir=TMP_ROOT / "mode_d",
        docs_dir=TMP_ROOT / "docs",
        phi_results_path=phi_path,
    )
    assert result["summary"]["workload_mode"] == "evidence_replay"
    assert result["summary"]["live_local_status"] == "NOT_IMPLEMENTED"
    shutil.rmtree(TMP_ROOT, ignore_errors=True)
