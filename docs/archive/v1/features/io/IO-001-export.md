---
id: IO-001
title: "Manuscript Export"
status: stable
area: io
mvp: false

ui_tooltip: "Export your manuscript as PDF, ePub, DOCX, or Markdown."
ui_help_short: |
  Export your finished or in-progress manuscript to industry-standard formats.
  Generate a formatted PDF for printing or sharing, an ePub for e-readers, a
  DOCX for your editor, or clean Markdown for further processing.
ui_help_long: |
  ## Manuscript Export

  When your manuscript is ready to leave Narrare — for a beta reader, an editor,
  a print-on-demand service, or your own archive — Export produces clean,
  properly formatted files.

  **Available formats:**

  - **PDF** — Formatted with customizable fonts, margins, and page layout.
    Suitable for printing and sharing.
  - **ePub** — Re-flowable e-book with chapter navigation and metadata.
    Works on Kindle (via conversion), Apple Books, Kobo, and other readers.
  - **DOCX** — Word-compatible document. Ideal for sending to editors or
    agents who expect track-changes capability.
  - **Markdown** — Plain text with structure. Useful for version control,
    static site generators, or feeding into other tools.

  **What gets exported:**
  All chapters in the selected volume, ordered by their position. Front matter
  (title page, copyright) and back matter are generated from project metadata.
  Optional inclusions: chapter summaries, character lists, location glossary.

  Export is non-destructive — your Narrare project is never modified.
ui_available_in: [dashboard, editor]

service: export/service.py
contract: ~
router: ~
prompt: ~
requires: [WRITE-011]
---

# IO-001 — Manuscript Export

> **Status:** ✅ Implemented / Stable — [ADR-081](../../architecture/decisions/ADR-081-export-pipeline-typst.md) fully implemented across Slices 0–8 + follow-ups; PR #163 CI green (Golden-Pages 26 passed, EPUBCheck passed). Shipped formats: **PDF** (Typst + `narrare-roman`, drop cap optional default off), **EPUB** (pandoc EPUB3, isbn/description metadata), **Markdown** (pandoc), **DOCX** (pandoc `--reference-doc` manuscript format, C3). No formats remain deferred.

## What it does

Converts a Narrare manuscript into downloadable files in PDF, ePub, DOCX, or
Markdown format. Export respects chapter ordering, includes optional front and
back matter generated from project metadata, and produces files ready for
editors, beta readers, or self-publishing platforms.

## Why it exists

A manuscript locked inside a writing tool is useless. Writers need to share
their work with editors who use Word, submit to publishers who expect specific
formats, load onto e-readers for personal review, or archive in a portable
format. Narrare's local-first philosophy means the writer owns their work —
export is how they take it anywhere.

The vision calls for an environment that is "available when you need it and
invisible when you don't." Export is the off-ramp: when you are done writing,
one click gets your manuscript out.

## Architecture Decision — [ADR-081](../../architecture/decisions/ADR-081-export-pipeline-typst.md)

> **The export pipeline is architecturally decided.** Summary of the decision;
> see the ADR for full rationale, alternatives, and contract sketches.

- **PDF engine: Typst** (chosen over LaTeX/SILE via a 3-way bake-off). User bar =
  "sehr hochwertig" ≈ **95%**; LaTeX's glyph-expansion edge (last 5–10% on
  compound-heavy German) is explicitly declined to avoid its ~300–600 MB footprint
  + non-reproducible output. SILE is **disqualified** (f-ligature ToUnicode defect
  breaks PDF search/copy).
- **Rendered via a bespoke `narrare-roman` Typst package** (an owned, single-purpose
  library — **not** a fork of a community template). Pipeline: `pandoc --to=typst
  --shift-heading-level-by=-1` → a thin Narrare wrapper → Typst compiles PDF. Three
  render-confirmed seam-fixes are baked in (F-1 heading shift, F-6 `\@` escape, F-7
  scalar-string metadata). Aesthetic: clean/minimal/official; B-format 129×198 mm;
  recto chapter starts + blank verso; mirrored Satzspiegel; running heads
  recto≠verso (suppressed on openers/blanks); frontmatter römisch → body arabisch;
  per-language (de/en/fr) smart quotes + hyphenation; widow/orphan protection. Drop
   caps **available, default off** (vendored `@preview/droplet` 0.3.1). **Font: Libertinus Serif, bundled (OFL)** — no
  silent font fallback.
- **EPUB + Markdown: pandoc** (EPUB3 + EPUBCheck validation), from the normalized
  form. pandoc is robust fire&forget for these simpler formats.
- **Narrare Normalizer (Core, pure):** the only Narrare-specific layer. TipTap HTML
  → clean semantic HTML/Markdown. **Strips** `AIAnnotation` + `GhostText` (editor
  artifacts must never reach export); **normalizes** `SceneBreak` and `DialogueMark`.
  Contract sketch: `ManuscriptNormalizer` Protocol (ADR-081).
- **Fire&forget robustness gate — Golden-Pages Acceptance Test** (CI): a varied
  corpus of "golden pages" (normal de prose; long-compound stress; de/en/fr mixed
  dialogue; chapter opener ± drop cap; scene break) rendered and checked visually +
  objectively. This is mandatory because bespoke templates can corrupt content
  unattended.
- **Execution:** in-process `asyncio.create_task` job (post-[ADR-080](../../architecture/decisions/ADR-080-remove-redis-taskiq-in-process-execution.md));
  `ProcessPoolExecutor` escalation is the documented contingency for 500-page
  manuscripts.
- **DOCX shipped 2026-08-17 (C3)** — `PandocDocxRenderer` passes the committed
  `apps/api/narrare/export/pandoc/reference.docx` via `--reference-doc`:
  the classic publishing manuscript format (Times 12 pt, 1.5 line spacing,
  0.5″ first-line indent, centred chapter headings). Verified by a golden test
  on the unzipped `word/document.xml` (byte-deterministic under a fixed
  reference — only `docProps/core.xml` timestamps vary). No new ADR: ADR-081's
  engine decision applies unchanged (its own out-of-scope note classified this
  as a feature-spec change).
- **Contracts (RULE-03):** `ManuscriptNormalizer`, `ExportService` (the RULE-12
  public API), `ManuscriptRenderer` (one RULE-08 adapter per external tool:
  Typst / pandoc), and `NarrareRomanConfig` (the stable Typst-package config keys)
  — all sketched in ADR-081; full definitions at implementation kickoff.

## How it works (User perspective)

1. Open the Export panel from the dashboard or editor menu
2. Select the volume to export (or "all volumes")
3. Choose a format: PDF, ePub, DOCX, or Markdown
4. Configure format-specific options:
   - **PDF:** font family, font size, margins, page size, header/footer text
   - **ePub:** cover image, metadata (author, ISBN, language), stylesheet
   - **DOCX:** none — one maintained manuscript format (Times 12 pt, 1.5
     line spacing, first-line indent, centred chapter headings)
   - **Markdown:** heading level for chapters, include/exclude front matter
5. Optionally include: chapter summaries, character list, location glossary
   as appendix sections
6. Click "Export" — file is generated and downloaded to your machine
7. Export settings are remembered for next time

## How it works (Technical)

> **Supersedes the earlier WeasyPrint / `python-docx` / `ebooklib` sketch.**
> The pipeline below is the [ADR-081](../../architecture/decisions/ADR-081-export-pipeline-typst.md)
> decision.

**Service:** `ExportService` in `apps/api/narrare/export/service.py`
**Contract:** `ExportService`, `ManuscriptRenderer` Protocols in
`apps/api/narrare/export/contracts.py` (sketched in ADR-081; full definitions at
implementation kickoff — RULE-03)
**Normalizer:** `ManuscriptNormalizer` Protocol in
`packages/core/narrare_core/export/contracts.py` (pure Core, no I/O)
**Entry point:** `POST /api/v1/export`

**Export pipeline (four stages — only stage 1 is Narrare-specific):**

1. **Normalization** (`ManuscriptNormalizer`, Core, pure) — Transform the stored
   TipTap HTML (`Chapter.content`) into clean semantic HTML/Markdown. **Strip**
   `AIAnnotation` + `GhostText` (editor artifacts must never reach export);
   **normalize** `SceneBreak` (→ explicit scene break) and `DialogueMark`
   (→ clean dialogue). Collect chapters in position order; assemble front/back
   matter from novel metadata.
2. **Conversion** (pandoc, with baked-in seam-fixes) — HTML → target AST:
   `--to=typst --shift-heading-level-by=-1` for PDF; EPUB3 for ePub; Markdown
   for `.md`; `--to=docx --reference-doc=<vendored reference.docx>` for DOCX
   (manuscript format, C3 — no `--toc`: submission manuscripts carry none).
3. **Rendering** (RULE-08 adapter per external tool — `apps/api/narrare/export/renderers/`):
   - **PDF** → `TypstPdfRenderer`: thin Narrare wrapper imports the bespoke
     `narrare-roman` Typst package + feeds the pandoc body; Typst compiles PDF.
     Bundled Libertinus Serif (OFL). Drop caps optional (default off, `@preview/droplet`).
   - **ePub** → `PandocEpubRenderer`: pandoc EPUB3, EPUBCheck-validated.
    - **Markdown** → `PandocMarkdownRenderer`: pandoc.
    - **DOCX** → `PandocDocxRenderer`: pandoc with the committed
      manuscript-format `reference.docx` (golden `document.xml` test — C3).
4. **Delivery** — Artifact written to a temp directory, served via a signed
   download URL, cleaned up after delivery. Export is non-destructive.

**v1 Export options schema (per ADR-081):**
```python
class ExportFormat(StrEnum):
    PDF = "pdf"
    EPUB = "epub"
    MARKDOWN = "md"
    DOCX = "docx"

class ExportOptions(BaseModel):
    format: ExportFormat
    volume_id: UUID | None  # None = all volumes
    include_front_matter: bool = True
    include_back_matter: bool = True
    include_summaries: bool = False
    include_character_list: bool = False
    include_location_glossary: bool = False
    pdf_options: PdfOptions | None        # narrare-roman config keys (paper, margins, font, drop_caps, ...)
    epub_options: EpubOptions | None
    markdown_options: MarkdownOptions | None
```

**Background processing (post-ADR-080):**
Export runs as an **off-request in-process job** via `asyncio.create_task`
(ADR-080 in-process execution boundary) — PDF compile + normalization of large
manuscripts is CPU-bound. Typst/pandoc run as subprocesses (off the event loop);
the normalizer runs in-process, with `ProcessPoolExecutor` escalation as the
documented contingency for 500-page manuscripts. In-flight export is lost on
restart (regenerable, non-destructive — RULE-11: logged, not silent). Each job
builds its own DB session. The client polls job status and receives the download
URL when ready.

## Constraints & Edge Cases

- PDF generation requires **Typst** (single ~15 MB static binary, exact version
  pinned — pre-1.0 v0.15.x) and **pandoc** (pinned) as deploy-time dependencies
  (ADR-029 VM-first setup). Missing binaries degrade gracefully (RULE-11): export
  reports unavailable, never silently falls back to a wrong font (the spike's
  headline fire&forget failure)
- **Libertinus Serif is bundled (OFL)** for reproducible PDF output — no silent
  font fallback
- EPUB embeds the bundled **Libertinus Serif (OFL)** via pandoc
  `--epub-embed-font`, consistent with PDF; the reader may still override
  via its own font settings, but there is no silent fallback to a different
  font at export time
- DOCX renders via the committed manuscript-format `reference.docx` — one
  maintained format, no user-selectable template (YAGNI, program design §11);
  a missing asset fast-fails (no silent fallback to pandoc's default styles).
  The normalizer strips Narrare-specific markup (AIAnnotation, GhostText)
  from all formats
- Export of a very large manuscript (500k+ words) may take 30+ seconds;
  background processing (in-process job, post-ADR-080) with progress indication
  is required; `ProcessPoolExecutor` escalation is the documented contingency
  for 500-page manuscripts
- Export is read-only — it never modifies the Narrare project
- No batch export of multiple formats in one action (separate requests)
- Cover image for ePub must be provided by the user; no cover generator
- Exported Markdown uses consistent heading levels but does not guarantee
  compatibility with every static site generator's frontmatter schema
- **Fire&forget robustness is gate-guaranteed** by the Golden-Pages Acceptance
  Test (CI) — bespoke templates can corrupt content unattended, so a varied
  corpus is rendered and checked on every change

## Related Features

- [WRITE-011](../writing/WRITE-011-volume-management.md) — Volume management (selects what to export)
- [SET-002](../settings/SET-002-project-settings.md) — Project metadata used in front/back matter
- [IO-002](IO-002-import.md) — Project import (the reverse operation)
- [IO-003](IO-003-sync.md) — External sync (continuous alternative to one-time export)
- [PLAN-003](../planning/PLAN-003-structure.md) — Story structure visualization (chapter ordering source)

## Status & History

- `project-init` — Added to registry as planned feature
- `2026-08-10` — **Architecturally decided**: [ADR-081](../../architecture/decisions/ADR-081-export-pipeline-typst.md)
  (Typst + `narrare-roman` + pandoc; Narrare Normalizer; Golden-Pages test).
  Supersedes the earlier WeasyPrint / `python-docx` / `ebooklib` sketch. DOCX
  deferred. Implementation not started.
- `2026-08-14` — **Follow-ups shipped** (branch `feat/io-001-followups`):
  (a) optional ISBN and description fields added to `EpubOptions` — request-level
  EPUB metadata (`dc:identifier` / `dc:description` via pandoc), no DB storage in
  v1; frontend export panel extended with ISBN input and description textarea;
  i18n keys added across en/de/fr. (b) Drop cap Slice 5g: `@preview/droplet`
  0.3.1 (MIT) vendored at
  `apps/api/narrare/export/typst/vendor/droplet/` with relative imports (no
  render-time network fetch); `drop-caps` config key in `narrare-roman`, default
  OFF, byte-neutral when off; Golden-Pages baselines unchanged. Only DOCX
  remains deferred.
- `2026-08-14` — **Implemented / Stable**: 4-stage non-LLM export pipeline shipped
  via PR #163 (Slices 0–8). **Stage 1:** Narrare Normalizer (Core, pure) strips
  AIAnnotation/GhostText, normalizes SceneBreak/DialogueMark — strip-guarantee
  asserted per mark. **Stage 2:** pandoc converts normalized HTML to target AST
  (Typst/EPUB3/Markdown) with baked-in seam-fixes F-1/F-6/F-7. **Stage 3:**
  Three RULE-08 renderer adapters — TypstPdfRenderer (bespoke `narrare-roman`
  package, scope floor 5a–5f complete: recto starts, mirrored Satzspiegel, running
  heads, 4-phase numbering, TOC, smart quotes/hyphenation, scene-break ornament;
  Libertinus Serif bundled OFL both formats), PandocEpubRenderer (EPUB3 +
  Libertinus embedded via `--epub-embed-font`), PandocMarkdownRenderer. **Stage 4:**
  In-process `asyncio.create_task` job (ADR-080) with in-memory registry,
  signed-token artifact delivery. CI gates green: Golden-Pages 26 passed / 0
  skipped (6 parametrized variants), EPUBCheck 5.3.0 passed. RULE-08 AST
  confinement checker enforced in CI. Toolchain pins: Typst 0.15.1, pandoc
  3.10.1, EPUBCheck 5.3.0. Graceful binary-absence degradation tested.
   **Deferred:** DOCX only (pandoc can add trivially — feature-spec change, not
   engine decision). Drop cap 5g and isbn/description EPUB metadata shipped as
   follow-ups on branch `feat/io-001-followups`.
- `2026-08-17` — **DOCX shipped (C3 — Post-Export Follow-ups §6)**:
  `PandocDocxRenderer` (RULE-08 adapter, same seam as PDF/EPUB/MD) renders
  via `--reference-doc` with the committed
  `apps/api/narrare/export/pandoc/reference.docx` (deterministic generator
  `scripts/generate_reference_docx.py`, pure stdlib). Manuscript format:
  Times 12 pt, 1.5 line spacing, 0.5″ first-line indent (every paragraph),
  centred chapter headings, Times 14 pt title page. Golden verification on
  the unzipped `word/document.xml` (byte-deterministic; sha256 baseline +
  `--golden-update` regeneration path) + manuscript-format style assertions
  on the output `styles.xml`. Frontend: fourth format card + i18n en/de/fr.
  No DocxOptions model (zero v1 options), no migration, no ADR change —
  ADR-081's Review-Trigger DOCX item closed.
