# Direction `out` — KB → Use

> Survey date: 2026-08-21 · Format/method: see [README.md](./README.md)
> Scope: user-reachable capabilities that read or apply KB content (worldbuilding
> browser, search, entity detail/graph, series canon, wiki, timeline, proactive
> context). Every API path below has a mechanically verified method-pinned
> router-decorator match AND a mounted-path confirmation (rg; verification output
> in `.superpowers/sdd/2026-08-20-kb-benchmark-package1-adr083-inventory/task-3-report.md`).

### CAP-OUT-01: Browse novel KB entries in the worldbuilding 3-column view

| Field | Value |
|---|---|
| Direction | out |
| API path(s) | `GET /api/v1/novels/{novel_id}/kb/entries` (router: `apps/api/narrare/kb/router.py`; client: `packages/web/lib/api/kb.ts`); `GET /api/v1/novels/{novel_id}/kb/entries/autocomplete` (router: `apps/api/narrare/kb/router_references.py`, included by `kb/router.py`; client: `packages/web/lib/api/kb.ts`) |
| Output artifact | Paginated `KBEntryListResponse` (filters: entity type, tags, review status); prefix-match autocomplete name list |
| LLM-backed | no (deterministic SQL reads via `kb/repository.py`) |
| Benchmarkable | yes (result sets are mechanically comparable against the reference KB) |
| Notes | Data source of the `WorldBuilding` 3-column browser (column 1 type tabs, column 2 entry list). The novel list does NOT merge Series-Canon entries — canon is read via CAP-OUT-05; the merged effective view exists only inside the proactive-context pipeline. |

### CAP-OUT-02: Search KB entries by text

| Field | Value |
|---|---|
| Direction | out |
| API path(s) | `GET /api/v1/novels/{novel_id}/kb/entries/search` (router: `apps/api/narrare/kb/router.py`; client: `packages/web/lib/api/kb.ts`) |
| Output artifact | `KBEntryListResponse` filtered by substring match on name/body |
| LLM-backed | no (lexical SQL `ILIKE` in `kb/repository.py::search` — no embedding ranking) |
| Benchmarkable | yes (deterministic lexical retrieval, scorable against reference queries) |
| Notes | Lexical only. Semantic retrieval has NO free-text user endpoint (Finding 1, INFRA-004); the sole user-facing semantic path is chapter-scoped (CAP-OUT-08). |

### CAP-OUT-03: Open an entity's detail view with its relationships

| Field | Value |
|---|---|
| Direction | out |
| API path(s) | `GET /api/v1/novels/{novel_id}/kb/entries/{entry_id}`; `GET /api/v1/novels/{novel_id}/kb/entries/{entry_id}/relationships`; `GET /api/v1/novels/{novel_id}/kb/relationships/inverse-suggestion` (router: `apps/api/narrare/kb/router.py` + `kb/router_relationships.py`; client: `packages/web/lib/api/kb.ts`) |
| Output artifact | `KBEntryResponse` (full metadata/body); `KBRelationshipResponse` list (direction filter); inverse rel-type mapping |
| LLM-backed | no (deterministic reads; inverse map is a static lookup) |
| Benchmarkable | yes (detail payloads and relationship sets are mechanically comparable to the reference) |
| Notes | Feeds the WorldBuilding column-3 detail panel. Inverse-suggestion is the read helper announced by Task 2 CAP-IN-05 Notes. |

### CAP-OUT-04: View the knowledge graph (KnowledgeGraphView)

| Field | Value |
|---|---|
| Direction | out |
| API path(s) | `GET /api/v1/novels/{novel_id}/kb/graph`; `GET /api/v1/novels/{novel_id}/kb/graph/shortest-path` (router: `apps/api/narrare/kb/router_graph.py`; client: `packages/web/lib/api/kb-graph.ts`) |
| Output artifact | `GraphResponse` (nodes = KB entries, edges = relationships, statistics; entity/rel-type filters, node/edge caps); `ShortestPathResponse` (BFS entity-ID path) |
| LLM-backed | no (`graph_service.py` imports no agents) |
| Benchmarkable | yes (graph structure and path queries are mechanically comparable to the reference graph) |
| Notes | Visualization data for graph mode of the worldbuilding view. |

### CAP-OUT-05: Read Series-Canon KB entries (SERIES-001 read side)

| Field | Value |
|---|---|
| Direction | out |
| API path(s) | `GET /api/v1/series/{series_id}/kb`; `GET /api/v1/series/{series_id}/kb/{entry_id}` (router: `apps/api/narrare/kb/router_canon.py`, included by `kb/router.py`; client: `packages/web/lib/api/series.ts`) |
| Output artifact | `SeriesKBEntry` list / single entry |
| LLM-backed | no (deterministic reads via `canon_service.py`) |
| Benchmarkable | yes (canon set mechanically comparable to the reference) |
| Notes | Canon half of the KB scope split — read counterpart of CAP-IN-05. |

### CAP-OUT-06: Read wiki overview, entity summaries, and chapter summaries (WIKI-001 read side)

| Field | Value |
|---|---|
| Direction | out |
| API path(s) | `GET /api/v1/novels/{novel_id}/wiki/summaries`; `GET /api/v1/novels/{novel_id}/wiki/summaries/{entity_id}`; `GET /api/v1/novels/{novel_id}/wiki/chapters/{chapter_id}/summary`; `GET /api/v1/novels/{novel_id}/wiki/index` (router: `apps/api/narrare/wiki/router.py`; client: `packages/web/lib/api/wiki.ts`) |
| Output artifact | `WikiSummaryListResponse` / `WikiSummaryResponse` / `WikiChapterSummaryResponse` / `WikiIndexResponse` (overview + health status) |
| LLM-backed | no (plain reads of the precomputed summary tables; the summary text originates from `WikiGenerationAgent` at write time — CAP-IN-08) |
| Benchmarkable | partially (presence/freshness/index are mechanically scorable; summary text quality needs an LLM judge declared in the run manifest per ADR-083 Decision 3) |
| Notes | Pure reads — no lazy generation on GET (`wiki/service.py::get_summaries` only reads; generation happens via refresh and background listeners). |

### CAP-OUT-07: Read the timeline and the character-age report (PLAN-004 read side)

| Field | Value |
|---|---|
| Direction | out |
| API path(s) | `GET /api/v1/planning/timeline/{novel_id}/events`; `GET /api/v1/planning/timeline/{novel_id}/events/{event_id}` (router: `apps/api/narrare/planning/router_timeline.py`, mounted under `/planning` with sub-prefix `/timeline`); `GET /api/v1/planning/timeline/{novel_id}/character-ages` (router: `apps/api/narrare/planning/router_timeline_analysis.py`, same mount) (client: `packages/web/lib/api/timeline.ts`) |
| Output artifact | `TimelineEventCRUDResponse` list (filters: event type, chapter, source, confirmation) / single event; `CharacterAgeReport` (ages computed from KB birth-date metadata + timeline events) |
| LLM-backed | no (deterministic CRUD reads; character ages = date arithmetic over `KBEntry.metadata_` via `CharacterAgeService`) |
| Benchmarkable | yes (event sets and computed ages are mechanically comparable to the reference timeline) |
| Notes | Timeline events live in the planning surface, not `kb_entries` (CAP-IN-07 note). The AI-analysis GET and the consistency GET on the same router are Findings 3–4, not entries. |

### CAP-OUT-08: Get proactive KB suggestions for a chapter (KB-005 query side)

| Field | Value |
|---|---|
| Direction | out |
| API path(s) | `GET /api/v1/novels/{novel_id}/kb/suggestions/{chapter_id}` (router: `apps/api/narrare/kb/router_suggestions.py`; client: none yet — API-mounted only) |
| Output artifact | Ranked `KBSuggestionResponse` list (`max_results` ≤ 100) |
| LLM-backed | no (3-stage pipeline in core `ProactiveContextService`: name matching → pgvector embedding search → hybrid scoring of similarity + usage + recency; no `narrare_core.agents` import) |
| Benchmarkable | yes (ranking is scorable against reference relevance sets) |
| Notes | The user-facing query path of KB-005 — the expected "internal-only" case does NOT hold; only the generation-time injection remains internal (Finding 2). No frontend call site exists yet (no `kb/suggestions` match in `packages/web/`). |

### CAP-OUT-09: Resolve @Name mentions in text to KB entries

| Field | Value |
|---|---|
| Direction | out |
| API path(s) | `POST /api/v1/novels/{novel_id}/kb/resolve-references` (router: `apps/api/narrare/kb/router_references.py`, included by `kb/router.py`; client: `packages/web/lib/api/kb.ts`) |
| Output artifact | `ResolveReferencesResponse` (linked references with entry IDs + rendered reference HTML) |
| LLM-backed | no (regex mention scan + case-insensitive exact-name lookup, `kb/_reference_resolution.py`) |
| Benchmarkable | yes (link set is scorable against reference mention→entry links) |
| Notes | Handed to Tasks 3/4 by Task 2 Finding 2; assigned to `out` here because it is pure lookup without a consistency verdict (Finding 8 — Task 4 must not double-count). Writes nothing. |

### CAP-OUT-10: Fetch KB entry-type templates (discovered beyond the seed list)

| Field | Value |
|---|---|
| Direction | out |
| API path(s) | `GET /api/v1/novels/{novel_id}/kb/templates`; `GET /api/v1/novels/{novel_id}/kb/templates/{entity_type}` (router: `apps/api/narrare/templates/router.py` with prefix `/novels/{novel_id}/kb/templates`; client: `packages/web/lib/api/kb.ts`) |
| Output artifact | `TemplateInfoResponse` list / `TemplateDetailResponse` (field definitions per entity type) |
| LLM-backed | no (static template reads) |
| Benchmarkable | yes (schema reads are mechanically comparable) |
| Notes | Read support for guided KB authoring (drives the create form / type tabs). Template-update management (`GET …/kb/templates/updates`, `GET …/kb/templates/{entity_type}/diff`) is prompt-system update UX, not KB use — deliberately not listed. |

## Findings

1. **No user-facing semantic (free-text) search endpoint (INFRA-004) — backend must expose this.**
   `GET /api/v1/novels/{novel_id}/kb/entries/search` is lexical `ILIKE` (`kb/repository.py::search`).
   Semantic retrieval exists (pgvector via `ProactiveContextService` stage 2) but is reachable only
   chapter-scoped through `GET /kb/suggestions/{chapter_id}` (CAP-OUT-08). The admin embeddings
   router (`/api/v1/admin/embeddings/*`: status, reprocess, model) manages embedding
   infrastructure, not user search. Free-text semantic retrieval is `not benchmarkable as-is`.
2. **KB-005 generation-time context injection is internal — not benchmarkable as-is.**
   The auto-attached context during writing/generation has no user-facing query path; only the
   query-side ranking is exposed (CAP-OUT-08). The injection effect is observable solely through
   generation output (indirect).
3. **AI timeline analysis on GET — direction `in` artifact, not an entry here.**
   `GET /api/v1/planning/timeline/{novel_id}` runs `TimelineAgent` on a GET and persists the
   timeline (`timeline_analysis_service.py`) — text→timeline, the CAP-IN-07 direction. Task 2 did
   not list it either; recorded for Task 5 synthesis.
4. **Temporal consistency check — direction `check`.**
   `GET /api/v1/planning/timeline/{novel_id}/consistency` (deterministic checks + optional
   `TimelineAgent` validation) is verdict-bearing → Task 4.
5. **KB consistency router — direction `check`.**
   `apps/api/narrare/kb/router_consistency.py` (mounted in `_app/main.py`) is verdict-bearing
   KB↔text analysis → Task 4.
6. **Non-KB planning/series surfaces not surveyed.**
   Storyboard/outline/sync/character-arc endpoints (`planning/router.py`) and the band-summary
   lifecycle (`series/router_band_summary.py`) read chapter-structure/plot-band data, not KB
   content — out of KB-direction scope.
7. **Memory subsystem deferred (carry-forward of Task 2 Finding 4).**
   `apps/api/narrare/memory/` writes no `kb_entries`; classification deferred to Task 5
   synthesis / baseline analysis (ADR-083 Design History).
8. **Scope decision — reference resolution assigned to `out`.**
   Task 2 Finding 2 handed `POST /kb/resolve-references` to Tasks 3/4; it is listed here
   (CAP-OUT-09) as pure lookup (no consistency verdict, no write). Task 4 must not double-count.
