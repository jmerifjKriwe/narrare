# IO-002 Corpus Analysis Pass — F3 (SETUP-003 follow-up) — Design Spec

> **Status:** Approved design record (2026-10-03) — formalizes the F3 design
> exploration; all project-owner rulings are FINAL (D12a, D13b, D14a, D15a,
> D16a, D17a, D18a, D19a, D20a, D21a — every ★ recommendation accepted).
> **ADR:** `docs/architecture/decisions/ADR-092-bulk-extraction-job.md`
> (engine) — F3 adds **no new ADR** (product scoping of an accepted engine).
> **Feature doc:** `docs/features/io/IO-002-import.md` (re-scoped same day)
> **Plan:** `docs/superpowers/plans/2026-10-03-io002-corpus-pass.md`
> **F2 sibling (engine):**
> `docs/superpowers/specs/2026-10-03-bulk-extraction-design.md`
> **Language of record:** English (project standard)

---

## §1 Scope

**In scope (F3):**

- **Corpus scope** on the ADR-092 engine: start a bulk-extraction job over a
  novel's accumulated chapters, enumerated server-side in `position` order.
- **Per-run cap + honest pre-run estimate** (D20a): protocol constants
  `CORPUS_PASS_MAX_CHAPTERS = 120`, `CORPUS_PASS_MAX_WORDS = 200_000`; an
  estimate surface shown BEFORE the run; explicit truncation messaging.
- **Dedup gate** (D15a): one automatic ADR-085 duplicate analysis when a
  corpus pass completes (deterministic engine only); suggestion count
  surfaced; a minimal suggestions review (endorse/reject) in the results UI.
- **Cost transparency** everywhere an estimate or a result is shown.
- Sidebar entry ("Analyze novel corpus") reusing the F2 panel (D19a).

**Explicitly out of scope (F3):**

- **Structure detection** — acts, arcs, timeline markers, planning-layer
  mapping: **deferred entirely** (D16a). Not "later in this feature" — out.
- **Reference documents** — character sheets, outlines, worldbuilding files as
  importable non-chapter documents: **dropped** (D17a).
- **Folder/directory upload** — deferred (D18a); SETUP-003's browser file
  upload remains the on-ramp.
- **Dashboard surface** — no new entry anywhere except the studio sidebar
  reuse (D19a).
- **DOCX coupling** (D21a) — the pass is chapter-source-agnostic; DOCX import
  is a separate SETUP-003 follow-up and is NOT a dependency of this feature.
- New agents, prompts, intents, chunkers, or KB write paths (D14a/D15a — the
  existing `ExtractionAgent` + apply endpoint carry everything).

---

## §2 Decision table (binding)

| # | Decision | Choice |
|---|----------|--------|
| D12 | Feature identity | **D12a**: IO-002 re-scoped as a **corpus analysis pass over imported (accumulated) chapters** — a product framing of the ADR-092 engine, not a new pipeline |
| D13 | Extraction targets | **D13b**: **entities + relationships** — proposal items of all existing types (`new_entity`, `update_entity`, `relationship`, `conflict`); relationships land in KB-008 via the existing apply flow |
| D14 | Chunking | **D14a**: **chapter = chunk** — one `ExtractionAgent` call per chapter, existing prompt (`core/prompts/_bundled/kb/en/extract`), existing roster/world-context semantics; no corpus re-chunking (oversized chapters are an F1-split problem, surfaced honestly) |
| D15 | Cross-chapter dedup | **D15a**: **per-chapter proposals + ADR-085 resolution as the dedup gate** — no inline fuzzy dedup; duplicates that slip through are detected post-pass and merged only by endorsement |
| D16 | Story-structure detection | **D16a**: **deferred entirely** (not built later in v1 — removed from the feature) |
| D17 | Reference documents | **D17a**: **dropped** from the feature (chapters only) |
| D18 | Folder upload | **D18a**: **deferred** (browser multi-file upload remains the input path) |
| D19 | Entry surfaces | **D19a**: **reuse wizard + sidebar entries** — the post-import CTA (F2) and the studio sidebar carry the corpus pass; no dashboard, no new navigation |
| D20 | Run size | **D20a**: **explicit per-run cap + honest pre-run estimate** — ≤ 120 chapters and ≤ 200,000 words per run (exact numbers below), estimate surface before start, explicit truncation when the cap bites |
| D21 | DOCX | **D21a**: **decoupled** — the pass never inspects provenance/format; works identically on typed, MD/TXT-imported, or future DOCX-imported chapters |

---

## §3 Relationship to the F2 engine (division of labor)

F2 (`2026-10-03-bulk-extraction-design.md`) ships the engine: explicit-id
jobs, five endpoints, runner/pacer/registry, panel with review reuse,
post-import CTA. F3 adds **product semantics on top**, touching no engine
invariant:

| Concern | F2 (engine) | F3 (corpus pass) |
|---|---|---|
| Chapter selection | explicit `chapter_ids` from the caller | server-side enumeration: whole novel in position order, cap-adjusted |
| Cap | engine guardrail 200 chapters (`BULK_EXTRACT_MAX_CHAPTERS`) | product cap 120 ch / 200k words (`CORPUS_PASS_*`) — always the tighter bound |
| Estimate | none (caller knows its counts) | estimate endpoint + confirm dialog (§4) |
| Job kind | `explicit` | adds `corpus` (marks the post-pass dedup trigger) |
| Post-completion | nothing | one automatic ADR-085 analysis + `suggestion_count` (§6) |
| UI entry | post-import CTA + panel | sidebar "Analyze novel corpus" reusing the same panel |

A fresh import's post-import CTA **is** a corpus pass in effect (the imported
chapters are the whole novel); F3 adds no second CTA — the sidebar entry
serves any novel any time (D19a).

---

## §4 Corpus scope, cap, and estimate (D20a — normative)

### 4.1 Constants (protocol constants, no settings surface — RULE-18b)

```python
CORPUS_PASS_MAX_CHAPTERS: Final[int] = 120
CORPUS_PASS_MAX_WORDS: Final[int] = 200_000
```

Rationale for the numbers: 120 chapters ≈ a long novel's chapter count at
typical lengths; 200k words ≈ the upper end of a full-length novel; at the
default analysis pace (5 calls/min) 120 calls take ≥ 24 minutes — the largest
run we are willing to default a user into. Both are revisable protocol
constants pinned by tests (like the v1 import guardrails).

### 4.2 Selection rule (deterministic)

Enumerate the novel's chapters via `ChapterRepository.list_by_novel`
(`apps/api/narrare/chapters/repository.py:36-42`, `position` order). The pass
covers the **longest prefix** of that order satisfying both
`len(prefix) ≤ 120` and `Σ word_count ≤ 200_000`. If the prefix is empty
(first chapter alone exceeds the word cap) → 422 telling the user to split
the chapter first (linking the F1 split affordance in the UI copy). Prefix
selection is **never silent** — the estimate always shows
`capped: true` with the full counts when truncation occurs (§4.3).

### 4.3 Estimate surface (exact shape)

`GET /api/v1/novels/{novel_id}/kb/extract/bulk/corpus/estimate` (owner-gated):

```json
{
  "total_chapters": 147,
  "total_word_count": 231_800,
  "selected_chapter_ids": ["<uuid>", "…"],
  "chapter_count": 120,
  "word_count": 189_400,
  "ai_calls": 120,
  "capped": true,
  "cap_reason": "chapters"            // "chapters" | "words" | null
}
```

`ai_calls = chapter_count` (D14a: one call per chapter — cost transparency is
a count of calls, never a vague "may take a while"). The FE confirm dialog
renders: `120 chapters (of 147) · 189,400 words · 120 AI calls` plus the
pacing note ("runs in the background at your analysis rate — default 5 AI
calls/minute"). When `capped`, the dialog explicitly offers the prefix run
(and says what remains). When not capped, `chapter_count == total_chapters`.

### 4.4 Start

`POST /api/v1/novels/{novel_id}/kb/extract/bulk/corpus` (no body) —
owner-gated; re-validates the selection server-side at start time (chapters
may have changed since the estimate); creates a job of kind `corpus` over the
current prefix ids; dispatches the F2 runner. Response: the F2
`BulkExtractionJobView` (201) / 409 while another job is active (engine
invariant) / 422 with counts when no prefix fits. Status/results/cancel/
resume: the **existing** F2 endpoints, unchanged shapes.

---

## §5 Chapter = chunk (D14a — what reuse means precisely)

- One `ExtractionService.extract_from_chapter` call per selected chapter —
  the **existing** prompt surface, roster, world context, run limits, retries
  (no new `LLMIntent`, no prompt edits, no chunker, no overlap windows).
- The accumulated-roster effect is the design's dedup *aid*: each call sees
  `existing_entity_names` + the typed ID roster
  (`apps/api/narrare/kb/extraction_service.py:182-192`), so **reviewing and
  applying chapters in position order** means later chapters propose
  `update_entity` against already-endorsed entries instead of fresh
  `new_entity` duplicates. The panel's position-order walking (F2 §8.2) is
  therefore not just UX — it is the cheap dedup mechanism.
- Oversized single chapters are not re-chunked: the word cap rejects them
  with a split-first message (honesty over silent truncation of prose).

---

## §6 Dedup gate (D15a — ADR-085 as the gate, not inline merging)

1. **Per-chapter proposals** apply through the existing endpoint
   `POST /novels/{novel_id}/kb/extract/apply` with `chapter_id`
   (`apps/api/narrare/kb/schemas_extraction.py:57-74`) — provenance stamps
   chapter positions (ADR-085 §5), which is what makes the deterministic
   temporal signals (handoff vs co-existence) work later.
2. **Post-pass trigger:** when a `corpus` job reaches `completed`, the runner
   performs ONE `resolution/analyze` call via the **non-adjudicated**
   analyzer (`get_resolution_analyzer`,
   `apps/api/narrare/kb/entity_resolution/dependencies.py:149` — deterministic
   engine, zero LLM calls; the auto-trigger never spends tokens silently).
   Own session, background context, same ADR-080 discipline as the pass
   itself. Failure → warning log + `dedup: {analyzed: false}` — visible, not
   fatal (RULE-11).
3. **Surfacing:** status/results views gain a `dedup` block:
   `{ "analyzed": true, "suggestion_count": 7 }`. The panel's results mode
   renders "7 possible duplicates found — review" opening the minimal
   suggestions review (§8).
4. **The gate:** endorse/reject via the EXISTING endpoints
   `POST …/kb/resolution/suggestions/{id}/endorse|reject`
   (`apps/api/narrare/kb/entity_resolution/router.py:75-110`) — merges happen
   only on endorsement (ADR-085 D3, suggestions-only). The pass never merges,
   never auto-applies, never re-runs analysis on its own.

---

## §7 Relationships → KB-008 (D13b)

Relationship proposals are ordinary extraction items
(`item_type: "relationship"`,
`packages/core/narrare_core/agents/extraction_types.py:32-43`); endorsement
applies them through the existing flow (`ExtractionApplyService` +
`RelationshipRepository`), making them immediately visible in the KB-008
graph. F3 adds **no** graph code — the graph is the beneficiary. The corpus
pass's value story for a migrated writer: entities accumulate chapter by
chapter, the graph densifies as relationships are endorsed, and ADR-085
keeps the roster clean.

---

## §8 Surfaces (D19a — reuse only)

- **Sidebar entry** `SidebarChapterList` (next to the existing import button,
  `packages/web/components/studio/SidebarChapterList.tsx:172-180`):
  "Analyze novel corpus" → estimate fetch → confirm dialog (§4.3 numbers,
  capped messaging, pacing note) → `POST …/corpus` → opens the F2
  `BulkExtractionPanel` with the returned `job_id`.
- **Post-import CTA (F2, unchanged):** for a just-imported novel the CTA pass
  over the imported chapters IS the corpus pass. No second CTA is added
  (D19a).
- **Panel (F2, extended once):** results mode gains the dedup card (§6.3) +
  a minimal `ResolutionSuggestionsList` (pairs with names + confidence band,
  endorse/reject buttons, empty state "No duplicates detected") — the
  ADR-085 review-trigger FE slice, scoped to the minimum the gate needs.
  New FE client `lib/api/kbResolution.ts` (list suggestions / endorse /
  reject) — none exists today.
- **No dashboard, no new navigation** (D19a). i18n keys ride the existing
  `studio` namespace (`kb.corpusPass.*`, `kb.resolution.*`) in en/de/fr
  (RULE-16, same task as first use).

---

## §9 DOCX decoupled (D21a)

The pass enumerates `Chapter` rows and reads `content` — it never sees file
names, formats, or provenance. DOCX import (a SETUP-003 follow-up) will
create chapters through the same commit path as MD/TXT today; a corpus pass
run afterwards behaves identically. Nothing in F3 may branch on chapter
origin.

---

## §10 Test strategy

| Layer | File | Covers |
|---|---|---|
| API unit | `tests/unit/api/kb/bulk_extraction/test_corpus.py` | selection rule (prefix, both caps, empty-prefix 422 with counts); estimate shape (capped/not); constants pinned (120/200k) |
| API unit | `tests/unit/api/kb/bulk_extraction/test_corpus_service.py` | owner gate before enumeration; start re-validates at start-time; kind=corpus; 409 reuse; 422 counts |
| API unit | `tests/unit/api/kb/bulk_extraction/test_post_pass_dedup.py` | completion of a corpus job triggers exactly one non-adjudicated analyze; suggestion_count lands on the job; analyze failure → analyzed:false + warning, job stays completed; explicit jobs never trigger |
| API integration | `tests/integration/kb/test_corpus_pass_api.py` | estimate→start→status(with dedup block after driving chapters done)→results over the real router; capped corpus (150 seeded chapters) honest numbers |
| FE unit | `packages/web/lib/api/kbResolution.test.ts` | list/endorse/reject paths + types |
| FE unit | `packages/web/components/studio/SidebarChapterList.test.tsx` (extend) | corpus entry opens confirm with honest numbers; capped copy; start calls corpus endpoint |
| FE unit | `packages/web/components/studio/extraction/BulkExtractionPanel.test.tsx` (extend) | dedup card renders count; suggestions list endorse/reject calls; empty state |
| FE unit | `packages/web/components/studio/extraction/ResolutionSuggestionsList.test.tsx` | pair rendering, endorse/reject handlers, loading/error |

RULE-10 discipline (the F1 lesson): every new service-ish file lands with its
unit test file in the SAME task; per-task verification includes
`python scripts/check_test_coverage_gaps.py --fail-on-missing`.

---

## §11 Risks & assumptions

| # | Risk | Mitigation / status |
|---|------|---------------------|
| R1 | 120-call runs are slow (≥24 min at default pace) | D20a accepted deliberately; estimate + pacing note make it a choice, never a surprise; cancel/resume bound the risk |
| R2 | Cross-chapter duplicates still created despite roster-aware prompts (the ADR-085 motivating defect) | Expected and gated: §6 post-pass analysis + endorsement-only merges; position-order review reduces the rate (§5) |
| R3 | Estimate at confirm time drifts from start-time corpus (chapters added between) | Start re-validates server-side (§4.4); drift → honest 422 or the new prefix, never a silent superset |
| R4 | The minimal suggestions review grows into a full resolution UI | Scoped to list + endorse/reject (§8); anything richer is its own feature slice (ADR-085 review-trigger scope note) |
| R5 | Post-pass analyze cost on huge rosters | Deterministic engine, one call, no LLM (§6.2); failure is visible and non-fatal |
| R6 | Users expect structure detection "because the old doc promised it" | The feature doc's Superseded-identity table kills the expectation explicitly (D16a) |

**Assumption ratified:** `CORPUS_PASS_MAX_CHAPTERS = 120` and
`CORPUS_PASS_MAX_WORDS = 200_000` are protocol constants — no settings
surface (RULE-18b), pinned by regression tests; revisiting them is a one-line
constant change + test update, not a product decision rediscovery.
