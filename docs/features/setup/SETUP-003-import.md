---
id: SETUP-003
title: "Project Import"
status: planned
area: setup
mvp: false

ui_tooltip: "Bring existing manuscripts and notes into a Narrare project."
ui_help_short: |
  Import your existing manuscript files — Markdown or plain text — into
  Narrare. Chapters are detected automatically from headings and chapter
  markers; you review and adjust them before anything is created.
ui_help_long: |
  ## Project Import

  Already have a manuscript in progress? Project Import lets you bring it into
  Narrare instead of starting from scratch.

  **Supported formats (v1):** Markdown (`.md`) and plain text (`.txt`). You
  select multiple files in your browser — Narrare detects chapter boundaries
  using frontmatter, headings (`#`/`##`), file splits, or explicit
  "Chapter X" / "Kapitel X" markers.

  **What happens during import:**

  1. You pick your files — they are uploaded and parsed server-side
  2. Narrare shows a preview: one row per detected chapter with a suggested
     title, word count, and source file
  3. You can rename any chapter and include/exclude any chapter
  4. On confirm, the selected chapters are appended to your novel

  Use this when you are migrating from another writing tool, recovering an
  older draft, or assembling chapters you wrote outside Narrare. Import is
  available during the Setup Wizard (Step 2, "Import manuscript") and from the
  novel workspace sidebar ("Import chapters").
ui_available_in: [setup-wizard, dashboard]

service: narrare/importing/service.py
contract: narrare/importing/contracts.py
router: narrare/importing/router.py
prompt: ~
requires: [SETUP-001]
adr: ADR-091
---

# SETUP-003 — Project Import

> **Status:** 📋 Planned (v1 specified 2026-10-02) — not yet implemented
> **Design spec:** `docs/superpowers/specs/2026-10-02-project-import-design.md`
> **ADR:** `docs/architecture/decisions/ADR-091-project-import-v1.md`

## What it does

Imports existing Markdown (`.md`) and plain-text (`.txt`) manuscript files as
chapters into a Narrare novel. Writers select files in their browser, review
a server-generated preview (suggested title, word count, source file per
detected chapter), rename/include/exclude chapters, and confirm — the
selected chapters are appended atomically. Writers migrating from other
tools bring their work in without retyping.

## Why it exists

Writers switching to Narrare often have tens of thousands of words already
written. Forcing them to copy-paste chapter by chapter creates a cliff that
stops adoption. Project Import eliminates that cliff: bring your manuscript
in and continue writing where you left off.

This directly addresses the vision's principle of being a writing *environment* —
not a tool that only works with content created inside it.

## How it works (User perspective)

1. From the Setup Wizard (Step 2, "Import manuscript" card) or the novel
   workspace sidebar ("Import chapters"), select one or more `.md`/`.txt` files
2. Narrare parses them server-side and previews every detected chapter:
   suggested title, word count, source file
3. Edit chapter titles inline; toggle chapters off that you do not want
4. Confirm:
   - Wizard: chapters are committed right after the new novel is created
   - Sidebar: chapters are appended to the existing novel
5. If the commit fails after the wizard already created the novel, a banner
   in the novel workspace offers a retry via the sidebar import

## How it works (Technical)

**Module pair (ADR-091):**

- `packages/core/narrare_core/importing/` — pure, deterministic, I/O-free
  parser: `detect_chapters(filename, text) -> list[DetectedChapter]`.
  Baseline: file-per-chapter. Markdown splits on ATX `#`/`##` headings
  (YAML frontmatter honored: `title`, `status`); TXT splits on
  `Chapter X` / `Kapitel X` (Arabic/Roman numerals) marker lines.
- `apps/api/narrare/importing/` — standard module (contracts → schemas →
  constants → service → repository → router → dependencies). First
  `UploadFile` surface in the API.

**Stateless two-phase API:**

- `POST /api/v1/import/preview` (multipart `files[]`) — guardrails + parse,
  **no DB writes**; returns indexed preview items.
- `POST /api/v1/import/commit` (multipart `files[]` + `novel_id` +
  `adjustments` JSON: `excluded_indices`, `title_overrides`) — re-parses
  deterministically (same bytes ⇒ same chapters), ownership-gated
  (foreign ≡ unknown → 404), appends `Chapter` rows atomically with
  `position = max(existing)+1..n`.

**Semantics:** append-only; no dedup; no undo (the preview is the
verification gate). Chapter `status` from frontmatter if present else
`draft`; `volume_id` stays NULL (mirrors the DemoLoader).

**Guardrails:** ≤ 100 files, ≤ 5 MB per file, ≤ 25 MB total, zero detected
chapters → 422 (naming the offending file where applicable). UTF-8 strict,
BOM tolerated; undecodable file → 422.

**Frontend:** shared `ImportPreviewPanel` + `ImportModal`
(`packages/web/components/studio/importing/`); sidebar action in
`SidebarChapterList`; wizard holds the selection (File[] + adjustments) in
`wizardStore` — never serialized into `setup/complete` — and commits it
after novel creation. `fetchApiUpload` (multipart-aware) in
`lib/api/core.ts`; `importing` i18n namespace (en/de/fr).

**Removed with v1:** the dormant server-side `import_path` mechanism
(backend schemas + validation branch, wizard input, Step-5 row, i18n keys) —
Docker-only distribution makes server-side paths a footgun (Q-011);
`starter="import"` on `/setup/complete` now simply creates an empty novel
that the frontend then populates via `/import/commit`.

## Constraints & Edge Cases

- Detection is heuristic; users verify the preview (title edit +
  include/exclude are the v1 adjustment surface — split/merge editing is a
  follow-up)
- Spelled-out chapter numbers ("Chapter one") are not recognized as markers
- Files with unknown extensions or non-UTF-8 encodings are rejected with a
  422 naming the file; no charset detection in v1
- Import is additive — running it twice creates duplicate chapters
- No undo for import — the preview is the safety gate
- DOCX support is an explicit follow-up slice (pandoc converter already
  ships with the export pipeline, ADR-081)
- Multipart bodies traverse the Next.js rewrite (`next.config.ts`); the
  implementation plan verifies real uploads > 1 MB through the rewrite
  before merge (spec §7 R1)

## Related Features

- [SETUP-001](SETUP-001-setup-wizard.md) — Setup Wizard where import first appears (Step 2)
- [SETUP-002](SETUP-002-demo-content.md) — Alternative to import: load demo content
- [IO-002](../io/IO-002-import.md) — Full project import & analysis with deeper AI
  understanding (separate future feature; v1 scope boundary in ADR-091)
- [KB-007](../kb/KB-007-extraction.md) — Per-chapter entity extraction (remains the
  only extraction surface in v1)
- [WRITE-011](../writing/WRITE-011-volume-management.md) — Volume management (imported
  chapters start unassigned)

## Status & History

- `project-init` — Added to registry as planned feature
- `2026-10-02` — v1 scoped and specified (approved brainstorm; ADR-091 +
  design spec): MD+TXT only, chapters only, browser multipart upload,
  `import_path` stub removal, wizard-step-2 inline + sidebar-modal entries.
  DOCX, bulk KB extraction, split/merge editing deferred (follow-up slices).
