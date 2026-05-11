from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_final_pack_files_exist():
    required_paths = [
        "results/prototype5/final_pack_audit.md",
        "results/prototype5/final_evidence_dashboard.md",
        "results/prototype5/microsoft_brief_alignment_matrix.md",
        "docs/research_question_mapping.md",
        "docs/metric_taxonomy.md",
        "docs/benchmark_card.md",
        "docs/model_run_cards/README.md",
        "docs/industry_use_case_industrial_robotics.md",
        "docs/claim_boundaries.md",
        "docs/prototype1_context_note.md",
        "docs/final_architecture_diagram_spec.md",
        "figures/final_zero_trust_architecture.mmd",
        "results/prototype5/safety_latency_frontier.csv",
        "results/prototype5/safety_latency_frontier.md",
        "results/prototype5/final_pack_completion_report.md",
    ]
    missing = [path for path in required_paths if not (ROOT / path).exists()]
    assert missing == []


def test_evidence_dashboard_has_required_claims():
    dashboard = read("results/prototype5/final_evidence_dashboard.md")
    required_claims = [
        "Local Foundry Local inference is feasible.",
        "Local SLMs can produce structured robot action proposals.",
        "Schema validity overestimates execution eligibility.",
        "Deterministic zero-trust gating blocks model-level false accepts",
        "Ambiguity increases rejection/false-accept risk.",
        "Model family/size affects schema validity, latency, and false accepts.",
        "Local-vs-cloud comparison shows a deployment trade-off",
        "Local inference has measurable CPU/memory/resource pressure.",
        "The project is industry-positioned for industrial robot task planning.",
        "Prototype 1 is optional early feasibility/context evidence",
        "PyBullet, if present, is a visual execution-context demonstrator only.",
    ]
    for claim in required_claims:
        assert claim in dashboard


def test_brief_alignment_has_required_rows():
    matrix = read("results/prototype5/microsoft_brief_alignment_matrix.md")
    required_rows = [
        "Literature and technology review",
        "Industry use-case identification",
        "Application/system architecture",
        "Fully on-device Foundry Local prototype",
        "Local LLM/SLM integration",
        "Model size / model-family / quantisation consideration",
        "Latency benchmarking",
        "Accuracy/reliability benchmarking",
        "Resource utilisation benchmarking",
        "Local-vs-cloud comparison",
        "Deployment feasibility discussion",
        "Cost/efficiency/maintenance trade-off discussion",
        "Reproducibility and evidence documentation",
    ]
    for row in required_rows:
        assert row in matrix


def test_metric_taxonomy_has_required_metrics():
    taxonomy = read("docs/metric_taxonomy.md")
    required_metrics = [
        "request_success",
        "parse_success",
        "json_valid",
        "schema_valid",
        "semantic_valid",
        "safety_valid",
        "execution_eligible",
        "model_level_false_accept",
        "pipeline_level_false_accept",
        "false_reject",
        "correct_reject",
        "rejection_reason",
        "ambiguity_level",
        "latency_ms",
        "local_latency_ms",
        "cloud_latency_ms",
        "cpu_usage",
        "memory_usage",
        "gpu_or_npu_visibility",
        "resource_pressure",
        "benchmark_size",
        "caveat",
    ]
    for metric in required_metrics:
        assert f"`{metric}`" in taxonomy


def test_research_question_mapping_has_main_rq():
    mapping = read("docs/research_question_mapping.md")
    assert "Can local SLMs served through Microsoft Foundry Local support safe and reliable industrial robot task-planning workflows" in mapping
    for rq in ["RQ1", "RQ2", "RQ3", "RQ4", "RQ5", "RQ6"]:
        assert rq in mapping


def test_claim_boundaries_mentions_limitations():
    boundaries = read("docs/claim_boundaries.md")
    required_sections = [
        "Benchmark Limitation",
        "Model Limitation",
        "Simulation Limitation",
        "Safety Limitation",
        "Resource Profiling Limitation",
        "Local-vs-Cloud Limitation",
        "PyBullet Limitation",
        "not statistically powered for population-level inference",
    ]
    for section in required_sections:
        assert section in boundaries


def test_prototype1_context_note_marks_gap_optional():
    note = read("docs/prototype1_context_note.md")
    assert "optional early feasibility" in note
    assert "does not rely on Prototype 1 audit files for its core claims" in note
    assert "does not affect the reported final model metrics" in note
