# Synthesis — Capability Counts + Findings Register

> Synthesized 2026-08-21 from [01-in.md](./01-in.md), [02-out.md](./02-out.md),
> [03-check.md](./03-check.md) · Format/method: see [README.md](./README.md)
> Consolidation only — no new claims beyond the three survey files (task rule).
> Source findings are cited as `in-Fn` / `out-Fn` / `check-Fn`, numbered per each
> file's trailing `## Findings` section.

## Capability counts

| Direction | Total | Benchmarkable yes | Partially | No | LLM-backed (yes/partial) |
|---|---|---|---|---|---|
| `in` (text → KB) | 8 | 4 | 4 | 0 | 6 |
| `out` (KB → use) | 10 | 9 | 1 | 0 | 0 |
| `check` (KB ↔ text) | 7 | 2 | 5 | 0 | 7 |
| **Total** | **25** | **15** | **10** | **0** | **13** |

- Counts tally the `Benchmarkable` and `LLM-backed` fields of the 25 entries
  verbatim (cross-check: `rg -c "^### CAP-"` → 8 / 10 / 7).
- No entry is `Benchmarkable: no`. The `partially` cases are dominated by
  free-form output portions that need an LLM judge declared in the run manifest
  (ADR-083 Decision 3) — the deterministic portion is mechanically scorable.
- `LLM-backed` counts `yes` + `partial` (any server-side LLM involvement);
  only CAP-CHK-02 is `yes`, the other 12 are `partial` (deterministic stages
  plus one agent stage).

## Findings register

Consolidated from the three survey files (20 raw findings → 11 register
entries; duplicates and carry-forwards merged, mapping closed — see `Sources`).
Verdict values are the survey files' own labels.

| # | Finding | Sources | Affected capability ID(s) | Verdict | Impact on the benchmark |
|---|---|---|---|---|---|
| 1 | **CONS-001/ADR-044 chapter↔KB consistency router implemented but unmounted** (KB-009 pattern): `apps/api/narrare/consistency/router.py` implements `POST /consistency/check`, `POST /consistency/check/stream` (SSE, ADR-044 staged pipeline), `POST /consistency/chapters/{chapter_id}/check` (incl. rule-based KB pre-check + per-issue suggestions) — never included in `_app/main.py`, routes 404 at runtime, while the frontend side exists (`consistency-stream.ts`, `useConsistencyStream.ts`). | check-F1 | — (would be the flagship `check` entry; mounted KB↔KB counterpart: CAP-CHK-01) | `backend must expose this` (mount the router); `not benchmarkable as-is` until then | Blocks the flagship chapter↔KB (`check` direction) detection measurement. The mount/expose decision is a PO/coordinator decision **outside this package**; it must be taken before the check-direction measurements on this capability can run. |
| 2 | **Spec §3 prototype scenario not realized end-to-end by any mounted capability** (character height 1.65 m in KB vs 1.80 m in chapter M prose). Designed realization = Finding 1 (endorse via CAP-IN-01 → single-chapter check `include_kb=true`); mounted partial realizations only: CAP-CHK-02 (prose vs series Canon — needs a series, canon scope) and CAP-CHK-05/06 (voice profiles only). No deterministic prose-vs-KB-field comparator exists (`rule_based_check` compares within-KB same-name entries; a prose-vs-KB numeric contradiction is catchable only by an LLM stage). | check-F2 | CAP-IN-01, CAP-CHK-02, CAP-CHK-05, CAP-CHK-06 | `not benchmarkable as-is` (consequence of Finding 1) | The instrument design's end-to-end prototype scenario (extraction → endorsement → contradiction detection, scored against injected error truth) cannot be benchmarked as designed until Finding 1 is resolved. |
| 3 | **KB-009 merge/dedup route implemented but unmounted**: `POST /kb/merge` (`kb/router_merge.py` + `KBMergeAgent` via `merge_service.py`) is never included in `_app/main.py`, no frontend client — 404 at runtime. | in-F1 | — (would be an `in`-direction entry; spec §3 lists merge under direction `in`) | `not benchmarkable as-is` (mounting the router would restore the capability) | Blocks the merge/dedup (`in` direction) measurement. The mount/expose decision is a PO/coordinator decision **outside this package**; it must be taken before the merge measurement can run. |
| 4 | **No user-facing free-text semantic search (INFRA-004)**: `GET /kb/entries/search` is lexical `ILIKE` (`kb/repository.py::search`); semantic retrieval (pgvector, `ProactiveContextService` stage 2) is reachable only chapter-scoped via `GET /kb/suggestions/{chapter_id}` (CAP-OUT-08); the admin embeddings router manages embedding infrastructure, not user search. | out-F1 | CAP-OUT-02, CAP-OUT-08 | `backend must expose this`; free-text semantic retrieval additionally `not benchmarkable as-is` | Semantic-retrieval quality cannot be measured on a user-facing surface; only lexical search (CAP-OUT-02) and chapter-scoped suggestion ranking (CAP-OUT-08) are measurable now. |
| 5 | **KB-005 generation-time context injection is internal-only**: the auto-attached context during writing/generation has no user-facing query path; the injection effect is observable solely through generation output (indirect). | out-F2 | CAP-OUT-08 | `not benchmarkable as-is` | Injection-effect measurement blocked (indirect observability only); the query-side ranking (CAP-OUT-08) is the measurable half. |
| 6 | **ADR-044 `ContradictionPromotionPolicy` + cross-feature ref-index backstop have no user-facing surface** (zero consumers): `ContradictionPromotionPolicy` (Core `context/integration_contracts/_kb_lifecycle.py`) and backend `CrossFeatureRefIndexImpl` + `RefIntegrityIssueSink` (provider in `consistency/deps.py`) are implemented, but no router or service injects `get_cross_feature_ref_index` and no site constructs the policy — ref-integrity issues are logged (sink), never promoted into a user-visible consistency report. | check-F3 | — (no capability; would augment the `check` direction) | `not benchmarkable as-is` | Ref-integrity promotion cannot be measured — no production surface produces the promotable report. |
| 7 | **Character-voice analysis writes KB content — `in`-direction coverage gap in `01-in.md`**: `POST /analysis/character-voice/{novel_id}` (SSE) persists the merged `VoiceAnalysis` into character KB entries (`character_voice_kb_writer.py` → `metadata["speech"]`); Task 2's scope covered the `kb/ series/ planning/ wiki/` routers only, so `analysis/` writers were not surveyed for direction `in`. The written profiles are the comparison base of CAP-CHK-05/06. (The author-voice twin writes `ProjectSettings`, not KB.) | check-F5 | CAP-CHK-05, CAP-CHK-06 (profile consumers); missing `in` entry | other (coverage gap — inventory revision needed) | `in`-direction capability count understated: a KB-writing capability is absent from the inventory; a later inventory revision must add the entry before its build-quality can be measured. |
| 8 | **AI timeline analysis on GET is direction `in` but absent from `01-in.md`**: `GET /planning/timeline/{novel_id}` runs `TimelineAgent` on a GET and persists the timeline (`timeline_analysis_service.py`) — text→timeline, the CAP-IN-07 direction; only the verdict-bearing consistency GET is listed (CAP-CHK-04). No double-count. | out-F3, check-F6 | CAP-IN-07 (same surface family), CAP-CHK-04 | other (coverage gap — inventory revision needed) | `in`-direction capability count understated; a later inventory revision must add the entry (or record a scope decision) before its extraction quality can be measured. |
| 9 | **Memory subsystem classification deferred**: `apps/api/narrare/memory/` (mem0-backed) writes no `kb_entries`; classification deferred to Task 5 synthesis / baseline analysis — the superseded Knowledge-Contract sub-project's mem0 classification is replaced by the empirical baseline runs (ADR-083 Design History). Task 5 ruling: **deferred to baseline analysis** (nothing in the three surveys indicates a user-facing KB capability). | in-F4, out-F7, check-F7 | — (no capability) | other (deferred) | None for package 1; if the baseline runs surface KB-relevant memory behavior, a later inventory revision is the response path (ADR-083 Decision 9 check). |
| 10 | **Task-2 hand-forwards resolved by Tasks 3/4 — ledger closed**: reference resolution → CAP-OUT-09 (pure lookup, no verdict, no write); proactive KB suggestions → CAP-OUT-08; temporal consistency check → CAP-CHK-04; KB consistency router (mounted) → CAP-CHK-01. Recorded so the carry-forward chain is explicitly terminal. | in-F2, in-F3, out-F4, out-F5, out-F8, check-F8 | CAP-OUT-08, CAP-OUT-09, CAP-CHK-01, CAP-CHK-04 | other (resolved scope ledger) | None (open items: zero). |
| 11 | **Non-KB / non-verdict surfaces deliberately not surveyed**: storyboard/outline/sync/character-arc endpoints and the band-summary lifecycle (chapter-structure/plot-band data, not KB); text-only analysis (coreference/pov/readability — prose vs prose-internal rules, no KB side); generative analysis (beta-reader, deep-dive, sentiment, dialogue-coach, story-suggest — feedback, not verdicts); series voice-profile CRUD (baseline management, not checking); template-update management (prompt-system UX); DELETE variants (not direction `in`). | out-F6, check-F4, check-F8 (+ Notes of CAP-IN-05, CAP-OUT-10) | — | other (explicit scope exclusion) | None — out of KB-benchmark scope by design (spec §3: the inventory measures exactly the KB user capabilities). |

**Count by verdict:** `backend must expose this` = 2 (Findings 1, 4) ·
`not benchmarkable as-is` = 4 (Findings 2, 3, 5, 6; Finding 4's retrieval half
carries the label too) · other = 5 (Findings 7–11: two coverage gaps, one
deferral, two scope-ledger closures).

## LLM-config dependency

All capabilities with `LLM-backed: yes` or `partial` — these execute
server-side LLM calls and require a valid backend LLM provider configuration
before any run (spec §6 "Runner Configuration & LLM Backend Config"; ADR-083
Decision 8: runner-local **gitignored** config file inside `benchmark/` with
real credentials; provisioning through the **normal user configuration path**
so the benchmarked instance is configured exactly like a real user's instance;
the run manifest records an LLM-config fingerprint, never the secret):

| Capability | LLM-backed | Agent involved (per survey) |
|---|---|---|
| CAP-IN-01 | partial | `ExtractionAgent` (extract; apply deterministic) |
| CAP-IN-02 | partial | `KBAssistAgent` (suggest/interview/enhance) |
| CAP-IN-03 | partial | `KBImproveAgent` (analyze; apply deterministic) |
| CAP-IN-04 | partial | `WorldbuildingAgent` phase 1/2 (analyze; apply deterministic) |
| CAP-IN-07 | partial | `TemporalExtractionAgent` (extract SSE; confirm deterministic) |
| CAP-IN-08 | partial | `WikiGenerationAgent` (forced refresh; mark-stale deterministic) |
| CAP-CHK-01 | partial | `worldbuilding_analyzer` phase 2 stages (relationship asymmetry algorithmic) |
| CAP-CHK-02 | yes | governed `series_consistency` agent, 1 call |
| CAP-CHK-03 | partial | governed `author_voice_drift` agent, 1 call (metrics/trend deterministic) |
| CAP-CHK-04 | partial | optional `TimelineAgent` validation (deterministic checks primary) |
| CAP-CHK-05 | partial | `CharacterVoiceCheckerAgent` (parsing/metrics deterministic) |
| CAP-CHK-06 | partial | `CharacterVoiceDriftAgent`, 1 call per profiled character |
| CAP-CHK-07 | partial | `AuthorVoiceDriftAgent`, 1 call per run |

- Direction `out` requires **no** LLM config (all 10 entries `LLM-backed: no`).
- Separately (scoring side, not config): the free-form output portions of the
  `partially` benchmarkable entries need an LLM judge declared in the run
  manifest per ADR-083 Decision 3 — model + version, never implicit.

## Gaps for later slices

Explicitly **out of this package** (per spec §8 sequence; package 1 =
ADR-083 + inventory only):

- **Corpus reference format** — machine-readable reference KB + injected-error
  truth format is defined in the corpus slice (spec §4; sequence step 3).
- **Runner** — deterministic Python HTTP/SSE client incl. LLM-config
  provisioning mechanics verified there (spec §6; sequence step 4).
- **Scoring** — per-direction measurement and run-artifact shape (spec §5;
  sequence step 4), LLM-judge declarations included.
- **Resolution of register Findings 1–6** — mounting/exposing decisions and
  production-surface changes are PO/coordinator decisions outside this
  package; until they land, the corpus/runner/scoring plans scope measurements
  to the mounted capability set (the 25 inventory entries + register caveats).
- Inventory revisions for Findings 7–8 (coverage gaps) ride along with the
  corpus slice's capability selection (ADR-083 Decision 9 check).
