# Direction `check` — KB ↔ Text

> Survey date: 2026-08-21 · Format/method: see [README.md](./README.md)
> Scope: user-reachable capabilities that render a consistency/drift verdict
> comparing text against KB content (or, where honestly classified, against a
> stated non-KB comparison base). Every API path below has a mechanically
> verified method-pinned router-decorator match AND a mounted-path
> confirmation (rg; verification output in
> `.superpowers/sdd/2026-08-20-kb-benchmark-package1-adr083-inventory/task-4-report.md`).

### CAP-CHK-01: Run a consistency check on the project's KB and manage its findings (KB-004)

| Field | Value |
|---|---|
| Direction | check |
| API path(s) | `POST /api/v1/novels/{novel_id}/kb/consistency-check` (router: `apps/api/narrare/kb/router_consistency.py`; client: `packages/web/lib/api/consistency.ts`) |
| Output artifact | `ConsistencyCheckResponse` — combined report: entry-internal field contradictions (LLM), relationship asymmetry (algorithmic), cross-entity pair contradictions (LLM); cached 10-min TTL, `refresh=true` bypasses |
| LLM-backed | partial (entry-internal + cross-entity stages use `WorldbuildingDeps` / `worldbuilding_analyzer.py` phase 2; relationship asymmetry is algorithmic) |
| Benchmarkable | partially (structured findings with category/severity are scorable against a seeded contradiction reference; free-text explanations need an LLM judge per ADR-083 Decision 3) |
| Notes | KB↔KB only — no prose side (the chapter-prose counterpart lives on the unmounted CONS-001 router, Finding 1). Dismiss management (`POST …/kb/consistency/dismiss`, `GET …/kb/consistency/dismissed`, `DELETE …/kb/consistency/dismissed/{fingerprint}`; CR-AUFG-07-26) belongs to this capability — deterministic finding state, noted not listed. |

### CAP-CHK-02: Check a band's chapter prose against the series Canon and keep the drift snapshot (SERIES-004)

| Field | Value |
|---|---|
| Direction | check |
| API path(s) | `POST /api/v1/series/{series_id}/consistency/check`; `GET /api/v1/series/{series_id}/consistency/{novel_id}` (router: `apps/api/narrare/series/router_consistency.py`; client: `packages/web/lib/api/series.ts`) |
| Output artifact | `SeriesConsistencyCheckResponse` (conflicts list + summary + transparency counts "checked N canon entries against M chapters"); the GET returns the persisted `SeriesDriftSnapshotResponse` + staleness verdict |
| LLM-backed | yes (governed `series_consistency` agent, 1 call — `series_consistency_service.py` imports `narrare_core.agents.series_consistency_agent`) |
| Benchmarkable | yes (prose↔KB: the conflict set is mechanically scorable against canon violations seeded into the reference) |
| Notes | Store-on-run (C2): the POST result is persisted as the band's latest drift snapshot before it is returned; the snapshot GET is a pure read. The checked `novel_id` arrives in the request body. |

### CAP-CHK-03: Check series narrator drift against the series voice baseline (SERIES-004)

| Field | Value |
|---|---|
| Direction | check |
| API path(s) | `POST /api/v1/series/{series_id}/voice-drift/check` (router: `apps/api/narrare/series/router_voice_drift.py`; client: `packages/web/lib/api/series.ts`) |
| Output artifact | `AuthorVoiceDriftResponse` (narrator metric trend + jumps + agent drift verdict; persisted into the band's drift snapshot) |
| LLM-backed | partial (deterministic per-chapter narrator metrics + trend/jump computation; governed `author_voice_drift` agent, 1 call via the reused `author_voice_drift_pipeline`) |
| Benchmarkable | partially — the comparison base is the series voice profile (`SeriesSettings.author_voice`) + prose narrator metrics, NOT KB content (KB-adjacent at best); the deterministic trend/jump signals are scorable, the agent verdict needs an LLM judge |
| Notes | Honest classification per inventory rules: a prose/voice-profile check, listed because SERIES-004 bundles it with the canon-contradiction check. Graceful `no_profile` when the series voice cannot be analysed. |

### CAP-CHK-04: Check temporal consistency of the timeline, incl. duration impossibilities (PLAN-004)

| Field | Value |
|---|---|
| Direction | check |
| API path(s) | `GET /api/v1/planning/timeline/{novel_id}/consistency` (router: `apps/api/narrare/planning/router_timeline_analysis.py`, mounted under `/planning` with sub-prefix `/timeline`; client: `packages/web/lib/api/timeline.ts`) |
| Output artifact | `TemporalConsistencyResponse` — merged issue list with `rule_id`, severity, event IDs, `suggestion`, and `source` (deterministic vs LLM) |
| LLM-backed | partial (deterministic `run_deterministic_checks` from `narrare_core.analysis.temporal`, incl. `DurationImpossibilityCheck` — impossible durations, death-before-birth, impossibly fast travel; optional `TimelineAgent` validation via `_timeline_consistency_helpers.py`) |
| Benchmarkable | yes (the deterministic issue set — rule IDs + event IDs — is mechanically scorable against a seeded impossible-timeline reference; the LLM portion needs a judge) |
| Notes | Events↔KB hybrid: timeline events (planning surface) are enriched with character birth dates loaded from KB (`timeline_consistency_service.py` step 3); prose enters only via extracted/confirmed events (CAP-IN-07). LLM-invoking GET (non-deterministic portion). Handed over by Task 3 Finding 4. |

### CAP-CHK-05: Check a chapter's dialogue against stored character voice profiles (WRITE-010)

| Field | Value |
|---|---|
| Direction | check |
| API path(s) | `POST /api/v1/analysis/voice-check/{chapter_id}` (SSE) (router: `apps/api/narrare/analysis/router_voice_check.py`, prefix `/analysis`; client: `packages/web/lib/api/voice-check-stream.ts`) |
| Output artifact | SSE stream — progress events, per-character verdict entries, terminal `done` event |
| LLM-backed | partial (deterministic dialogue parsing + voice metrics; `CharacterVoiceCheckerAgent` produces the verdict — `voice_check_agent_runner.py` imports `narrare_core.agents.character_voice_checker_agent`) |
| Benchmarkable | partially (per-character verdict entries are scorable against seeded dialogue-voice violations; the explanations are free-form) |
| Notes | Comparison base = voice profiles stored in character KB entries (`metadata["speech"]`, written by the character-voice pipeline — Finding 5), read via `VoiceProfileConsumer` (ADR-050); `kb_relationships` flow in as context. Read-only — never writes KB. Discovered beyond the seed list. |

### CAP-CHK-06: Analyse longitudinal per-character voice drift against stored profiles (ANAL-009, ADR-073)

| Field | Value |
|---|---|
| Direction | check |
| API path(s) | `POST /api/v1/analysis/voice-drift/{novel_id}` (SSE) (router: `apps/api/narrare/analysis/router_voice_drift.py`, prefix `/analysis`; client: `packages/web/lib/api/voice-drift-stream.ts`) |
| Output artifact | SSE stream — per-character drift results (deterministic trend + jump signals, agent verdict) and graceful `no_profile` events |
| LLM-backed | partial (deterministic per-chapter metrics/trend/jumps; `CharacterVoiceDriftAgent`, one call per profiled speaking character — `voice_drift_agent_runner.py`) |
| Benchmarkable | partially (KB↔text: stored KB voice profiles vs per-chapter prose metrics; the deterministic trend/jump signals are scorable, the agent verdict needs an LLM judge) |
| Notes | Read-only drift pipeline (ADR-073). Characters without profiles or dialogue degrade gracefully (`no_profile`), never error. Discovered beyond the seed list. |

### CAP-CHK-07: Analyse novel-level narrator drift against the author-voice profile (ANAL-009 Phase 2B, ADR-074)

| Field | Value |
|---|---|
| Direction | check |
| API path(s) | `POST /api/v1/analysis/author-voice-drift/{novel_id}` (SSE) (router: `apps/api/narrare/analysis/router_author_voice_drift.py`, prefix `/analysis`; client: `packages/web/lib/api/author-voice-drift-stream.ts`) |
| Output artifact | SSE stream — narrator drift result (trend + jumps + agent verdict) and graceful `no_profile` |
| LLM-backed | partial (deterministic narrator metrics + trend/jumps; `AuthorVoiceDriftAgent`, 1 call per run — `author_voice_drift_agent_runner.py`) |
| Benchmarkable | partially — the comparison base is `ProjectSettings.author_voice`, NOT KB content; the deterministic signals are scorable, the agent verdict needs an LLM judge |
| Notes | Novel-level twin of CAP-CHK-03, listed for symmetry with the seeded SERIES-004 variant — Task 5 may reclassify. Display-only, never persisted. Discovered beyond the seed list. |

## Findings

1. **CONS-001/ADR-044 chapter↔KB consistency router is implemented but unmounted (KB-009 pattern) — `backend must expose this` (mount the router).**
   `apps/api/narrare/consistency/router.py` (prefix `/consistency`) implements
   `POST /api/v1/consistency/check`, `POST /api/v1/consistency/check/stream` (SSE;
   ADR-044 staged pipeline: `extracting_facts` → `checking_consistency` → final
   `ConsistencyResponse` event → `[DONE]`), and
   `POST /api/v1/consistency/chapters/{chapter_id}/check`, with the deterministic
   rule-based KB pre-check (`rule_helpers.py::rule_based_check`, confidence=1.0,
   merged with the LLM issues) and the per-issue `suggestion` field (CONS-001
   suggested actions). The router is never included in `_app/main.py` and imported
   nowhere else → all three routes 404 at runtime, while the frontend side exists
   (`packages/web/lib/api/consistency-stream.ts` + `lib/hooks/useConsistencyStream.ts`).
   This is the flagship error-detection capability of the `check` direction —
   `not benchmarkable as-is` until mounted.
2. **Spec §3 prototype scenario (height 1.65 m in KB vs 1.80 m in chapter M prose) is NOT realized end-to-end by any mounted capability.**
   The designed realization is exactly Finding 1: endorse the extracted 1.65 m into
   the KB (CAP-IN-01), then run the single-chapter check with `include_kb=true`
   (`check_chapter`: "Compares a single chapter against KB entity data") — unmounted.
   Mounted partial realizations: CAP-CHK-02 (prose vs series Canon — requires a
   series and checks canon scope, not the novel KB overlay) and CAP-CHK-05/06
   (voice-profile contradictions only). No deterministic prose-vs-KB-field
   comparator exists — `rule_based_check` compares same-name entries within the KB
   only; a prose-vs-KB numeric contradiction is catchable only by an LLM stage.
3. **ADR-044 `ContradictionPromotionPolicy` + cross-feature ref-index backstop have no user-facing surface.**
   `ContradictionPromotionPolicy` (`packages/core/narrare_core/context/integration_contracts/_kb_lifecycle.py`)
   and the backend `CrossFeatureRefIndexImpl` + `RefIntegrityIssueSink`
   (`consistency/ref_index.py`, `ref_integrity_sink.py`, provider in `deps.py`) are
   implemented, but no router or service injects `get_cross_feature_ref_index` and
   no site constructs the policy — ref-integrity issues are logged (sink), never
   promoted into a user-visible consistency report → `not benchmarkable as-is`.
4. **Text-only analysis checks not surveyed as entries.**
   `POST /analysis/coreference/{chapter_id}`, `POST /analysis/pov`, and
   `POST /analysis/readability` (verdict-bearing) compare prose against
   prose-internal rules — no KB side, out of `check` (KB ↔ text) scope. Generative
   analysis (beta-reader, deep-dive, sentiment, dialogue-coach, story-suggest)
   produces feedback, not verdicts — likewise out.
5. **Character-voice analysis writes KB content — direction `in` gap in `01-in.md`.**
   `POST /api/v1/analysis/character-voice/{novel_id}` (SSE) persists the merged
   `VoiceAnalysis` into character KB entries (`character_voice_kb_writer.py` →
   `metadata["speech"]`). Task 2's scope covered the `kb/ series/ planning/ wiki/`
   routers only, so `analysis/` writers were not surveyed for direction `in` —
   handed to Task 5. (The author-voice twin `POST /analysis/author-voice/{novel_id}`
   writes `ProjectSettings`, not KB.)
6. **Timeline LLM analysis GET stays direction `in` (carry-forward of Task 3 Finding 3).**
   `GET /api/v1/planning/timeline/{novel_id}` (TimelineAgent, persists) is
   text→timeline; only the verdict-bearing `GET …/consistency` is listed here
   (CAP-CHK-04). No double-count.
7. **Memory subsystem deferred (carry-forward of Task 2 Finding 4 / Task 3 Finding 7)** —
   `apps/api/narrare/memory/` classification deferred to Task 5 synthesis /
   baseline analysis (ADR-083 Design History).
8. **Scope decisions — reference resolution and non-check surfaces.**
   `POST /kb/resolve-references` stays in `out` (CAP-OUT-09; Task 3 Finding 8 —
   pure lookup, no verdict). Series voice-profile CRUD (`/series/{id}/voice`)
   manages the drift baseline, it does not check; the band-summary lifecycle and
   storyboard/outline surfaces are non-KB (Task 3 Finding 6).
