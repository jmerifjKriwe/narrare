## Phase 1: Session Model & Storage

### 1.1 Session models
- Create `apps/api/narrare/kb/session_models.py`
- Define `KBCreationField` and `KBCreationSession` Pydantic models
- Template field extraction from KB schema registry

### 1.2 Session store
- Create `apps/api/narrare/kb/session_store.py`
- Redis-backed ephemeral storage with 30min TTL
- Methods: create, get, update, delete
- Graceful error if Redis unavailable

### 1.3 Session model tests
- Create `tests/unit/api/kb/test_session_models.py`
- Test model creation, validation, field updates, status transitions

## Phase 2: Assist Service

### 2.1 KBAssistProtocol and schemas
- Add `KBAssistProtocol` to `apps/api/narrare/kb/suggest_contracts.py` or new file
- Add response schemas to `apps/api/narrare/kb/schemas.py`: KBAssistQuestionResponse, KBAssistSuggestionResponse, KBAssistEnhancementResponse

### 2.2 KBAssistService
- Create `apps/api/narrare/kb/assist_service.py`
- Orchestrates KBAssistAgent + ProactiveContextService + KB templates
- Maps KBAssistOutput to response schemas
- Mode routing: interview → question, suggest → suggestion, enhance → draft

### 2.3 Template field extraction
- Implement `get_template_fields(entity_type)` using KB schema registry
- Map Pydantic model fields to KBCreationField objects
- Handle nested field groups

### 2.4 Assist service tests
- Create `tests/unit/api/kb/test_assist_service.py`
- Fake KBAssistAgent, fake ProactiveContextService
- Test mode routing, context formatting, template extraction

## Phase 3: Session Service & Endpoints

### 3.1 KBSessionService
- Create `apps/api/narrare/kb/session_service.py`
- Session lifecycle: create, get, answer_field, request_suggestion, request_interview_question, request_enhancement, complete, abandon
- Delegates to KBAssistService for AI operations
- Delegates to KBCreationSessionStore for storage

### 3.2 REST endpoints
- Create `apps/api/narrare/kb/router_sessions.py`
- Register in `apps/api/narrare/_app/main.py`
- All endpoints under `/novels/{novel_id}/kb/sessions/`

### 3.3 SSE endpoint
- Add `GET /novels/{novel_id}/kb/sessions/{session_id}/stream`
- StreamingResponse with text/event-stream
- Event types: question, suggestion, draft_update, complete, error

### 3.4 Dependency injection
- Add `get_kb_session_service()` and `get_kb_assist_service()` to `apps/api/narrare/kb/dependencies.py`

### 3.5 Session service and router tests
- Create `tests/unit/api/kb/test_session_service.py`
- Create `tests/unit/api/kb/test_router_sessions.py` (if router is substantial enough)

## Phase 4: Validation

### 4.1 Architecture check
- Run `scripts/check_architecture.py` — must pass clean

### 4.2 Test suite
- All new + existing tests pass

### 4.3 Update docs
- Update CURRENT_STATE.md with KB-002 backend status
- Update KB-002 spec status
