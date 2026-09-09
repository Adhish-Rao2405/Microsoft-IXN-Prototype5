# Six-figure qualification

FIGURE_GATE=PASS
VISUAL_QUALIFICATION_COMPLETED=YES
PUBLICATION_VISUAL_COUNT=6
ASSET_FILE_COUNT=24
FILE_BACKED_ARTICLE_SHA_MATCH=YES
LOCKED_ARTICLE_MODIFIED=NO
CANONICAL_MARKDOWN_MODIFIED=NO
OVERLEAF_MANUSCRIPT_MODIFIED=NO
FULL_ARTICLE_RENDERED=NO
COMMIT_CREATED=NO
PUSH_EXECUTED=NO

## Locked reference

Authoritative file: `C:\Users\reach\Microsoft-IXN-Prototype5-integrated-demo\docs\microsoft_blog\microsoft_blog_final_text_file_backed.md`

SHA256 before and after the figure work: `A25F2BB3869D9B1D4D45365A342DA7C60DE3E5A80DA5C2FDBA9A5751C489ABD0`.

Direct text review confirmed every requested anchor:

- Title: Schema Validity Is Not Enough.
- Subtitle: Governing Local SLM Robot Planning with Microsoft Foundry Local.
- Selected P3 run: 25/30 schema-valid, 4/30 execution-eligible, and the separate 12 model-level false accepts.
- C10: gauze pack and `ambiguous_reference`.
- P4: accepted 90 → 18 → 14 → 14; retained successes 14 → 14 → 14 → 14; false-accept classifications 76 → 4 → 0 → 0.
- D4.3: 18/18 invariant pairs.
- D4.5: seven valid microphone attempts, six submissions, one discard, and six parse failures.
- B3.2: 118 support-material penetration findings and zero physics steps.
- Physical execution authority remains `NOT_IMPLEMENTED`.
- Results remain bounded to dissertation evidence; future work is presented as future work. No post-dissertation results were added.

## Visual decisions and inspection

The latest user-supplied six-figure specification governs this set. Earlier seven-figure briefs remain historical files. The approved compact vertical layouts supersede their earlier landscape requirement.

| Order | Source stem | Technical and visual result |
| --- | --- | --- |
| 1 | fig01_hero | PASS. Minimal MODEL PROPOSAL ≠ AUTHORITY treatment; miniature gate sequence removed. Physical authority remains unavailable. |
| 2 | fig02_foundry_local_stack | PASS. Application/runtime/hardware/governance composition retained. Microsoft and project ownership are explicit; runtime details reflowed into two columns; hardware coverage caveat remains visible. |
| 3 | fig04_zero_trust_architecture | PASS. Only ACCEPT leads to eligibility and a separate qualification step. CLARIFY/REJECT terminates at no progression. Frozen evidence has independent provenance and no incoming derivation arrow. Physical authority is terminal and NOT_IMPLEMENTED. |
| 4 | fig05_validity_funnel | PASS. 30 → 25 → 4 retained. The 12 classification is spatially separated with no funnel arrow. Selected model, run, denominator and interpretation are visible and in the caption. Container widths are schematic. |
| 5 | fig08_p4_admission_rules | PASS. The locked heading, all three aligned count sequences, prior-success qualification and retrospective scope are retained. No time axis, causal intervention or physical-safety symbolism. |
| 6 | fig07_voice_boundary | PASS. Explicit operator review precedes submission. Reviewed and typed commands converge on the same path. Architecture-only and no speech-accuracy claim remain visible. |

All six figures were visually inspected in actual 390-pixel browser screenshots and again in 390-pixel rasterizations of their PDF exports. Text is readable without zoom, with no visible clipping, collisions or ambiguous connectors. Labels use at least 14 CSS pixels at that width. The layouts use explicit labels in addition to colour. Browser screenshots at 900 pixels are also retained; the visual pass is based on the more restrictive 390-pixel inspection.

Automated checks confirmed no glyph-ink text overlaps or out-of-canvas text. Glyph-ink bounds were used because SVG font-wide bounding boxes produce false collisions for large mathematical symbols; visual inspection independently confirmed the result.

Each PDF is one page with the expected canvas bounds, selectable text matching every SVG label, vector content and no embedded raster images. Each Overleaf copy matches its corresponding exported PDF byte-for-byte. The PDF/browser pixel-difference values in the integrity record are diagnostic only; different rasterizers are not expected to produce identical pixels.

## Delivery records

- [Complete exact-path and SHA256 inventory, with captions and alt text](PUBLICATION_INVENTORY.md)
- [Machine-readable 24-file hash inventory](asset_hashes.json)
- [Browser export and layout checks](export_checks.json)
- [PDF checks and baseline integrity comparison](integrity_checks.json)
- [Browser mobile preview, figures 1–3](mobile_contact_sheet_1.png)
- [Browser mobile preview, figures 4–6](mobile_contact_sheet_2.png)
- [PDF mobile preview, figures 1–3](pdf_contact_sheet_1.png)
- [PDF mobile preview, figures 4–6](pdf_contact_sheet_2.png)

The P4 caption begins with the required exact sentence: “Same 120 retained records; dependent retrospective reclassification.” It additionally explains that the 14 retained successes are previously classified records. Captions and alt text are supplied separately for later integration; they have not been inserted into either manuscript.

## Scope and closure

Five existing figure families were updated, accounting for 20 existing SVG/PNG/PDF asset paths. One new P4 family adds four asset paths. Historical chronology and local/cloud figures, historical review PDFs, screenshots and videos were preserved. All other files in the 44-file blog baseline retain their original hashes, including the locked article, canonical Markdown and Overleaf manuscript.

Edits and generated outputs are confined to the blog figure directories and corresponding `docs/microsoft_blog/overleaf/figures` PDF copies. Dissertation, P5 implementation and submission evidence paths were outside the edit scope. No experimental reruns or additional result claims were introduced.

Only individual figures were rendered. No full article render, commit or push was performed.

## Hero terminology refinement — 2026-09-08

The subsequent publication integration gate authorized the hero-only refinement to “Physical execution authority: NOT_IMPLEMENTED”. Only the hero SVG and its PNG/PDF exports were regenerated. The other five publication figure families retain their approved bytes. The hero passed the same 390-pixel layout check and visual inspection, and the inventory now records its updated hashes. The full-article render status above describes the earlier figure gate; the later integration render is recorded separately under `reviews/publication_integration`.
