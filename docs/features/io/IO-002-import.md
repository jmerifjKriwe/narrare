---
id: IO-002
title: "Project Import & Analysis"
status: planned
area: io
mvp: false

ui_tooltip: "Import and analyze an existing writing project into Narrare."
ui_help_short: |
  Import a complete writing project — manuscript files, outlines, character
  notes, and worldbuilding documents — and let Narrare analyze the full corpus
  to build a structured Knowledge Base with characters, locations, relationships,
  and plot threads.
ui_help_long: |
  ## Project Import & Analysis

  Unlike a simple file import (SETUP-003), Project Import & Analysis processes
  an entire existing writing project and deeply understands its contents.

  **What you bring in:**
  Manuscript chapters, character sheets, outline documents, worldbuilding notes,
  timelines — any combination of DOCX, Markdown, and TXT files organized in a
  directory structure.

  **What Narrare does with it:**

  1. **Parses** all files into chapters and reference documents
  2. **Analyzes** the full text corpus to identify characters, locations,
     factions, objects, and their relationships
  3. **Builds** a Knowledge Base from the analysis, with confidence scores
     for every extracted entity and fact
  4. **Detects** the story's structure — act breaks, plot arcs, timeline —
     and maps it into the planning layer

  This is the migration path for writers who have an extensive existing project
  and want Narrare's Knowledge Base and analysis features without weeks of
  manual data entry.

  Import & Analysis is available from the project dashboard and processes in the
  background — you can monitor progress and review results at your own pace.
ui_available_in: [dashboard]

service: import_service/analyze_service.py
contract: ~
router: ~
prompt: ~
requires: [KB-001, KB-007, KB-008, INFRA-001]
---

# IO-002 — Project Import & Analysis

> **Status:** 📋 Planned — not yet implemented

## What it does

Deeply analyzes an existing writing project's full corpus — manuscript, notes,
outlines, and worldbuilding documents — to produce a fully structured Narrare
project with chapters, a populated Knowledge Base, relationship graphs, and
detected story structure. Goes beyond file import by understanding the content,
not just parsing the format.

## Why it exists

Many serious writers have spent months or years building a novel in Scrivener,
Google Docs, or plain folders. Their story has dozens of characters, complex
relationships, and detailed worldbuilding — all scattered across files with no
structured representation.

The vision describes a Knowledge Base that "remembers your world." For existing
projects, that KB must be built from the text itself. Manual entry of 40+
characters, their interrelationships, locations, factions, and plot threads is
unrealistic. Import & Analysis automates the heavy lifting, so the writer can
focus on verifying and refining rather than transcribing.

## How it works (User perspective)

1. From the dashboard, select "Import Existing Project"
2. Point to a directory containing your manuscript and supporting documents
3. Narrare scans the directory and previews detected files grouped by type:
   chapters, character notes, outlines, worldbuilding docs
4. Confirm or adjust the file classification
5. Click "Start Analysis" — processing runs in the background
6. Monitor progress: a real-time indicator shows which files are being processed
7. When complete, review the results:
   - **Chapters** — verify split detection and ordering
   - **KB Entities** — review extracted characters, locations, factions, objects
   - **Relationships** — confirm detected connections between entities
   - **Story Structure** — review detected acts, plot arcs, timeline markers
8. Accept all, or selectively edit and reject individual items
9. Your Narrare project is ready with manuscript and Knowledge Base populated

## How it works (Technical)

**Service:** `ImportAnalysisService` in `import_service/analyze_service.py`
**Contract:** `ImportAnalysisProtocol` in `import_service/contracts.py` (to be defined)
**Entry point:** `POST /api/v1/import/analyze`
**Background:** TaskIQ task for long-running analysis

**Analysis pipeline (multi-stage):**

1. **File discovery** — Recursive directory scan with MIME-type detection.
   Heuristic classification based on file names, paths, and content patterns
   (e.g., files in `characters/` → character notes).
2. **Parsing** — Same format parsers as SETUP-003 (DOCX, Markdown, TXT).
   Chapters are identified and ordered; reference documents are categorized.
3. **Corpus analysis** — Full-text LLM analysis via `LLMIntent.PROJECT_ANALYZE`:
   - Identify all named entities and their types
   - Extract relationships and their nature
   - Detect story structure markers (act breaks, time jumps)
   - Identify plot threads and their status
4. **KB construction** — Build KB entries from analysis results using KB-001's
   entity creation. Entity types auto-detected (character, location, faction,
   object, concept). Uses KB-007's extraction confidence scoring.
5. **Knowledge Graph population** — Feed extracted relationships into KB-008's
   graph structure for cross-referencing and consistency checking.
6. **Structure detection** — Map detected acts and arcs into the planning layer
   (PLAN-003 story structure).

**Corpus chunking:**
Large corpora are processed in chunks (~10k words each) with context overlap.
Entity deduplication across chunks uses embedding similarity (INFRA-004).

**Progress tracking:**
Task state stored in Redis with TTL. Frontend polls `GET /api/v1/import/analyze/{task_id}/status`
for real-time progress updates.

## Constraints & Edge Cases

- Full analysis is LLM-intensive — a 100k-word project may require multiple
  API calls and several minutes of processing time
- Analysis quality depends on the LLM model's capability; smaller or cheaper
  models may miss subtle relationships or misclassify entities
- Files with non-standard encodings may fail parsing; UTF-8 is strongly
  recommended
- Directory structure is used as a hint for file classification but is not
  required — a flat directory of Markdown files works too
- Very large projects (>300k words) may need to be imported in volumes
  to manage processing time and token costs
- The analysis is a best-effort AI interpretation — writers must review
  all suggested entities and relationships before accepting
- No incremental re-analysis — if you add new files later, a full re-analysis
  is required (or use SETUP-003 for individual file additions)
- Binary formats (RTF, ODT) are not supported; convert to DOCX or TXT first

## Related Features

- [SETUP-003](../setup/SETUP-003-import.md) — Simple file import (lighter weight, no deep analysis)
- [KB-001](../kb/KB-001-entity-management.md) — KB entity management (target for created entities)
- [KB-007](../kb/KB-007-extraction.md) — Entity extraction engine (reused for analysis)
- [KB-008](../kb/KB-008-knowledge-graph.md) — Knowledge Graph (target for relationships)
- [KB-009](../kb/KB-009-kb-merge.md) — KB entity merge (deduplicate extracted entities)
- [PLAN-003](../planning/PLAN-003-structure.md) — Story structure (receives detected acts)
- [IO-001](IO-001-export.md) — Manuscript export (the reverse operation)

## Status & History

- `project-init` — Added to registry as planned feature
