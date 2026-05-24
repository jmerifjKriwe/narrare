## Context

WRITE-003 (Extend Chapter) sits between two existing patterns:

- **WRITE-002 (Full Draft)**: Side-panel generation with WritingGraph (6-step agent
  orchestration), 1500–5000 words, explicit accept/reject via panel buttons.
- **WRITE-007 (Inline Suggest)**: Ghost text decoration, 1–3 sentences, no DB lifecycle,
  Tab/Escape interaction.

Extend is neither: it inserts 100–1000 words inline at the cursor, streams via SSE,
and needs full feedback tracking (accept/reject/modify → mem0). This hybrid nature
means we cannot simply reuse either pattern — but the differences are structural,
not superficial.

Four features share the same fundamental need: insert AI text into the editor and
track what the user does with it:

| Feature | Insert Method | Length | Tracking Needed |
|---------|--------------|--------|-----------------|
| WRITE-003 Extend | At cursor | 100–1000w | Full (accept/reject/modify) |
| WRITE-004 Rewrite | Replace selection | Variable | Full (accept/reject/modify) |
| WRITE-007 InlineSuggest | Ghost text (decoration) | 1–3 sentences | Minimal (tab/escape counters) |
| WRITE-009 Unblock | At cursor | 100–300w | Full (accept/reject) |

The design therefore splits into two layers: **editor infrastructure** (reusable) and
**extend pipeline** (feature-specific).

## Goals / Non-Goals

**Goals:**

- Build generic editor infrastructure (`AIAnnotation`) for tracking AI-generated text
  across all current and future AI text features
- Implement the Extend pipeline (endpoint → pipeline → prompt → stream) with full
  mem0 feedback integration
- Ensure precise modify-detection (original text vs. user-edited version) using
  ProseMirror transaction tracking, not position-based heuristics
- Enable clean-save behavior: AI annotations are editor state, not document state

**Non-Goals:**

- WRITE-004 (Rewrite) implementation — will consume the `AIAnnotation` infrastructure
  but is a separate change
- WRITE-009 (Unblock) implementation — same
- Modifying the existing `GhostText` extension — it handles a different pattern
  (non-persistent decoration) and stays as-is
- Multi-step agent orchestration for extend — a direct LLM call is correct
- Offline mode or local model support

## Decisions

### D1: `GenerationMode.EXTEND` as separate enum value (not a flag)

**Decision**: Add `EXTEND = "extend"` to `GenerationMode` in `_enums.py` and
`GenerationModeEnum` in `schemas.py`.

**Alternatives considered**:
- `FULL_DRAFT` with `extend=True` flag — blurs what "mode" means, creates
  branching logic inside `_full_draft()`, risks cross-contamination
- Separate service class entirely — overkill; extend reuses context assembly,
  draft processing, and feedback infrastructure

**Rationale**: The input contract is fundamentally different (cursor context vs.
outline). A separate mode gives clean dispatch in the pipeline, a distinct API
schema, and zero risk of FULL_DRAFT logic affecting extend behavior.

### D2: Separate endpoint `POST /extend` (not parameter on `/generate`)

**Decision**: New endpoint `POST /api/v1/writing/chapters/{chapter_id}/extend`
with `ExtendRequest` schema. Reuses existing SSE streaming (`GET /generation/{id}/stream`)
and accept/reject endpoints.

**Alternatives considered**:
- `POST /generate` with `mode: "extend"` — the request body shape differs
  (`text_before`/`text_after` vs. `outline`/`prompt`), making validation awkward
- WebSocket for extend — adds connection complexity with no benefit over SSE

**Rationale**: `ExtendRequest` has a different shape (`text_before`, `text_after`,
`length`) than `GenerateRequest`. A dedicated endpoint means clear validation and
clearer API semantics. The streaming and lifecycle endpoints remain shared.

### D3: Frontend sends `text_before`/`text_after` (not `cursor_position`)

**Decision**: Frontend splits document at cursor position and sends the text
segments. Backend never receives a numeric offset.

**Alternatives considered**:
- `cursor_position: number` — race condition with autosave; server may not have
  the latest content
- Full document + cursor position — wasteful; text_before is already sufficient

**Rationale**: The `InlineSuggestRequest` pattern already proves this works. The
frontend has authoritative knowledge of the editor state; sending pre-split text
eliminates an entire class of sync bugs.

### D4: ProseMirror Mark for AI text tracking (not Decoration)

**Decision**: `ai-generated` ProseMirror `Mark` with attributes: `request_id`,
`source`, `original_text`, `status`, `created_at`. A companion Plugin
(`AIAnnotationTracker`) monitors transactions within marked ranges.

**Alternatives considered**:
- Decoration-based tracking — decorations are visual-only, not part of the
  document, cannot carry metadata through save/load, cannot be inspected by
  transaction listeners
- React state (`originalTextRef`) — fragile, position-based, fails when user
  inserts/deletes text before the marked region
- ProseMirror `Node` — too heavy; marks are inline overlays on existing text

**Rationale**: Marks are part of the document model, carry arbitrary attributes,
and survive ProseMirror's transaction system. The `original_text` attribute
provides a reliable comparison baseline for modify-detection. The Tracker Plugin
uses ProseMirror's built-in transaction mapping (which handles insertions,
deletions, and position shifts correctly) — no manual position bookkeeping.

### D5: Clean Save — marks removed before persisting

**Decision**: `Autosave` extension removes all `ai-generated` marks before
calling `saveFn`. Pending marks trigger an implicit ACCEPT feedback event.

**Alternatives considered**:
- Persist marks to DB — stale marks after reload, complex lifecycle management,
  "pending" state in saved content is semantically wrong for a writing tool
- Strip marks without feedback — loses learning data

**Rationale**: Chapter content should always be clean prose. AI annotations are
an editor interaction state (like a selection or cursor position), not a document
property. When autosave fires, pending marks are resolved as accepted — the text
stays, the mark is removed, a feedback event is recorded.

### D6: Direct LLM call for extend (no WritingGraph)

**Decision**: `WritingPipeline._extend()` makes a single LLM call through the
composer and gateway. No agent orchestration, no plan-review-revise cycle.

**Alternatives considered**:
- WritingGraph with extend-specific steps — overkill for continuation; the
  quality comes from prompt construction (style matching), not iteration
- Scene-by-scene extend — contradicts the "seamless continuation" UX

**Rationale**: Extend's quality depends on the prompt (style analysis, pre-text
verbatim, scene state) and context assembly, not on multi-step agent reasoning.
A direct call is simpler, faster, and produces exactly what the spec requires.

### D7: Extend reuses `generation_requests` table

**Decision**: Extend creates a `generation_request` row with `mode = "extend"`.
No new database table or migration needed.

**Rationale**: The lifecycle is identical (pending → streaming → completed/failed),
the same columns apply (chapter_id, novel_id, user_id, status, tone, word_count,
tokens_used), and the feedback system already keys off `generation_request.id`.
A new table would duplicate structure without adding value.

## Risks / Trade-offs

- **[Risk] ProseMirror Mark serialization**: If the `ai-generated` mark's
  `toHTML()`/`parseHTML()` is not configured correctly, marks could leak into
  saved chapter content.
  → **Mitigation**: The `Autosave` extension explicitly strips marks before
  calling `saveFn`. Belt-and-suspenders: also configure the mark with
  `excludes: "_"` and `inclusive: false` to minimize serialization surface.

- **[Risk] Large text_before payloads**: A 10,000-char `text_before` field
  could strain request parsing.
  → **Mitigation**: `ExtendRequest.text_before` is capped at 10,000 chars
  (`max_length=10000`). The pipeline truncates further to the last ~1000 tokens
  for the actual LLM call.

- **[Risk] Multiple pending marks**: If the user triggers extend twice before
  resolving the first mark, there would be two overlapping pending regions.
  → **Mitigation**: `AIAnnotationTracker` auto-resolves any existing pending
  mark (implicit accept) before inserting a new one. Only one pending region
  exists at a time.

- **[Trade-off] Implicit accept on autosave**: The user loses the ability to
  reject after autosave fires. This is intentional — the alternative (persisting
  marks) creates worse problems. Users can always Ctrl+Z after implicit accept.
