# Scratchpad (NOTES-001) — Design

> **Status:** Approved in brainstorming session 2026-08-21 (PO approved all sections).
> **Next step:** implementation plan via `writing-plans`.

## 1. Problem & Goal

Writers have thoughts, ideas, and concepts that do not belong to any novel yet —
a plot twist idea while shopping, a worldbuilding thought for an undefined
project, a craft question worth keeping. Narrare currently has no home for
these: the KB is strictly novel/series-scoped (SERIES-001 STI + scope columns),
chapters are prose, and CHAT-001 is a conversation, not storage.

The Scratchpad is a low-friction, novel-independent place to capture, curate,
and later discuss these thoughts inside Narrare.

**Non-goals (v1):** pinning, soft-delete, nesting/hierarchy, rich text,
auto-tagging, "promote note → KB entry", multi-note summarization. All are
possible follow-ups; none block v1 value.

## 2. Decisions (from brainstorming, all PO-approved)

| # | Question | Decision |
|---|----------|----------|
| Q1 | Organization | Multiple individual notes with light structure |
| Q2 | Structure | Hybrid: fixed `note_type` + free tags; tag **autocomplete** over existing tags (new tags always allowed) |
| Q3 | Localization of types | Types stored as language-neutral keys, displayed via `packages/i18n` (en/de/fr) |
| Q4 | Scope | Notes are global by default; **optionally** linkable to one novel OR one series (never both) |
| Q5 | AI in v1 | Light: (a) discuss note in chat, (b) semantic search |
| Q6 | UI | Both: full `/scratchpad` page AND global quick-capture panel |
| Q7 | Content format | Markdown (stored as text, edited as text, rendered preview) |
| Approach | Architecture | **A — dedicated domain module** `notes` (rejected: KB-scope extension B, localStorage C) |

## 3. Architecture

Dedicated domain module following the established house pattern — a note is
not a KB entity, not a chapter, not a chat message; it gets its own home
(RULE-05/06).

```
packages/core/narrare_core/notes/     ← pure: types, tag normalization, contracts
apps/api/narrare/notes/               ← contracts → schemas → models → repository
                                        → service → router (house pattern)
packages/web/                         ← /scratchpad page + quick-capture panel
```

**Reused infrastructure (verified against code):**

- **Embeddings:** generic `run_embed_source_inprocess(source_type, source_id, content)`
  (ADR-080 in-process pattern) — notes are a new `source_type="note"`. The task
  performs its own content-hash comparison (skips unchanged content), so no
  hook manager is needed; a thin dispatch in the service suffices.
  `UNIQUE(source_type, source_id, model)` and the vector search's `source_type`
  filter work unchanged (the KB metadata `LEFT JOIN` yields `usage_count = 0`
  for non-KB sources — verified).
- **Chat:** CHAT-001 pipeline; note content is injected as runtime input
  (like the user message), not as a prompt template — RULE-02-safe.

**No new ADR** anticipated: this combines established patterns (ADR-080
in-process tasks, ADR-075-style scope invariant, existing embedding infra).
The pre-implementation gate (Architecture specialist) confirms; if the
`project_id` optionalization of `ChatRequest` is judged contract-relevant, a
small ADR follows from that gate.

## 4. Data Model

**Core (`narrare_core/notes/`, pure):**

- `types.py`: `NoteType` — keys `idea | concept | question | other`
  (language-neutral; display via i18n `notes.type.*`).
- Tag normalization: lowercase, trim, collapse whitespace, dedupe,
  max 10 tags × 32 chars per tag. Free-form otherwise (no tag registry).
- Fallback title: first non-empty content line when no title is given.

**Table `notes` (Alembic `0041_notes`, RULE-14 — atomic up/down):**

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `title` | TEXT NULL | empty → fallback: first content line |
| `content` | TEXT NOT NULL DEFAULT '' | Markdown; cap ~50,000 chars |
| `note_type` | TEXT NOT NULL | key from `NoteType` |
| `tags` | TEXT[] | GIN index; autocomplete via `DISTINCT unnest` |
| `novel_id` | UUID NULL → novels | `ON DELETE SET NULL` — **the note outlives the novel** |
| `series_id` | UUID NULL → series | `ON DELETE SET NULL` |
| `created_at` / `updated_at` | TIMESTAMPTZ | default sort: `updated_at DESC` |

**Scope invariant (DB CHECK, mirrors `ck_kb_entries_scope_invariant`):**
`NOT (novel_id IS NOT NULL AND series_id IS NOT NULL)`.
Semantics differ deliberately from the KB: **both NULL = global note** (the
normal case), at most one link set. A Pydantic validator enforces the same
invariant as a second layer.

## 5. API Surface

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/notes` | List; filters `note_type`, `tag`, `novel_id`, `series_id`, `q` (ILIKE); `limit`/`offset`; sort `updated_at DESC` |
| `POST /api/v1/notes` | Create (quick-capture and full editor both use this) |
| `GET /api/v1/notes/{id}` | Detail |
| `PATCH /api/v1/notes/{id}` | Partial update |
| `DELETE /api/v1/notes/{id}` | Hard delete + embedding cleanup (`delete_by_source("note", id)`) |
| `GET /api/v1/notes/tags` | Distinct existing tags (autocomplete; optional prefix `q`) |
| `POST /api/v1/notes/search` | Semantic search (see §6a); accepts the same optional filters as the list endpoint |

No SSE: the notes module itself has no LLM-streaming endpoint (RULE-20
applies to AI backend endpoints; this is CRUD + search). Auth/ownership
follow the existing module conventions.

## 6. AI Integration

### 6a — Semantic Search

- **On create/update:** service dispatches the existing
  `run_embed_source_inprocess("note", str(note_id), text)` where
  `text = title + "\n" + content`; truncation follows existing embedding
  pipeline behavior.
- **On delete:** `delete_by_source("note", note_id)` — no ghost embeddings.
- **Search:** `POST /api/v1/notes/search` — body `{query, note_type?, tag?,
  novel_id?, series_id?, limit?}` (same filter semantics as the list
  endpoint, all optional) → embed query, vector search with
  `source_type='note'`, return hits with `similarity` score.
- **Graceful degradation (RULE-11):** no embedding provider configured or
  embedding fails → transparent ILIKE fallback, response carries
  `mode: "lexical"` instead of `"semantic"`. Notes are always searchable.
  The lexical `GET /notes?q=` filter remains independent.

### 6b — Discuss Note in Chat

- `ChatRequest` gains `note_id: UUID | None`; **`project_id` becomes optional**
  (currently required — global notes have no project; the one deliberate
  change to existing code, backward compatible).
- ChatService loads the note via the notes contract (no cross-module
  repository access) and injects it as an **explicit context block** into
  `ChatDeps` — note text is runtime input, not a prompt template (RULE-02).
- Without `project_id`, KB/project context tiers are skipped (matches
  CHAT-001: "KB empty → still useful for general craft questions").
- Same SSE endpoint/streaming; frontend "discuss" button opens the chat
  panel with the note pre-loaded.

## 7. Frontend

**Page `/scratchpad`** (sidebar entry; layout follows Worldbuilding/Settings
patterns):

- Left: note list (title/fallback, type badge, tags, `updated_at`), filter
  bar — type dropdown (localized labels), tag filter (autocomplete chips),
  novel/series filter (only if links exist), search field.
- Right: selected note — Markdown editor (textarea) with rendered-preview
  toggle, type select, tag input with autocomplete (`GET /notes/tags`; new
  tags freely typable), optional novel/series link, "discuss in chat" button,
  delete with ConfirmDialog.
- Empty state: single "capture a thought" card (type + text) creating the
  first note.

**Quick-capture panel (global):** sidebar button (note icon) + keyboard
shortcut (collision-free, concrete binding chosen in the plan) open a slim
slide-over: optional title, type (default `idea`), text, optional tag —
save creates the note and toasts with "open in scratchpad" link. Capture is
fast; curation lives on the page.

**Tech:** TanStack Query hooks (`useNotes`, `useNote`, `useCreateNote`,
`useUpdateNote`, `useDeleteNote`, `useNoteTags`, `useSemanticNoteSearch`)
with query keys + invalidation; semantic search as a second mode in the
search field (toggle "semantic", honest `lexical`/`semantic` result badge —
RULE-11 spirit in the UI); Motion animations via central variants; one
responsibility per component, within RULE-04 file-size limits.

**i18n:** new `notes.*` namespace in en/de/fr — including localized type
labels (`notes.type.idea` etc.).

> **⚠️ Mandatory for implementation:** the frontend slices (page + quick
> capture) MUST load the `frontend-design` skill (superpowers) before
> writing UI code — explicit PO requirement (session 2026-08-21).

## 8. Testing

- **Core unit:** tag normalization (case/whitespace/dedupe/limits), fallback
  title, `NoteType` keys, scope validator (both set → error; both empty → OK).
- **Backend unit:** service (embedding dispatch on create/update, embedding
  cleanup on delete, ILIKE filters, tag distinct), repository queries,
  RULE-11 regression: missing embedding provider → `mode: "lexical"`, no 500.
- **Backend integration:** router roundtrips (CRUD + filters + tags
  endpoint), **Alembic 0041 roundtrip** (up/down; CHECK constraint present —
  RULE-14 pattern), ownership/404 paths.
- **Chat extension:** `project_id` optional (legacy requests unchanged),
  `note_id` context injection (note text in context, not template),
  conversation without project.
- **Frontend (Vitest):** list/filter/editor/quick-capture components, type
  labels per locale, search-mode toggle with honest badge, Markdown preview.
- **Gates:** `just verify` / `scripts/check_architecture.py` green;
  embedding task dispatch faked in tests (no real provider calls).

## 9. Slicing (one logical unit per delegation, own test cycle each)

1. **Core** — `narrare_core/notes/` (types + contracts)
2. **DB** — model + Alembic `0041` + migration roundtrip test
3. **Backend CRUD** — repository → service (incl. embedding dispatch) →
   router + schemas
4. **Search** — tags endpoint + semantic search with lexical fallback
5. **Chat integration** — `project_id` optional + `note_id` context
6. **Frontend page** — list/filter/editor/preview *(loads `frontend-design`)*
7. **Quick capture** — global panel + shortcut *(loads `frontend-design`)*
8. **i18n + docs** — `notes.*` en/de/fr, feature file `NOTES-001`, INDEX entry

## 10. Risks & Notes

- **`ChatRequest.project_id` optionalization** is the only touch of existing
  behavior — covered by explicit regression tests (legacy requests
  unchanged); Architecture gate decides on a small ADR if needed.
- **Embedding cost:** one embedding per note create/change (skipped when
  unchanged — hash compare inside the task). Quick-capture bursts are
  naturally small.
- **Feature ID:** registered as `NOTES-001` (new feature area `notes`);
  INDEX entry created in slice 8, spec file per feature-file schema.
