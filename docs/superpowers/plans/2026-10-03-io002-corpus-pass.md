# IO-002 Corpus Analysis Pass (F3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Productize the ADR-092 engine as IO-002's corpus analysis pass — server-side novel-wide chapter enumeration with a 120-chapter/200k-word per-run cap, an honest pre-run estimate, one automatic post-pass ADR-085 duplicate analysis, and the reusing sidebar/panel frontend surfaces.

**Architecture:** F3 layers product semantics onto the F2 engine (`kb/bulk_extraction/`, shipped by plan `2026-10-03-bulk-extraction.md` — F3 starts only after that plan's T1–T5 are merged): a pure `corpus.py` (enumerate → deterministic prefix selection → estimate), two service/router methods+routes riding the existing endpoints' invariants, a `kind="corpus"` marker on jobs that arms one post-completion dedup analysis (deterministic ADR-085 engine, own session), and FE reuse — sidebar entry + confirm dialog + dedup card + minimal suggestions list inside the existing `BulkExtractionPanel`. See spec `docs/superpowers/specs/2026-10-03-io002-corpus-pass-design.md`.

**Tech Stack:** Python 3.14 · FastAPI · Pydantic v2 · pytest/vitest · React 19 · TanStack Query · next-intl (en/de/fr). No new dependencies. No new ADR (ADR-092 governs the engine).

## Global Constraints

- Project language: **English** — all code, comments, tests; i18n values follow existing locale files.
- **Prerequisite:** F2 plan T1–T5 merged (engine + endpoints live). F3 FE tasks additionally require F2 T6–T7.
- **RULE-03:** the one new seam (chapter enumeration) is a Protocol in `bulk_extraction/contracts.py` before implementation (T1).
- **RULE-04:** file-size limits hold; `corpus.py` is pure and small.
- **RULE-06:** routers delegate immediately; services hold no SQLAlchemy; the post-pass analysis runs in the runner's own session.
- **RULE-07:** `narrare_core` untouched; no engine invariant (F2 spec §4–§7) is weakened — F3 only adds.
- **RULE-10 (THE F1 LESSON — hard):** every new service-ish file lands with its unit test file **in the SAME task**. Per-task verification MUST include `uv run python scripts/check_test_coverage_gaps.py --fail-on-missing` (exit 0).
- **RULE-11:** estimate truncation is explicit (`capped`/`cap_reason`), post-pass analysis failure is visible (`analyzed: false` + warning log) and non-fatal; no silent anything.
- **RULE-16:** new i18n keys (`studio.kb.corpusPass.*`, `studio.kb.resolution.*`) — `en`/`de`/`fr` in the SAME task as first use (T4, T5).
- **RULE-17:** FE field names EXACTLY match `bulk_extraction/schemas.py` (`CorpusEstimateView`, `dedup` block) — same commit as the schema change (T2 backend, T4/T5 mirror).
- **RULE-18b:** `CORPUS_PASS_MAX_CHAPTERS = 120`, `CORPUS_PASS_MAX_WORDS = 200_000` are protocol constants in `corpus.py` — NO settings surface.
- **RULE-19/20/23:** SessionDep factories; complete behavior per task; zero new `# type: ignore` / `@ts-ignore`.
- Errors: `ValidationError` → 422 with honest counts; `NotFoundError` → 404 (owner gate first, always); `ConflictError` → 409 (engine's active-job rule reused).
- Git writes (add/commit/push) are executed by the coordinator via **NarrarePlatformSpecialist**.
- Verification commands (repo root): backend unit `uv run --all-packages pytest <path> -v`; coverage-gap gate `uv run python scripts/check_test_coverage_gaps.py --fail-on-missing`; integration `just _ensure-services` then `uv run --all-packages pytest tests/integration/kb/test_corpus_pass_api.py -v`; frontend `cd packages/web && pnpm test -- <filter>` (+ `pnpm type-check`); architecture `just check-architecture`; final gate `just verify`.

## Cross-task contract table — names every implementer must share

| Concept | Exact name | Defined | Consumed |
|---|---|---|---|
| Caps | `CORPUS_PASS_MAX_CHAPTERS = 120`, `CORPUS_PASS_MAX_WORDS = 200_000` | T1 `corpus.py` | T1 selection, T2 service, T4 dialog copy |
| Selection | `select_corpus_prefix(chapters: Sequence[CorpusChapterRow]]) -> CorpusSelection` — longest position-order prefix fitting both caps; empty → `ValidationError` with counts | T1 | T2 estimate/start |
| Estimate view | `CorpusEstimateView{total_chapters, total_word_count, selected_chapter_ids, chapter_count, word_count, ai_calls, capped, cap_reason}` | T2 schemas | T4 FE mirror |
| Reader Protocol | `CorpusChapterSource` (`async def load_all(self, novel_id: UUID) -> list[BulkChapterRefWithWords]`) | T1 contracts | T2 service |
| Job kind | `registry.create(..., kind: Literal["explicit", "corpus"] = "explicit")` + `kind_of(job_id)` | T2 registry mod | T3 runner trigger |
| Dedup block | `dedup: {analyzed: bool, suggestion_count: int | None} | None` on status/results views (`None` for explicit jobs) | T2 schemas/registry | T3 runner writes, T5 FE card |
| Post-pass seam | `runner._run_post_pass_analysis(novel_id: UUID, owner_id: UUID) -> tuple[bool, int | None]` | T3 runner | T3 tests fake it |
| FE client | `bulkExtractionApi.corpusEstimate(novelId)`, `.startCorpusPass(novelId)`; `kbResolutionApi.{listSuggestions, endorse, reject}` | T4/T5 | T4/T5 UI |
| Surfaces | sidebar entry + `CorpusEstimateDialog` (T4); dedup card + `ResolutionSuggestionsList` (T5) — all inside existing `BulkExtractionPanel`/sidebar hosts | T4/T5 | — |

**Invariants:** (1) the prefix rule is deterministic — same chapter list ⇒ same selection; (2) the estimate never understates (`ai_calls == chapter_count`, capped messaging when truncating); (3) `dedup` is `None` on explicit jobs and `{analyzed: false, suggestion_count: null}` until the post-pass ran; (4) the post-pass analyzer is the NON-adjudicated one (deterministic only — no silent LLM spend); (5) endorse/reject call the existing ADR-085 endpoints verbatim.

## Task sizing deviations (deliberate)

- ≤ 3 *source* files / ≤ 250 *production* LOC per task (tests + i18n data excluded). Deviations:
  - **T2** touches 4 files — three are small extensions of F2 modules (schemas/service/router/registry); no new module.
  - **T4/T5** touch 6 files each — 3 are the `en`/`de`/`fr` `studio.json` triples (RULE-16 forces same-task).

---

### Task 1: Pure corpus scope module — enumeration, prefix selection, estimate math

**Files:**
- Create: `apps/api/narrare/kb/bulk_extraction/corpus.py`
- Modify: `apps/api/narrare/kb/bulk_extraction/contracts.py` (+ `CorpusChapterSource` Protocol, + `CorpusChapterRow` frozen dataclass = `BulkChapterRef` + `word_count: int`)
- Test: `tests/unit/api/kb/bulk_extraction/test_corpus.py`

**Interfaces:**
- Consumes: T1-F2 `BulkChapterRef` shape; `narrare_core.shared.errors.ValidationError`.
- Produces (T2/T4 rely on exact names):
  - `CORPUS_PASS_MAX_CHAPTERS: Final[int] = 120`, `CORPUS_PASS_MAX_WORDS: Final[int] = 200_000`
  - `CorpusSelection` frozen dataclass: `selected: tuple[BulkChapterRef, ...]`, `total_chapters: int`, `total_word_count: int`, `capped: bool`, `cap_reason: Literal["chapters", "words"] | None`
  - `select_corpus_prefix(chapters: Sequence[CorpusChapterRow]) -> CorpusSelection` — longest position-order prefix with `len ≤ 120` and `Σ word_count ≤ 200_000`; caller passes rows ALREADY in position order (assert monotonic positions); empty prefix (first chapter alone over the word cap) → `ValidationError` whose message carries `total_chapters`, the offending chapter's title + word count, and the split-first guidance.
  - `build_estimate(selection: CorpusSelection) -> CorpusEstimateData` where `CorpusEstimateData` is the pydantic-free dataclass mirrored 1:1 by T2's `CorpusEstimateView` (fields per the contract table; `ai_calls = len(selected)`).

- [ ] **Step 1: Write the failing tests** — `tests/unit/api/kb/bulk_extraction/test_corpus.py`:
  - `test_caps_pinned`: 120 / 200_000 exactly.
  - `test_small_novel_selects_everything`: 3 chapters, 9k words → all selected, `capped=False`, `cap_reason=None`.
  - `test_chapter_cap_bites_first`: 150 chapters × 1k words → 120 selected, `capped=True`, `cap_reason="chapters"`, totals honest (150 / 150k).
  - `test_word_cap_bites_first`: 90 chapters × 2.4k words → prefix stops at the last chapter keeping Σ ≤ 200k (83 chapters = 199.2k), `cap_reason="words"`, `capped=True`.
  - `test_boundary_exact_fit`: 120 chapters summing to exactly 200_000 → all selected, `capped=False`.
  - `test_single_oversized_chapter_rejected`: one 250k-word chapter → `ValidationError` naming the title, the word count, and "split".
  - `test_prefix_never_skips`: a prefix boundary chapter that would overflow is excluded, not skipped past (selection is a strict prefix).
  - `test_estimate_fields`: `build_estimate` maps selection 1:1 (`ai_calls == len(selected)`, ids ordered).
- [ ] **Step 2:** Run `uv run --all-packages pytest tests/unit/api/kb/bulk_extraction/test_corpus.py -v` — FAIL (no module).
- [ ] **Step 3: Implement** `corpus.py` (pure; no imports outside stdlib/`contracts`/core errors) + extend `contracts.py` with the Protocol and row dataclass.
- [ ] **Step 4:** Task tests PASS + `uv run python scripts/check_test_coverage_gaps.py --fail-on-missing` exit 0.
- [ ] **Step 5: Commit** — `git add apps/api/narrare/kb/bulk_extraction/ tests/unit/api/kb/bulk_extraction/test_corpus.py` · message `feat(kb): corpus pass scope — deterministic cap selection + estimate (F3 T1)`

---

### Task 2: Corpus estimate/start service + routes + job kind + dedup view fields

**Files:**
- Modify: `apps/api/narrare/kb/bulk_extraction/schemas.py` (+ `CorpusEstimateView`; + `dedup: BulkDedupInfo | None = None` on status/results views)
- Modify: `apps/api/narrare/kb/bulk_extraction/registry.py` (`create(..., kind="explicit")`, `kind_of(job_id)`, dedup state + `mark_dedup(job_id, suggestion_count)` / `mark_dedup_unavailable(job_id)`)
- Modify: `apps/api/narrare/kb/bulk_extraction/service.py` (+ `corpus_estimate(novel_id, user_id)`, `start_corpus(novel_id, user_id)`)
- Modify: `apps/api/narrare/kb/bulk_extraction/router.py` (+ `GET …/kb/extract/bulk/corpus/estimate`, `POST …/kb/extract/bulk/corpus`)
- Test: `tests/unit/api/kb/bulk_extraction/test_corpus_service.py`, `tests/integration/kb/test_corpus_pass_api.py`

**Interfaces:**
- Consumes: T1 selection/estimate; T1-F2 `BulkExtractionJobStore`, dispatcher, `verify_novel_owned`; a `ChapterRepository.list_by_novel`-backed `CorpusChapterSource` (wired in `dependencies.py` — extend the existing factory, no new factory file).
- Produces (T3/T4/T5 rely on): `BulkDedupInfo{analyzed: bool, suggestion_count: int | None}`; service methods — `corpus_estimate`: gate → load all rows → `select_corpus_prefix` → `CorpusEstimateView`; `start_corpus`: gate → re-load + re-select (start-time truth) → `has_active_for` → 409 → `create(kind="corpus")` → dispatch → job view. Routes return `CorpusEstimateView` (200) and `BulkExtractionJobView` (201); 422 with counts when the prefix is empty.

- [ ] **Step 1: Failing unit tests** (`test_corpus_service.py`; fake store/reader/dispatcher per F2 T5 patterns):
  - `test_estimate_gates_ownership_first` (foreign novel → `NotFoundError`, reader untouched);
  - `test_estimate_small_novel` / `test_estimate_capped_corpus` (view fields incl. `capped`, `cap_reason`, `selected_chapter_ids` prefix);
  - `test_start_revalidates_at_start_time` (reader returns a different set at start than the estimate call — job created over the START-time prefix);
  - `test_start_reuses_active_job_rule` (`has_active_for` → `ConflictError`, create never called);
  - `test_start_creates_corpus_kind` (store receives `kind="corpus"`);
  - `test_dedup_block_defaults` (registry: explicit job → `dedup is None`; corpus job → `{analyzed: False, suggestion_count: None}`; `mark_dedup` flips both fields).
- [ ] **Step 2:** Run — FAIL.
- [ ] **Step 3: Implement** the four file extensions; `dependencies.py` gains the `CorpusChapterSource` wiring (no new file).
- [ ] **Step 4:** Unit tests PASS + coverage-gap gate exit 0.
- [ ] **Step 5: Integration test** (`tests/integration/kb/test_corpus_pass_api.py`; `just _ensure-services`): seed a 150-chapter novel (position order, ~1k words each) → `GET …/corpus/estimate` asserts `{total_chapters: 150, chapter_count: 120, capped: true, cap_reason: "chapters", ai_calls: 120}` → `POST …/corpus` (201) → `GET …/status` shows 120 chapter rows in position order and `dedup.analyzed == false` → foreign user 404 on both routes → empty-prefix 422 (seed a fresh novel with one 250k-word chapter).
- [ ] **Step 6:** Integration PASS + `just check-architecture` exit 0.
- [ ] **Step 7: Commit** — `git add apps/api/narrare/kb/bulk_extraction/ tests/unit/api/kb/bulk_extraction/test_corpus_service.py tests/integration/kb/test_corpus_pass_api.py` · message `feat(kb): corpus pass estimate/start endpoints + job kind + dedup fields (F3 T2)`

---

### Task 3: Post-pass dedup trigger (deterministic ADR-085 analysis on completion)

**Files:**
- Modify: `apps/api/narrare/kb/bulk_extraction/runner.py` (post-completion hook + injectable seam)
- Test: `tests/unit/api/kb/bulk_extraction/test_post_pass_dedup.py`

**Interfaces:**
- Consumes: T2 `kind_of`/`mark_dedup`/`mark_dedup_unavailable`; `ResolutionAnalysisService.analyze(novel_id, user_id, refresh=True)` constructed exactly as `get_resolution_analyzer` wires it (`apps/api/narrare/kb/entity_resolution/dependencies.py:149-163`) — the NON-adjudicated analyzer (deterministic; zero LLM calls).
- Produces: `async def _run_post_pass_analysis(novel_id: UUID, owner_id: UUID) -> tuple[bool, int | None]` — own session via `get_session_factory()`; returns `(analyzed, suggestion_count)`; module attribute so tests monkeypatch it. Runner change: after `mark_job_completed(job_id)`, if `registry.kind_of(job_id) == "corpus"` → `await _run_post_pass_analysis(...)` → `mark_dedup(job_id, count)` on success / `mark_dedup_unavailable(job_id)` + `logger.warning("corpus_post_pass_dedup_failed", …)` on ANY exception (job stays `completed` — the pass itself succeeded). Runs BEFORE the runner returns (inside the GC-guarded task; drain-cancellation still wins — a shutdown-cancelled job never reaches the trigger, `dedup` stays `{analyzed: false}`).

- [ ] **Step 1: Failing unit tests** (`test_post_pass_dedup.py`; fake registry + fake `_run_post_pass_analysis`):
  - `test_corpus_completion_triggers_once` (kind=corpus, 2 chapters done → hook called once with the novel/owner, `mark_dedup(job_id, 7)` observed; job remains `completed`);
  - `test_explicit_jobs_never_trigger` (kind=explicit → hook not called);
  - `test_hook_failure_is_visible_not_fatal` (hook raises → `mark_dedup_unavailable` + warning log record; job stays `completed`);
  - `test_shutdown_cancel_skips_trigger` (cancel before completion → no hook, dedup block untouched);
  - `test_real_hook_builds_own_session` (with the real `_run_post_pass_analysis`, monkeypatching only the analyzer construction inside the session context — assert session-factory use + `refresh=True`).
- [ ] **Step 2:** Run — FAIL.
- [ ] **Step 3: Implement** the runner extension.
- [ ] **Step 4:** Task tests + the F2 runner suite (`test_runner.py`) stay green (explicit path unchanged) + coverage-gap gate exit 0.
- [ ] **Step 5: Commit** — `git add apps/api/narrare/kb/bulk_extraction/runner.py tests/unit/api/kb/bulk_extraction/test_post_pass_dedup.py` · message `feat(kb): corpus post-pass ADR-085 dedup trigger (F3 T3)`

---

### Task 4: FE corpus entry — sidebar entry + estimate confirm dialog (+ i18n)

**Files:**
- Modify: `packages/web/lib/api/bulkExtraction.ts` (+ `corpusEstimate`, `startCorpusPass` + `CorpusEstimate` type mirror)
- Create: `packages/web/components/studio/kb/CorpusEstimateDialog.tsx`
- Modify: `packages/web/components/studio/SidebarChapterList.tsx` (entry next to the import button, `:172-180`)
- Modify: `packages/i18n/messages/{en,de,fr}/studio.json` (`kb.corpusPass.*`)
- Test: extend `packages/web/components/studio/SidebarChapterList.test.tsx`; new `packages/web/components/studio/kb/CorpusEstimateDialog.test.tsx`

**Interfaces:**
- Consumes: T2 estimate/start endpoints (RULE-17 mirror of `CorpusEstimateView`); F2 `BulkExtractionPanel` (opened with the returned `job_id` — panel gains an optional `initialJobId` prop, additive); `useAIOperation` conventions for the start action (§16).
- Produces: `CorpusEstimateDialog(props: { novelId: string; open: boolean; onOpenChange: (open: boolean) => void; onStart: (jobId: string) => void })` — fetches the estimate on open (loading/error/degrade states per §16); renders the honest line `"{chapter_count} chapters (of {total_chapters}) · {word_count} words · {ai_calls} AI calls"` (the "(of N)" clause only when `capped`) + pacing note + cap explanation when `capped` (`cap_reason`-keyed copy); `Start` → `startCorpusPass` → `onStart(job_id)`. Sidebar entry "Analyze novel corpus" (`data-testid="corpus-pass-btn"`) below the import button, hidden when the novel has zero chapters.

- [ ] **Step 1: Failing vitest:** dialog renders honest numbers for a capped fixture (150/120 case asserting the "(of 150)" clause and `cap_reason: "chapters"` copy) and an uncapped fixture; start button calls `startCorpusPass` and invokes `onStart` with the job id; 422 empty-prefix error renders the split-first message; sidebar entry visible with chapters / hidden for empty novels; entry → dialog → panel chain.
- [ ] **Step 2:** `pnpm test -- CorpusEstimateDialog SidebarChapterList` — FAIL.
- [ ] **Step 3: Implement** the three files + locale triples: `kb.corpusPass.{entry, title, estimateLine, ofTotal, cappedChapters, cappedWords, pacingNote, start, cancel, splitFirstError}`.
- [ ] **Step 4:** Full `pnpm test` + `pnpm type-check` green; coverage-gap gate exit 0.
- [ ] **Step 5: Commit** — `git add packages/web/ packages/i18n/messages/` · message `feat(web): corpus pass sidebar entry + honest estimate confirm (F3 T4)`

---

### Task 5: FE dedup surfaces — dedup card + minimal suggestions review (+ i18n)

**Files:**
- Create: `packages/web/lib/api/kbResolution.ts` (list/endorse/reject + types mirroring `entity_resolution/schemas_resolution.py`)
- Create: `packages/web/components/studio/extraction/ResolutionSuggestionsList.tsx`
- Modify: `packages/web/components/studio/extraction/BulkExtractionPanel.tsx` (dedup card in results mode)
- Modify: `packages/i18n/messages/{en,de,fr}/studio.json` (`kb.resolution.*`)
- Test: `packages/web/lib/api/kbResolution.test.ts`, `packages/web/components/studio/extraction/ResolutionSuggestionsList.test.tsx`, extend `BulkExtractionPanel.test.tsx`

**Interfaces:**
- Consumes: T2 `dedup` block (RULE-17 mirror: `BulkDedupInfo`); existing endpoints `GET …/kb/resolution/suggestions`, `POST …/kb/resolution/suggestions/{id}/endorse`, `POST …/{id}/reject` (`apps/api/narrare/kb/entity_resolution/router.py:60-110`); F2 panel results mode.
- Produces: `kbResolutionApi = { listSuggestions(novelId, signal?), endorseSuggestion(novelId, suggestionId, signal?), rejectSuggestion(novelId, suggestionId, signal?) }`; `ResolutionSuggestionsList(props: { novelId: string })` — list of suggestion pairs (entry names + confidence band), per-row Endorse / Reject with optimistic removal + error rollback, empty state "No duplicates detected", loading/error states; panel dedup card: `dedup === null` → hidden; `analyzed === false` → "Duplicate check unavailable" (muted, non-blocking); `analyzed === true` → `"{count} possible duplicates found — review"` button toggling the list (lazy-fetched).

- [ ] **Step 1: Failing vitest:** card hidden for `dedup: null`; unavailable variant for `analyzed: false`; count variant opens the list; list renders pairs from a fixture, endorse removes the row (endpoint called), reject removes the row (204 path), empty state renders when `suggestions: []`.
- [ ] **Step 2:** `pnpm test -- ResolutionSuggestionsList BulkExtractionPanel kbResolution` — FAIL.
- [ ] **Step 3: Implement** the three files + locale triples: `kb.resolution.{title, empty, endorse, reject, endorsed, rejected, loadFailed, dedupFound ("{count} possible duplicates found"), dedupUnavailable, review}`.
- [ ] **Step 4:** Full `pnpm test` + `pnpm type-check` green; coverage-gap gate exit 0.
- [ ] **Step 5: Commit** — `git add packages/web/ packages/i18n/messages/` · message `feat(web): corpus pass dedup card + minimal ADR-085 suggestions review (F3 T5)`

---

### Task 6: Docs closure (no production code)

**Files:**
- Modify: `docs/features/io/IO-002-import.md` (frontmatter `status: planned` → `implemented` after the layers land; keep the Superseded-identity table)
- Modify: `docs/features/INDEX.md` (IO-002 row status 📋 → ✅; title already "Corpus Analysis Pass")
- Modify: `docs/_shared/CURRENT_STATE.md` (one volatility-policy-compliant entry: facts + ADR/spec links, no counts)
- Modify: `docs/architecture/decisions/ADR-085-kb-entity-resolution-layer.md` (Review Triggers: the "frontend consumption" item references this slice as its resolution)

**Steps:**
- [ ] **Step 1:** Update the four docs (CURRENT_STATE entry must pass `check_current_state_facts.py` — links/commands only).
- [ ] **Step 2:** `just check-architecture` — exit 0 (frontmatter schema, feature path accuracy — the IO-002 frontmatter paths from the 2026-10-03 rewrite now exist).
- [ ] **Step 3:** `just verify` (coordinator-triggered via **NarrarePlatformSpecialist**) — full gate green.
- [ ] **Step 4: Commit** — `git add docs/` · message `docs(io): IO-002 corpus analysis pass implemented — feature + ADR-085 closure (F3 T6)`

---

## Self-review checklist (executed)

- Spec §4 (scope/cap/estimate) → T1+T2+T4; §5 (chapter=chunk) → no code (engine reuse; pinned by T2 integration ordering assertions); §6 (dedup gate) → T2+T3+T5; §7 (relationships) → no new code (existing apply flow; asserted in T5's e2e-level fixtures); §8 (surfaces) → T4+T5; §9 (DOCX decoupling) → no code by construction (enumeration only). §1 out-of-scope items → deliberately absent from every task.
- No placeholders: every task carries exact signatures, wire shapes, and enumerated test cases with concrete fixtures.
- Type consistency: `CorpusEstimateView` (T2) ≡ `CorpusEstimate` (T4); `BulkDedupInfo` (T2) ≡ dedup card props (T5); `kind_of`/`mark_dedup` (T2) ≡ runner calls (T3).
