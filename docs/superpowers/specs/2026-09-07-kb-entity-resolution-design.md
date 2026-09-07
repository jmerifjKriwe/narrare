# KB Entity Resolution Layer — Design Spec

> **Status:** Proposed with ADR-085 (2026-09-07) — binding design record
> **ADR:** `docs/architecture/decisions/ADR-085-kb-entity-resolution-layer.md`
> **Evidence base:** benchmark runs `2026-09-07-clean-incremental-1..3`
> (duplicate "Anna"/"Anna Meyer"; distractor "Anna Meier" ch-09;
> run -3 relation coverage 0.2222 entity-blocked)
> **Language of record:** English (project standard)

---

## §1 Scope

**In scope:** detection of likely-duplicate KB entries within one novel scope;
suggestion surface with per-signal evidence; deterministic merge execution on
explicit endorsement; provenance stamping by the extraction apply flow;
benchmark capability CAP-IN-10 (detection + merge measurement).

**Explicitly out of scope (v1):**

- Auto-merge execution (any policy) — the engine reports an
  `auto_merge_eligible` band; nothing executes without the endorse endpoint.
- Series-Canon scope (entries with `novel_id IS NULL`) — novel scope only in
  v1; canon dedup is a follow-up with its own review.
- Cross-novel / cross-series resolution.
- Frontend UI (separate slice; RULE-16/17 obligations named there).
- Name similarity between *different entity types* — candidates are
  same-`entity_type` only.

---

## §2 Module boundary

```
packages/core/narrare_core/kb/resolution/     ← pure, deterministic, no I/O
    __init__.py
    models.py        EntitySnapshot, EntryProvenance, SignalResult,
                     PairScore, ResolutionBand  (frozen dataclasses)
    name_tiers.py    normalization + S1 tier classification (pure)
    signals.py       S2 temporal, S3 attributes, S4 neighborhood, S5 embedding
    scoring.py       weights, calibration constants, veto logic, band mapping

apps/api/narrare/kb/entity_resolution/        ← orchestration + HTTP
    __init__.py
    contracts.py     Protocols (RULE-03; written first)
    snapshot_service.py    builds EntitySnapshot tuples from repos
    analysis_service.py    snapshots → engine → suggestions; cache; LLM band
    merge_executor.py      deterministic merge execution (D4 semantics)
    adjudicator.py         thin adapter over kb.merge_service.KBMergeService
    schemas_resolution.py  Pydantic request/response models
    router.py              thin routes (RULE-06/12)
    dependencies.py        SessionDep factories (RULE-19)
```

**Dependency direction (RULE-07, one-way):**

```
router.py → analysis_service/merge_executor → snapshot_service →
    KBRepositoryProtocol / RelationshipRepositoryProtocol / ChapterRepositoryProtocol
analysis_service → narrare_core.kb.resolution.scoring (pure)
analysis_service → adjudicator.py → kb/merge_service.py (KBMergeService, existing)
```

**Justification for the sub-package** (first inside `kb/`): the domain root
holds 60+ flat files; the resolution feature is a cohesive vertical
(detection + merge + endorsement lifecycle) whose 8–9 flat-prefixed files
would deepen the navigation problem. The flat-prefix alternative was rejected
for that reason; the sub-package changes no dependency direction and adds one
`include_router` line in `_app/main.py`.

**Untouched invariants:** `kb/_extraction_resolution.py` stays blocking-only;
`kb/merge_service.py` keeps its Mode-1 prompt governance (ADR-054) unchanged;
`kb/router_merge.py` is deleted when the resolution router lands (ADR-085 D5).

---

## §3 Contracts (Protocol-level, RULE-03)

```python
# apps/api/narrare/kb/entity_resolution/contracts.py  (written FIRST)

class SnapshotBuilderProtocol(Protocol):
    """Assembles pure EntitySnapshot tuples for one novel scope."""
    async def build(self, novel_id: UUID) -> tuple[EntitySnapshot, ...]: ...

class ResolutionAnalyzerProtocol(Protocol):
    """Detection pass: snapshots → scored, banded suggestions."""
    async def analyze(
        self, novel_id: UUID, user_id: UUID, *, refresh: bool = False
    ) -> ResolutionAnalysis: ...

class MergeExecutorProtocol(Protocol):
    """Executes one endorsed merge; idempotent."""
    async def execute(
        self, novel_id: UUID, user_id: UUID, plan: MergePlan
    ) -> MergeExecutionResult: ...

class UncertainBandAdjudicatorProtocol(Protocol):
    """LLM annotation for mid-band pairs (adapter over KBMergeService)."""
    async def adjudicate(
        self, novel_id: UUID, user_id: UUID, pairs: Sequence[PairCandidate]
    ) -> Sequence[Adjudication]: ...


# narrare_core/kb/resolution/scoring.py (pure engine — the testable seam)

class ResolutionEngineProtocol(Protocol):
    def score_pair(self, a: EntitySnapshot, b: EntitySnapshot) -> PairScore: ...
    def find_candidates(
        self, snapshots: Sequence[EntitySnapshot]
    ) -> tuple[tuple[EntitySnapshot, EntitySnapshot], ...]: ...
```

```python
# narrare_core/kb/resolution/models.py (frozen dataclasses — shape, not impl)

@dataclass(frozen=True)
class EntryProvenance:
    chapters: tuple[int, ...]              # ordered chapter positions
    first_seen_chapter: int | None
    last_seen_chapter: int | None
    name_variants: tuple[str, ...]         # names used in updates

@dataclass(frozen=True)
class EntitySnapshot:
    entry_id: UUID
    name: str
    entity_type: str
    status: str                            # deprecated entries are excluded
                                           # by the builder, not the engine
    metadata: Mapping[str, object]
    provenance: EntryProvenance | None     # None = unknown (never negative)
    neighbor_ids: frozenset[UUID]          # via relationship adjacency
    embedding: Sequence[float] | None      # precomputed; None = unknown

@dataclass(frozen=True)
class SignalResult:
    signal: str                            # "name_tier" | "temporal" | ...
    value: float                           # normalized [-1, 1]
    veto: bool = False
    detail: str = ""                       # human-readable evidence

@dataclass(frozen=True)
class PairScore:
    entry_a_id: UUID                       # ordered: min/max by id
    entry_b_id: UUID
    confidence: float                      # [0, 1]
    band: ResolutionBand                   # SUPPRESSED | REVIEW | AUTO_ELIGIBLE
    signals: tuple[SignalResult, ...]
    vetoes: tuple[str, ...]
```

---

## §4 Detection signals & confidence semantics

All computation is deterministic over snapshots. Every signal returns a value
in `[-1, 1]` (+ corroborating, − contradicting, 0 unknown/neutral), a veto
flag, and a human-readable detail string that surfaces in the suggestion
response (evidence transparency).

### Signal definitions

| ID | Signal | Values | Notes |
|----|--------|--------|-------|
| S1 | `name_tier` | `1.0` exact after normalization; `0.7` token-subset (short form ⊂ long form, shared first token, e.g. "Anna" ⊂ "Anna Meyer"); `0.4` fuzzy (stdlib `difflib` ratio ≥ 0.87, e.g. "Meier"~"Meyer"); `0.0` none | Normalization: casefold, diacritic fold, whitespace/punctuation collapse (reuse the benchmark `normalize_text` semantics conceptually; engine has its own pure copy — benchmark imports nothing from the product and vice versa). |
| S2 | `temporal` | `+1.0` handoff: provenance ranges non-overlapping, gap ≤ `HANDOFF_MAX_GAP=2` chapter positions, order consistent (shorter-name variant earlier); `−1.0` **co-existence** (veto): chapter ranges overlap/interleave AND `S1 < 1.0` (two distinguishable referents active in the same text); `+1.0` if `S1 == 1.0` with overlap (double extraction of one referent); `0` unknown provenance or gap > threshold | The distractor discriminator. Same-chapter distinguishable variants = author deliberately distinguishing two people. |
| S3 | `attributes` | `+1.0` continuity: ≥ 1 semantically shared metadata key with compatible values (e.g. age snapshots forming a consistent progression, same profession) and no contradiction; `−1.0` **contradiction (veto)**: same semantic key with incompatible values at overlapping validity (different stated gender, different birth date); `0` no shared keys | Semantic-key mapping is a small typed table (`age*`, `profession`, `gender`, `birth*`, `residence*`) — shared-prefix families, no LLM. |
| S4 | `neighborhood` | `+1.0` Jaccard(neighbor_ids) ≥ 0.3; `−0.5` disjoint when both have ≥ 2 relationships; `0` sparse/unknown | Weak corroborator by design — same social circle is suggestive, never decisive. |
| S5 | `embedding` | `+1.0` cosine ≥ 0.82 over name+body embeddings (existing pgvector data); `0` below threshold or missing | Never negative: semantically similar *different* people exist (the trap itself). |

### Confidence formula

```
raw  = 0.35·S1 + 0.30·S2 + 0.20·S3 + 0.10·S4 + 0.05·S5     (weights sum to 1.0)
conf = clamp01(raw)

Overrides (deterministic):
  any veto                     → conf = min(conf, 0.40), band ≤ REVIEW, veto listed
  zero corroborations          → conf = min(conf, 0.55)   # name-only ceiling:
                                (corroboration = S2 > 0 or S3 > 0 or S4 > 0)
                                an S1-only or S1+S5 pair can never reach AUTO_ELIGIBLE
```

### Bands

| Band | Threshold | Meaning |
|------|-----------|---------|
| `AUTO_ELIGIBLE` | conf ≥ `0.85` AND no veto AND `S1 ≥ 0.7` AND corroborations ≥ 2 AND `S2 = +1.0` (handoff/double-extraction) | Reported as `auto_merge_eligible: true`. **v1 executes nothing automatically** — the flag is benchmark input and future-policy input (ADR-085 D3). |
| `REVIEW` | conf ≥ `0.45` | Surfaced as a suggestion; optionally annotated by the LLM adjudicator. |
| `SUPPRESSED` | conf < `0.45` | Not surfaced; counted in analysis stats; debug-logged (RULE-11 — never silently dropped). |

Calibration constants (`AUTO_THRESHOLD=0.85`, `REVIEW_THRESHOLD=0.45`,
`HANDOFF_MAX_GAP=2`, `FUZZY_RATIO=0.87`, `EMBEDDING_COS=0.82`,
`NEIGHBOR_JACCARD=0.3`, weights) are module-level `Final` constants in
`scoring.py`, documented as ADR-085-referenced defaults; recalibration is a
spec-table edit with benchmark evidence (review trigger), not runtime config.

### Worked examples (corpus-grounded)

**Duplicate case — "Anna" (ch-01–03) vs "Anna Meyer" (ch-04+):**
S1 = 0.7 (subset) → 0.245; S2 = +1.0 (handoff, gap ≤ 2) → 0.30;
S3 = +1.0 (age 24@ch-01 → progression consistent, no contradiction) → 0.20;
S4 = +1.0 (shared family/colleague neighborhood) → 0.10;
S5 = +1.0 → 0.05. `raw = 0.895` → AUTO_ELIGIBLE (no veto, 3 corroborations,
S1 ≥ 0.7, S2 = handoff). Expected benchmark outcome: suggested, true positive.

**Distractor case — "Anna Meyer" vs "Anna Meier" (ch-09, co-active):**
S1 = 0.4 (fuzzy) → 0.14; S2 = −1.0 co-existence **veto** → −0.30;
S3 = 0 or −1.0 (disjoint facts / residence conflict) → ≤ 0;
S4 = −0.5 (disjoint neighborhoods) → −0.05; S5 = +1.0 → 0.05.
`raw ≤ −0.16` → clamp 0, veto listed → SUPPRESSED. Even with maximally
generous S3/S4, the veto caps conf at 0.40 → below REVIEW. The designed trap
is structurally rejected, not probabilistically.

**Distractor vs short form — "Anna" vs "Anna Meier":**
S1 = 0.7 (subset) → 0.245; S2 = 0 (gap 5 > 2: not a handoff); S3 = 0 (no
shared keys); S4 = −0.5 → −0.05; S5 = +1.0 → 0.05. `raw = 0.245` →
SUPPRESSED. Name-shape temptation alone never surfaces a suggestion.

---

## §5 Provenance stamping (enabler)

- `ApplyExtractionRequest` gains `chapter_id: UUID | None = None`
  (backward-compatible; the UI review panel and the benchmark driver know the
  chapter; the extract endpoint is already chapter-scoped).
- `apply_new_entity_item` / `apply_update_entity_item` maintain a reserved
  `metadata["provenance"]` block after merge-not-clobber composition:
  `{chapters: [...], first_seen_chapter, last_seen_chapter, name_variants}`
  (chapter *position*, resolved via `ChapterRepository`).
- `_extraction_resolution.merge_metadata` call sites strip a `provenance` key
  from `proposed_content` before composition — LLM proposals cannot forge or
  clobber provenance (red-first test required).
- Entries created before this change (or without `chapter_id`) have
  `provenance: None` → S2 = 0 (unknown), never negative. Documented
  limitation; no backfill in v1 (open question OQ-3).

---

## §6 Merge semantics (executor)

Input: `MergePlan {survivor_id, loser_id, result_name?, suggestion_id}` —
validated by re-scoring the pair (stateless suggestion identity,
ADR-085 Implementation Notes).

1. **Survivor selection (deterministic total order):** more metadata fact
   keys → more relationships → longer name (`decide_rename` guard keeps the
   fuller name; "Anna" + "Anna Meyer" → survivor named "Anna Meyer") → older
   `created_at`. Endorse may override the survivor but never the semantics.
2. **Metadata:** recursive two-sided merge; scalar conflict → survivor value
   wins, conflict recorded in `metadata["resolution"]["conflicts"]`
   (`{key, survivor_value, loser_value}`) — merge-not-clobber, no silent loss.
3. **Relationships:** re-point every edge referencing the loser to the
   survivor; skip rows that would collide on
   `uq_kb_relationships_unique(source_id, target_id, rel_type)`; never delete
   the surviving counterpart edge.
4. **Loser:** `status='deprecated'` (CHECK-constraint value) +
   `metadata["resolution"] = {merged_into, merged_at, suggestion_id,
   confidence}`. **Never deleted** — reversible, FK-safe, audit trail.
5. **Embeddings:** survivor `embeddings_dirty = true` (existing hooks re-embed).
6. **Transaction & idempotency:** single DB transaction; re-execution on an
   already-deprecated loser is a logged no-op returning the original result.
7. **Integration contract (RULE-03, cross-feature):** downstream consumers
   (list/search/graph/suggestions/writing context) must treat
   `status='deprecated'` entries as non-authoritative. §9 names the
   visibility-policy verification; a listing/graph exclusion filter is part
   of the executor slice if verification shows leakage.

## §7 Endpoint surface

All routes thin (RULE-06/12), novel-scoped, token-auth via existing deps:

| Method | Path | Behavior |
|--------|------|----------|
| POST | `/novels/{novel_id}/kb/resolution/analyze` | Run detection (cached; `refresh: bool = false` in body forces recompute). Response: suggestions + stats (per-band counts, suppressed count) + `cache_hit`. |
| GET | `/novels/{novel_id}/kb/resolution/suggestions` | Current cached suggestions without recompute (404-free: empty list when never analyzed). |
| POST | `/novels/{novel_id}/kb/resolution/suggestions/{suggestion_id}/endorse` | Validate by re-scoring; execute merge; return `MergeExecutionResult`. Optional body: `{survivor_id?}`. |
| POST | `/novels/{novel_id}/kb/resolution/suggestions/{suggestion_id}/reject` | Dismiss via the existing dismissed-suggestions pattern (persistent). 204. |

`analysis_service` caching mirrors the consistency-cache pattern (keyed on
novel scope + entries hash; invalidated on KB mutation). Suggestion identity:
`suggestion_id = sha256(min(idA,idB) ‖ max(idA,idB))` truncated — stateless,
re-validated at endorse time; no suggestion table, no migration.

## §8 Benchmark integration (ADR-083 D3/D9)

- **New capability `CAP-IN-10`** ("KB entity-resolution detection + merge",
  in-direction, `llm_backed: true` — honestly declared because the uncertain
  band may call the adjudicator; the deterministic core is what the detection
  metric scores). Registry + `inventory/01-in.md` + finding in-F1/F3
  resolution ("superseded by CAP-IN-10") updated in the same change.
- **Driver step** (in_direction): after incremental ingest (and optionally
  per chapter), call `analyze`, record suggestions to run artifacts
  (`in_records` pattern). Apply payloads must carry the new `chapter_id`.
- **New scorer `benchmark/scoring/resolution_match.py`:** derive *expected
  duplicate pairs* from the reference + actual entries — all entries whose
  normalized name/slug matches a reference entity's `name ∪ aliases` form one
  claim group; groups with ≥ 2 entries yield expected merge pairs
  (deterministic, transitive). "Anna" + "Anna Meyer" → one group (alias
  "Anna"); "Anna Meier" → its own reference → cross-pairs are false
  positives by construction (the precision trap, machine-checked).
  Metrics: suggestion **precision** (suggested ∩ expected / suggested),
  **recall** (expected ∩ suggested / expected), **band quality**
  (AUTO_ELIGIBLE ⊆ expected), veto effectiveness (distractor pair never
  suggested — binary gate).
- **Merge execution measurement:** endorse all non-rejected suggestions via
  the production endpoint (explicit, deterministic — no auto-merge policy
  involved), then re-run OUT scoring: entity coverage improves (duplicate
  `spurious` disappears), relation coverage unblocks (run -3's 6 blocked
  edges). Measurement validity: detection metrics never touch the LLM band.

## §9 Phased rollout (each phase complete, tested, inert-until-mounted)

| Phase | Content | Gate |
|-------|---------|------|
| P1 | Core engine (models, name_tiers, signals, scoring) + contracts | Unit tests incl. §4 worked-example pins (red-first); pyright/ruff/architecture clean; zero app wiring |
| P2 | Provenance stamping (schemas_extraction field, apply-flow stamping, forge-strip guard) | Red-first forge-strip test; apply tests stay green; no behavior change when `chapter_id` absent |
| P3 | Snapshot builder + analysis service + cache + router analyze/suggestions + main.py include | Route tests (auth, scope, 404→200); engine fed by fakes; RULE-17 types land here |
| P4 | Merge executor + endorse/reject + dismissed integration + retire `router_merge.py` + deprecated-visibility filter | Executor tests (idempotency, constraint dedupe, conflict record); router-merge removal verified by inventory + route table |
| P5 | Uncertain-band adjudicator adapter (KBMergeService) + wiring | Adapter test with faked agent; no new prompt surface (Mode-1 template reused) |
| P6 | Benchmark: CAP-IN-10 + driver step + `resolution_match.py` + inventory/docs | Registry consistency test; scorer unit tests incl. distractor binary gate; one manual baseline re-run (program rules) |

**Verification checklist for implementing slices** (named checks, not
assumptions): (a) metadata-template validation admits reserved `provenance`/
`resolution` keys (`_validators.py` / `build_entry_updates`); (b) chapter
*position* resolution handles renumbered chapters via repository, not stored
numbers; (c) list/search/graph exclude `deprecated` unless explicitly
requested; (d) `ApplyExtractionRequest` stays backward-compatible (old
clients, old run artifacts); (e) `check_architecture.py` green with the new
sub-package; (f) series-canon entries (`novel_id IS NULL`) are excluded from
novel-scoped analysis.

## §10 Rule-compliance matrix (ADR-085 Consequences, expanded)

RULE-01b (LLM only via existing agent), 02/02a/02b (no new prompt surface;
existing governed merge template), 03 (contracts first, §3), 04 (sub-package
split; limits per table), 05/06/07 (§2 direction), 08 (stdlib `difflib` only),
10 (per-slice tests), 11 (suppressed/veto/skips logged + counted), 12 (thin
router), 14 (avoided — JSONB), 16/17 (deferred to frontend slice, named),
18/18b (calibration constants are documented code constants, not router
config), 19 (SessionDep factories), 20 (phases complete; auto-merge absent
by decision, not half-built), 22 (LLM band rides existing invocation
evidence), 23 (no suppressions).
