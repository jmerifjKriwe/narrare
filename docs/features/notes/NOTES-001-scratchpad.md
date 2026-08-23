---
id: NOTES-001
title: "Scratchpad"
status: stable
area: notes
mvp: false

ui_tooltip: "Capture a thought before it escapes — ideas, concepts, questions, unbound to any novel."
ui_help_short: |
  The Scratchpad is a low-friction home for thoughts that do not belong to a
  novel yet: plot ideas, worldbuilding concepts, craft questions. Capture
  quickly from anywhere, curate later, and discuss notes with the chat.
ui_help_long: |
  Notes live independently of novels and series. Each note has a type
  (idea, concept, question, other), free-form tags, and Markdown content.
  A note can optionally be linked to one novel or one series — never both —
  and the link never deletes the note. Semantic search finds notes by
  meaning and always falls back to plain text search, so notes stay
  findable even without an embedding provider. The "Discuss in chat"
  button opens a chat with the note attached as context. Quick capture
  (Ctrl/Cmd+Shift+U or the sidebar bolt) saves a thought from anywhere in
  the app in seconds.
ui_available_in: ["sidebar", "quick-capture"]

service: apps/api/narrare/notes/service.py
contract: apps/api/narrare/notes/contracts.py#NoteServiceProtocol
router: apps/api/narrare/notes/router.py
prompt: ""
requires: ["INFRA-004"]
---

# [NOTES-001] — Scratchpad

## What it does

A novel-independent place to capture, curate, and discuss thoughts: ideas,
concepts, questions that do not belong to any project yet.

## Why it exists

Writers have thoughts at odd moments — shopping, commuting, mid-chapter.
Before the Scratchpad those thoughts had no home: the KB is strictly
novel/series-scoped, chapters are prose, and chat is a conversation, not
storage. The Scratchpad removes the "where do I put this?" friction.

## How it works (User perspective)

1. The writer presses Ctrl/Cmd+Shift+U (or the sidebar bolt) and types a
   thought — a title, a type, and a tag are optional.
2. A toast confirms the capture with a link to the Scratchpad.
3. On `/scratchpad` the writer curates: filter by type/tag, edit Markdown
   with a preview toggle, tag with autocomplete, optionally link to a novel
   or a series.
4. "Discuss in chat" opens a chat panel with the note pre-loaded as context.
5. Search supports a semantic mode; the result badge honestly shows
   `semantic` or `lexical`.

## How it works (Technical)

**Entry point:** `apps/api/narrare/notes/router.py` → `/api/v1/notes` (CRUD, `/tags`, `/search`)
**Service:** `NoteService` in `apps/api/narrare/notes/service.py`; `NoteSearchService` in `search_service.py`
**Contract:** `NoteServiceProtocol` in `apps/api/narrare/notes/contracts.py`; `NoteLookupProtocol` + `NoteSnapshot` in `packages/core/narrare_core/notes/contracts.py`
**Data:** `notes` table (migration `0041_notes`): scope CHECK (`NOT (novel_id IS NOT NULL AND series_id IS NOT NULL)`), GIN index on `tags TEXT[]`, FKs `ON DELETE SET NULL`
**Embeddings:** `source_type="note"` through the generic in-process pipeline (`run_embed_source_inprocess`, ADR-080); delete cleans embeddings (`EmbeddingService.delete`)
**Chat:** `ChatRequest.note_id` + optional `project_id` (migration `0042`); note text injected as runtime context via `format_note_context_block` (RULE-02-safe)
**Frontend:** `packages/web/components/notes/*`, TanStack hooks in `lib/hooks/useNotes.ts`, `notes.*` i18n namespace (en/de/fr)

## Constraints & Notes

- Notes are always searchable (RULE-11): semantic search degrades to ILIKE
  with an honest `mode` badge.
- The note outlives its link: `ON DELETE SET NULL` on novel/series.
- No pinning, soft-delete, nesting, rich text, auto-tagging, or
  promote-to-KB in v1 (spec non-goals).
