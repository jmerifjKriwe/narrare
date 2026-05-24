# KB Assist Agent — Specification

## Requirements

### REQ-01: KBAssistAgent class
- **What**: `KBAssistAgent` extends `NarrareAgent[KBAssistDeps, KBAssistOutput]`
- **Why**: Provides the core LLM agent for assisted KB entity creation with multiple interaction modes
- **Details**:
  - Lives in `packages/core/narrare_core/agents/kb_assist_agent.py`
  - Uses `KBAssistOutput` as structured output type (see REQ-03)
  - Composes with `KBAgent` toolset via `Toolset` + `ToolSearch` capabilities
  - System prompt loaded from bundled prompts (see kb-prompts spec)
  - Output function handles mode-specific field population
  - Follows same pattern as `DraftAgent`: `__init__` accepts `model`, `kb_agent`, `system_prompt`

### REQ-02: KBAssistDeps
- **What**: Dependency injection class for KBAssistAgent
- **Details**:
  - `language: str = "en"` — output language
  - `genre: str = ""` — project genre for context
  - `entity_type: str = ""` — target entity type (character, location, etc.)
  - `template_structure: dict[str, Any] | None = None` — JSON schema of the entity type template
  - `existing_answers: dict[str, Any] | None = None` — previously collected field values
  - `world_context: str | None = None` — assembled world context (from KBCreationContextAssembly or KBAgent tools)

### REQ-03: KBAssistOutput structured output
- **What**: Pydantic model with mode discriminator and optional fields
- **Details**:
  - `mode: Literal["question", "suggestion", "draft", "complete"]`
  - Mode-specific optional fields:
    - `question` mode: `question: str`, `field_key: str`, `reasoning: str | None`
    - `suggestion` mode: `suggestion: str`, `field_key: str`, `reasoning: str | None`, `context_used: list[str] | None`
    - `draft` mode: `draft_entry: dict[str, Any]`, `progress: float` (0.0-1.0), `reasoning: str | None`
    - `complete` mode: `final_entry: dict[str, Any]`, `progress: float` (1.0), `reasoning: str | None`
  - `context_used: list[str] | None` — which KB entities were referenced
  - Lives in `packages/core/narrare_core/agents/kb_assist_types.py`

### REQ-04: Mode behavior
- **What**: Each mode has specific behavior and output shape
- **Details**:
  - **question mode**: Agent asks the user a single focused question about one template field. Returns `field_key` to identify which field. Used in interview interaction.
  - **suggestion mode**: Agent suggests a value for a specific field based on world context and existing answers. Returns `suggestion` text and `field_key`.
  - **draft mode**: Agent generates a partial or full draft of the entity entry, filling multiple template fields. Returns `draft_entry` dict and `progress` (0.0-1.0).
  - **complete mode**: Agent finalizes the entity entry. Returns `final_entry` dict and `progress` = 1.0.
  - The `mode` field is set by the LLM based on the user prompt context and system prompt instructions.

### REQ-05: KBAgent toolset composition
- **What**: KBAssistAgent composes with existing KBAgent tools
- **Details**:
  - When `kb_agent` is provided in `__init__`, adds `ToolSearch` + `Toolset(kb_agent.get_toolset())` capabilities
  - Agent can use `search_kb`, `get_entity`, `get_related_entities` to query world context
  - When `kb_agent` is None, agent operates without KB search (template-only mode)
  - Same pattern as `DraftAgent.__init__`

### REQ-06: Unit tests
- **What**: Test suite using `TestModel` and `FunctionModel`
- **Details**:
  - Test each mode produces correct output shape
  - Test KBAssistDeps injection
  - Test agent with and without KBAgent toolset
  - Test output function handles partial output (streaming)
  - Test model retry validation (if applicable)
  - Lives in `tests/unit/core/agents/test_kb_assist_agent.py`
