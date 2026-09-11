# KB Entity Resolution Layer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detect and merge duplicate KB entities (e.g. "Anna" vs "Anna Meyer") without ever merging the designed distractor ("Anna Meier"), per ADR-085.

**Architecture:** Pure deterministic Core engine (`narrare_core/kb/resolution/`) over frozen `EntitySnapshot`s; API orchestration sub-package (`apps/api/narrare/kb/entity_resolution/`); suggestions-only v1 (no auto-merge); merge = survivor + deprecated loser, never deleted; benchmark measures detection (CAP-IN-10).

**Tech Stack:** Python 3.14, stdlib `difflib` (RULE-08: no new deps), FastAPI, SQLAlchemy async, pytest. No migrations (JSONB metadata; RULE-14 avoided).

**Binding spec:** `docs/superpowers/specs/2026-09-07-kb-entity-resolution-design.md` (§-references below). ADR: `docs/architecture/decisions/ADR-085-kb-entity-resolution-layer.md`.

## Global Constraints

- Project language English. All code/comments/tests in English.
- RULE-03: contracts (Protocols) written FIRST in each package slice.
- RULE-04: hard file limits (400 lines Python); split before exceeding.
- RULE-11: suppressed pairs/vetoes/skips are logged and counted, never silently dropped.
- Calibration constants are module-level `Final` constants (RULE-18/18b), never router config.
- No `git commit --no-verify`. Commits via conventional messages; one commit per task.
- Gates per task: targeted pytest green → `uv run pyright` FULL 0 → `uv run ruff check .` clean. Final task adds `scripts/check_architecture.py` exit 0.
- ADR-084 draft (`docs/architecture/decisions/ADR-084-*.md`) is untracked PO property: NEVER stage, NEVER delete.

---

### Task 1: Core resolution models

**Files:**
- Create: `packages/core/narrare_core/kb/resolution/__init__.py`
- Create: `packages/core/narrare_core/kb/resolution/models.py`
- Test: `tests/unit/core/kb/resolution/test_models.py`

**Interfaces:**
- Produces (spec §3, verbatim): `EntryProvenance(chapters: tuple[int, ...], first_seen_chapter: int | None, last_seen_chapter: int | None, name_variants: tuple[str, ...])`; `EntitySnapshot(entry_id: UUID, name: str, entity_type: str, status: str, metadata: Mapping[str, object], provenance: EntryProvenance | None, neighbor_ids: frozenset[UUID], embedding: Sequence[float] | None)`; `SignalResult(signal: str, value: float, veto: bool = False, detail: str = "")`; `PairScore(entry_a_id: UUID, entry_b_id: UUID, confidence: float, band: ResolutionBand, signals: tuple[SignalResult, ...], vetoes: tuple[str, ...])`; `ResolutionBand = Literal["SUPPRESSED", "REVIEW", "AUTO_ELIGIBLE"]`.

- [ ] **Step 1: Write failing tests** — frozen dataclasses reject mutation (`__setattr__` raises `FrozenInstanceError`); `PairScore` normalizes id order? NO — constructor takes ids as given; the SCORING layer orders them (document in docstring). Test field presence and defaults (`veto=False`, `detail=""`), `SignalResult` value bounds are NOT validated at model level (scoring clamps).

```python
import dataclasses
import uuid
import pytest
from narrare_core.kb.resolution.models import (
    EntryProvenance, EntitySnapshot, SignalResult, PairScore, ResolutionBand,
)

def _snap(name: str = "Anna") -> EntitySnapshot:
    return EntitySnapshot(
        entry_id=uuid.uuid4(), name=name, entity_type="character",
        status="active", metadata={}, provenance=None,
        neighbor_ids=frozenset(), embedding=None,
    )

def test_snapshots_are_frozen():
    s = _snap()
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.name = "X"

def test_signal_result_defaults():
    r = SignalResult(signal="name_tier", value=0.7)
    assert r.veto is False and r.detail == ""

def test_provenance_fields():
    p = EntryProvenance(chapters=(1, 2, 3), first_seen_chapter=1,
                        last_seen_chapter=3, name_variants=("Anna",))
    assert p.chapters == (1, 2, 3)
```

- [ ] **Step 2: Run RED** — `uv run pytest tests/unit/core/kb/resolution/test_models.py -q` fails (module missing).
- [ ] **Step 3: Implement** — `models.py` with the five frozen dataclasses + `ResolutionBand` Literal exactly per Interfaces; `__init__.py` re-exports them (`__all__`). No logic.
- [ ] **Step 4: Run GREEN** + gates (pyright, ruff).
- [ ] **Step 5: Commit** `feat(core): kb resolution models (ADR-085 P1)`

---

### Task 2: Name tiers (S1)

**Files:**
- Create: `packages/core/narrare_core/kb/resolution/name_tiers.py`
- Test: `tests/unit/core/kb/resolution/test_name_tiers.py`

**Interfaces:**
- Consumes: nothing (pure stdlib).
- Produces: `normalize_name(value: str) -> str` (casefold, diacritic fold via unicodedata NFKD strip-combining, collapse whitespace/punctuation to single spaces, strip); `classify_name_tier(a: str, b: str) -> tuple[float, str]` returning `(tier_value, tier_name)` with `1.0 EXACT`, `0.7 SUBSET`, `0.4 FUZZY`, `0.0 NONE` per spec §4 S1 (subset = one normalized name's token set ⊆ other's AND shared first token; fuzzy = `difflib.SequenceMatcher.ratio() >= 0.87` on the shorter-vs-longer normalized full names; tier constants `Final`: `EXACT=1.0 SUBSET=0.7 FUZZY=0.4 NONE=0.0`, `FUZZY_RATIO=0.87`).

- [ ] **Step 1: Failing tests** (red-first distractor pins from §4):

```python
from narrare_core.kb.resolution.name_tiers import classify_name_tier, normalize_name

def test_exact_after_normalization():
    assert classify_name_tier("Anna Meyer", "anna  meyer!") == (1.0, "EXACT")

def test_subset_anna_in_anna_meyer():
    assert classify_name_tier("Anna", "Anna Meyer") == (0.7, "SUBSET")

def test_fuzzy_meier_vs_meyer():
    assert classify_name_tier("Anna Meier", "Anna Meyer") == (0.4, "FUZZY")

def test_none_disjoint_names():
    assert classify_name_tier("Peter Meyer", "Lisa Brandt") == (0.0, "NONE")

def test_subset_requires_shared_first_token():
    # "Meyer" is a subset token-wise but not first-token aligned
    assert classify_name_tier("Meyer", "Anna Meyer") == (0.4, "FUZZY")  # ratio >= .87? verify; else NONE
```

The last test: compute the actual difflib ratio for ("meyer", "anna meyer") ≈ 0.727 < 0.87 → expect `(0.0, "NONE")`. Pin whichever the implementation yields after deciding; the pin documents intent: no shared first token → not SUBSET.

- [ ] **Step 2: RED** → **Step 3: Implement** pure functions + `Final` constants.
- [ ] **Step 4: GREEN** + gates.
- [ ] **Step 5: Commit** `feat(core): kb resolution name tiers S1 (ADR-085 P1)`

---

### Task 3: Signals S2–S5

**Files:**
- Create: `packages/core/narrare_core/kb/resolution/signals.py`
- Test: `tests/unit/core/kb/resolution/test_signals.py`

**Interfaces:**
- Consumes: `EntitySnapshot`, `EntryProvenance`, `SignalResult`, name_tiers.
- Produces (all pure): `temporal_signal(a, b, s1_tier: float) -> SignalResult` (signal="temporal"; +1.0 handoff: both provenances non-None, ranges non-overlapping, gap = max(first_seen_b, first_seen_a) − min(last_seen_…) ordering-consistent ≤ `HANDOFF_MAX_GAP=2`; −1.0 VETO co-existence: overlapping/interleaving ranges AND s1_tier < 1.0; +1.0 when s1_tier == 1.0 with overlap; 0.0 unknown/gap>2; detail strings name the case); `attributes_signal(a, b) -> SignalResult` (signal="attributes"; semantic key families `("age", "profession", "gender", "birth", "residence")` — a metadata key belongs to a family if its normalized form starts with the family name; continuity +1.0: ≥1 family with compatible values on both sides and no contradiction; contradiction −1.0 VETO: same family incompatible at overlapping validity (different gender strings, or two age keys whose (year, value) pairs imply different birth years); compatibility for ages: numeric values differing by ≤1 when keys carry different years are "progression", equal years must match exactly; 0.0 no shared families); `neighborhood_signal(a, b) -> SignalResult` (signal="neighborhood"; Jaccard(neighbor_ids) ≥ `NEIGHBOR_JACCARD=0.3` → +1.0; both ≥2 neighbors and Jaccard == 0 → −0.5; else 0.0); `embedding_signal(a, b) -> SignalResult` (signal="embedding"; cosine ≥ `EMBEDDING_COS=0.82` and both embeddings non-None same length → +1.0; else 0.0 — never negative).

- [ ] **Step 1: Failing tests** — build snapshot helpers; pin: handoff (Anna ch1-3 vs Anna Meyer ch4-6, s1=0.7) → +1.0; co-existence veto (Anna Meyer ch4-12 vs Anna Meier ch9-10, s1=0.4) → −1.0 veto=True; s1=1.0 overlap → +1.0 no veto; unknown provenance → 0.0; gender contradiction veto; age progression 24@2017 vs 27@2020 → +1.0 continuity; same-year different-age → −1.0 veto; Jaccard cases; embedding cosine 0.9 → +1.0, 0.5 → 0.0, missing → 0.0.
- [ ] **Step 2: RED** → **Step 3: Implement** (constants `Final` here: `HANDOFF_MAX_GAP=2`, `NEIGHBOR_JACCARD=0.3`, `EMBEDDING_COS=0.82`).
- [ ] **Step 4: GREEN** + gates.
- [ ] **Step 5: Commit** `feat(core): kb resolution signals S2-S5 (ADR-085 P1)`

---

### Task 4: Scoring engine

**Files:**
- Create: `packages/core/narrare_core/kb/resolution/scoring.py`
- Test: `tests/unit/core/kb/resolution/test_scoring.py`

**Interfaces:**
- Consumes: models, name_tiers, signals.
- Produces: `class ResolutionEngine` with `score_pair(a: EntitySnapshot, b: EntitySnapshot) -> PairScore` and `find_candidates(snapshots: Sequence[EntitySnapshot]) -> tuple[tuple[EntitySnapshot, EntitySnapshot], ...]` (same entity_type, S1 tier ≥ FUZZY i.e. > NONE, pair ids ordered `(min, max)`); module constants `Final`: `W_NAME=0.35 W_TEMPORAL=0.30 W_ATTRIBUTES=0.20 W_NEIGHBORHOOD=0.10 W_EMBEDDING=0.05`, `AUTO_THRESHOLD=0.85`, `REVIEW_THRESHOLD=0.45`, `VETO_CAP=0.40`, `NAME_ONLY_CEILING=0.55`. `score_pair`: raw = Σ weight·signal.value; any veto → conf = min(conf, 0.40) and band ≤ REVIEW; zero corroborations (S2>0 or S3>0 or S4>0) → conf = min(conf, 0.55); AUTO_ELIGIBLE iff conf ≥ 0.85 AND no veto AND S1 ≥ 0.7 AND corroborations ≥ 2 AND S2 == +1.0; REVIEW iff conf ≥ 0.45; else SUPPRESSED. Vetoes tuple lists veto signal names; signals tuple carries all five `SignalResult`s.

- [ ] **Step 1: Failing tests** — pin the §4 worked examples EXACTLY:

```python
def test_duplicate_anna_case_auto_eligible():
    # S1=0.7 -> 0.245, S2=+1 -> 0.30, S3=+1 -> 0.20, S4=+1 -> 0.10, S5=+1 -> 0.05
    score = engine.score_pair(anna_ch1_3, anna_meyer_ch4_plus)
    assert score.confidence == pytest.approx(0.895)
    assert score.band == "AUTO_ELIGIBLE"

def test_distractor_coexistence_suppressed():
    score = engine.score_pair(anna_meyer, anna_meier_ch9)
    assert score.vetoes == ("temporal",)
    assert score.confidence <= 0.40
    assert score.band == "SUPPRESSED"

def test_anna_vs_meier_gap_suppressed():
    # S1=0.7, S2=0 (gap 5), S3=0, S4=-0.5, S5=+1 -> 0.245
    score = engine.score_pair(anna_ch1_3, anna_meier_ch9)
    assert score.confidence == pytest.approx(0.245)
    assert score.band == "SUPPRESSED"

def test_name_only_ceiling():
    # S1=0.7, S2=0, S3=0, S4=0 (sparse), S5=+1 -> raw 0.295 -> capped path n/a but band REVIEW? conf=0.295 < 0.45 -> SUPPRESSED
    # stronger case: S1=1.0 exact, S2/S3/S4=0, S5=1.0 -> raw 0.40 -> ceiling applies -> conf min(0.40,0.55)=0.40 -> SUPPRESSED
    score = engine.score_pair(exact_a, exact_b_unknown_rest)
    assert score.confidence == pytest.approx(0.40)
    assert score.band == "SUPPRESSED"
```

- [ ] **Step 2: RED** → **Step 3: Implement**.
- [ ] **Step 4: GREEN** + gates. **Phase P1 complete — zero app wiring, engine fully pure.**
- [ ] **Step 5: Commit** `feat(core): kb resolution scoring engine + bands (ADR-085 P1)`

---

### Task 5: Provenance stamping

**Files:**
- Modify: `apps/api/narrare/kb/schemas_extraction.py` (add `chapter_id: UUID | None = None` to `ApplyExtractionRequest`)
- Modify: `apps/api/narrare/kb/_extraction_apply_entity.py` (stamp `metadata["provenance"]` on create/update after merge-not-clobber)
- Modify: `apps/api/narrare/kb/_extraction_resolution.py` (strip `provenance` key from proposed content before composition)
- Test: extend `tests/unit/api/kb/test_apply_extraction*.py` + new `tests/unit/api/kb/test_provenance_stamping.py`

**Interfaces:**
- Consumes: `merge_metadata` (existing), `ChapterRepository` (resolve chapter position).
- Produces: reserved metadata block `{"provenance": {"chapters": [int...], "first_seen_chapter": int|None, "last_seen_chapter": int|None, "name_variants": [str...]}}` maintained by the APPLY FLOW only; `chapter_id` optional on the request; absent `chapter_id` → zero behavior change (no stamp when creating, no update when updating without provenance knowledge — but never REMOVE existing provenance).

- [ ] **Step 1: Failing tests** (red-first, spec §5): (a) forge-strip — proposed_content containing `"provenance": {...forged...}` never reaches stored metadata; (b) create with chapter_id=ch(pos 3) stamps `first=last=3, chapters=[3], name_variants=[name]`; (c) second apply ch(pos 7) same entry appends: `chapters=[3,7], first=3, last=7`; (d) apply without chapter_id leaves existing provenance untouched; (e) update_entity with a new name appends to `name_variants`; (f) old-shape requests (no chapter_id) still apply cleanly — backward compat.
- [ ] **Step 2: RED** → **Step 3: Implement** (position resolved via ChapterRepository ordering, not stored numbers — spec §9(b)).
- [ ] **Step 4: GREEN** (`uv run pytest tests/unit/api/kb/ -q`) + gates. Also verify `_validators.py`/`build_entry_updates` admit the reserved key (spec §9(a)) — adjust validator if it rejects.
- [ ] **Step 5: Commit** `feat(kb): extraction provenance stamping + forge guard (ADR-085 P2)`

---

### Task 6: Snapshot builder + contracts

**Files:**
- Create: `apps/api/narrare/kb/entity_resolution/__init__.py`
- Create: `apps/api/narrare/kb/entity_resolution/contracts.py`
- Create: `apps/api/narrare/kb/entity_resolution/snapshot_service.py`
- Test: `tests/unit/api/kb/entity_resolution/test_snapshot_service.py`

**Interfaces:**
- Consumes: `KBRepository`, `RelationshipRepository`, `ChapterRepository` (existing protocols/repos), Core models.
- Produces (spec §3): `SnapshotBuilderProtocol.build(novel_id: UUID) -> tuple[EntitySnapshot, ...]`; `class SnapshotBuilder` implementing it: fetches non-deprecated entries for the novel scope (excludes `novel_id IS NULL` canon rows AND `status='deprecated'`), parses `metadata["provenance"]` (tolerant: missing/invalid → `provenance=None`), collects neighbor id sets from relationship adjacency, leaves `embedding=None` in v1 (S5 stays 0 until wired — engine tolerates). Contracts file also declares `ResolutionAnalyzerProtocol`, `MergeExecutorProtocol`, `UncertainBandAdjudicatorProtocol` (spec §3 signatures verbatim) for later tasks.

- [ ] **Step 1: Failing tests** — fakes for the three repos; assert: deprecated excluded; canon (novel_id None) excluded; provenance parsed (dict → EntryProvenance with tuples); invalid provenance → None; neighbors frozenset from both source and target sides; empty novel → empty tuple.
- [ ] **Step 2: RED** → **Step 3: Implement** contracts FIRST, then builder.
- [ ] **Step 4: GREEN** + gates (`check_architecture.py` now sees the sub-package — run it here).
- [ ] **Step 5: Commit** `feat(kb): entity_resolution sub-package + snapshot builder (ADR-085 P3)`

---

### Task 7: Analysis service + schemas + cache

**Files:**
- Create: `apps/api/narrare/kb/entity_resolution/analysis_service.py`
- Create: `apps/api/narrare/kb/entity_resolution/schemas_resolution.py`
- Test: `tests/unit/api/kb/entity_resolution/test_analysis_service.py`

**Interfaces:**
- Consumes: `SnapshotBuilderProtocol`, `ResolutionEngine`, existing consistency-cache pattern (`kb/consistency_cache.py`).
- Produces: `class ResolutionAnalysisService` (implements `ResolutionAnalyzerProtocol`): `analyze(novel_id, user_id, *, refresh=False) -> ResolutionAnalysis` — build snapshots (cache-keyed on novel + entries hash; `refresh` forces recompute), `find_candidates` → `score_pair` each, map to `ResolutionSuggestion` schemas: `suggestion_id = sha256(f"{min_id}{max_id}")[:16]`, `auto_merge_eligible` flag (= band AUTO_ELIGIBLE), per-signal evidence list (signal, value, veto, detail), stats `{review, auto_eligible, suppressed}` counts + `cache_hit: bool`. SUPPRESSED pairs: counted + `logger.info("resolution_pair_suppressed", ...)` (RULE-11), never in the suggestion list. Pydantic response models in `schemas_resolution.py`: `ResolutionAnalysisResponse{suggestions: list[SuggestionResponse], stats: BandStats, cache_hit: bool}`.

- [ ] **Step 1: Failing tests** — fake builder returns the §4 worked-example snapshot pairs; assert: duplicate pair surfaced REVIEW/AUTO with 0.895; distractor NOT in suggestions but in `stats.suppressed`; suggestion_id stable across two calls (stateless); `cache_hit=False` then `True` on second analyze without refresh; refresh recomputes.
- [ ] **Step 2: RED** → **Step 3: Implement**.
- [ ] **Step 4: GREEN** + gates.
- [ ] **Step 5: Commit** `feat(kb): resolution analysis service + caching (ADR-085 P3)`

---

### Task 8: Router + dependencies + mount

**Files:**
- Create: `apps/api/narrare/kb/entity_resolution/router.py`
- Create: `apps/api/narrare/kb/entity_resolution/dependencies.py`
- Modify: `apps/api/narrare/_app/main.py` (one `include_router` line)
- Test: `tests/unit/api/kb/entity_resolution/test_router.py`

**Interfaces:**
- Consumes: analysis service + auth/novel-scope deps (existing patterns from other kb routers).
- Produces: spec §7 endpoints (analyze + suggestions GET only in this task; endorse/reject in Task 10): `POST /novels/{novel_id}/kb/resolution/analyze` (body `{refresh: bool = false}`), `GET /novels/{novel_id}/kb/resolution/suggestions` (empty list when never analyzed — 404-free). Thin routes (RULE-06/12), `SessionDep` factories in dependencies.py (RULE-19). TS types: RULE-17 obligations are frontend-slice; backend OpenAPI generates.

- [ ] **Step 1: Failing tests** — route tests with service fakes: 401 without token; 404 wrong novel scope; analyze 200 shape; suggestions GET empty-list 200 pre-analyze; analyze then suggestions returns pair. Verify route table contains the new prefix.
- [ ] **Step 2: RED** → **Step 3: Implement** + mount.
- [ ] **Step 4: GREEN** (`tests/unit/api/kb/` + router tests) + gates.
- [ ] **Step 5: Commit** `feat(kb): resolution analyze/suggestions endpoints mounted (ADR-085 P3)`

---

### Task 9: Merge executor

**Files:**
- Create: `apps/api/narrare/kb/entity_resolution/merge_executor.py`
- Test: `tests/unit/api/kb/entity_resolution/test_merge_executor.py`

**Interfaces:**
- Consumes: KBRepository, RelationshipRepository, `decide_rename` (existing guard), session savepoints (pattern from extraction apply Task B fix).
- Produces: `MergePlan {survivor_id, loser_id, suggestion_id}` (+ `result_name: str | None = None` — accepted only from `decide_rename` auto-result; explicit custom names rejected 422 per PO ruling OQ-5); `MergeExecutionResult {survivor_id, loser_id, merged_fact_keys, repointed_relationships, skipped_relationships, conflicts}`; `class MergeExecutor` (implements `MergeExecutorProtocol`): spec §6 semantics — deterministic survivor order (more metadata fact keys → more relationships → longer name via `decide_rename` → older `created_at`) computed when caller does not override; recursive two-sided metadata merge, scalar conflicts → survivor wins + recorded in `metadata["resolution"]["conflicts"]`; relationship re-point loser→survivor with `uq_kb_relationships_unique` collision skip (never delete counterpart); loser `status='deprecated'` + `metadata["resolution"]={merged_into, merged_at, suggestion_id, confidence}`; survivor `embeddings_dirty=True`; single transaction; idempotent re-execution on deprecated loser = logged no-op returning original result.

- [ ] **Step 1: Failing tests** — survivor order each tiebreak level; conflicts recorded not dropped; duplicate-edge collision skipped and counted; loser deprecated never deleted; idempotent second call no-op; custom result_name → 422; canonical-name pick via decide_rename ("Anna"+"Anna Meyer" → survivor "Anna Meyer").
- [ ] **Step 2: RED** → **Step 3: Implement**.
- [ ] **Step 4: GREEN** + gates.
- [ ] **Step 5: Commit** `feat(kb): deterministic merge executor (ADR-085 P4)`

---

### Task 10: Endorse/reject + deprecated visibility

**Files:**
- Modify: `apps/api/narrare/kb/entity_resolution/router.py` (+endorse/+reject routes)
- Modify: `apps/api/narrare/kb/entity_resolution/analysis_service.py` (re-validation hook)
- Modify: `apps/api/narrare/kb/repository.py` list/search + `router_graph.py` queries — exclude `status='deprecated'` unless explicitly requested (spec §6.7, §9(c))
- Test: extend router tests + `tests/unit/api/kb/test_kb_visibility.py`

**Interfaces:**
- Consumes: MergeExecutor, analysis cache, existing dismissed-suggestions persistence pattern.
- Produces: `POST .../resolution/suggestions/{suggestion_id}/endorse` — recompute the pair score (stateless id → entry pair), require band ≥ REVIEW still (else 409 with reason), optional body `{survivor_id}` override, execute merge, invalidate analysis cache, return `MergeExecutionResult`; `POST .../reject` — persist dismissal (existing pattern), 204, cache stays (pair excluded from future suggestions lists by dismissal check).

- [ ] **Step 1: Failing tests** — endorse happy path merges + cache invalidated; endorse stale/low-band → 409; reject → 204 + excluded from suggestions; deprecated entries invisible in entries list/search/graph by default, visible with explicit include flag.
- [ ] **Step 2: RED** → **Step 3: Implement**.
- [ ] **Step 4: GREEN** + gates.
- [ ] **Step 5: Commit** `feat(kb): resolution endorse/reject + deprecated visibility (ADR-085 P4)`

---

### Task 11: Retire router_merge

**Files:**
- Delete: `apps/api/narrare/kb/router_merge.py`
- Modify: `apps/api/narrare/_app/main.py` (remove include)
- Modify: `docs/architecture/decisions/ADR-083-kb-benchmark-infrastructure.md` D9 note (KB-009 superseded by CAP-IN-10) — small edit
- Test: `tests/unit/api/kb/test_route_table.py` (new or existing)

**Interfaces:**
- Consumes: nothing new. `KBMergeService` class STAYS (Task 12 adapter uses it); only the HTTP surface dies.

- [ ] **Step 1: Failing test** — route table must NOT contain the merge prefix; resolution prefix present.
- [ ] **Step 2: RED** → **Step 3: Delete + edit docs.** Sweep `rg "router_merge|kb/merge"` for imports; fix all.
- [ ] **Step 4: GREEN** (`tests/unit/api/` wide — catch stragglers) + gates.
- [ ] **Step 5: Commit** `feat(kb): retire KB-009 merge router, superseded by resolution (ADR-085 D5)`

---

### Task 12: Uncertain-band adjudicator adapter

**Files:**
- Create: `apps/api/narrare/kb/entity_resolution/adjudicator.py`
- Modify: `apps/api/narrare/kb/entity_resolution/analysis_service.py` (wire adjudicator into REVIEW band, feature: only when pairs exist; invocation evidence rides existing pipeline — RULE-22)
- Test: `tests/unit/api/kb/entity_resolution/test_adjudicator.py`

**Interfaces:**
- Consumes: `KBMergeService` (existing Mode-1 governed prompt — NO new prompt surface, RULE-02b).
- Produces: `class UncertainBandAdjudicator` (implements `UncertainBandAdjudicatorProtocol`): `adjudicate(novel_id, user_id, pairs) -> Sequence[Adjudication]` where `Adjudication {pair_key, supports_merge: bool, note: str}`; adapter converts PairScore/snapshots to the KBMergeService input shape and back; LLM failure → note the failure, `supports_merge=False` default (never crashes analysis — RULE-11 logged).

- [ ] **Step 1: Failing tests** — faked KBMergeService agent: annotate path adds notes to REVIEW suggestions; agent exception → logged, adjudication absent, analyze still 200.
- [ ] **Step 2: RED** → **Step 3: Implement**.
- [ ] **Step 4: GREEN** + gates. **P3–P5 complete.**
- [ ] **Step 5: Commit** `feat(kb): uncertain-band adjudicator adapter (ADR-085 P5)`

---

### Task 13: CAP-IN-10 registry + inventory

**Files:**
- Modify: `benchmark/capabilities_registry.py` (+CAP-IN-10 entry, `llm_backed: true`)
- Modify: `benchmark/inventory/01-in.md` (+CAP-IN-10 section; KB-009 finding marked superseded)
- Test: `benchmark/tests/test_capabilities_registry.py` (consistency)

**Interfaces:**
- Produces: registry entry `CAP-IN-10` "KB entity-resolution detection + merge", in-direction, requires `CAP-IN-01` (ingest precondition), endpoint paths `/novels/{id}/kb/resolution/*`.

- [ ] **Step 1: Failing test** — registry contains CAP-IN-10, paths match the live router route table (mirror the existing registry-consistency test pattern).
- [ ] **Step 2: RED** → **Step 3: Implement** registry + inventory doc section.
- [ ] **Step 4: GREEN** + gates.
- [ ] **Step 5: Commit** `feat(benchmark): CAP-IN-10 entity-resolution capability (ADR-085 P6)`

---

### Task 14: Benchmark driver step + chapter_id

**Files:**
- Modify: `benchmark/drivers/in_direction.py` (+analyze step for CAP-IN-10)
- Modify: `benchmark/ingest_steps.py` (apply payloads carry `chapter_id`)
- Modify: `benchmark/drivers/in_records.py` (record types for resolution suggestions)
- Test: extend `benchmark/tests/test_driver_in*.py`

**Interfaces:**
- Consumes: CAP-IN-10 registry, analyze endpoint, endorse endpoint (merge measurement: endorse all non-rejected suggestions — spec §8).
- Produces: driver events `resolution:analyze` (suggestions + stats recorded to run artifacts) and `resolution:endorse` loop (each endorse result recorded); ingest `endorse` requests gain `chapter_id` (the chapter just extracted).

- [ ] **Step 1: Failing tests** — fake HTTP: analyze called with right path/body; suggestions parsed into records; endorse per suggestion id; ingest endorse request body asserts `chapter_id` present.
- [ ] **Step 2: RED** → **Step 3: Implement**.
- [ ] **Step 4: GREEN** + gates.
- [ ] **Step 5: Commit** `feat(benchmark): resolution driver steps + provenance chapter_id (ADR-085 P6)`

---

### Task 15: Resolution scorer + runner wiring

**Files:**
- Create: `benchmark/scoring/resolution_match.py`
- Modify: `benchmark/runner_scoring.py` (wire resolution scoring phase: analyze + endorse + re-fetch)
- Test: `benchmark/tests/test_resolution_match.py`

**Interfaces:**
- Consumes: run artifacts (resolution records), reference corpus alias groups, entity matcher bindings.
- Produces (spec §8): `score_resolution(expected_groups, suggestions, endorsed) -> ResolutionScore` — expected pairs derived from alias groups (entries binding to the same reference entity = one group; ≥2 entries → transitive pair set); metrics: precision, recall, band quality (AUTO_ELIGIBLE ⊆ expected), `distractor_never_suggested: bool` (binary gate: any cross-reference-entity pair suggested → False). Runner: after OUT scoring, run resolution phase, re-fetch KB state, re-score entities+relations — report `pre/post` entity coverage delta and relation unblocking.

- [ ] **Step 1: Failing tests** — synthetic: Anna+AnnaMeyer suggested+endorsed, AnnaMeier never suggested → precision 1.0, recall 1.0, gate True; missing duplicate → recall hit; cross-pair suggested → gate False.
- [ ] **Step 2: RED** → **Step 3: Implement**.
- [ ] **Step 4: GREEN** + full gates incl. `uv run pytest benchmark/tests/ -q` + `scripts/check_architecture.py` exit 0.
- [ ] **Step 5: Commit** `feat(benchmark): resolution scorer CAP-IN-10 + rerun wiring (ADR-085 P6)`

---

## Post-plan (not plan tasks)

- Manual baseline re-run: `uv run python -m benchmark run --variant clean --mode incremental --capabilities CAP-IN-01,CAP-IN-10,CAP-OUT-03` (program rules: manual, never CI).
- CURRENT_STATE.md update + push decision (PO).
