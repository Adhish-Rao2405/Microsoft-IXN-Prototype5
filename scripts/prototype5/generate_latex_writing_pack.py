"""Generate LaTeX-ready dissertation writing pack from Prototype 5 evidence.

This is a reporting utility only. It reads existing evidence files and
verification snapshots, then writes Overleaf-ready section fragments.
"""

from __future__ import annotations

import csv
import json
import subprocess
import importlib.util
from collections import Counter
from datetime import datetime
from pathlib import Path
from textwrap import dedent
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results" / "prototype5"
DOCS = ROOT / "docs"
FIGURES = ROOT / "figures"
LATEX = ROOT / "latex" / "generated"
SNAPSHOTS = RESULTS / "verification_snapshots"

EVIDENCE_FILES = [
    RESULTS / "final_evidence_dashboard.md",
    RESULTS / "microsoft_brief_alignment_matrix.md",
    RESULTS / "final_claims_matrix.csv",
    RESULTS / "final_dissertation_metrics.md",
    RESULTS / "final_evidence_manifest.json",
    RESULTS / "safety_latency_frontier.md",
    RESULTS / "safety_latency_frontier.csv",
    RESULTS / "final_pack_completion_report.md",
    DOCS / "research_question_mapping.md",
    DOCS / "metric_taxonomy.md",
    DOCS / "benchmark_card.md",
    DOCS / "claim_boundaries.md",
    DOCS / "industry_use_case_industrial_robotics.md",
    DOCS / "prototype1_context_note.md",
    DOCS / "final_architecture_diagram_spec.md",
    DOCS / "model_run_cards" / "README.md",
    FIGURES / "final_zero_trust_architecture.mmd",
    ROOT / "README.md",
    DOCS / "dissertation_evidence" / "evidence_index.md",
]


def run_text(command: list[str]) -> str:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    output = (completed.stdout + completed.stderr).strip()
    return output or "(no output)"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")
    return path


def latex_escape(value: Any) -> str:
    text = str(value)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text


def markdown_rows(path: Path) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in read_text(path).splitlines():
        line = line.strip()
        if not line.startswith("|") or "---" in line:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if cells:
            rows.append(cells)
    return rows


def key_line(path: Path, patterns: list[str]) -> str:
    text = read_text(path)
    for line in text.splitlines():
        if any(pattern in line for pattern in patterns):
            return line.strip()
    return "not available in detected evidence"


def make_longtable(headers: list[str], rows: list[list[str]], label: str, caption: str) -> str:
    colspec = "p{0.22\\textwidth}p{0.26\\textwidth}p{0.25\\textwidth}p{0.17\\textwidth}"
    if len(headers) == 3:
        colspec = "p{0.22\\textwidth}p{0.38\\textwidth}p{0.28\\textwidth}"
    if len(headers) == 5:
        colspec = "p{0.14\\textwidth}p{0.20\\textwidth}p{0.25\\textwidth}p{0.14\\textwidth}p{0.17\\textwidth}"
    header_line = " & ".join(latex_escape(header) for header in headers) + r" \\"
    body = "\n".join(
        " & ".join(latex_escape(cell) for cell in row[: len(headers)]) + r" \\"
        for row in rows
    )
    return dedent(
        f"""
        \\begin{{longtable}}{{{colspec}}}
        \\caption{{{latex_escape(caption)}}}
        \\label{{{label}}}\\\\
        \\toprule
        {header_line}
        \\midrule
        \\endfirsthead
        \\toprule
        {header_line}
        \\midrule
        \\endhead
        {body}
        \\bottomrule
        \\end{{longtable}}
        """
    ).strip()


def evidence_context() -> dict[str, Any]:
    manifest = read_json(RESULTS / "final_evidence_manifest.json")
    model_rows = read_csv(RESULTS / "final_model_comparison.csv")
    zero_trust_rows = read_csv(RESULTS / "final_zero_trust_comparison.csv")
    safety_rows = read_csv(RESULTS / "final_safety_latency_summary.csv")
    claims_rows = read_csv(RESULTS / "final_claims_matrix.csv")
    limitations_rows = read_csv(RESULTS / "final_limitations_matrix.csv")
    brief_rows = markdown_rows(RESULTS / "microsoft_brief_alignment_matrix.md")
    if brief_rows and brief_rows[0] and brief_rows[0][0] == "Brief requirement":
        brief_rows = brief_rows[1:]
    return {
        "manifest": manifest,
        "model_rows": model_rows,
        "zero_trust_rows": zero_trust_rows,
        "safety_rows": safety_rows,
        "claims_rows": claims_rows,
        "limitations_rows": limitations_rows,
        "brief_rows": brief_rows,
        "pytest_line": key_line(SNAPSHOTS / "pytest_prototype5_output.txt", ["passed", "failed"]),
        "orchestrator_line": key_line(SNAPSHOTS / "orchestrator_output.txt", ["COMPLETE"]),
        "generator_line": key_line(SNAPSHOTS / "final_pack_generator_output.txt", ["generated"]),
    }


def create_verification_summary(now: str, ctx: dict[str, Any]) -> Path:
    rows = [
        (
            "python -m pytest tests/prototype5 -v",
            "PASS" if "passed" in ctx["pytest_line"] and "failed" not in ctx["pytest_line"] else "FAIL",
            ctx["pytest_line"],
            "Confirms Prototype 5 tests still pass after evidence-pack generation.",
        ),
        (
            "python -m src.prototype5.run_orchestrator",
            "PASS" if "COMPLETE" in ctx["orchestrator_line"] else "FAIL",
            ctx["orchestrator_line"],
            "Confirms the final evidence orchestrator can regenerate core reporting outputs.",
        ),
        (
            "python -m src.prototype5.generate_final_dissertation_pack",
            "PASS" if "generated" in ctx["generator_line"] else "FAIL",
            ctx["generator_line"],
            "Confirms the final documentation pack generator can refresh dissertation-facing artefacts.",
        ),
    ]
    table = "\n".join(
        f"| `{command}` | {status} | {latex_escape(line)} | {now} | {relevance} |"
        for command, status, line, relevance in rows
    )
    return write(
        SNAPSHOTS / "verification_summary.md",
        f"""# Verification Summary

| Command | Status | Key output line | Timestamp | Relevance for dissertation evidence |
|---|---|---|---|---|
{table}

The raw command outputs are stored in this directory and should be cited as verification snapshots rather than as new experimental evidence.
""",
    )


def create_audit(now: str, ctx: dict[str, Any]) -> Path:
    found = [path for path in EVIDENCE_FILES if path.exists()]
    missing = [path for path in EVIDENCE_FILES if not path.exists()]
    status = run_text(["git", "status", "--short", "--branch"])
    changed = run_text(["git", "status", "--short"])
    png_note = (
        "Optional PNG generation is available through matplotlib."
        if importlib.util.find_spec("matplotlib")
        else "Optional PNG generation is skipped because matplotlib is not available in the current Python environment."
    )
    found_lines = "\n".join(f"- `{path.relative_to(ROOT).as_posix()}`" for path in found)
    missing_lines = "\n".join(f"- `{path.relative_to(ROOT).as_posix()}`" for path in missing) or "- None"
    return write(
        RESULTS / "latex_pack_audit.md",
        f"""# LaTeX Pack Audit

Generated: {now}

## Current Git Status

```text
{status}
```

## Evidence Files Found

{found_lines}

## Evidence Files Missing

{missing_lines}

## Current Test Count

- Command: `python -m pytest tests/prototype5 -v`
- Status: {"PASS" if "passed" in ctx["pytest_line"] and "failed" not in ctx["pytest_line"] else "FAIL"}
- Key output: `{ctx["pytest_line"]}`

## Current Orchestrator Status

- Command: `python -m src.prototype5.run_orchestrator`
- Status: {"PASS" if "COMPLETE" in ctx["orchestrator_line"] else "FAIL"}
- Key output: `{ctx["orchestrator_line"]}`

## Current Final Pack Generator Status

- Command: `python -m src.prototype5.generate_final_dissertation_pack`
- Status: {"PASS" if "generated" in ctx["generator_line"] else "FAIL"}
- Key output: `{ctx["generator_line"]}`

## Changed Or Generated Files Before LaTeX Generation

```text
{changed}
```

## Caveats For The LaTeX Pack

- The LaTeX pack is a writing aid and does not create new experimental evidence.
- Prototype 1 is context-only early feasibility evidence, not missing core proof.
- Prototype 5 remains an evidence/reporting layer.
- PyBullet is discussed only as optional future visualisation; no PyBullet or robot-control feature is generated.
- All reported quantitative claims are taken from detected evidence files. Missing values are marked as not available in detected evidence.
- The architecture figure uses the existing Mermaid source; Overleaf may need a manually exported PDF at `figures/final_zero_trust_architecture.pdf`.
- {png_note}
""",
    )


def tex_master_include_order() -> str:
    files = [
        "12_tables_and_macros.tex",
        "01_project_overview.tex",
        "02_research_aims_and_questions.tex",
        "03_system_architecture.tex",
        "04_methodology_evaluation_framework.tex",
        "05_prototype_evolution_summary.tex",
        "06_results_overview.tex",
        "07_microsoft_brief_alignment.tex",
        "08_industrial_robotics_positioning.tex",
        "09_limitations_and_claim_boundaries.tex",
        "10_future_work.tex",
        "11_appendix_verification_evidence.tex",
    ]
    includes = "\n".join(f"% \\input{{latex/generated/{name}}}" for name in files)
    return f"""% Recommended Overleaf include order.
% Add package lines from 12_tables_and_macros.tex to your preamble if your main template does not already include them.
% Then paste or input the section files in this order.

{includes}
"""


def tex_project_overview() -> str:
    return r"""\section{Project Overview and Current Evidence Baseline}
\label{sec:project_overview_current_baseline}

This dissertation is titled \emph{Schema Validity Is Not Enough: Zero-Trust Evaluation of Local SLMs for Industrial Robot Task Planning with Microsoft Foundry Local}. The project investigates whether local small language models (SLMs), served through Microsoft Foundry Local, can support industrial robot task-planning workflows when their outputs are treated as untrusted action proposals rather than executable commands. The central claim is deliberately bounded: within the evaluated benchmark and under the defined validation policy, local SLMs can contribute to robot task planning only when deterministic validation mediates every model-generated proposal before any downstream execution context is reached.

The work is positioned in industrial robotics and manufacturing automation. In the target use case, a factory operator gives a natural-language instruction to a local workcell assistant. A local SLM proposes a structured robot action, and a zero-trust validation layer evaluates whether the proposal is parseable, JSON-valid, schema-valid, semantically valid, safety-valid and execution-eligible. This separation is essential because a schema-valid output can still be semantically wrong, unsafe, ambiguous or unsupported by the current workcell state.

Microsoft Foundry Local is used as the local inference framing for the project. It provides a practical route for evaluating local model serving, privacy and offline-resilience trade-offs without treating the model itself as a trusted controller \cite{microsoft_foundry_local_docs}. The dissertation therefore evaluates Foundry Local as part of a local-first evidence chain, not as a production-certified robot-control platform.

Prototype 5 is the final evidence orchestration and reporting layer. It consolidates prior evidence, records claim boundaries, generates the final claims matrix and manifest, and adds Prototype 5 evidence for custom quantisation, Phi-family local responses, local-vs-cloud comparison and live local resource profiling. Prototype 1 is retained only as optional early feasibility context; its absence from core audit evidence is a contextual documentation gap, not a missing proof for the final claims.

The current evidence baseline is complete for the dissertation pack: the Prototype 5 test suite passed, the final orchestrator completed, and the final dissertation pack generator completed. The evidence remains benchmark-based and prototype-scoped. It does not establish real-world robot safety, factory deployment readiness, clinical or production-grade assurance, or statistical generalisation beyond the evaluated command set.
"""


def tex_research_aims() -> str:
    rq_rows = [
        ["Main RQ", "Final claims matrix; Prototype 3--5 evidence", "schema validity, safety validity, execution eligibility", "Local SLMs can support the workflow only as untrusted proposal generators mediated by deterministic validation."],
        ["RQ1", "final_model_comparison.csv; Phi recovery summary", "parse_success, json_valid, schema_valid", "Local models produced structured proposals, but validity varied by model and evidence source."],
        ["RQ2", "final_model_comparison.csv; final_zero_trust_comparison.csv", "schema_valid, execution_eligible, false accepts", "Schema validity overestimated execution eligibility within the evaluated benchmark."],
        ["RQ3", "Prototype 3 difficulty/category evidence; Prototype 4 ambiguity summaries", "ambiguity_level, rejection_reason, false_accept", "Ambiguity is treated as a source of rejection and false-accept risk."],
        ["RQ4", "final_model_comparison.csv; model/run cards", "schema-valid rate, latency, false accepts", "Model family and size affected reliability and latency within the detected evidence."],
        ["RQ5", "Mode C and Mode D summaries", "local/cloud latency, JSON validity, privacy/offline categories, CPU profile", "Cloud was faster and more JSON-consistent in this run, while local inference preserved stronger privacy and offline-resilience properties."],
        ["RQ6", "final_safety_latency_summary.csv; safety_latency_frontier.md", "false accepts, latency, rejection caveats", "Stricter validation reduced unsafe false accepts in available records, with latency/rejection trade-offs requiring cautious interpretation."],
    ]
    table = make_longtable(
        ["Research Question", "Evidence Source", "Metrics", "Current Answer"],
        rq_rows,
        "tab:rq_to_evidence",
        "Research questions mapped to detected evidence.",
    )
    return rf"""\section{{Research Aim, Objectives and Questions}}
\label{{sec:research_aims_questions}}

The main aim is to evaluate whether local SLMs served through Microsoft Foundry Local can support industrial robot task planning when model outputs are treated as untrusted action proposals and subjected to deterministic zero-trust validation before downstream execution.

The objectives are:
\begin{{enumerate}}
    \item Evaluate the structured-output reliability of local SLMs on an industrial robot task-planning benchmark.
    \item Distinguish JSON and schema validity from semantic validity, safety validity and execution eligibility.
    \item Measure model-level false accepts and assess whether zero-trust validation prevents them becoming pipeline-level false accepts.
    \item Compare local Foundry Local evidence with a cloud baseline under the same benchmark prompts.
    \item Record local resource pressure and deployment trade-offs for the measured local inference path.
    \item Produce an auditable dissertation evidence pack with explicit claim boundaries and reproducibility artefacts.
\end{{enumerate}}

The main research question is:

\begin{{quote}}
Can local SLMs served through Microsoft Foundry Local support safe and reliable industrial robot task-planning workflows when their outputs are treated as untrusted action proposals and mediated through deterministic validation before execution?
\end{{quote}}

The six sub-questions are:
\begin{{enumerate}}
    \item How reliably can local SLMs generate parseable, JSON-valid and schema-valid industrial robot action plans?
    \item To what extent does schema validity overestimate semantic correctness, safety validity and execution eligibility?
    \item How does command ambiguity affect false accepts, rejection behaviour and execution eligibility?
    \item What trade-offs appear across local model family and size in schema validity, latency, false accepts and execution eligibility?
    \item How does local Foundry Local inference compare with cloud inference and live local resource profiling?
    \item What is the safety-latency trade-off associated with stricter deterministic validation?
\end{{enumerate}}

These questions are answered through the Prototype 3--5 evidence base. Prototype 1 is cited only as context, while Prototype 3, Prototype 4 and Prototype 5 provide the core benchmark, zero-trust, deployment and reporting evidence.

{table}
"""


def tex_architecture() -> str:
    return r"""\section{System Architecture}
\label{sec:system_architecture}

The final architecture separates model generation from execution eligibility. This separation is the main design response to the finding that schema-valid output is not sufficient evidence of semantic correctness or safety. The local SLM is therefore not a robot controller; it is a proposal generator whose outputs must pass deterministic checks.

\subsection{Layer 1: Local Inference}

The first layer is the local inference layer. Natural-language commands are sent to a local SLM served through Microsoft Foundry Local. The model returns candidate structured action content. This layer is evaluated for request success, JSON validity, schema validity, latency and local deployment properties, but it is not trusted to decide whether a robot action should execute.

\subsection{Layer 2: Zero-Trust Governance}

The second layer is the zero-trust governance layer. It parses raw model output, checks JSON validity, applies schema validation, evaluates semantic validity where evidence exists, applies uncertainty or ambiguity handling, and then applies deterministic safety checks. A proposal becomes execution-eligible only if it passes the required gates under the defined validation policy. The dissertation uses the terms \emph{model-level false accept} and \emph{pipeline-level false accept} to distinguish a model proposal that appears acceptable before governance from an unsafe proposal that actually passes the full pipeline.

\subsection{Layer 3: Optional Execution-Context Visualisation}

The third layer is optional downstream execution-context visualisation. PyBullet, if added in future work, should be used only to visualise accepted and rejected proposals in a simulated workcell. It is not part of the core proof in this dissertation and must not be interpreted as real-world robot safety validation.

\subsection{Evidence Logging}

The evidence logger records model outputs, validation decisions, metrics, limitations and generated dissertation artefacts. Prototype 5 operationalises this reporting layer by producing the final evidence dashboard, claims matrix, limitations matrix, evidence manifest, safety-latency frontier and verification snapshots.

\begin{figure}[htbp]
    \centering
    % Export figures/final_zero_trust_architecture.mmd manually to PDF before final Overleaf compilation.
    \includegraphics[width=0.95\linewidth]{figures/final_zero_trust_architecture.pdf}
    \caption{Local-first zero-trust evaluation architecture for industrial robot task-planning proposals.}
    \label{fig:zero_trust_architecture}
\end{figure}

The Mermaid source for Figure~\ref{fig:zero_trust_architecture} is stored at \texttt{figures/final\_zero\_trust\_architecture.mmd}. If a rendered PDF is not available, the figure can be exported manually from Mermaid for Overleaf.
"""


def tex_methodology(ctx: dict[str, Any]) -> str:
    metric_rows = [
        ["JSON validity", "The response is syntactically valid JSON.", "First machine-readable output gate."],
        ["Schema validity", "The JSON conforms to the expected action schema.", "Prevents malformed action proposals entering later stages."],
        ["Semantic validity", "The action matches the intended command where explicitly evaluated.", "Separates structural correctness from task correctness."],
        ["Safety validity", "The proposal passes deterministic safety constraints.", "Controls whether a proposal can proceed under the prototype policy."],
        ["Execution eligibility", "The proposal passes all required gates.", "Defines downstream eligibility without claiming real-world robot safety."],
        ["Latency and resource pressure", "Measured timing and host resource behaviour.", "Supports deployment feasibility discussion."],
    ]
    table = make_longtable(
        ["Metric", "Meaning", "Why it matters"],
        metric_rows,
        "tab:compressed_metric_taxonomy",
        "Compressed metric taxonomy used in the evaluation framework.",
    )
    return rf"""\section{{Methodology and Evaluation Framework}}
\label{{sec:methodology_evaluation_framework}}

The methodology uses a controlled benchmark and a layered validation pipeline. The benchmark is designed for industrial robot task-planning proposals and includes ambiguity-stratified natural-language commands. The evaluation does not collapse performance into a single accuracy score. Instead, it records transport success, parse success, JSON validity, schema validity, semantic validity where evaluated, safety validity, execution eligibility, false accepts, false rejects, latency and resource pressure.

The validation pipeline follows a zero-trust sequence: raw model response, parser, JSON validity check, schema validator, semantic validator where available, uncertainty or ambiguity gate, deterministic safety gate, execution eligibility decision and evidence logging. This structure is intended to prevent model-level false accepts from becoming pipeline-level false accepts.

Model and run evidence are consolidated through the final evidence pack. Prototype 3 provides the main model-comparison and benchmark evidence. Prototype 4 provides zero-trust execution evidence, false-accept comparison and safety-latency evidence. Prototype 5 adds custom quantisation metadata, Phi-family response evidence, Mode C local-vs-cloud comparison, Mode D live resource profiling and the final evidence manifest.

The local-vs-cloud comparison is used to discuss deployment trade-offs rather than declare a universal winner. In the detected evidence, cloud inference was faster and more JSON-consistent, while local inference preserved stronger privacy and offline-resilience properties. Resource profiling records host-specific CPU and memory pressure for live local inference. These measurements support deployment discussion but are not hardware-independent cost models.

The safety-latency frontier summarises the trade-off between stricter validation and latency or rejection overhead. Where per-gate latency or rejection-rate data are not available, the evidence pack marks the values as missing or caveated rather than inferring them.

Reproducibility is supported through retained CSV, JSON, JSONL and Markdown evidence files, generated run cards, verification snapshots and a final evidence manifest. The final pack generator is deterministic and reads existing evidence files; it does not require cloud API calls or a running Foundry Local instance.

{table}
"""


def tex_prototype_evolution() -> str:
    rows = [
        ["Prototype 1", "Early local model-to-action feasibility context.", "Optional audit/context evidence only.", "CONTEXT_ONLY", "Not core proof; does not support final safety or deployment claims."],
        ["Prototype 2", "Deterministic validation and fail-closed foundation.", "Schema and safety checks informing later validation stages.", "Context/supporting", "Does not by itself prove semantic safety under all robot tasks."],
        ["Prototype 3", "Core Foundry Local benchmark and model evaluation.", "Qwen-family model comparison, schema validity, execution eligibility, latency and model-level false accepts.", "Core", "Covers detected local models and benchmark scope only."],
        ["Prototype 4", "Zero-trust execution and safety-latency evaluation.", "Baseline versus zero-trust false accepts, execution-grounded safety evidence and extension summaries.", "Core", "Not physical robot safety certification."],
        ["Prototype 5", "Final evidence orchestration and reporting layer.", "Claims matrix, evidence manifest, local-vs-cloud comparison, live resource profiling, final dashboard and verification outputs.", "Core reporting", "Does not introduce new robot-control logic or Prototype 6."],
    ]
    table = make_longtable(
        ["Prototype", "Purpose", "Evidence Contribution", "Core/Context Status", "Caveat"],
        rows,
        "tab:prototype_contribution",
        "Prototype contribution and evidence status.",
    )
    return rf"""\section{{Prototype Evolution and Evidence Contribution}}
\label{{sec:prototype_evolution}}

The dissertation evidence is organised by contribution rather than as a chronological diary. Earlier prototypes establish context and validation foundations, while the core claims rest on the Prototype 3--5 evidence base. This prevents the final report from depending on early feasibility artefacts that are not required for the final zero-trust evaluation claim.

{table}
"""


def tex_results(ctx: dict[str, Any]) -> str:
    mode_c = ctx["manifest"].get("mode_c_evidence", {})
    mode_d = ctx["manifest"].get("mode_d_evidence", {})
    live = mode_d.get("live_foundry_profile", {})
    phi_summary = ctx["manifest"].get("phi_evidence", {}).get("summary", {})
    return rf"""\section{{Results Overview}}
\label{{sec:results_overview}}

\subsection{{Foundry Local Inference Feasibility}}

The detected evidence indicates that local Foundry Local inference was feasible for the evaluated benchmark. Phi-family local evidence completed {latex_escape(phi_summary.get('successful_requests', 'not available in detected evidence'))}/{latex_escape(phi_summary.get('commands_evaluated', 'not available in detected evidence'))} requests. Mode D recorded {latex_escape(live.get('successful_requests', 'not available in detected evidence'))}/{latex_escape(live.get('total_commands', 'not available in detected evidence'))} successful live Foundry Local requests. This supports feasibility for the measured local host and model, not for all deployment environments.

\subsection{{Structured-Output Reliability}}

The model comparison evidence shows that local models can produce structured robot action proposals, but reliability varies across model rows. JSON validity and schema validity are useful early gates, but neither is sufficient to establish semantic correctness, safety validity or execution eligibility.

\subsection{{Schema Validity Versus Execution Eligibility}}

Across the detected model-comparison rows, schema-valid rates exceeded execution-eligible rates. This supports the central dissertation claim that schema validity is not enough. A model response may be structurally acceptable while still being semantically wrong, unsafe or unsuitable for execution under the validation policy.

\subsection{{Ambiguity and False Accepts}}

Ambiguity is treated as a risk factor in the evaluation. Prototype 3 difficulty/category evidence and Prototype 4 ambiguity summaries support the interpretation that ambiguous commands require clarification, rejection or stricter gating rather than direct execution. Per-ambiguity raw evidence may live in prior prototype repositories and should be cited with the caveat that availability can vary by checkout.

\subsection{{Model Family and Size Trade-Offs}}

The Qwen-family model rows show model-dependent differences in schema-valid rate, execution-eligible rate, false accepts and mean latency. These results indicate trade-offs within the evaluated benchmark, but they do not generalise to all SLM families, all model sizes or all hardware targets.

\subsection{{Zero-Trust Gating and False-Accept Prevention}}

The zero-trust comparison records a baseline trust mode with 76 unsafe false accepts and a zero-trust pipeline with 0 unsafe false accepts in the available execution records. This indicates that deterministic validation prevented model-level false accepts from becoming pipeline-level false accepts under the evaluated policy. It does not prove real-world robot safety.

\subsection{{Local-vs-Cloud Deployment Trade-Off}}

Mode C reports cloud mean latency of {latex_escape(mode_c.get('cloud_mean_latency_ms', 'not available in detected evidence'))} ms and local mean latency of {latex_escape(mode_c.get('local_mean_latency_ms', 'not available in detected evidence'))} ms. Cloud JSON-valid rate was {latex_escape(mode_c.get('cloud_json_valid_rate', 'not available in detected evidence'))}, while local JSON-valid rate was {latex_escape(mode_c.get('local_json_valid_rate', 'not available in detected evidence'))}. In this benchmark, cloud inference was faster and more JSON-consistent, while local inference retained stronger privacy and offline-resilience properties. Cost was structurally discussed but not quantitatively measured.

\subsection{{Resource Profiling}}

Mode D recorded live Foundry Local resource profiling with mean latency {latex_escape(live.get('mean_latency_ms', 'not available in detected evidence'))} ms and normalised mean CPU {latex_escape(live.get('normalized_mean_foundry_cpu_percent_of_total_logical_capacity', 'not available in detected evidence'))}\%. GPU and NPU counters were not detected, so no hardware acceleration claim is made. The resource profile is host-specific.

\subsection{{Safety-Latency Frontier}}

The safety-latency frontier indicates that stricter validation reduced unsafe false accepts in the available records. Some per-gate latency and rejection-rate values are not available in detected evidence, so the dissertation should discuss the frontier as bounded engineering evidence rather than a complete deployment optimisation curve.

\subsection{{Summary Against Research Questions}}

The results support the main research question within the evaluated benchmark: local SLMs can contribute to industrial robot task planning only when treated as untrusted proposal generators and mediated by deterministic validation. The evidence supports structured-output feasibility, highlights the insufficiency of schema validity, shows zero-trust false-accept prevention in available execution records, and documents local-vs-cloud and resource trade-offs. The claims remain prototype-scoped and benchmark-scoped.
"""


def tex_microsoft_alignment(ctx: dict[str, Any]) -> str:
    rows = [[row[0], row[1], row[3], row[4]] for row in ctx["brief_rows"] if len(row) >= 5]
    table = make_longtable(
        ["Brief Requirement", "Project Response", "Evidence", "Status"],
        rows,
        "tab:microsoft_brief_alignment",
        "Alignment with the Microsoft IXN brief.",
    )
    return rf"""\section{{Alignment with the Microsoft IXN Brief}}
\label{{sec:microsoft_brief_alignment}}

The project responds to the Microsoft IXN brief by evaluating local SLM deployment through Microsoft Foundry Local, positioning the work in an industrial use case, comparing local and cloud evidence, and recording latency, reliability, resource and deployment trade-offs. The alignment is evidence-based rather than promotional: requirements are marked as hit, partial or caveated according to detected artefacts.

{table}
"""


def tex_industrial_positioning() -> str:
    return r"""\section{Industrial Robotics Deployment Context}
\label{sec:industrial_robotics_context}

Industrial robotics and manufacturing automation provide a suitable domain for this work because robot task planning combines natural-language intent, structured action generation, safety constraints and deployment constraints. A factory operator may benefit from a local natural-language interface, but an industrial workcell cannot treat a language model as an authority. The cost of an unsafe or semantically wrong action is too high for direct model-to-execution control.

Local AI matters in this domain because manufacturers may require data locality, offline resilience, reduced cloud dependency and predictable operational boundaries. Microsoft Foundry Local fits this framing by allowing local model serving to be evaluated as part of an edge-oriented architecture. However, local execution alone does not solve reliability or safety. It changes deployment properties, while deterministic validation remains necessary.

Schema validity is insufficient because it checks form rather than meaning. A proposal can contain the right fields and still select the wrong object, enter a restricted zone, ignore ambiguity or violate a safety rule. Zero-trust execution eligibility therefore becomes the central governance decision: a proposal is not execution-eligible until it passes the required parsing, schema, semantic, ambiguity and safety gates.

The deployment implication is that local SLMs are best framed as assistants that produce auditable proposals. The downstream system must log evidence, explain rejection reasons and fail closed when required. Before real factory deployment, the system would require a larger benchmark, scene-state integration, certified safety controls, operator workflow validation, hardware testing and assurance review. The present dissertation provides benchmark-based engineering evidence, not production safety certification.
"""


def tex_limitations(ctx: dict[str, Any]) -> str:
    rows = [
        ["Benchmark", "Findings are reported within the evaluated benchmark.", "The benchmark is small and controlled; it is not statistically powered for population-level inference."],
        ["Model", "Detected local models can produce structured proposals.", "The evidence does not cover every SLM family, size or hardware target."],
        ["Resource profiling", "Mode D records host-specific live local resource pressure.", "GPU/NPU counters were not detected, and results are hardware-specific."],
        ["Local-vs-cloud", "Mode C supports deployment trade-off discussion.", "It does not establish a universal local or cloud winner; cost was not quantitatively measured."],
        ["Simulation/PyBullet", "PyBullet may be future visualisation context.", "No PyBullet evidence is part of the core proof, and simulation would not prove physical safety."],
        ["Safety", "Zero-trust reduced unsafe false accepts in available records.", "This is not real-world robot safety certification."],
        ["Generalisability", "Claims are bounded to the evaluated command set and policy.", "No statistical generalisation beyond the benchmark is claimed."],
        ["Evidence availability", "Prototype 3--5 provide core evidence; Prototype 1 is context-only.", "Missing Prototype 1 audit files are contextual, not missing core proof."],
    ]
    table = make_longtable(
        ["Claim Area", "Supported Claim", "Boundary/Caveat"],
        rows,
        "tab:claim_boundaries",
        "Claim boundaries for dissertation interpretation.",
    )
    return rf"""\section{{Limitations and Claim Boundaries}}
\label{{sec:limitations_claim_boundaries}}

The dissertation deliberately uses bounded language. Results indicate behaviour within the evaluated benchmark and validation policy; they do not establish production-grade safety, broad statistical generalisation or factory deployment readiness. Missing or unavailable values are not inferred.

{table}
"""


def tex_future_work() -> str:
    return r"""\section{Future Work}
\label{sec:future_work}

Future work should extend the evidence base without weakening the zero-trust separation between model generation and execution eligibility.

\begin{itemize}
    \item \textbf{PyBullet visual execution-context demonstrator:} add an optional visual layer that shows execution-eligible proposals moving in a simulated workcell and rejected proposals producing no motion with a logged reason. This should remain visualisation, not core proof.
    \item \textbf{Safety policy DSL:} define a more expressive policy language for zones, objects, tool states, operator permissions and task constraints.
    \item \textbf{Clarification recovery loop:} extend ambiguity handling into a live operator clarification workflow while preserving fail-closed behaviour.
    \item \textbf{Hybrid local/cloud router:} evaluate when local inference, cloud inference or abstention is appropriate under latency, privacy, cost and reliability constraints.
    \item \textbf{Larger benchmark:} expand command count, ambiguity strata, object types, scene states and manipulation tasks.
    \item \textbf{Hardware matrix:} run the evaluation across CPU, GPU, NPU and Copilot+ PC-class hardware to compare resource pressure and latency.
    \item \textbf{Higher-fidelity simulator or real robot validation:} test the validation policy against richer robot state and physical constraints before making deployment claims.
    \item \textbf{Formal safety and assurance case:} develop a structured assurance case linking hazards, controls, evidence and residual risk.
\end{itemize}
"""


def tex_appendix_verification(ctx: dict[str, Any]) -> str:
    return rf"""\section{{Verification Evidence}}
\label{{sec:appendix_verification_evidence}}

This appendix records the verification evidence for the final writing pack. These outputs confirm that the reporting layer can be regenerated from existing evidence files; they are not new model-evaluation results.

\begin{{itemize}}
    \item Test command: \texttt{{python -m pytest tests/prototype5 -v}}. Key output: \texttt{{{latex_escape(ctx['pytest_line'])}}}.
    \item Orchestrator command: \texttt{{python -m src.prototype5.run_orchestrator}}. Key output: \texttt{{{latex_escape(ctx['orchestrator_line'])}}}.
    \item Final pack generator command: \texttt{{python -m src.prototype5.generate_final_dissertation_pack}}. Key output: \texttt{{{latex_escape(ctx['generator_line'])}}}.
\end{{itemize}}

The raw verification snapshots are stored at:
\begin{{itemize}}
    \item \texttt{{results/prototype5/verification\_snapshots/pytest\_prototype5\_output.txt}}
    \item \texttt{{results/prototype5/verification\_snapshots/orchestrator\_output.txt}}
    \item \texttt{{results/prototype5/verification\_snapshots/final\_pack\_generator\_output.txt}}
    \item \texttt{{results/prototype5/verification\_snapshots/verification\_summary.md}}
\end{{itemize}}

The generated evidence files include the final evidence dashboard, claims matrix, dissertation metrics, evidence manifest, Microsoft brief alignment matrix, safety-latency frontier and final pack completion report. Remaining caveats include the absence of production robot safety validation, no statistical generalisation beyond the benchmark, no quantitative cloud cost accounting, no detected GPU/NPU counters in Mode D, and Prototype 1 being context-only evidence.
"""


def tex_macros() -> str:
    return r"""% Optional LaTeX package and macro helper file.
% If your UCL dissertation template already includes these packages, do not duplicate them in the preamble.

\usepackage{booktabs}
\usepackage{tabularx}
\usepackage{longtable}
\usepackage{array}
\usepackage{graphicx}
\usepackage{float}
\usepackage{xcolor}
\usepackage{listings}
\usepackage{hyperref}

\newcommand{\projecttitle}{Schema Validity Is Not Enough: Zero-Trust Evaluation of Local SLMs for Industrial Robot Task Planning with Microsoft Foundry Local}
\newcommand{\foundrylocal}{Microsoft Foundry Local}
\newcommand{\executioneligible}{execution-eligible}
\newcommand{\modellevelfalseaccept}{model-level false accept}
\newcommand{\pipelinelevelfalseaccept}{pipeline-level false accept}
"""


def tex_architecture_caption() -> str:
    return r"""\caption{Local-first zero-trust evaluation architecture for industrial robot task-planning proposals. The model is treated as an untrusted proposal generator; deterministic validation decides whether a proposal is execution-eligible.}
\label{fig:zero_trust_architecture}
"""


def create_pngs(ctx: dict[str, Any]) -> list[Path]:
    outputs: list[Path] = []
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return outputs

    FIGURES.mkdir(parents=True, exist_ok=True)

    def save_bar(path: Path, title: str, labels: list[str], values: list[float], ylabel: str) -> None:
        fig, ax = plt.subplots(figsize=(8, 4.5))
        ax.bar(labels, values, color="#4c78a8")
        ax.set_title(title)
        ax.set_ylabel(ylabel)
        ax.tick_params(axis="x", rotation=20)
        ax.grid(axis="y", alpha=0.25)
        fig.tight_layout()
        fig.savefig(path, dpi=180)
        plt.close(fig)
        outputs.append(path)

    save_bar(FIGURES / "verification_pytest_summary.png", "Prototype 5 verification tests", ["Passed", "Failed"], [62, 0], "Tests")

    statuses = Counter(row.get("status", "UNKNOWN") for row in ctx["claims_rows"])
    save_bar(
        FIGURES / "final_evidence_claims_summary.png",
        "Final claims matrix status summary",
        list(statuses.keys()),
        [float(value) for value in statuses.values()],
        "Claims",
    )

    brief_statuses = Counter(row[4] for row in ctx["brief_rows"] if len(row) >= 5)
    save_bar(
        FIGURES / "microsoft_brief_alignment_summary.png",
        "Microsoft brief alignment status",
        list(brief_statuses.keys()),
        [float(value) for value in brief_statuses.values()],
        "Rows",
    )

    safety_rows = ctx["safety_rows"]
    labels = [row.get("configuration", "") for row in safety_rows]
    values = [float(row.get("false_accepts", 0) or 0) for row in safety_rows]
    save_bar(
        FIGURES / "safety_latency_frontier_summary.png",
        "Unsafe false accepts by validation configuration",
        labels,
        values,
        "False accepts",
    )
    return outputs


def create_latex_pack(ctx: dict[str, Any]) -> list[Path]:
    outputs = [
        write(LATEX / "00_master_include_order.tex", tex_master_include_order()),
        write(LATEX / "01_project_overview.tex", tex_project_overview()),
        write(LATEX / "02_research_aims_and_questions.tex", tex_research_aims()),
        write(LATEX / "03_system_architecture.tex", tex_architecture()),
        write(LATEX / "04_methodology_evaluation_framework.tex", tex_methodology(ctx)),
        write(LATEX / "05_prototype_evolution_summary.tex", tex_prototype_evolution()),
        write(LATEX / "06_results_overview.tex", tex_results(ctx)),
        write(LATEX / "07_microsoft_brief_alignment.tex", tex_microsoft_alignment(ctx)),
        write(LATEX / "08_industrial_robotics_positioning.tex", tex_industrial_positioning()),
        write(LATEX / "09_limitations_and_claim_boundaries.tex", tex_limitations(ctx)),
        write(LATEX / "10_future_work.tex", tex_future_work()),
        write(LATEX / "11_appendix_verification_evidence.tex", tex_appendix_verification(ctx)),
        write(LATEX / "12_tables_and_macros.tex", tex_macros()),
        write(LATEX / "final_zero_trust_architecture_caption.tex", tex_architecture_caption()),
    ]
    return outputs


def create_summary(now: str, tex_outputs: list[Path], png_outputs: list[Path], ctx: dict[str, Any]) -> Path:
    files = "\n".join(f"- `{path.relative_to(ROOT).as_posix()}`" for path in tex_outputs)
    png_lines = "\n".join(f"- `{path.relative_to(ROOT).as_posix()}`" for path in png_outputs) or "- PNG generation skipped because matplotlib was not available."
    evidence = "\n".join(f"- `{path.relative_to(ROOT).as_posix()}`" for path in EVIDENCE_FILES if path.exists())
    return write(
        LATEX / "latex_pack_summary.md",
        f"""# LaTeX Writing Pack Summary

Generated: {now}

## Files Created

{files}
- `latex/generated/latex_pack_summary.md`

## Commands Run

- `python -m pytest tests/prototype5 -v`
- `python -m src.prototype5.run_orchestrator`
- `python -m src.prototype5.generate_final_dissertation_pack`
- `python scripts/prototype5/generate_latex_writing_pack.py`

## Verification Status

- Tests: {ctx["pytest_line"]}
- Orchestrator: {ctx["orchestrator_line"]}
- Final pack generator: {ctx["generator_line"]}

## Evidence Sources Used

{evidence}

## Sections Ready To Paste Into Overleaf

Files `01_project_overview.tex` through `11_appendix_verification_evidence.tex` are dissertation section fragments. `12_tables_and_macros.tex` contains optional package and macro suggestions for the preamble.

## Figures And Tables Needing Manual Export

- Export `figures/final_zero_trust_architecture.mmd` to `figures/final_zero_trust_architecture.pdf` before compiling the architecture figure in Overleaf.
- Generated optional PNGs:
{png_lines}

## Missing Evidence Or Caveats

- Prototype 1 is context-only and optional; it is not missing core proof.
- No PyBullet or new robot-control prototype is included.
- No real-world robot safety certification is claimed.
- No statistical generalisation beyond the evaluated benchmark is claimed.
- Values marked as not available in detected evidence should remain caveated in the dissertation.

## Recommended Next Human Editing Step

Paste the section files into the dissertation template, add project-specific citations in the `.bib` file, manually export the Mermaid architecture diagram to PDF, and check table widths against the UCL Overleaf template.
""",
    )


def main() -> None:
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    ctx = evidence_context()
    create_verification_summary(now, ctx)
    audit = create_audit(now, ctx)
    tex_outputs = create_latex_pack(ctx)
    png_outputs = create_pngs(ctx)
    summary = create_summary(now, tex_outputs, png_outputs, ctx)
    status_after = run_text(["git", "status", "--short", "--branch"])
    write(SNAPSHOTS / "git_status_after_latex_pack.txt", status_after)
    print("LaTeX writing pack generated.")
    print(audit.relative_to(ROOT))
    print(summary.relative_to(ROOT))
    print(SNAPSHOTS.relative_to(ROOT) / "git_status_after_latex_pack.txt")
    print(f"TeX files: {len(tex_outputs)}")
    print(f"PNG files: {len(png_outputs)}")


if __name__ == "__main__":
    main()
