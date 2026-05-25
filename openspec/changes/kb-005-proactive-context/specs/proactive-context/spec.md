# Proactive Context — Specification

## Requirements

### REQ-01: Suggestion dataclass
- **What**: `Suggestion` dataclass in `core/context/suggestion.py`
- **Details**:
  - `entry_id: UUID` — the KB entry ID
  - `entry_type: str` — entity type (character, location, etc.)
  - `name: str` — entity display name
  - `relevance_score: float` — 0.0-1.0, final hybrid score
  - `reason: Literal["mentioned_in_text", "semantically_similar", "recently_used"]` — why it was suggested
  - `similarity: float` — raw embedding cosine similarity
  - `usage_count: int` — how many times this entry has been accepted
  - `last_referenced_at: datetime | None` — when last accepted
  - Frozen, slots=True (follow pattern from `SearchResult` in embeddings/store.py)

### REQ-02: ProactiveContextProtocol
- **What**: Runtime-checkable protocol in `core/context/contracts.py`
- **Details**:
  ```python
  @runtime_checkable
  class ProactiveContextProtocol(Protocol):
      async def suggest(
          self,
          chapter_content: str,
          *,
          novel_id: UUID,
          chapter_frontmatter: dict[str, Any] | None = None,
          entity_names: list[str] | None = None,
          max_results: int = 20,
      ) -> list[Suggestion]: ...
  ```

### REQ-03: ProactiveContextService
- **What**: Implementation of `ProactiveContextProtocol` in `core/context/proactive_service.py`
- **Details**:
  - Constructor receives `EmbeddingStoreProtocol` via DI
  - `suggest()` method implements 3-stage pipeline:
    1. **Stage 1 — Name matching**: Check which `entity_names` appear in `chapter_content` (case-insensitive, word boundary matching, min 3 chars)
    2. **Stage 2 — Embedding search**: Call `EmbeddingStoreProtocol.search(query=chapter_content, source_type="kb_entry", novel_id=novel_id, limit=max_results)`
    3. **Stage 3 — Scoring**: Build `ScoredCandidate` list from embedding results, apply name-match boost (+0.2 to similarity for matched names), call `rank_candidates()` to get final ordering
  - Map results to `Suggestion` objects with appropriate `reason` field
  - Deduplicate by entry_id (name match + embedding match for same entry)
  - Respect `max_results` limit (default 20, max 100)

### REQ-04: Name matching algorithm
- **What**: Extract which entity names appear in chapter text
- **Details**:
  - Input: `chapter_content: str`, `entity_names: list[str]`
  - Case-insensitive matching
  - Word boundary matching (`\b{name}\b` regex pattern) — avoid partial matches
  - Minimum name length 3 characters (filter out very short names like "AI")
  - Return: `set[str]` of matched names
  - Lives as a private method `_match_entity_names()` in ProactiveContextService
  - Or as a standalone function `match_entity_names()` if it helps testability

### REQ-05: Score boosting for name matches
- **What**: Entities whose names appear in the text get a relevance boost
- **Details**:
  - If entity name is found in chapter text: boost similarity by +0.2 (capped at 1.0)
  - This is applied BEFORE `rank_candidates()` scoring
  - The `reason` field is set to `"mentioned_in_text"` for boosted entries
  - Entries not found in text but found via embedding search get `"semantically_similar"`

### REQ-06: Unit tests
- **What**: Test suite for ProactiveContextService using fake EmbeddingStoreProtocol
- **Details**:
  - Fake `EmbeddingStoreProtocol` that returns predefined results
  - Test name matching (exact, case-insensitive, word boundary, min length)
  - Test embedding search integration (service calls search with correct params)
  - Test score boosting (mentioned entities rank higher)
  - Test deduplication (same entry from name match + embedding)
  - Test max_results enforcement
  - Test empty inputs (empty content, no entity names, no embeddings)
  - File: `tests/unit/core/context/test_proactive_service.py`

### REQ-07: context module __init__.py
- **What**: Update `core/context/__init__.py` with proper exports
- **Details**: Export `ProactiveContextProtocol`, `ProactiveContextService`, `Suggestion`
