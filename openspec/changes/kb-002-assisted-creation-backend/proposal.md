## Why

KB-002 (Assisted KB Creation) needs backend infrastructure: session model for template-guided creation flows, REST endpoints for session CRUD, SSE endpoint for streaming AI responses, and service layer connecting KBAssistAgent + ProactiveContextService. The KBAssistAgent (4-mode) and ProactiveContextService are already built. This change connects them to the API layer.

## What Changes

- **New `KBCreationSession` model** — ephemeral session tracking entity type, field values, AI suggestions, status (active/review/complete/abandoned)
- **New `KBAssistService`** in `api/kb/assist_service.py` — orchestrates KBAssistAgent + ProactiveContextService + KBRepository for assisted creation
- **New `KBSessionService`** in `api/kb/session_service.py` — manages session lifecycle (create, update field, accept suggestion, complete, abandon)
- **New `KBCreationField`** model — tracks per-field state (question, user_value, ai_suggested_value, source, final_value)
- **New REST endpoints** — session CRUD: create, get, answer field, accept suggestion, complete, abandon
- **New SSE endpoint** — streaming AI responses during interview/suggest modes
- **New contracts, schemas, dependencies** in existing kb/ module files

## Capabilities

### New Capabilities
- `kb-assist-service`: Service layer orchestrating KBAssistAgent + ProactiveContextService + KB templates for assisted entity creation. Handles intent detection (manual → suggest → interview → auto-generate) and delegates to the appropriate agent mode.
- `kb-session-api`: REST + SSE endpoints for KB creation sessions. Create session, fill fields, get AI suggestions, stream interview questions, complete session.

### Modified Capabilities
- (none — existing modules are consumed, not modified)

## Impact

- **API layer**: New `kb/assist_service.py`, `kb/session_service.py`, `kb/router_sessions.py`, `kb/session_models.py`
- **Dependencies**: Uses KBAssistAgent (core), ProactiveContextService (core), KBRepository (api), EmbeddingService (api)
- **No new migrations** — sessions are ephemeral (Redis-backed with TTL), not persisted in PostgreSQL
