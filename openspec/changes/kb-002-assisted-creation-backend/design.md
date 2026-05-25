## Context

We have:
- **KBAssistAgent** (`core/agents/kb_assist_agent.py`) — 4-mode agent (question, suggestion, draft, complete) with KBAgent toolset composition
- **KBAssistOutput** (`core/agents/kb_assist_types.py`) — structured output with mode discriminator
- **KB prompts** (`core/prompts/_bundled/kb/en/`) — interview, suggest, enhance, extract
- **ProactiveContextService** (`core/context/proactive_service.py`) — 3-stage suggestion pipeline
- **KBRepository + Service** (`api/kb/`) — full CRUD for KB entries
- **KBSuggestService** (`api/kb/suggest_service.py`) — proactive suggestions endpoint

What's missing: the orchestration layer that ties them together for the user-facing "assisted creation" flow. The agent exists, the context service exists, the templates exist — but there's no API to create a session, fill fields, get suggestions, and complete entries.

## Goals / Non-Goals

**Goals:**
- `KBCreationSession` with `KBCreationField` per template field — tracks session state
- `KBAssistService` that orchestrates KBAssistAgent + ProactiveContextService + templates
- REST endpoints for session lifecycle (create, get, answer, suggest, complete, abandon)
- SSE endpoint for streaming AI responses in interview mode
- Session storage in Redis with 30min TTL (ephemeral, not persistent)

**Non-Goals:**
- Frontend UI (separate change)
- Graph traversal suggestions (future phase)
- Deepen existing entries (starts with "create new" only)
- Auto-generate mode (starts with manual + suggest + interview only)

## Decisions

### D1: Redis for session storage, not PostgreSQL

**Decision:** Sessions are ephemeral creation flows. Redis with 30min TTL is the right storage. Final entries are saved via KB-001 CRUD.

**Rationale:** Sessions are temporary by nature. They expire if abandoned. No need for persistence, migrations, or complex queries. Redis TTL auto-cleans. If Redis is unavailable, sessions fail gracefully (user can try again).

### D2: REST for CRUD, SSE for streaming

**Decision:**
- REST: `POST /sessions`, `GET /sessions/{id}`, `PATCH /sessions/{id}/fields/{field}`, `POST /sessions/{id}/complete`, `DELETE /sessions/{id}`
- SSE: `GET /sessions/{id}/stream` — streaming AI responses for interview and suggest modes

**Rationale:** REST for data operations is simple and clear. SSE for streaming avoids WebSocket complexity. Turn-based Q&A with optional streaming output.

### D3: Field-level state tracking

**Decision:**
```python
class KBCreationField(BaseModel):
    field_key: str
    label: str
    field_type: str  # "text", "list", "boolean", "select"
    required: bool
    user_value: str | None = None
    ai_suggested_value: str | None = None
    ai_reasoning: str | None = None
    source: Literal["user", "ai", "world_derived", "merged"] = "user"
    final_value: str | None = None
```

**Rationale:** Each field tracks its own provenance (who suggested it and why). The `source` field enables transparent AI assistance. `final_value` is what gets saved — either user_value, ai_suggested_value, or a merged version.

### D4: KBAssistService is the orchestrator

**Decision:** `KBAssistService` coordinates:
1. Building `KBAssistDeps` from session state + world context (ProactiveContextService)
2. Running KBAssistAgent in the appropriate mode
3. Updating session fields from agent output
4. Returning structured responses to the API layer

**Rationale:** Keeps the API router thin (RULE-06). Service handles all orchestration logic between agent, context service, and session.

### D5: Template fields from KB schema registry

**Decision:** Field structure comes from `core/kb/schemas/registry.py` — the same templates used for manual entry creation.

**Rationale:** No duplication. When templates change, assisted creation automatically reflects the changes.

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| Redis dependency may not be set up in all environments | Check Redis availability at startup. Graceful error message if unavailable. |
| SSE streaming is more complex than REST | Keep SSE implementation simple — single event stream per session. |
| Agent mode detection (interview vs suggest) needs prompt engineering | Start with explicit mode from client, not auto-detection. |
| Session TTL means abandoned sessions auto-delete | Feature, not bug. 30min is generous. Users can restart. |
