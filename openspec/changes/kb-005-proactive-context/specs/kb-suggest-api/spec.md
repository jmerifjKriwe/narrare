# KB Suggest API — Specification

## Requirements

### REQ-01: KBSuggestProtocol
- **What**: Contract in `api/kb/contracts.py`
- **Details**:
  ```python
  @runtime_checkable
  class KBSuggestProtocol(Protocol):
      async def get_suggestions(
          self,
          chapter_id: UUID,
          *,
          novel_id: UUID,
          max_results: int = 20,
      ) -> list[KBSuggestionResponse]: ...
  ```

### REQ-02: KBSuggestService
- **What**: Thin API-layer service in `api/kb/suggest_service.py`
- **Details**:
  - Constructor receives:
    - `proactive_context: ProactiveContextProtocol` — core service
    - `chapter_repo: ChapterRepositoryProtocol` — to load chapter content
    - `kb_repo: KBRepositoryProtocol` — to load entity names for the novel
  - `get_suggestions()` method:
    1. Load chapter content + frontmatter from `chapter_repo`
    2. Load all entity names for the novel from `kb_repo`
    3. Delegate to `proactive_context.suggest()` with resolved data
    4. Map `Suggestion` → `KBSuggestionResponse`
    5. Return list
  - If chapter not found: raise `NotFoundError`
  - If no entity names: still run embedding search (empty name list)

### REQ-03: KBSuggestionResponse schema
- **What**: Pydantic response model in `api/kb/schemas.py`
- **Details**:
  ```python
  class KBSuggestionResponse(BaseModel):
      entry_id: UUID
      entry_type: str
      name: str
      relevance_score: float
      reason: str
      similarity: float
      usage_count: int
      last_referenced_at: datetime | None
  ```

### REQ-04: API endpoint
- **What**: `GET /api/v1/kb/suggestions/{chapter_id}` in `api/kb/router.py`
- **Details**:
  - Query parameters: `max_results: int = Query(default=20, ge=1, le=100)`
  - Requires novel context (from auth/session)
  - Returns `list[KBSuggestionResponse]`
  - Delegates immediately to `KBSuggestService`
  - Follows RULE-06: no business logic in router

### REQ-05: Dependency injection
- **What**: Wire `KBSuggestService` in `api/kb/dependencies.py`
- **Details**:
  - Factory function `get_kb_suggest_service()` that:
    - Creates `ProactiveContextService` with injected `EmbeddingStoreProtocol`
    - Creates `KBSuggestService` with injected services
  - Register in FastAPI app

### REQ-06: Integration tests
- **What**: Test suite for KBSuggestService with fakes
- **Details**:
  - Fake `ProactiveContextProtocol` that returns predefined suggestions
  - Fake chapter repo and KB repo
  - Test successful suggestion flow
  - Test chapter not found → raises NotFoundError
  - Test empty entity names → still returns embedding results
  - Test max_results parameter is passed through
  - File: `tests/unit/api/kb/test_suggest_service.py`
