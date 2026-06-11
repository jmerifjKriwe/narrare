---
id: SETUP-003
title: "Project Import"
status: planned
area: setup
mvp: false

ui_tooltip: "Bring existing manuscripts and notes into a Narrare project."
ui_help_short: |
  Import your existing manuscript files — DOCX, Markdown, or plain text — into
  Narrare. Chapters are detected automatically, and the AI can scan your text
  to populate the Knowledge Base with characters, locations, and relationships
  it finds.
ui_help_long: |
  ## Project Import

  Already have a manuscript in progress? Project Import lets you bring it into
  Narrare instead of starting from scratch.

  **Supported formats:** DOCX, Markdown (.md), and plain text (.txt). You can
  import individual files or an entire directory — Narrare detects chapter
  boundaries using headings, file splits, or explicit markers.

  **What happens during import:**

  1. Files are parsed and chapters are created in your project
  2. Frontmatter or metadata in your files maps to chapter titles and notes
  3. Optionally, the AI scans imported text and suggests KB entries for
     characters, locations, and other entities it recognizes

  Use this when you are migrating from another writing tool, recovering an
  older draft, or assembling chapters you wrote outside Narrare. Import is
  available during the Setup Wizard (Step 3) and from the project dashboard.
ui_available_in: [setup-wizard, dashboard]

service: setup/analyze_service.py
contract: ~
router: ~
prompt: ~
requires: [SETUP-001, KB-007]
---

# SETUP-003 — Project Import

> **Status:** 📋 Planned — not yet implemented

## What it does

Imports existing manuscript files (DOCX, Markdown, TXT) into a Narrare project,
automatically splitting them into chapters and optionally extracting entities
for the Knowledge Base. Writers can bring work started in other tools — Scrivener
exports, Google Docs downloads, or plain text folders — into Narrare without
retyping.

## Why it exists

Writers switching to Narrare often have tens of thousands of words already written.
Forcing them to copy-paste chapter by chapter, or manually re-enter every character
and location into the KB, creates a cliff that stops adoption. Project Import
eliminates that cliff: bring your manuscript in, let the AI populate the KB, and
continue writing where you left off.

This directly addresses the vision's principle of being a writing *environment* —
not a tool that only works with content created inside it.

## How it works (User perspective)

1. From the Setup Wizard (Step 3) or the project dashboard, select "Import"
2. Choose a file (DOCX, MD, TXT) or a directory containing multiple files
3. Narrare previews how the content will be split into chapters
4. Adjust chapter boundaries if the auto-detection missed a split point
5. Optionally enable "AI-powered KB extraction" to suggest characters,
   locations, and relationships from the imported text
6. Click "Import" — chapters are created, KB suggestions appear for review
7. Review and approve or reject each KB suggestion
8. Start writing — your manuscript and Knowledge Base are ready

## How it works (Technical)

**Service:** `ImportService` in `setup/analyze_service.py`
**Contract:** `ImportProtocol` in `setup/contracts.py` (to be defined)
**Entry points:** Setup Wizard Step 3 and `POST /api/v1/import`

**File parsing pipeline:**
1. **Format detection** — MIME type and extension determine the parser
2. **DOCX parsing** — `python-docx` extracts paragraphs, preserving headings
   as chapter boundaries
3. **Markdown parsing** — ATX headings (`#`, `##`) mark chapter splits;
   frontmatter maps to chapter metadata
4. **TXT parsing** — heuristic splitting on double newlines with pattern
   matching for "Chapter X" markers
5. **Chapter creation** — each detected section becomes a `Chapter` record
   linked to the active novel

**Optional KB extraction:**
Reuses KB-007's `ExtractionService` to scan imported text for entities,
facts, and relationships. Results go through the same review/endorse flow.

**File size handling:**
Files exceeding 50k words are chunked and processed sequentially to avoid
timeout and memory issues.

## Constraints & Edge Cases

- DOCX support covers standard Word documents; complex formatting (tables,
  embedded images, tracked changes) is stripped to clean text
- Chapter boundary detection is heuristic — users must verify and may need
  to adjust splits manually
- Very large files (>100k words) require chunked import with a progress indicator
- Encoding detection relies on `chardet`; rare encodings may fail and require
  manual UTF-8 conversion before import
- Import is additive — running it twice creates duplicate chapters (no
  deduplication without user confirmation)
- KB extraction is optional and requires LLM availability; import succeeds
  without it
- No undo for import — users should verify the preview before confirming

## Related Features

- [SETUP-001](SETUP-001-setup-wizard.md) — Setup Wizard where import first appears (Step 3)
- [SETUP-002](SETUP-002-demo-content.md) — Alternative to import: load demo content
- [KB-007](../kb/KB-007-extraction.md) — Entity extraction used for optional KB population
- [KB-001](../kb/KB-001-entity-management.md) — KB entity management (target for extracted data)
- [IO-002](../io/IO-002-import.md) — Full project import & analysis with deeper AI understanding
- [WRITE-011](../writing/WRITE-011-volume-management.md) — Volume management for multi-book imports

## Status & History

- `project-init` — Added to registry as planned feature
