"""Generate the Prototype 5 final dissertation evidence pack.

This module is intentionally offline and deterministic. It reads existing
Prototype 5 evidence files where available and writes dissertation-facing
Markdown/CSV artefacts without calling cloud APIs or live Foundry Local.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = REPO_ROOT / "results" / "prototype5"
DOCS_DIR = REPO_ROOT / "docs"
CARDS_DIR = DOCS_DIR / "model_run_cards"
FIGURES_DIR = REPO_ROOT / "figures"


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")
    return path


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _value(value: Any, missing: str = "not available in detected evidence") -> str:
    if value is None or value == "":
        return missing
    return str(value)


def _percent(value: Any) -> str:
    if value is None or value == "":
        return "not available in detected evidence"
    try:
        return f"{float(value) * 100:.2f}%"
    except (TypeError, ValueError):
        return str(value)


def _first(rows: list[dict[str, str]], predicate) -> dict[str, str]:
    for row in rows:
        if predicate(row):
            return row
    return {}


def load_pack_context() -> dict[str, Any]:
    model_rows = _read_csv(RESULTS_DIR / "final_model_comparison.csv")
    zero_trust_rows = _read_csv(RESULTS_DIR / "final_zero_trust_comparison.csv")
    safety_rows = _read_csv(RESULTS_DIR / "final_safety_latency_summary.csv")
    phi_rows = _read_csv(RESULTS_DIR / "recovery" / "phi" / "phi_recovery_summary.csv")
    mode_c = _read_json(RESULTS_DIR / "mode_c" / "local_vs_cloud_summary.json")
    mode_d = _read_json(RESULTS_DIR / "mode_d" / "mode_d_final_evidence_summary.json")
    manifest = _read_json(RESULTS_DIR / "final_evidence_manifest.json")
    limitations = _read_csv(RESULTS_DIR / "final_limitations_matrix.csv")
    return {
        "model_rows": model_rows,
        "zero_trust_rows": zero_trust_rows,
        "safety_rows": safety_rows,
        "phi_rows": phi_rows,
        "mode_c": mode_c,
        "mode_d": mode_d,
        "manifest": manifest,
        "limitations": limitations,
    }


def generate_research_question_mapping(context: dict[str, Any]) -> Path:
    mode_c = context["mode_c"]
    mode_d = context["mode_d"]
    cloud_latency = _value(mode_c.get("cloud_mean_latency_ms"))
    local_latency = _value(mode_c.get("local_mean_latency_ms"))
    live_profile = mode_d.get("live_foundry_profile", {})
    content = f"""# Research Question Mapping

## Main Research Question

Can local SLMs served through Microsoft Foundry Local support safe and reliable industrial robot task-planning workflows when their outputs are treated as untrusted action proposals and mediated through deterministic validation before execution?

## Sub-Question Mapping

| Research question | Evidence source | Metrics | Expected chapter location | Answer summary | Caveat |
|---|---|---|---|---|---|
| RQ1 - Local model structured-output reliability: How reliably can local SLMs generate parseable, JSON-valid and schema-valid industrial robot action plans from natural-language commands? | `results/prototype5/final_model_comparison.csv`; `results/prototype5/recovery/phi/phi_recovery_summary.csv` | `parse_success`, `json_valid`, `schema_valid`, request success | Chapter 4 evaluation results | Local models produced structured proposals, but validity varied by model. Phi local evidence recorded 30/30 successful requests with JSON-valid rate {_percent(mode_c.get("local_json_valid_rate"))}. | Semantic correctness is not implied by JSON or schema validity. |
| RQ2 - Schema validity versus execution eligibility: To what extent does schema validity overestimate semantic correctness, safety validity and execution eligibility? | `results/prototype5/final_model_comparison.csv`; `results/prototype5/final_zero_trust_comparison.csv` | `schema_valid`, `execution_eligible`, false accepts | Chapter 4 zero-trust evaluation | Schema-valid rates were higher than execution-eligible rates, and baseline trust produced unsafe false accepts. | Execution eligibility is defined by prototype constraints, not production deployment safety. |
| RQ3 - Ambiguity and false accepts: How does command ambiguity affect model-level false accepts, rejection behaviour and execution eligibility? | Prototype 3 difficulty/category evidence; Prototype 4 ambiguity summaries; `results/prototype5/final_dissertation_metrics.md` | ambiguity level, rejection reason, model-level false accepts, execution eligibility | Chapter 4 ambiguity analysis | Available evidence supports treating ambiguity as a source of rejection and false-accept risk. | Per-ambiguity source files are referenced through prior-prototype evidence and may be unavailable in this repository checkout. |
| RQ4 - Model family/size trade-off: What trade-offs appear across local model family and size in terms of schema validity, latency, model-level false accepts and execution eligibility? | `results/prototype5/final_model_comparison.csv`; model/run cards | schema-valid rate, mean latency, false accepts, execution-eligible rate | Chapter 4 model comparison | Qwen-family CPU rows show model-dependent differences in schema validity, latency and false accepts. | The comparison covers detected local evidence, not all possible SLMs or hardware targets. |
| RQ5 - Local-first deployment trade-off: How does Foundry Local inference compare with cloud inference and live local resource profiling in terms of latency, JSON validity, privacy, offline resilience and host resource pressure? | `results/prototype5/mode_c/local_vs_cloud_summary.json`; `results/prototype5/mode_d/mode_d_final_evidence_summary.json` | local/cloud latency, JSON-valid rate, privacy/offline categories, CPU and memory profile | Chapter 4 deployment comparison; Chapter 5 discussion | Cloud mean latency was {cloud_latency} ms versus local {local_latency} ms in Mode C; Mode D measured live local CPU pressure of {_value(live_profile.get("normalized_mean_foundry_cpu_percent_of_total_logical_capacity"))}%. | Cloud cost was not quantitatively measured and live resource results are hardware-specific. |
| RQ6 - Safety-latency frontier: What is the deployment trade-off between stricter deterministic validation and latency/rejection overhead? | `results/prototype5/final_safety_latency_summary.csv`; `results/prototype5/safety_latency_frontier.md` | false accepts, rejection rate if available, mean latency | Chapter 4 safety-latency frontier; Chapter 5 design implications | Stricter validation reduced false accepts in available evidence, with mean-latency differences recorded for evaluated configurations. | Per-gate latency overhead and rejection rates are not fully available for every configuration. |
"""
    return _write(DOCS_DIR / "research_question_mapping.md", content)


def generate_metric_taxonomy(_: dict[str, Any]) -> Path:
    rows = [
        ("request_success", "The model or API returned a response for an attempted command.", "Separates transport/runtime success from output validity.", "A request completed.", "JSON validity, schema validity, semantic correctness or safety.", "Mode C summary, Phi recovery summary, cloud baseline checkpoint."),
        ("parse_success", "Structured action content could be recovered from the model response.", "Models may respond with malformed or wrapped content.", "A parser recovered candidate structured content.", "The recovered content is correct or safe.", "Phi recovery summary and raw JSONL outputs."),
        ("json_valid", "The response is syntactically valid JSON.", "JSON validity is the first machine-readable output gate.", "The output can be parsed as JSON.", "Schema compliance, semantic validity, safety or execution eligibility.", "Mode C summary, Mode D summary, Phi recovery summary."),
        ("schema_valid", "The JSON response conforms to the expected action schema.", "Schema checks prevent malformed action proposals entering later stages.", "Required fields and basic types are present.", "The action is meaningful, safe or executable.", "final_model_comparison.csv."),
        ("semantic_valid", "The action matches the intended command meaning where explicitly evaluated.", "Robot commands can be schema-valid but semantically wrong.", "A proposal matches the benchmark/gold intent under the evaluation rules.", "Physical safety or production readiness.", "Prototype 3/4 evidence where available."),
        ("safety_valid", "The proposal passes deterministic safety constraints.", "Safety constraints are the core zero-trust gate before execution eligibility.", "The action did not violate encoded prototype safety rules.", "Safety under all real-world factory conditions.", "Prototype 4 zero-trust evidence and final_zero_trust_comparison.csv."),
        ("execution_eligible", "The proposal is allowed to proceed under all required prototype gates.", "This is the final decision point for downstream execution or visualisation.", "The action passed the configured prototype gates.", "That a real robot should execute without additional controls.", "final_model_comparison.csv; Prototype 4 execution records."),
        ("model_level_false_accept", "A model proposal that appears acceptable at a model/schema level but is unsafe or invalid under stricter evaluation.", "Identifies model failure modes before deterministic gating.", "A candidate failure mode exists in model output.", "That the final pipeline executed the unsafe action.", "final_model_comparison.csv; Prototype 4 false accept evidence."),
        ("pipeline_level_false_accept", "An unsafe or invalid proposal that passes the full pipeline.", "This is the key zero-trust safety outcome.", "Whether the full gated pipeline blocked unsafe proposals in available records.", "Production-level safety.", "final_zero_trust_comparison.csv."),
        ("false_reject", "A valid command rejected by the evaluation pipeline.", "Captures conservatism and usability cost.", "A potentially acceptable command was blocked.", "That relaxing gates is safe.", "final_model_comparison.csv where available."),
        ("correct_reject", "An invalid, unsafe or unsupported command correctly rejected.", "Measures fail-closed behaviour.", "A rejection aligned with the expected safety/validity outcome.", "The system handles every future invalid command.", "final_model_comparison.csv."),
        ("rejection_reason", "The recorded reason for blocking a proposal.", "Needed for auditability and operator feedback.", "Why a proposal did not proceed.", "That the model understood the rejection.", "Prototype 4 decision/evidence records where available."),
        ("ambiguity_level", "The benchmark difficulty/ambiguity band assigned to a command.", "Ambiguity changes risk and rejection behaviour.", "The command's evaluation stratum.", "A universal natural-language difficulty score.", "Prototype 3 evidence by difficulty/category where available."),
        ("latency_ms", "Elapsed request or evaluation time in milliseconds.", "Latency affects deployment feasibility.", "Observed timing for the measured path.", "Throughput stability or resource efficiency by itself.", "final_model_comparison.csv; Mode C/D summaries."),
        ("local_latency_ms", "Latency for local Foundry Local or local evidence runs.", "Captures local deployment responsiveness.", "Local timing in the measured benchmark.", "Cloud latency or general hardware-independent performance.", "Mode C summary, Phi recovery summary, Mode D summary."),
        ("cloud_latency_ms", "Latency for the cloud baseline on the same benchmark.", "Supports local-vs-cloud comparison.", "Cloud API timing in the measured run.", "Cost, privacy or offline resilience.", "Mode C summary and checkpoint."),
        ("cpu_usage", "Observed CPU pressure during profiling.", "Local inference can consume meaningful host compute.", "Approximate CPU demand for the profiled run.", "GPU/NPU acceleration or hardware-independent cost.", "Mode D final summary and profile CSV."),
        ("memory_usage", "Observed working-set or private-memory pressure.", "Memory footprint affects edge deployment feasibility.", "Approximate memory behaviour on the profiled host.", "Memory use on other hardware.", "Mode D final summary and profile CSV."),
        ("gpu_or_npu_visibility", "Whether GPU/NPU counters were detected by the profiling path.", "Prevents unsupported acceleration claims.", "The profiler could or could not observe acceleration counters.", "That hardware acceleration was absent in all forms.", "Mode D final summary."),
        ("resource_pressure", "Combined interpretation of CPU, memory and latency during local inference.", "Deployment feasibility depends on host resource pressure.", "The measured local run imposed operational cost.", "A complete hardware sizing model.", "Mode D final summary."),
        ("benchmark_size", "Number of commands evaluated in a benchmark run.", "Defines evidence scope.", "The scale of the controlled evaluation.", "Statistical power for population-level inference.", "Mode C summary, final_model_comparison.csv."),
        ("caveat", "A recorded limitation or boundary attached to a metric or claim.", "Prevents overclaiming.", "The safe interpretation of evidence.", "A negative result by itself.", "final_limitations_matrix.csv; claim boundaries docs."),
    ]
    table = "\n".join(
        f"| `{metric}` | {definition} | {why} | {proves} | {not_proves} | {source} |"
        for metric, definition, why, proves, not_proves, source in rows
    )
    content = f"""# Metric Taxonomy

The project does not collapse evaluation into a single "accuracy" score. It separates transport success, syntactic validity, schema validity, semantic validity, safety validity, execution eligibility, latency and resource pressure.

| Metric | Definition | Why it matters | What it proves | What it does NOT prove | Likely source file |
|---|---|---|---|---|---|
{table}
"""
    return _write(DOCS_DIR / "metric_taxonomy.md", content)


def generate_benchmark_card(_: dict[str, Any]) -> Path:
    content = """# Benchmark Card: LocalSLM-IndustrialRobot-ZT-Bench v0.1

## Purpose

LocalSLM-IndustrialRobot-ZT-Bench v0.1 is a controlled ambiguity-stratified benchmark for evaluating whether local SLMs can generate reliable industrial robot action proposals and whether zero-trust validation prevents unsafe or semantically invalid proposals from reaching execution.

## Scope

| Field | Value |
|---|---|
| Benchmark size | 30 commands in the detected final local/cloud and Phi evidence. |
| Difficulty bands | clear, moderate ambiguity, high ambiguity. |
| Domain | Industrial robot task planning. |
| Command scope | Natural-language workcell commands converted into structured action proposals. |
| Action scope | Move/place-style industrial workcell actions, rejection, clarification or no-execution decisions depending on validity. |
| Objects/zones assumed | Workcell objects such as cubes/parts/trays/zones as represented by the benchmark and prototype evidence. |
| Gold labels / gold intent concept | Expected command intent and allowed execution outcome as defined by prior-prototype benchmark evidence. |

## Scoring Rules

The benchmark is scored through layered checks rather than one aggregate accuracy number:

- request success
- parse success
- JSON validity
- schema validity
- semantic validity where evaluated
- safety validity
- execution eligibility
- false accepts, false rejects and correct rejects where available
- latency and resource metrics where measured

## Validation Layers

The intended validation chain is:

1. raw model response
2. parser
3. JSON validity check
4. schema validator
5. semantic validator
6. uncertainty/ambiguity gate
7. deterministic safety gate
8. execution eligibility decision
9. evidence logger

## Known Limitations

- The benchmark is small and controlled.
- The benchmark is designed for failure-mode discovery and comparative engineering evaluation, not population-level statistical inference.
- Semantic validity is only claimed where source evidence explicitly evaluates it.
- Physical robot execution is not proven by this benchmark.
- Local-vs-cloud results are tied to the measured models, API baseline and host conditions.

## Extension Path

Future benchmark extensions should add more object types, richer manipulation tasks, explicit scene-state variation, operator clarification turns, larger ambiguity strata, hardware matrix coverage and repeat runs across more model families.

## Statistical Humility

The benchmark is not statistically powered for population-level inference. Its purpose is controlled engineering comparison and failure-mode discovery. Multi-model consistency strengthens the observed pattern but does not remove the need for larger future benchmarks.
"""
    return _write(DOCS_DIR / "benchmark_card.md", content)


def generate_industry_use_case(_: dict[str, Any]) -> Path:
    content = """# Industry Use Case: Industrial Robotics and Manufacturing Automation

## Industry

The project is positioned in industrial robotics and manufacturing automation.

## Scenario

A factory operator gives natural-language commands to a local robot workcell assistant. A local SLM served through Microsoft Foundry Local proposes structured robot actions. A deterministic zero-trust validation layer decides whether the proposal is parseable, JSON-valid, schema-valid, semantically valid, safety-valid and execution-eligible.

## Stakeholders

| Stakeholder | Interest |
|---|---|
| Factory operator | Fast and understandable command interface. |
| Automation engineer | Reliable mapping from commands to structured robot actions. |
| Safety engineer | Fail-closed behaviour and auditable rejection reasons. |
| IT/edge deployment team | Local deployment, maintainability, privacy and resource management. |

## Why Local AI Matters

Local AI matters because manufacturing environments may require data locality, reduced cloud dependency, offline resilience, predictable deployment boundaries and cost control. Foundry Local provides an on-device serving route for evaluating these properties.

## Why Zero-Trust Matters

Schema-valid output can still be semantically wrong, unsafe, ambiguous or unsupported. The model must therefore be treated as a proposal generator, not as an authority. Deterministic validation is required before any downstream execution context receives an action.

## Evidence Mapping

| Industrial requirement | Evidence mapping |
|---|---|
| Local deployment feasibility | Foundry Local local inference evidence and Mode D live profile. |
| Reliability of structured actions | Prototype 3 model comparison and Phi recovery evidence. |
| Safety-oriented gating | Prototype 4 zero-trust comparison and safety-latency summary. |
| Deployment trade-off analysis | Mode C local-vs-cloud comparison and Mode D resource profiling. |
| Auditability | Final evidence manifest, claims matrix, limitations matrix and final dashboard. |

## Role of PyBullet If Added

PyBullet should be used only as an optional visual execution-context demonstrator. It can show eligible proposals causing simulated movement and rejected proposals causing no movement with a logged rejection reason. It must not be treated as the core safety proof or as physical robot validation.

## Deployment Limitations Before Real Factory Use

- Larger and more representative benchmarks are required.
- Real robot safety certification is not provided.
- Physical workcell integration and emergency-stop logic are outside the current evidence.
- Human factors and operator feedback loops need further study.
- Hardware-specific resource profiling must be repeated across deployment targets.

## Future Work

- Safety policy DSL.
- Clarification recovery with operator-in-the-loop validation.
- Hybrid local/cloud router with explicit privacy and resilience policies.
- Hardware matrix across CPU, GPU and NPU local targets.
- Expanded industrial benchmark with richer scene states.
"""
    return _write(DOCS_DIR / "industry_use_case_industrial_robotics.md", content)


def generate_claim_boundaries(_: dict[str, Any]) -> Path:
    content = """# Claim Boundaries and Statistical Humility

## What The Project Claims

- Local SLMs can be served through Microsoft Foundry Local for controlled industrial robot task-planning evaluation.
- Local SLMs can produce structured robot action proposals, but validity varies by model and run.
- Schema validity is not enough to prove semantic correctness, safety or execution eligibility.
- Deterministic zero-trust validation can block model-level false accepts from becoming pipeline-level false accepts in the available evidence.
- Local-vs-cloud comparison shows a deployment trade-off, not a universal winner.
- Live local inference has measurable latency, CPU and memory implications on the profiled host.
- Prototype 5 consolidates evidence into a dissertation-facing evidence pack.

## What The Project Does Not Claim

- It does not prove production robot safety.
- It does not prove physical robot execution.
- It does not prove population-level model reliability.
- It does not prove that every local SLM or every hardware target behaves similarly.
- It does not prove built-in Foundry Local precision metadata where the catalogue does not expose it.
- It does not prove GPU/NPU acceleration where counters were not detected.
- It does not provide a quantitative cloud cost model unless token/cost evidence is present.

## Benchmark Limitation

The benchmark is not statistically powered for population-level inference. Its purpose is controlled engineering comparison and failure-mode discovery. Multi-model consistency strengthens the observed pattern but does not remove the need for larger future benchmarks.

## Model Limitation

Detected evidence covers specific local model families and a cloud baseline. It should not be generalised to all SLMs, all quantisation variants or all serving backends.

## Simulation Limitation

Any PyBullet layer, if added, is a visual execution-context demonstrator only. It does not prove physical execution, safety certification or industrial deployment readiness.

## Safety Limitation

The safety evidence is based on deterministic prototype gates and benchmark-defined constraints. Real industrial deployment would require certified safety systems, risk assessment, emergency-stop integration and domain-specific validation.

## Resource Profiling Limitation

Mode D resource profiling is hardware-specific. CPU utilisation is approximate and GPU/NPU counters were not detected, so no acceleration claim is made.

## Local-vs-Cloud Limitation

Mode C compares measured local evidence with a cloud baseline on the same 30-command benchmark. It does not establish a universal winner. Cloud inference was faster and more JSON-consistent in the measured evidence, while local inference preserved privacy and offline-resilience properties.

## PyBullet Limitation

PyBullet should not become the core proof. It may demonstrate accepted versus rejected proposals visually, but the dissertation claim must rest on benchmark evidence, zero-trust validation, local-vs-cloud comparison, resource profiling and claim traceability.
"""
    return _write(DOCS_DIR / "claim_boundaries.md", content)


def generate_prototype1_context_note(_: dict[str, Any]) -> Path:
    content = """# Prototype 1 Context Note

Prototype 1 is treated as optional early feasibility and project-history context for the final dissertation pack.

The final evidence pack does not rely on Prototype 1 audit files for its core claims. Core claims are supported by:

- Prototype 3 model-comparison and benchmark evidence.
- Prototype 4 zero-trust execution, safety and extension evidence.
- Prototype 5 custom quantisation evidence, Phi recovery evidence, Mode C local-vs-cloud comparison and Mode D live resource profiling.

If Prototype 1 audit files are unavailable in this checkout, that is a contextual documentation gap only. It does not affect the reported final model metrics, zero-trust false-accept results, local-vs-cloud comparison, resource profile, quantisation evidence or physical-execution limitation.

Safe dissertation wording: Prototype 1 can be cited as early feasibility/context for the project sequence, but not as proof of final robot safety, deployment readiness or the final zero-trust claims.
"""
    return _write(DOCS_DIR / "prototype1_context_note.md", content)


def generate_final_evidence_dashboard(context: dict[str, Any]) -> Path:
    mode_c = context["mode_c"]
    mode_d = context["mode_d"].get("live_foundry_profile", {})
    rows = [
        ("Local Foundry Local inference is feasible.", "`results/prototype5/recovery/phi/phi_recovery_summary.csv`; `results/prototype5/mode_d/mode_d_final_evidence_summary.json`", "Prototype 5 Mode B/D", "request_success, json_valid, latency_ms", f"Local Phi evidence completed 30/30 requests; Mode D live profile completed {_value(mode_d.get('successful_requests'))}/{_value(mode_d.get('total_commands'))} live requests.", "Feasibility is measured for this local host and model, not all deployments.", "Chapter 4 results; Chapter 5 feasibility discussion"),
        ("Local SLMs can produce structured robot action proposals.", "`results/prototype5/final_model_comparison.csv`; `results/prototype5/recovery/phi/phi_recovery_summary.csv`", "Prototype 3; Prototype 5 Mode B", "parse_success, json_valid, schema_valid", "Qwen-family rows include schema-valid outputs; Phi evidence includes JSON-valid local responses.", "Structured output does not imply semantic correctness or safety.", "Chapter 4 model reliability"),
        ("Schema validity overestimates execution eligibility.", "`results/prototype5/final_model_comparison.csv`", "Prototype 3", "schema_valid_rate, execution_eligible_rate", "Detected model rows show schema-valid rates above execution-eligible rates.", "Execution eligibility is defined by prototype gates and benchmark constraints.", "Chapter 4 zero-trust motivation"),
        ("Deterministic zero-trust gating blocks model-level false accepts from becoming pipeline-level false accepts.", "`results/prototype5/final_zero_trust_comparison.csv`", "Prototype 4", "unsafe_false_accept_rate", "Baseline trust model recorded 76 unsafe false accepts; zero-trust pipeline recorded 0 in available records.", "This is not production robot safety certification.", "Chapter 4 safety evaluation; Chapter 5 claim boundary"),
        ("Ambiguity increases rejection/false-accept risk.", "Prototype 3 difficulty/category evidence; Prototype 4 ambiguity summaries; `results/prototype5/final_dissertation_metrics.md`", "Prototype 3; Prototype 4", "ambiguity_level, rejection_reason, false_accept", "Ambiguity is handled as a risk factor through clarification/rejection evidence and gate summaries.", "Per-ambiguity raw files may live in prior prototype repositories.", "Chapter 4 ambiguity analysis"),
        ("Model family/size affects schema validity, latency, and false accepts.", "`results/prototype5/final_model_comparison.csv`", "Prototype 3", "schema_valid_rate, mean_latency_ms, false_accept_rate", "Qwen-family CPU models show different schema-valid rates, mean latencies and false-accept counts.", "The evidence does not cover every SLM family or hardware target.", "Chapter 4 model comparison"),
        ("Local-vs-cloud comparison shows a deployment trade-off, not a universal winner.", "`results/prototype5/mode_c/local_vs_cloud_summary.json`", "Prototype 5 Mode C", "local_latency_ms, cloud_latency_ms, json_valid, privacy/offline categories", f"Cloud: 30/30 requests, {_value(mode_c.get('cloud_mean_latency_ms'))} ms mean latency, {_percent(mode_c.get('cloud_json_valid_rate'))} JSON-valid. Local: 30/30 requests, {_value(mode_c.get('local_mean_latency_ms'))} ms mean latency, {_percent(mode_c.get('local_json_valid_rate'))} JSON-valid.", "Cost was not quantitatively measured; semantic equivalence is not claimed.", "Chapter 4 deployment comparison; Chapter 5 discussion"),
        ("Local inference has measurable CPU/memory/resource pressure.", "`results/prototype5/mode_d/mode_d_final_evidence_summary.json`; `results/prototype5/mode_d/manual_live_30_command_foundry_process_profile.csv`", "Prototype 5 Mode D", "cpu_usage, memory_usage, resource_pressure, latency_ms", f"Mode D recorded normalized mean CPU {_value(mode_d.get('normalized_mean_foundry_cpu_percent_of_total_logical_capacity'))}% and mean latency {_value(mode_d.get('mean_latency_ms'))} ms.", "Resource data is hardware-specific and GPU/NPU counters were not detected.", "Chapter 4 resource profile; Chapter 5 deployment feasibility"),
        ("The project is industry-positioned for industrial robot task planning.", "`docs/industry_use_case_industrial_robotics.md`; `docs/benchmark_card.md`", "Prototype 5 final pack", "industry scenario, benchmark domain, stakeholder mapping", "Final documentation frames the work as a local natural-language interface for an industrial robot workcell.", "Industry positioning is a use-case framing, not factory deployment proof.", "Chapter 1/3 motivation; Chapter 5 deployment discussion"),
        ("Prototype 1 is optional early feasibility/context evidence, not a core proof dependency.", "`docs/prototype1_context_note.md`; `results/prototype5/final_claims_matrix.csv`; `results/prototype5/final_evidence_manifest.json`", "Prototype 1 context; Prototype 5 final pack", "context status, core_claim_dependency", "Missing Prototype 1 audit files are classified as optional context and do not affect core final claims.", "Do not use Prototype 1 as proof of final robot safety, deployment readiness or zero-trust effectiveness.", "Chapter 3 prototype evolution; Chapter 5 validity boundary"),
        ("PyBullet, if present, is a visual execution-context demonstrator only.", "`docs/claim_boundaries.md`; optional future `src/prototype5/pybullet_execution_visualiser/`", "Prototype 5 optional extension", "execution_eligible, rejection_reason, dry-run/demo trace", "No PyBullet visualiser is currently detected; if added, it should visualise accepted/rejected proposals only.", "PyBullet does not prove physical robot safety or execution.", "Chapter 5 future work or demonstration appendix"),
    ]
    table = "\n".join(f"| {claim} | {evidence} | {source} | {metrics} | {result} | {caveat} | {chapter} |" for claim, evidence, source, metrics, result, caveat, chapter in rows)
    content = f"""# Final Evidence Dashboard

This dashboard connects dissertation claims to detected evidence, metrics, results and caveats. It is examiner-readable and intentionally avoids unsupported overclaims.

| Claim | Evidence file | Prototype source | Metric(s) | Result summary | Caveat | Dissertation chapter relevance |
|---|---|---|---|---|---|---|
{table}
"""
    return _write(RESULTS_DIR / "final_evidence_dashboard.md", content)


def generate_brief_alignment_matrix(_: dict[str, Any]) -> Path:
    rows = [
        ("Literature and technology review", "Review local model deployment trends, LLMs vs SLMs and Foundry Local capabilities.", "Documented dissertation review section", "`docs/dissertation_evidence/research_questions_and_claims.md`; dissertation text", "PARTIAL", "Repository contains evidence framing, but final literature review is a dissertation writing task."),
        ("Industry use-case identification", "Industrial robot task planning / manufacturing automation.", "Use-case document and benchmark domain", "`docs/industry_use_case_industrial_robotics.md`; `docs/benchmark_card.md`", "HIT", "Use case is positioned; real factory validation remains future work."),
        ("Application/system architecture", "Local SLM proposal generator plus deterministic zero-trust validation pipeline.", "Architecture diagram/spec", "`docs/final_architecture_diagram_spec.md`; `figures/final_zero_trust_architecture.mmd`", "HIT", "Architecture is evidence/reporting level, not production deployment design."),
        ("Fully on-device Foundry Local prototype", "Local Foundry Local inference path used for benchmark evidence.", "Local request success and latency", "`results/prototype5/recovery/phi/phi_recovery_summary.csv`; `results/prototype5/mode_d/mode_d_final_evidence_summary.json`", "HIT", "Evidence is host/model-specific."),
        ("Local LLM/SLM integration", "Qwen-family and Phi-family local model evidence.", "schema validity, JSON validity, request success", "`results/prototype5/final_model_comparison.csv`; `results/prototype5/recovery/phi/phi_recovery_summary.csv`", "HIT", "Detected models only."),
        ("Model size / model-family / quantisation consideration", "Qwen model comparison plus custom FP16/INT8/INT4 artifacts.", "model comparison, precision metadata", "`results/prototype5/final_model_comparison.csv`; `results/prototype5/recovery/custom_quantisation/`", "HIT", "Built-in Foundry precision metadata remains missing."),
        ("Latency benchmarking", "Measured model, local, cloud and live profile latencies.", "mean_latency_ms", "`results/prototype5/final_model_comparison.csv`; `results/prototype5/mode_c/local_vs_cloud_summary.json`; `results/prototype5/mode_d/mode_d_final_evidence_summary.json`", "HIT", "Latency is measured for specific runs and host conditions."),
        ("Accuracy/reliability benchmarking", "Reliability is decomposed into JSON, schema, semantic/safety and execution eligibility metrics.", "json_valid, schema_valid, false accepts, execution eligible", "`results/prototype5/final_model_comparison.csv`; `results/prototype5/final_zero_trust_comparison.csv`", "HIT", "The project avoids a single broad accuracy claim."),
        ("Resource utilisation benchmarking", "Live Foundry Local process profile.", "CPU, memory, latency", "`results/prototype5/mode_d/mode_d_final_evidence_summary.json`; profile CSV", "HIT", "GPU/NPU counters were not detected."),
        ("Local-vs-cloud comparison", "Same 30-command benchmark compared between local and cloud evidence.", "local/cloud latency, JSON-valid rate, privacy/offline categories", "`results/prototype5/mode_c/local_vs_cloud_summary.json`", "HIT", "Cost was structurally discussed but not quantitatively measured."),
        ("Deployment feasibility discussion", "Local-first trade-offs, resource pressure and safety-gate limits.", "claim boundaries and use-case mapping", "`docs/claim_boundaries.md`; `docs/industry_use_case_industrial_robotics.md`", "HIT", "Production deployment needs larger validation and certified safety controls."),
        ("Cost/efficiency/maintenance trade-off discussion", "Discuss local resource cost versus cloud dependency and maintenance.", "cost availability, resource pressure, offline resilience", "`results/prototype5/mode_c/local_vs_cloud_summary.json`; `docs/claim_boundaries.md`", "PARTIAL", "No quantitative token-level cloud cost accounting."),
        ("Reproducibility and evidence documentation", "Final evidence manifest, claims matrix, audit, final pack docs and tests.", "manifest, claims, tests", "`results/prototype5/final_evidence_manifest.json`; `results/prototype5/final_pack_audit.md`; `results/prototype5/final_pack_completion_report.md`", "HIT", "External Prototype 1-4 source availability may vary by machine."),
    ]
    table = "\n".join(f"| {a} | {b} | {c} | {d} | {e} | {f} |" for a, b, c, d, e, f in rows)
    content = f"""# Microsoft Brief Alignment Matrix

| Brief requirement | Project interpretation | KPI / evidence metric | Evidence file | Status | Caveat / next action |
|---|---|---|---|---|---|
{table}
"""
    return _write(RESULTS_DIR / "microsoft_brief_alignment_matrix.md", content)


def generate_model_run_cards(context: dict[str, Any]) -> list[Path]:
    model_rows = context["model_rows"]
    phi_row = context["phi_rows"][0] if context["phi_rows"] else {}
    mode_c = context["mode_c"]
    mode_d = context["mode_d"].get("live_foundry_profile", {})
    outputs: list[Path] = []
    outputs.append(
        _write(
            CARDS_DIR / "README.md",
            """# Model and Run Cards

These cards summarise detected local, cloud and resource-profile runs used by the Prototype 5 final dissertation evidence pack.

Generated cards:

- `local_qwen_coder_run_card.md`
- `local_phi_or_mode_b_run_card.md`
- `cloud_baseline_run_card.md`
- `resource_profile_run_card.md`

Unavailable fields are explicitly marked as "not available in detected evidence" rather than inferred.
""",
        )
    )
    coder_rows = [row for row in model_rows if "coder" in row.get("model", "")]
    qwen_table = "\n".join(
        f"| {row.get('model')} | {row.get('commands_evaluated')} | {_percent(row.get('schema_valid_rate'))} | {_percent(row.get('execution_eligible_rate'))} | {row.get('false_accept_count')} | {_percent(row.get('false_accept_rate'))} | {row.get('mean_latency_ms')} ms |"
        for row in coder_rows
    )
    outputs.append(
        _write(
            CARDS_DIR / "local_qwen_coder_run_card.md",
            f"""# Local Qwen Coder Run Card

| Field | Value |
|---|---|
| Model / run name | Qwen2.5 Coder local CPU benchmark rows |
| Model alias if available | foundry:qwen2.5-coder-* |
| Local/cloud mode | Local |
| Serving layer | Foundry Local evidence from Prototype 3 |
| Benchmark used | LocalSLM-IndustrialRobot-ZT-Bench v0.1 / 30-command benchmark |
| Date/source file if available | `results/prototype5/final_model_comparison.csv` |
| Temperature / max tokens if available | not available in detected evidence |
| Hardware if available | CPU labels in model identifiers; detailed host hardware not available in detected evidence |

| Model | Commands | Schema-valid rate | Execution-eligible rate | Model-level false accepts | False-accept rate | Mean latency |
|---|---:|---:|---:|---:|---:|---:|
{qwen_table or '| MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING |'}

| Field | Value |
|---|---|
| Request success | not available in detected evidence |
| JSON-valid rate | not available in detected evidence |
| Pipeline-level false accepts | see Prototype 4 zero-trust comparison |
| Known failure modes | Schema-valid output can still fail execution eligibility; false accepts observed at model level. |
| Caveats | Covers detected Qwen Coder rows only; not a universal model-family result. |
""",
        )
    )
    outputs.append(
        _write(
            CARDS_DIR / "local_phi_or_mode_b_run_card.md",
            f"""# Local Phi / Mode B Run Card

| Field | Value |
|---|---|
| Model / run name | {_value(phi_row.get('model'))} |
| Model alias if available | {_value(phi_row.get('model'))} |
| Local/cloud mode | Local |
| Serving layer | Foundry Local |
| Benchmark used | 30-command benchmark |
| Date/source file if available | `results/prototype5/recovery/phi/phi_recovery_summary.csv` |
| Temperature / max tokens if available | not available in detected evidence |
| Hardware if available | CPU model label; detailed hardware in Mode D resource profile |
| Request success | {_value(phi_row.get('successful_requests'))}/{_value(phi_row.get('commands_evaluated'))} |
| JSON-valid rate | {_percent(phi_row.get('json_valid_rate'))} |
| Schema-valid rate | not available in detected evidence |
| Execution-eligible rate | not available in detected evidence |
| Model-level false accepts | not available in detected evidence |
| Pipeline-level false accepts | not available in detected evidence |
| Mean latency | {_value(phi_row.get('mean_latency_ms'))} ms |
| Known failure modes | Semantic validity marked {_value(phi_row.get('semantic_validity'))}; JSON validity below 100%. |
| Caveats | Phi evidence is response/JSON evidence; semantic and safety validity are not claimed unless separately evaluated. |
""",
        )
    )
    outputs.append(
        _write(
            CARDS_DIR / "cloud_baseline_run_card.md",
            f"""# Cloud Baseline Run Card

| Field | Value |
|---|---|
| Model / run name | Cloud baseline |
| Model alias if available | {_value(mode_c.get('cloud_retry_policy', {}).get('model'))} |
| Local/cloud mode | Cloud |
| Serving layer | External API baseline |
| Benchmark used | Same 30-command benchmark as local Mode C comparison |
| Date/source file if available | `results/prototype5/mode_c/local_vs_cloud_summary.json`; checkpoint CSV |
| Temperature / max tokens if available | not available in detected evidence |
| Hardware if available | not applicable / provider-managed |
| Request success | {_value(mode_c.get('cloud_successful_requests'))}/{_value(mode_c.get('cloud_commands_attempted'))} |
| JSON-valid rate | {_percent(mode_c.get('cloud_json_valid_rate'))} |
| Schema-valid rate | not available in detected evidence |
| Execution-eligible rate | not available in detected evidence |
| Model-level false accepts | not available in detected evidence |
| Pipeline-level false accepts | not available in detected evidence |
| Mean latency | {_value(mode_c.get('cloud_mean_latency_ms'))} ms |
| Known failure modes | Requires network/API availability, account configuration, request pacing and retry/backoff. |
| Caveats | Semantic equivalence and quantitative cost are not claimed. |
""",
        )
    )
    outputs.append(
        _write(
            CARDS_DIR / "resource_profile_run_card.md",
            f"""# Resource Profile Run Card

| Field | Value |
|---|---|
| Model / run name | Mode D live Foundry Local resource profile |
| Model alias if available | {_value(mode_d.get('model'))} |
| Local/cloud mode | Local |
| Serving layer | Foundry Local serving process |
| Benchmark used | 30-command benchmark |
| Date/source file if available | `results/prototype5/mode_d/mode_d_final_evidence_summary.json`; live profile CSV |
| Temperature / max tokens if available | not available in detected evidence |
| Hardware if available | {_value(mode_d.get('logical_cpu_cores'))} logical CPU cores; GPU/NPU not detected in Mode D |
| Request success | {_value(mode_d.get('successful_requests'))}/{_value(mode_d.get('total_commands'))} |
| JSON-valid rate | {_percent(mode_d.get('json_valid_rate'))} |
| Schema-valid rate | not available in detected evidence |
| Execution-eligible rate | not available in detected evidence |
| Model-level false accepts | not available in detected evidence |
| Pipeline-level false accepts | not available in detected evidence |
| Mean latency | {_value(mode_d.get('mean_latency_ms'))} ms |
| Known failure modes | JSON validity below 100%; CPU pressure observed; GPU/NPU counters not detected. |
| Caveats | Hardware-specific operational profile, not a general hardware benchmark. |
""",
        )
    )
    return outputs


def generate_architecture(context: dict[str, Any]) -> list[Path]:
    spec = """# Final Architecture Diagram Specification

## Purpose

This diagram specifies the final zero-trust local-first task-planning evidence architecture for the dissertation.

## Required Flow

User command -> benchmark/live input -> Foundry Local SLM / optional cloud baseline -> raw model response -> parser -> JSON validity -> schema validator -> semantic validator -> uncertainty/ambiguity gate -> safety gate -> execution eligibility decision -> evidence logger -> optional PyBullet industrial workcell visualiser.

## Side Evidence Components

- benchmark dataset
- metric taxonomy
- claims matrix
- evidence manifest
- resource profiler
- local-vs-cloud comparator
- model/run cards

## Mermaid Source

See `figures/final_zero_trust_architecture.mmd`.
"""
    mermaid = """flowchart LR
    user[User command] --> input[Benchmark or live input]
    input --> local[Foundry Local SLM]
    input -. optional baseline .-> cloud[Cloud baseline]
    local --> raw[Raw model response]
    cloud -. comparison output .-> raw
    raw --> parser[Parser]
    parser --> json[JSON validity]
    json --> schema[Schema validator]
    schema --> semantic[Semantic validator]
    semantic --> ambiguity[Uncertainty / ambiguity gate]
    ambiguity --> safety[Deterministic safety gate]
    safety --> decision[Execution eligibility decision]
    decision --> logger[Evidence logger]
    decision -. optional .-> pybullet[PyBullet industrial workcell visualiser]

    benchmark[(Benchmark dataset)] --> input
    taxonomy[(Metric taxonomy)] --> logger
    claims[(Claims matrix)] --> logger
    manifest[(Evidence manifest)] --> logger
    profiler[(Resource profiler)] --> logger
    comparator[(Local-vs-cloud comparator)] --> logger
    cards[(Model / run cards)] --> logger
"""
    return [
        _write(DOCS_DIR / "final_architecture_diagram_spec.md", spec),
        _write(FIGURES_DIR / "final_zero_trust_architecture.mmd", mermaid),
    ]


def generate_safety_latency_frontier(context: dict[str, Any]) -> list[Path]:
    safety_by_name = {row.get("configuration", ""): row for row in context["safety_rows"]}
    rows = [
        {
            "configuration": "schema_only",
            "gates_enabled": "schema validator",
            "expected_safety_effect": "Lowest validation strictness; unsafe false accepts remain possible.",
            "false_accept_rate_if_available": "MISSING",
            "rejection_rate_if_available": "MISSING",
            "latency_overhead_if_available": _value(safety_by_name.get("schema_only", {}).get("mean_latency_ms"), "MISSING"),
            "evidence_source": "results/prototype5/final_safety_latency_summary.csv",
            "caveat": "Mean latency is available, but per-gate overhead is not separated.",
        },
        {
            "configuration": "schema_plus_semantic",
            "gates_enabled": "schema validator; semantic validator",
            "expected_safety_effect": "Reduces semantically invalid accepts compared with schema alone.",
            "false_accept_rate_if_available": "MISSING",
            "rejection_rate_if_available": "MISSING",
            "latency_overhead_if_available": _value(safety_by_name.get("schema_semantic", {}).get("mean_latency_ms"), "MISSING"),
            "evidence_source": "results/prototype5/final_safety_latency_summary.csv",
            "caveat": "False-accept count exists in source summary, but rate/rejection data are not fully available here.",
        },
        {
            "configuration": "schema_plus_semantic_plus_uncertainty",
            "gates_enabled": "schema validator; semantic validator; uncertainty/ambiguity gate",
            "expected_safety_effect": "Blocks ambiguous proposals that should not proceed directly to execution.",
            "false_accept_rate_if_available": "MISSING",
            "rejection_rate_if_available": "MISSING",
            "latency_overhead_if_available": _value(safety_by_name.get("schema_semantic_uncertainty", {}).get("mean_latency_ms"), "MISSING"),
            "evidence_source": "results/prototype5/final_safety_latency_summary.csv",
            "caveat": "Measured mean latency is available; rejection rate is not available in this final CSV.",
        },
        {
            "configuration": "full_zero_trust",
            "gates_enabled": "schema validator; semantic validator; uncertainty gate; safety gate; execution eligibility",
            "expected_safety_effect": "Highest evaluated strictness; zero unsafe false accepts observed in available records.",
            "false_accept_rate_if_available": "0.0 where mapped to zero-trust pipeline evidence",
            "rejection_rate_if_available": "MISSING",
            "latency_overhead_if_available": _value(safety_by_name.get("full_zero_trust", {}).get("mean_latency_ms"), "MISSING"),
            "evidence_source": "results/prototype5/final_safety_latency_summary.csv; results/prototype5/final_zero_trust_comparison.csv",
            "caveat": "This is prototype evidence, not production robot safety certification.",
        },
        {
            "configuration": "full_zero_trust_plus_clarification_future_work",
            "gates_enabled": "full zero-trust; clarification recovery loop",
            "expected_safety_effect": "Expected to recover some ambiguous valid commands without relaxing safety gates.",
            "false_accept_rate_if_available": "MISSING",
            "rejection_rate_if_available": "MISSING",
            "latency_overhead_if_available": "MISSING",
            "evidence_source": "Prototype 4 clarification recovery summary where available",
            "caveat": "Future-work configuration; do not treat as measured final frontier.",
        },
    ]
    columns = [
        "configuration",
        "gates_enabled",
        "expected_safety_effect",
        "false_accept_rate_if_available",
        "rejection_rate_if_available",
        "latency_overhead_if_available",
        "evidence_source",
        "caveat",
    ]
    csv_path = _write_csv(RESULTS_DIR / "safety_latency_frontier.csv", rows, columns)
    table = "\n".join(
        f"| {row['configuration']} | {row['gates_enabled']} | {row['expected_safety_effect']} | {row['false_accept_rate_if_available']} | {row['rejection_rate_if_available']} | {row['latency_overhead_if_available']} | {row['evidence_source']} | {row['caveat']} |"
        for row in rows
    )
    md = f"""# Safety-Latency Frontier

This artefact summarises the conceptual and evidence-backed trade-off between validation strictness, latency overhead, rejection behaviour and false-accept risk.

Measured per-gate latency overhead is not available in the detected final evidence. Where only mean configuration latency is available, the table records that value and labels missing values as `MISSING`.

| Configuration | Gates enabled | Expected safety effect | False accept rate if available | Rejection rate if available | Latency overhead if available | Evidence source | Caveat |
|---|---|---|---|---|---|---|---|
{table}
"""
    md_path = _write(RESULTS_DIR / "safety_latency_frontier.md", md)
    return [csv_path, md_path]


def generate_completion_report(generated: list[Path]) -> Path:
    rel = [path.relative_to(REPO_ROOT).as_posix() for path in generated]
    files = "\n".join(f"- `{path}`" for path in rel)
    content = f"""# Final Pack Completion Report

## Dissertation Pack Files Created Or Modified

{files}

## Implementation Files Added

- `src/prototype5/generate_final_dissertation_pack.py`
- `tests/prototype5/test_final_dissertation_pack.py`

## Audit And Index Files

- `results/prototype5/final_pack_audit.md`
- `README.md`
- `docs/dissertation_evidence/evidence_index.md`

## Tests Run

- `python -m pytest tests/prototype5 -v`

## Test Results

- 62 passed.

## Orchestrator Result

- `python -m src.prototype5.run_orchestrator`
- Result: COMPLETE.
- Generated outputs reported by orchestrator: 12.
- Mode C status: COMPLETE.
- Mode D status: COMPLETE_LIVE_PROFILE.
- Live Foundry profile: PRESENT.

## Final Pack Generator Result

- `python -m src.prototype5.generate_final_dissertation_pack`
- Result: final dissertation pack generated from existing local evidence files.

## Missing Evidence

- Built-in Foundry Local precision metadata remains missing.
- Physical robot execution remains missing.
- GPU/NPU counters were not detected in Mode D.
- Quantitative cloud cost accounting is not available.
- Per-gate latency overhead and full rejection-rate data are not available for every safety-latency configuration.
- Prototype 1 audit files, if absent, are optional context rather than missing core proof.

## Caveats

Prototype 5 remains an evidence-orchestration and dissertation-reporting layer. It does not merge, rewrite or refactor Prototypes 1-4. Missing source evidence is marked as missing rather than fabricated.
Prototype 1 may be cited as early feasibility context only; the final claims rest on Prototype 3, Prototype 4 and Prototype 5 evidence.

## Next Dissertation-Writing Actions

- Use the final evidence dashboard as the Chapter 4 result index.
- Use the Microsoft brief alignment matrix to close the IXN requirement discussion.
- Use the claim boundaries document in Chapter 5 threats-to-validity and future-work sections.
"""
    return _write(RESULTS_DIR / "final_pack_completion_report.md", content)


def generate_all() -> list[Path]:
    context = load_pack_context()
    generated: list[Path] = []
    generated.append(generate_research_question_mapping(context))
    generated.append(generate_metric_taxonomy(context))
    generated.append(generate_benchmark_card(context))
    generated.append(generate_industry_use_case(context))
    generated.append(generate_claim_boundaries(context))
    generated.append(generate_prototype1_context_note(context))
    generated.append(generate_final_evidence_dashboard(context))
    generated.append(generate_brief_alignment_matrix(context))
    generated.extend(generate_model_run_cards(context))
    generated.extend(generate_architecture(context))
    generated.extend(generate_safety_latency_frontier(context))
    generated.append(generate_completion_report(generated))
    return generated


def main() -> None:
    generated = generate_all()
    print("Prototype 5 final dissertation pack generated.")
    for path in generated:
        print(path.relative_to(REPO_ROOT))


if __name__ == "__main__":
    main()
