## Phase 1: Core Layer — ProactiveContextService

### 1.1 Suggestion dataclass
- Create `packages/core/narrare_core/context/suggestion.py`
- Define `Suggestion` dataclass (frozen, slots=True) with all fields from REQ-01

### 1.2 ProactiveContextProtocol
- Create `packages/core/narrare_core/context/contracts.py`
- Define `ProactiveContextProtocol` (runtime_checkable) with `suggest()` method

### 1.3 Name matching utility
- Implement `match_entity_names()` in `packages/core/narrare_core/context/name_matching.py`
- Case-insensitive, word boundary regex, min 3 chars
- Standalone function for testability

### 1.4 ProactiveContextService
- Create `packages/core/narrare_core/context/proactive_service.py`
- Implements `ProactiveContextProtocol`
- 3-stage pipeline: name matching → embedding search → scoring
- Uses `EmbeddingStoreProtocol` via DI
- Score boosting for name-matched entities
- Deduplication by entry_id

### 1.5 Context module exports
- Update `packages/core/narrare_core/context/__init__.py`

### 1.6 Core unit tests
- Create `tests/unit/core/context/test_suggestion.py` — Suggestion dataclass tests
- Create `tests/unit/core/context/test_name_matching.py` — name matching tests
- Create `tests/unit/core/context/test_proactive_service.py` — full pipeline tests with fake EmbeddingStoreProtocol

## Phase 2: API Layer — KBSuggestService

### 2.1 KBSuggestProtocol
- Add `KBSuggestProtocol` to `apps/api/narrare/kb/contracts.py`

### 2.2 KBSuggestionResponse schema
- Add `KBSuggestionResponse` to `apps/api/narrare/kb/schemas.py`

### 2.3 KBSuggestService
- Create `apps/api/narrare/kb/suggest_service.py`
- Thin wrapper: load chapter → load entity names → delegate to ProactiveContextService → map response

### 2.4 API endpoint
- Add `GET /api/v1/kb/suggestions/{chapter_id}` to `apps/api/narrare/kb/router.py`

### 2.5 Dependency injection
- Add `get_kb_suggest_service()` to `apps/api/narrare/kb/dependencies.py`
- Wire ProactiveContextService with EmbeddingStoreProtocol

### 2.6 API unit tests
- Create `tests/unit/api/kb/test_suggest_service.py`
- Fake ProactiveContextProtocol, fake repos

## Phase 3: Validation

### 3.1 Architecture check
- Run `scripts/check_architecture.py` — must pass clean

### 3.2 Full test suite
- All new + existing tests pass

### 3.3 Update docs
- Update `docs/_shared/CURRENT_STATE.md` with KB-005 status
- Update `docs/features/kb/KB-005-kb-suggest.md` status → `in progress` / `implemented`
- Update `docs/features/infra/INFRA-009-proactive-context.md` status
