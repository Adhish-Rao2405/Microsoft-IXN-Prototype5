from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_readme_reflects_current_mode_e_state():
    readme = read("README.md")

    assert "Prototype 5 tests: 297 passed" in readme
    assert "Tests: 297 passed" in readme
    assert "Mode E.2 live industrial evaluation: `COMPLETE_LIVE_INDUSTRIAL_EVALUATION`" in readme
    assert "Mode E.2 is evidence under a curated industrial benchmark and deterministic policy context" in readme
    assert "does not prove production robot safety or general industrial deployment readiness" in readme
    assert "Prototype 5 does not introduce new inference" not in readme
    assert "Prototype 5's core orchestrator does not introduce new planning logic" in readme


def test_older_mode_e_docs_are_marked_historical():
    for relative_path in [
        "docs/prototype5/mode_e_evidence_summary.md",
        "docs/prototype5/mode_e_dissertation_wording.md",
    ]:
        content = read(relative_path)
        assert "Status note" in content
        assert "mode_e_final_evidence_summary.md" in content
        assert "mode_e_final_dissertation_wording.md" in content
        assert "mode_e_lee_feedback_closure.md" in content
        assert "Historical/pre-E.2 note" in content


def test_final_dashboard_includes_mode_e_claims_and_boundaries():
    dashboard = read("results/prototype5/final_evidence_dashboard.md")
    lowered = dashboard.lower()

    for claim_id in ["C15", "C16", "C17"]:
        assert claim_id in dashboard

    assert "schema_valid_rate = 0.6333" in dashboard
    assert "execution_eligible_rate = 0.1" in dashboard
    assert "schema_valid_minus_execution_eligible_gap = 0.5333" in dashboard
    assert "pipeline_false_accepts = 0" in dashboard
    assert "mean_latency_ms = 28359.26" in dashboard
    assert "max_latency_ms = 66928.25" in dashboard

    for phrase in [
        "curated industrial benchmark",
        "deterministic policy context",
        "single local phi-3-mini model alias",
        "single foundry local runtime/machine",
        "no real robot execution",
        "does not prove production robot safety",
        "general industrial deployment readiness",
    ]:
        assert phrase in lowered


def test_final_dashboard_includes_latency_deployment_framing():
    dashboard = read("results/prototype5/final_evidence_dashboard.md")
    lowered = dashboard.lower()

    assert "latency profile constrains the deployment interpretation" in lowered
    assert "local-first supervisory task proposal and validation" in lowered
    assert "not low-latency closed-loop robot control" in lowered
