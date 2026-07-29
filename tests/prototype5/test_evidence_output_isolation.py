from pathlib import Path

from scripts.prototype5 import run_mode_e_benchmark_audit
from scripts.prototype5 import run_mode_e_policy_audit
from src.prototype5.evidence_paths import (
    DOCS_DIR,
    EXPECTED_DOC_FILES,
    EXPECTED_RESULT_FILES,
    RESULTS_DIR,
)
from src.prototype5.run_orchestrator import run


def _snapshot(paths: list[Path]) -> dict[Path, bytes]:
    return {path: path.read_bytes() for path in paths if path.exists()}


def test_orchestrator_explicit_roots_do_not_modify_production_defaults(tmp_path):
    canonical_paths = [
        *(RESULTS_DIR / name for name in EXPECTED_RESULT_FILES),
        *(DOCS_DIR / name for name in EXPECTED_DOC_FILES),
    ]
    before = _snapshot(canonical_paths)

    generated_runs = []
    for run_number in (1, 2):
        results_dir = tmp_path / f"run_{run_number}" / "results"
        docs_dir = tmp_path / f"run_{run_number}" / "docs"
        _, generated = run(results_dir=results_dir, docs_dir=docs_dir)
        generated_runs.append(generated)

        assert generated
        assert all(path.exists() for path in generated)
        assert all(
            path.is_relative_to(results_dir) or path.is_relative_to(docs_dir)
            for path in generated
        )

    assert _snapshot(canonical_paths) == before
    assert {
        path.relative_to(tmp_path / "run_1")
        for path in generated_runs[0]
    } == {
        path.relative_to(tmp_path / "run_2")
        for path in generated_runs[1]
    }


def test_mode_e_audit_writers_do_not_escape_explicit_output_root(tmp_path):
    canonical_paths = [
        run_mode_e_benchmark_audit.AUDIT_JSON,
        run_mode_e_benchmark_audit.AUDIT_MD,
        run_mode_e_policy_audit.AUDIT_JSON,
        run_mode_e_policy_audit.AUDIT_MD,
    ]
    before = _snapshot(canonical_paths)
    output_dir = tmp_path / "mode_e"

    run_mode_e_benchmark_audit.run_audit(output_dir)
    run_mode_e_policy_audit.run_audit(output_dir)

    assert {path.name for path in output_dir.iterdir()} == {
        "mode_e_benchmark_audit.json",
        "mode_e_benchmark_audit.md",
        "mode_e_policy_audit.json",
        "mode_e_policy_audit.md",
    }
    assert _snapshot(canonical_paths) == before
