## Context

INFRA-004 is complete with:
- `EmbeddingStoreProtocol` in `core/embeddings/store.py` — `search()` method returns `list[SearchResult]`
- `rank_candidates()` + `ScoringConfig` + `ScoredCandidate` in `core/embeddings/scoring.py` — hybrid scoring with 0.50 similarity + 0.30 usage + 0.20 recency
- `ContextUsageService` in `api/kb/usage_service.py` — tracks accept/dismiss in `context_usage_events` table
- `kb_entries` columns: `last_referenced_at`, `usage_count` — updated on accept

The 3-stage pipeline from KB-005 spec:
1. **Content Analysis**: Extract entity names from chapter text, detect themes
2. **KB Search**: Embedding search (pgvector) + name matching + graph traversal
3. **Scoring**: Hybrid formula using `rank_candidates()`

The core service must be platform-independent (no SQLAlchemy, no FastAPI). It receives abstract interfaces via DI and returns domain objects. The API service wraps it with concrete implementations.

## Goals / Non-Goals

**Goals:**
- `ProactiveContextProtocol` + `ProactiveContextService` in core/ — the 3-stage pipeline
- `KBSuggestService` in api/ — thin wrapper with concrete deps
- `GET /api/v1/kb/suggestions/{chapter_id}` endpoint
- Unit tests for core service (using fakes)
- Integration tests for API endpoint
- Max 20 suggestions per request

**Non-Goals:**
- Real-time SSE updates as user types (future — needs debounced WebSocket)
- Graph traversal (relationship-based suggestions) — Phase 2, after relationship queries are in core
- Theme detection via LLM — start with entity name extraction only
- Integration with WritingContextAssembler — separate change after this one

## Decisions

### D1: Core service receives abstract data, not DB entities

**Decision:** `ProactiveContextService.suggest()` receives:
- `chapter_content: str` — the text to analyze
- `chapter_frontmatter: dict[str, Any] | None` — frontmatter with POV character, location
- `novel_id: UUID` — for embedding search scope
- Returns `list[Suggestion]` — domain objects

**Rationale:** Core layer has no DB access. The API service resolves chapter content and frontmatter before calling core. This keeps core testable and platform-independent.

### D2: Name extraction uses regex, not LLM

**Decision:** Extract entity names from chapter text using a simple pattern:
1. Get all known entity names for the novel from `KBQueryService`
2. Check which names appear in the chapter text (case-insensitive substring match)
3. Boost those entities' similarity scores

**Alternatives considered:**
- LLM-based entity extraction (via ExtractionAgent): More accurate but adds latency and LLM cost to every suggestion request. Overkill for name matching.
- Named Entity Recognition (NER) model: Additional infrastructure, deployment complexity.
- ✅ Simple string matching against known entity names: Fast, no LLM cost, sufficient for explicit references.

**Rationale:** Proactive suggestions must be fast (sub-second). String matching against known names is instant. Semantic similarity via embeddings handles the implicit references. No LLM needed for this.

### D3: Suggestion is a core dataclass

**Decision:**
```python
@dataclass(frozen=True, slots=True)
class Suggestion:
    entry_id: UUID
    entry_type: str
    name: str
    relevance_score: float  # 0-1, from hybrid scoring
    reason: str  # "mentioned in text" | "semantically similar" | "recently used"
    similarity: float  # raw embedding similarity
    usage_count: int
    last_referenced_at: datetime | None
```

**Rationale:** Core returns rich domain objects. API serializes to Pydantic response models.

### D4: ProactiveContextService uses EmbeddingStoreProtocol, not repository

**Decision:** The service receives `EmbeddingStoreProtocol` via DI for vector search. It does not know about SQLAlchemy models, the `embeddings` table, or pgvector internals.

**Rationale:** Follows RULE-07 (dependency direction) and RULE-03 (contract first). The `EmbeddingStoreProtocol.search()` already returns what we need.

### D5: KBSuggestService resolves deps then delegates

**Decision:** The API service:
1. Loads chapter content + frontmatter from `ChapterRepository`
2. Loads entity names for the novel from `KBRepository`
3. Creates `ProactiveContextService` (or uses cached instance)
4. Calls `service.suggest()` with the resolved data
5. Maps `Suggestion` → `KBSuggestionResponse` Pydantic model

**Rationale:** Thin wrapper pattern. All logic in core, API handles HTTP and data resolution.

### D6: Two source signals for this implementation

**Decision:** Initial implementation supports 2 signals:
1. **Embedding similarity**: `EmbeddingStoreProtocol.search()` → candidates
2. **Name matching**: String match against known entity names → boost

Graph traversal (relationships) and usage-event-based boosting are deferred to Phase 2.

**Rationale:** The two signals cover the most important use cases. Graph traversal adds complexity that's not needed for the MVP of this feature. Usage signals from `rank_candidates()` are already included in the scoring formula.

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| Name matching is case-insensitive substring → false positives for short names | Require minimum name length (3+ chars). Exact word boundary matching. |
| No graph traversal → misses related entities | Acceptable for initial implementation. Embeddings cover semantic relationships. |
| No theme detection → misses thematic suggestions | Acceptable. Embedding similarity covers thematic similarity implicitly. |
| Sub-second latency requirement | Embedding search is fast (HNSW index). Name matching is instant. No LLM calls in the pipeline. |
