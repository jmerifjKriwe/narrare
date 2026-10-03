---
id: IO-002
title: "Corpus Analysis Pass"
status: planned
area: io
mvp: false

ui_tooltip: "Run a paced, reviewable KB extraction pass over a novel's accumulated chapters."
ui_help_short: |
  Let Narrare read your existing chapters — imported or written — and propose
  Knowledge Base entities and relationships chapter by chapter. You review and
  endorse; nothing enters the KB without you.
ui_help_long: |
  ## Corpus Analysis Pass

  The Corpus Analysis Pass runs the KB extraction agent over a novel's
  accumulated chapters — in story order, paced in the background — and turns
  each chapter into a reviewable set of proposals: new entities, updates to
  existing ones, and relationships between them.

  **What happens:**

  1. Choose "Analyze novel corpus" (studio sidebar) — or accept the prompt
     right after importing chapters
  2. Narrare shows an honest pre-run estimate: chapters, words, and AI calls
  3. The pass runs server-side at your analysis-rate pace — you can watch
     progress, cancel, and resume
  4. Review each chapter's proposals (confidence-scored, with source quotes)
  5. Endorse what is right — endorsed items are applied per chapter
  6. When the pass finishes, Narrare checks the accumulated roster for likely
     duplicates and offers merge suggestions you can endorse or reject

  **Boundaries (honest):** one AI call per chapter; at most 120 chapters and
  200,000 words per run; chapters that are too large should be split first
  (the import preview's split tools can do that). Story-structure detection,
  reference documents, and folder upload are not part of this feature.
ui_available_in: [editor, kb]

service: kb/bulk_extraction/corpus.py
contract: kb/bulk_extraction/contracts.py
router: kb/bulk_extraction/router.py
prompt: core/prompts/_bundled/kb/en/extract
requires: [KB-007, KB-008]
---

# IO-002 — Corpus Analysis Pass

> **Status:** 📋 Planned — re-scoped 2026-10-03 (SETUP-003 follow-up F3).
> Engine: [ADR-092](../../architecture/decisions/ADR-092-bulk-extraction-job.md)
> bulk extraction job. Design:
> [corpus-pass spec](../../superpowers/specs/2026-10-03-io002-corpus-pass-design.md).
> All PO rulings FINAL (D12a, D13b, D14a, D15a, D16a, D17a, D18a, D19a,
> D20a, D21a).

## What it does

One paced, reviewable Knowledge Base extraction pass over a novel's
**accumulated chapters** — however they got there (typed, imported Markdown /
TXT, future import formats). Each chapter produces proposal items (new
entities, entity updates, relationships) that the user reviews and endorses;
endorsed items are applied per chapter through the existing KB-007 flow.
After the pass, the accumulated roster is checked for likely duplicates via
ADR-085, and merge suggestions are offered for endorsement.

## Why it exists

Writers who arrive with a finished or partial manuscript want the Knowledge
Base to build itself from the text (ADR-091 imports the chapters; the KB
stays empty without this pass). Manually triggering per-chapter extraction
and baby-sitting one modal at a time does not scale to a book — the pass
makes the mechanical part a background job with honest costs and keeps every
KB write behind explicit human endorsement.

## How it works (User perspective)

1. Studio sidebar → "Analyze novel corpus" (for a just-imported novel, the
   post-import card offers the same pass over the imported chapters)
2. A confirm dialog shows the honest estimate: N chapters · M words ·
   N AI calls, plus a note that the run is paced in the background
3. If the novel exceeds the per-run cap, the dialog says so explicitly and
   proposes the longest start-of-book prefix within the cap
4. Start — progress is visible per chapter; cancel and resume work
5. Review chapter by chapter: confidence-scored items with source quotes;
   select-all / select-none; apply per chapter
6. On completion, a duplicate check runs automatically — "N possible
   duplicates found" — endorse or reject each merge suggestion
7. Relationships land in the Knowledge Graph (KB-008) as they are endorsed

## How it works (Technical)

**Engine:** ADR-092 `kb/bulk_extraction/` job — start/status/results/cancel/
resume REST endpoints, in-process runner, shared analysis-rate pacer
(`NARRARE_RATE_LIMIT_ANALYSIS`), in-memory registry (job lost on restart →
"interrupted" state; nothing is written pre-endorsement, so restarts are
always safe).

**Corpus scope (D12a/D14a):** enumerate the novel's chapters in `position`
order (`ChapterRepository.list_by_novel`); **chapter = chunk** — one
`ExtractionAgent` call per chapter via the existing
`ExtractionService.extract_from_chapter` (roster + world context per call, so
applying chapters in order improves later proposals).

**Per-run cap (D20a):** protocol constants `CORPUS_PASS_MAX_CHAPTERS = 120`
and `CORPUS_PASS_MAX_WORDS = 200_000`; the pass covers the longest prefix of
chapters (in position order) that fits both; estimate surfaces the full
corpus counts and any truncation honestly.

**Dedup gate (D15a):** per-chapter proposals apply through the existing
`POST /novels/{novel_id}/kb/extract/apply` (with `chapter_id` → ADR-085
provenance). On pass completion, one automatic duplicate analysis
(ADR-085 deterministic engine, no LLM) surfaces a suggestion count;
endorse/reject uses the existing
`/kb/resolution/suggestions/{id}/endorse|reject` endpoints. There is **no**
inline fuzzy dedup in the pass itself.

**Relationships (D13b):** relationship proposals ride the same items list and
apply flow; they populate the KB-008 graph.

## Constraints & Edge Cases

- One AI call per chapter; a chapter far beyond normal length should be split
  first (F1 split tools) — the pass never re-chunks prose
- Per-run cap 120 chapters / 200,000 words; larger novels run in multiple
  passes (start-of-book prefix first) — never silently
- Runs share the analysis rate budget with every interactive AI feature
  (default 5 calls/min): a 120-chapter pass takes ≥ 24 minutes at the
  operator's configured pace
- Jobs are in-memory: an API restart mid-pass loses the job (the panel shows
  "interrupted"; already-applied items are safe and stay applied)
- Duplicate detection after the pass is advisory: nothing merges without
  endorsement (ADR-085 suggestions-only policy)

## Related Features

- [SETUP-003](../setup/SETUP-003-import.md) — chapter import (the most
  common on-ramp for a corpus pass)
- [KB-007](../kb/KB-007-extraction.md) — the extraction engine this pass
  batches; the apply/endorse contract
- [KB-008](../kb/KB-008-knowledge-graph.md) — target of applied relationships
- [ADR-085](../../architecture/decisions/ADR-085-kb-entity-resolution-layer.md)
  — the duplicate-detection gate
- [ADR-092](../../architecture/decisions/ADR-092-bulk-extraction-job.md) — the
  job engine
- [IO-001](IO-001-export.md) — the reverse direction (mancript out)

## Status & History

- `2026-10-03` — **Re-scoped** from "Project Import & Analysis" to "Corpus
  Analysis Pass" (SETUP-003 follow-up F3; PO rulings D12a–D21a FINAL).
  Superseded identity below.
- `project-init` — Added to registry as "Project Import & Analysis"
  (planned).

## Superseded identity (replaced 2026-10-03 — do not build)

The original IO-002 promised a monolithic "Import & Analysis" that ingested a
directory tree of manuscript + notes, auto-detected file types, built
reference documents, detected story structure (acts/arcs/timeline) into the
planning layer, and was driven from a dashboard. That identity is **replaced**
— ruling by ruling:

| Original promise | Replaced by (ruling) |
|---|---|
| Directory-tree upload & recursive discovery | **Deferred** (D18a) — SETUP-003 browser file upload is the on-ramp |
| Reference documents (character sheets, outlines, worldbuilding files) | **Dropped** (D17a) — chapters only; KB-001/KB-004 cover manual reference material |
| Story-structure detection into PLAN-003 | **Deferred entirely** (D16a) — planning structure stays author-driven |
| New `ImportAnalysisService` + `LLMIntent.PROJECT_ANALYZE` + corpus chunking | **Replaced** (D12a/D14a) — corpus pass over chapters; chapter = chunk via the existing `ExtractionAgent` (no new intent, no new prompt, no chunker) |
| Custom cross-chunk embedding dedup | **Replaced** (D15a) — per-chapter proposals + ADR-085 resolution as the dedup gate |
| Dashboard entry, background TaskIQ/Redis task tracking | **Replaced** (D19a/D12a) — wizard + sidebar entries on the ADR-080/092 in-process job with REST polling |
| DOCX ingestion as a prerequisite | **Decoupled** (D21a) — the pass is format-agnostic; DOCX import is a separate SETUP-003 follow-up |
