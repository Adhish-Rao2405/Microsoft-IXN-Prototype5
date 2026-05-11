# DISS Draft Cleanup Report

## Files Copied

- `dissertation_drafts/DISS_DRAFT.pdf`
- `dissertation_drafts/DISS_DRAFT.tex`

The PDF and source were already present in `dissertation_drafts/` when cleanup began.

## Files Created

- `dissertation_drafts/DISS_DRAFT_cleaned.tex`
- `dissertation_drafts/references.bib`
- `dissertation_drafts/DISS_DRAFT_cleanup_report.md`

## LaTeX Issues Fixed

- Removed the duplicate `Conclusion` heading.
- Removed duplicate bibliography blocks and retained one ACM bibliography setup.
- Kept ACM format with `\documentclass[sigconf,nonacm]{acmart}`.
- Kept section-only hierarchy; no `\chapter` commands are present.
- Reorganised section hierarchy into Introduction, Background and Related Work, System Design and Methodology, Results and Evaluation, Discussion, Conclusion and Appendix.
- Converted system design, methodology, prototype evolution, results and discussion child headings to `\subsection{...}` under their parent sections.
- Replaced the broken architecture `\includegraphics` call with a boxed placeholder because `figures/final_zero_trust_architecture.pdf` is not present.
- Escaped appendix command underscores in `\texttt{python -m src.prototype5.run\_orchestrator}` and `\texttt{python -m src.prototype5.generate\_final\_dissertation\_pack}`.
- Added `references.bib` entry for `microsoft_foundry_local_docs`.
- Kept wide tables as `table*` with `tabularx`; no `longtable` is used in the cleaned ACM body.

## Remaining Manual Overleaf Tasks

- Expand the `Background and Related Work` placeholder with the final literature review and citations.
- Upload or export the final architecture diagram if replacing the placeholder later.
- Run a full Overleaf compile using the ACM template and check table float placement.
- Add all final bibliography entries beyond the Microsoft Foundry Local placeholder.
- Polish transitions so the final document reads as one dissertation rather than assembled evidence sections.

## Local PDF Compilation

Local PDF compilation was attempted with:

```powershell
pdflatex -interaction=nonstopmode -halt-on-error DISS_DRAFT_cleaned.tex
```

The compile did not reach document processing because the local MiKTeX installation reported that first-run/update setup has not been completed:

```text
pdflatex: major issue: So far, you have not checked for MiKTeX updates.
```

Overleaf should therefore be used as the primary ACM compile environment unless the local MiKTeX installation is updated/configured.

## Caveats

- No Prototype 5 core logic, metrics, benchmark results or evidence values were changed.
- No cloud API calls were made.
- No PyBullet implementation or Prototype 6 was added.
- Claims remain bounded to the evaluated benchmark and validation policy.
- The cleaned source does not claim real-world robot safety, production deployment readiness or statistical generalisation beyond the benchmark.
