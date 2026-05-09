from pathlib import Path
import shutil

from src.prototype5.evidence_paths import EXPECTED_INPUT_PATHS, collect_input_status, path_exists

TMP_ROOT = Path("tests/prototype5/_tmp")


def test_expected_paths_are_defined():
    required = {
        "prototype3_rq5_comparison_csv",
        "prototype4_execution_comparison_csv",
        "prototype4_safety_latency_frontier_csv",
        "prototype1_audit_summary_json",
        "prototype2_audit_summary_json",
    }
    assert required.issubset(EXPECTED_INPUT_PATHS)


def test_missing_inputs_are_recorded():
    shutil.rmtree(TMP_ROOT, ignore_errors=True)
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    present = TMP_ROOT / "present.csv"
    present.write_text("a\n1\n", encoding="utf-8")
    status = collect_input_status({"present": present, "missing": TMP_ROOT / "missing.csv"})
    assert status["present"]["status"] == "PRESENT"
    assert status["missing"]["status"] == "MISSING"
    assert path_exists(Path(present))
    shutil.rmtree(TMP_ROOT, ignore_errors=True)
