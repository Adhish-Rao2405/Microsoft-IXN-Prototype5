import json
import shutil
from pathlib import Path

from src.prototype5.phi_recovery_metrics import (
    collect_phi_evidence,
    load_phi_results,
    summarise_phi_results,
)
from src.prototype5.phi_recovery_runner import (
    _extract_response_text,
    _parse_json_response,
    run_phi_recovery,
    strip_json_fences,
)


TMP_ROOT = Path("tests/prototype5/_tmp_phi_metrics")


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": '```json\n{"action": "move", "object": "red cube"}\n```'
                        }
                    }
                ]
            }
        ).encode("utf-8")


def test_summarise_phi_results_present_for_all_successes():
    results = [
        {
            "model_id": "Phi-3",
            "request_success": True,
            "parse_success": True,
            "json_valid": True,
            "latency_ms": 10,
        }
        for _ in range(30)
    ]
    summary = summarise_phi_results(results, expected_commands=30)
    assert summary["evidence_status"] == "PRESENT"
    assert summary["parse_success_rate"] == 1.0
    assert summary["json_valid_rate"] == 1.0


def test_summarise_phi_results_partial_for_some_successes():
    summary = summarise_phi_results(
        [
            {"model_id": "Phi-3", "request_success": True, "parse_success": False, "json_valid": False},
            {"model_id": "Phi-3", "request_success": False, "parse_success": False, "json_valid": False},
        ],
        expected_commands=30,
    )
    assert summary["evidence_status"] == "PARTIAL"
    assert summary["successful_requests"] == 1


def test_collect_phi_evidence_from_jsonl_outputs():
    shutil.rmtree(TMP_ROOT, ignore_errors=True)
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    results_path = TMP_ROOT / "phi_recovery_results.jsonl"
    rows = [
        {
            "model_id": "Phi-3",
            "request_success": True,
            "parse_success": True,
            "json_valid": True,
            "latency_ms": 5,
        }
    ]
    results_path.write_text(json.dumps(rows[0]) + "\n", encoding="utf-8")

    loaded = load_phi_results(results_path)
    evidence = collect_phi_evidence(TMP_ROOT)

    assert loaded == rows
    assert evidence["phi_status"] == "PARTIAL"
    assert evidence["real_output_count"] == 1
    shutil.rmtree(TMP_ROOT, ignore_errors=True)


def test_strip_json_fences_handles_json_fenced_content():
    text = '```json\n{"action": "move"}\n```'
    assert strip_json_fences(text) == '{"action": "move"}'
    parse_success, json_valid, _ = _parse_json_response(text)
    assert parse_success is True
    assert json_valid is True


def test_strip_json_fences_handles_plain_json():
    text = '  {"action": "pick"}  '
    assert strip_json_fences(text) == '{"action": "pick"}'


def test_extract_response_text_handles_message_content():
    payload = {"choices": [{"message": {"content": '{"action": "move"}'}}]}
    assert _extract_response_text(payload) == '{"action": "move"}'


def test_extract_response_text_handles_delta_content():
    payload = {"choices": [{"delta": {"content": '{"action": "move"}'}}]}
    assert _extract_response_text(payload) == '{"action": "move"}'


def test_limited_run_with_successful_fenced_json_is_partial(monkeypatch):
    from src.prototype5 import phi_recovery_runner

    shutil.rmtree(TMP_ROOT, ignore_errors=True)
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        phi_recovery_runner,
        "discover_foundry_models",
        lambda base_url=None: {
            "base_url": "http://127.0.0.1:49313",
            "request_success": True,
            "phi_model_ids": ["Phi-3-mini-4k-instruct-generic-cpu:3"],
            "model_ids": ["Phi-3-mini-4k-instruct-generic-cpu:3"],
        },
    )
    monkeypatch.setattr(
        phi_recovery_runner,
        "load_benchmark_cases",
        lambda: {
            "status": "PRESENT",
            "path": "benchmark.json",
            "cases": [
                {"command_id": f"C{index:02d}", "command_text": "Move the red cube"}
                for index in range(1, 31)
            ],
        },
    )
    monkeypatch.setattr(phi_recovery_runner, "urlopen", lambda request, timeout: FakeResponse())

    result = run_phi_recovery(
        output_dir=TMP_ROOT,
        requested_model="Phi-3-mini-4k-instruct-generic-cpu:3",
        timeout_seconds=1,
        max_tokens=32,
        limit_commands=1,
    )

    assert result["summary"]["successful_requests"] == 1
    assert result["summary"]["parse_success_rate"] == 1.0
    assert result["summary"]["evidence_status"] == "PARTIAL"
    shutil.rmtree(TMP_ROOT, ignore_errors=True)
