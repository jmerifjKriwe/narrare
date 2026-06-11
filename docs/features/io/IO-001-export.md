---
id: IO-001
title: "Manuscript Export"
status: planned
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

> **Status:** 📋 Planned — not yet implemented

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

## How it works (User perspective)

1. Open the Export panel from the dashboard or editor menu
2. Select the volume to export (or "all volumes")
3. Choose a format: PDF, ePub, DOCX, or Markdown
4. Configure format-specific options:
   - **PDF:** font family, font size, margins, page size, header/footer text
   - **ePub:** cover image, metadata (author, ISBN, language), stylesheet
   - **DOCX:** heading styles, page breaks between chapters
   - **Markdown:** heading level for chapters, include/exclude front matter
5. Optionally include: chapter summaries, character list, location glossary
   as appendix sections
6. Click "Export" — file is generated and downloaded to your machine
7. Export settings are remembered for next time

## How it works (Technical)

**Service:** `ExportService` in `export/service.py`
**Contract:** `ExportProtocol` in `export/contracts.py` (to be defined)
**Entry point:** `POST /api/v1/export`

**Export pipeline:**

1. **Assembly** — Collect all chapters for the selected volume, ordered by
   position. Generate front matter (title page, copyright) and back matter
   from novel metadata.
2. **Rendering** — Format-specific renderer converts the assembled content:
   - **PDF:** WeasyPrint for HTML-to-PDF with CSS @page rules for layout
   - **ePub:** `ebooklib` constructs the ePub package with TOC and metadata
   - **DOCX:** `python-docx` builds the document with styled headings and
     paragraph formatting
   - **Markdown:** Direct serialization with configurable heading levels
3. **Delivery** — File is written to a temp directory, streamed to the client
   via a signed download URL, and cleaned up after delivery.

**Export options schema:**
```python
class ExportOptions(BaseModel):
    format: Literal["pdf", "epub", "docx", "markdown"]
    volume_id: UUID | None  # None = all volumes
    include_front_matter: bool = True
    include_back_matter: bool = True
    include_summaries: bool = False
    include_character_list: bool = False
    include_location_glossary: bool = False
    pdf_options: PdfOptions | None
    epub_options: EpubOptions | None
    docx_options: DocxOptions | None
    markdown_options: MarkdownOptions | None
```

**Background processing:**
Large manuscripts (>50 chapters) are exported as a background task via TaskIQ.
The client polls for completion and receives the download URL when ready.

## Constraints & Edge Cases

- PDF generation requires WeasyPrint, which needs specific system libraries
  (Pango, GDK-Pixbuf) — these must be present in the deployment environment
- ePub does not support custom fonts embedded from Narrare; the reader's
  font settings apply
- DOCX export produces a clean document without Narrare-specific markup;
  comments, inline suggestions, and AI annotations are not included
- Export of a very large manuscript (500k+ words) may take 30+ seconds;
  background processing with progress indication is required
- Export is read-only — it never modifies the Narrare project
- No batch export of multiple formats in one action (separate requests)
- Cover image for ePub must be provided by the user; no cover generator
- Exported Markdown uses consistent heading levels but does not guarantee
  compatibility with every static site generator's frontmatter schema

## Related Features

- [WRITE-011](../writing/WRITE-011-volume-management.md) — Volume management (selects what to export)
- [SET-002](../settings/SET-002-project-settings.md) — Project metadata used in front/back matter
- [IO-002](IO-002-import.md) — Project import (the reverse operation)
- [IO-003](IO-003-sync.md) — External sync (continuous alternative to one-time export)
- [PLAN-003](../planning/PLAN-003-structure.md) — Story structure visualization (chapter ordering source)

## Status & History

- `project-init` — Added to registry as planned feature
