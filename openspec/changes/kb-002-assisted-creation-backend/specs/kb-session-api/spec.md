# KB Session API — Specification

## Requirements

### REQ-01: Session model
- **What**: `KBCreationSession` and `KBCreationField` Pydantic models in `api/kb/session_models.py`
- **Details**:
  ```python
  class KBCreationField(BaseModel):
      field_key: str
      label: str
      field_type: Literal["text", "list", "boolean", "select"]
      required: bool = False
      options: list[str] | None = None  # for select type
      user_value: str | None = None
      ai_suggested_value: str | None = None
      ai_reasoning: str | None = None
      source: Literal["user", "ai", "world_derived", "merged"] = "user"
      final_value: str | None = None

  class KBCreationSession(BaseModel):
      id: UUID
      novel_id: UUID
      user_id: UUID
      entity_type: str
      status: Literal["active", "review", "complete", "abandoned"] = "active"
      fields: list[KBCreationField]
      context_entries: list[str] = []  # entry names used as context
      created_at: datetime
      updated_at: datetime
  ```

### REQ-02: Session storage
- **What**: Redis-backed session storage with TTL
- **Details**:
  - `KBCreationSessionStore` in `api/kb/session_store.py`
  - Uses Redis for ephemeral storage with 30min TTL
  - Key pattern: `kb:session:{session_id}`
  - Methods: create, get, update, delete
  - If Redis unavailable: raise ServiceUnavailableError with clear message
  - Auto-extends TTL on each update

### REQ-03: KBSessionService
- **What**: Service in `api/kb/session_service.py`
- **Details**:
  - `create_session(novel_id, user_id, entity_type)` → creates session with template fields
  - `get_session(session_id)` → retrieves session
  - `answer_field(session_id, field_key, value)` → updates field with user value
  - `request_suggestion(session_id, field_key)` → calls KBAssistService, returns suggestion
  - `request_interview_question(session_id)` → calls KBAssistService, returns next question
  - `request_enhancement(session_id)` → calls KBAssistService, returns enhanced draft
  - `complete_session(session_id)` → marks complete, triggers save via KB-001
  - `abandon_session(session_id)` → marks abandoned
  - Validates session status transitions: active → review → complete/abandoned

### REQ-04: REST endpoints
- **What**: Endpoints in `api/kb/router_sessions.py`
- **Details**:
  - `POST /novels/{novel_id}/kb/sessions` — create session (body: entity_type)
  - `GET /novels/{novel_id}/kb/sessions/{session_id}` — get session
  - `PATCH /novels/{novel_id}/kb/sessions/{session_id}/fields/{field_key}` — answer field
  - `POST /novels/{novel_id}/kb/sessions/{session_id}/suggest/{field_key}` — request suggestion
  - `POST /novels/{novel_id}/kb/sessions/{session_id}/interview` — get next interview question
  - `POST /novels/{novel_id}/kb/sessions/{session_id}/enhance` — request enhancement
  - `POST /novels/{novel_id}/kb/sessions/{session_id}/complete` — complete and save
  - `DELETE /novels/{novel_id}/kb/sessions/{session_id}` — abandon session
  - All endpoints under RULE-06 (thin router, immediate delegation to service)

### REQ-05: SSE endpoint
- **What**: Streaming endpoint for interview and enhance modes
- **Details**:
  - `GET /novels/{novel_id}/kb/sessions/{session_id}/stream` — SSE endpoint
  - Streams KBAssistAgent output as events
  - Event types: `question`, `suggestion`, `draft_update`, `complete`, `error`
  - Uses FastAPI StreamingResponse with `text/event-stream` media type
  - Falls back to REST response if streaming not requested

### REQ-06: Dependency injection
- **What**: Wire session service dependencies in `api/kb/dependencies.py`
- **Details**:
  - `get_kb_session_service()` — creates KBSessionService with Redis + KBAssistService + KBRepository
  - `get_kb_assist_service()` — creates KBAssistService with KBAssistAgent + ProactiveContextService
  - Redis client from existing app dependency

### REQ-07: Unit tests
- **What**: Test suite for session service and models
- **Details**:
  - Session model creation and validation
  - Field value update with source tracking
  - Session status transitions
  - Session store with fake Redis
  - KBSessionService orchestration
  - Router endpoint tests with fake service
  - Files: `tests/unit/api/kb/test_session_models.py`, `tests/unit/api/kb/test_session_service.py`
