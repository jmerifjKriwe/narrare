## Why

KB-005 (Proactive KB Suggestions) and INFRA-009 (Proactive Context Loading) are merged into a single feature. INFRA-004 (Embedding Store) is complete — the embeddings table, hybrid scoring, and usage tracking all exist. Now we need the **core service** that orchestrates the 3-stage pipeline (content analysis → KB search → scoring/ranking) and the **API endpoint** that exposes it. This is the foundational infrastructure that KB-002 (Assisted Creation) will also consume for world context assembly.

## What Changes

- **New `ProactiveContextService`** in `core/context/proactive_service.py` — platform-independent service implementing the 3-stage suggestion pipeline using `EmbeddingStoreProtocol` for vector search and `rank_candidates()` for hybrid scoring. No DB/HTTP dependencies.
- **New `ProactiveContextProtocol`** in `core/context/contracts.py` — runtime-checkable protocol for DI.
- **New `KBSuggestService`** in `api/kb/suggest_service.py` — thin API-layer wrapper that resolves deps (novel_id → chapter content, entity metadata) and delegates to `ProactiveContextService`.
- **New `KBSuggestProtocol`** in `api/kb/contracts.py` — contract for the API service.
- **New API endpoint** `GET /api/v1/kb/suggestions/{chapter_id}` — returns ranked suggestions with relevance scores.
- **New Pydantic schemas** in `api/kb/schemas.py` — request/response models for suggestions.
- **New integration** with existing `ContextUsageService` — suggestions include usage signals from `context_usage_events`.

## Capabilities

### New Capabilities
- `proactive-context`: Core service for 3-stage KB suggestion pipeline (content analysis → embedding search → hybrid scoring). Platform-independent protocol + implementation. Consumed by API layer and future KB-002 context assembly.
- `kb-suggest-api`: API endpoint and service for KB suggestions. Thin wrapper over ProactiveContextService that handles HTTP concerns (request validation, response serialization, dependency injection).

### Modified Capabilities
- (none — existing modules are not modified, only consumed via DI)

## Impact

- **Core layer**: New `context/proactive_service.py` and `context/contracts.py`
- **API layer**: New `kb/suggest_service.py`, modified `kb/contracts.py`, `kb/schemas.py`, `kb/router.py`
- **Dependencies**: Consumes `EmbeddingStoreProtocol` (INFRA-004), `rank_candidates`/`ScoringConfig` (core/embeddings), `ContextUsageService` (api/kb)
- **No migrations needed** — all DB schema already exists from INFRA-004
