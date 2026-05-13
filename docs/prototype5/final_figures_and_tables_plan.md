# Final Figures And Tables Plan

## Purpose

This plan lists the figures and tables that should carry the dissertation argument. It prioritises evidence clarity over prototype chronology.

## Required Figures

| Figure | Chapter | Purpose | Source evidence | Status |
|---|---|---|---|---|
| System evolution diagram | Chapter 1 or 3 | Show Prototype 1 to Prototype 5 as one research system. | Prototype descriptions; final evidence pack. | Writing/diagram task only. |
| Local SLM planning pipeline | Chapter 3 | Show natural language to model proposal to deterministic validation. | Validation pipeline docs; zero-trust architecture. | Writing/diagram task only. |
| Zero-trust architecture diagram | Chapter 3 or 4 | Show fail-closed deterministic gates. | `figures/final_zero_trust_architecture.mmd`; final dashboard. | Existing figure spec available. |
| Validation funnel | Chapter 4 | Show request success to parse/JSON/schema/semantic/safety/execution-eligible. | E0.4 and Mode E.2 metrics. | Writing/plot task only. |
| Schema-valid vs execution-eligible bar chart | Chapter 4 | Show central gap visually. | E0.4 and Mode E.2 metrics. | Writing/plot task only. |
| Latency distribution or summary figure | Chapter 4/5 | Support supervisory/offline deployment framing. | E0.4 latency; Mode E.2 latency; Mode D resource profile. | Writing/plot task only. |

## Required Tables

| Table | Chapter | Purpose | Source evidence | Status |
|---|---|---|---|---|
| Research questions and evidence map | Chapter 1/3 | Connect RQ1-RQ5 to evidence. | `docs/prototype5/rq_to_evidence_matrix.md`; `results/prototype5/dissertation_rq_evidence_matrix.csv`. | Created as planning artefact. |
| Prototype contribution matrix | Chapter 3 | Prevent build-log narrative by assigning each prototype a research role. | `docs/prototype5/dissertation_argument_map.md`. | Writing task only. |
| Benchmark composition table | Chapter 3 | Show original benchmark and Mode E benchmark scope. | benchmark configs; Mode E audit. | Writing task only. |
| E0.4 repeatability metrics | Chapter 4 | Show stable live-repeatability evidence. | `results/prototype5/mode_e0/full_pipeline_live_repeatability_summary.json`. | Metrics available. |
| Mode E.2 industrial metrics | Chapter 4 | Show industrial benchmark evidence. | `results/prototype5/mode_e/mode_e2_live_industrial_summary.json`. | Metrics available. |
| E0.4 vs Mode E.2 descriptive comparison | Chapter 4 | Show the gap persists across benchmark conditions without claiming statistical generality. | E0.4 and Mode E.2 summaries. | Writing task only. |
| Model false accepts vs pipeline false accepts | Chapter 4 | Support zero-trust validation claim. | Prototype 4 comparison; E0.4; Mode E.2. | Writing task only. |
| Deployment suitability matrix | Chapter 5 | Position local-first system as supervisory/offline, not closed-loop control. | Mode C/D; E0.4 and Mode E.2 latency. | Writing task only. |
| Limitations and future work table | Chapter 5 | Keep boundaries visible and examiner-safe. | `docs/prototype5/examiner_safe_claims_and_boundaries.md`. | Writing task only. |

## Figures And Tables Not Needed

Avoid adding figures that make the work look like a product demo:

- dashboard screenshots
- synthetic robot execution screenshots
- new simulator diagrams
- new mode timelines beyond Prototype 1 to Prototype 5
- marketing-style architecture graphics

## Final Writing Rule

Every figure or table should support one of three moves:

1. prove local proposal generation is feasible but bounded
2. show schema validity overestimates execution eligibility
3. show deterministic validation and deployment boundaries

If a figure does not support one of those moves, omit it.

