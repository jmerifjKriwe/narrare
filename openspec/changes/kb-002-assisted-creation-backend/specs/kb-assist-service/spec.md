# KB Assist Service — Specification

## Requirements

### REQ-01: KBAssistService
- **What**: Orchestration service in `api/kb/assist_service.py`
- **Details**:
  - Receives: session state (entity_type, existing field values, mode)
  - Builds `KBAssistDeps` from session + ProactiveContextService output
  - Runs `KBAssistAgent` in the requested mode
  - Maps `KBAssistOutput` back to session-friendly format
  - No Redis interaction — that's KBSessionService's job
- **RULE-06**: One responsibility: agent orchestration, not session management

### REQ-02: ProactiveContext integration
- **What**: Assist service uses ProactiveContextService for world context
- **Details**:
  - Calls `ProactiveContextProtocol.suggest()` to get relevant KB entries
  - Formats suggestions into `world_context` string for `KBAssistDeps`
  - Falls back to empty context if ProactiveContextService unavailable

### REQ-03: Template field extraction
- **What**: Build field list from KB schema registry
- **Details**:
  - `get_template_fields(entity_type: str) -> list[KBCreationField]`
  - Reads from `core/kb/schemas/registry.py` — get_schema(entity_type)
  - Maps Pydantic model fields to `KBCreationField` objects
  - Handles nested field groups (appearance, personality, background for characters)

### REQ-04: Mode routing
- **What**: Map requested mode to KBAssistAgent invocation
- **Details**:
  - `interview` mode → Build prompt with template structure, call agent, expect `question` output
  - `suggest` mode → Build prompt with target field, call agent, expect `suggestion` output
  - `enhance` mode → Build prompt with all current values, call agent, expect `draft`/`complete` output
  - `auto-generate` mode → Build prompt with world context, call agent, expect `complete` output

### REQ-05: KBAssistProtocol
- **What**: Contract for the assist service
- **Details**:
  ```python
  @runtime_checkable
  class KBAssistProtocol(Protocol):
      async def get_interview_question(
          self, *, novel_id: UUID, entity_type: str,
          existing_fields: dict[str, str],
      ) -> KBAssistQuestionResponse: ...
      async def get_suggestion(
          self, *, novel_id: UUID, entity_type: str,
          field_key: str, existing_fields: dict[str, str],
      ) -> KBAssistSuggestionResponse: ...
      async def get_enhancement(
          self, *, novel_id: UUID, entity_type: str,
          existing_fields: dict[str, str],
      ) -> KBAssistEnhancementResponse: ...
  ```

### REQ-06: Response schemas
- **What**: Pydantic response models in `api/kb/schemas.py`
- **Details**:
  - `KBAssistQuestionResponse`: question text, field_key, reasoning
  - `KBAssistSuggestionResponse`: suggestion text, field_key, reasoning, context_used
  - `KBAssistEnhancementResponse`: draft_entry (dict), progress (0-1), reasoning

### REQ-07: Unit tests
- **What**: Test suite for KBAssistService with fakes
- **Details**:
  - Fake KBAssistAgent that returns predefined KBAssistOutput
  - Fake ProactiveContextProtocol that returns predefined suggestions
  - Test mode routing (interview → question, suggest → suggestion, enhance → draft)
  - Test template field extraction for each entity type
  - Test context formatting from ProactiveContextService output
  - File: `tests/unit/api/kb/test_assist_service.py`
