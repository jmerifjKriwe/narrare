# Extraction Agent — Specification

## Requirements

### REQ-01: ExtractionAgent class
- **What**: `ExtractionAgent` extends `NarrareAgent[ExtractionDeps, ExtractionOutput]`
- **Why**: Extracts entities, facts, and relationships from chapter text with structured output
- **Details**:
  - Lives in `packages/core/narrare_core/agents/extraction_agent.py`
  - Uses `ExtractionOutput` as structured output type (see REQ-03)
  - Composes with `KBAgent` toolset via `Toolset` + `ToolSearch` capabilities (for checking existing entities)
  - System prompt loaded from bundled prompts (see kb-prompts spec)
  - Follows same pattern as `ChapterSummaryAgent`: `__init__` accepts `model`, `kb_agent`, `system_prompt`

### REQ-02: ExtractionDeps
- **What**: Dependency injection class for ExtractionAgent
- **Details**:
  - `language: str = "en"` — output language
  - `genre: str = ""` — project genre
  - `novel_id: str = ""` — novel identifier for context
  - `existing_entity_names: list[str] = []` — names of known entities for dedup detection
  - `chapter_title: str = ""` — title of the chapter being analyzed

### REQ-03: ExtractionOutput structured output
- **What**: Pydantic model with list of extraction items
- **Details**:
  - `ExtractionOutput`:
    - `results: list[ExtractionItem]`
    - `analysis_notes: str = ""` — agent's overall observations about the text
  - `ExtractionItem`:
    - `item_type: Literal["new_entity", "update_entity", "relationship", "conflict"]`
    - `entity_type: str | None = None` — character, location, faction, etc.
    - `name: str` — entity or relationship name
    - `confidence: float` — 0.0 to 1.0 confidence score
    - `source_text: str` — exact quote from the chapter text
    - `proposed_content: dict[str, Any] | None = None` — suggested metadata fields
    - `target_entity_id: str | None = None` — for updates: which existing entity
    - `conflict_description: str | None = None` — for conflicts: what contradicts
    - `relationship_type: str | None = None` — for relationships: ally, member_of, etc.
    - `related_entity_name: str | None = None` — for relationships: the other entity
  - Lives in `packages/core/narrare_core/agents/extraction_types.py`

### REQ-04: Extraction behavior
- **What**: How the agent processes chapter text
- **Details**:
  - Agent receives chapter text as the prompt
  - Produces a list of `ExtractionItem` entries
  - **new_entity**: A previously unknown entity mentioned in the text. Includes `entity_type` and `proposed_content`.
  - **update_entity**: New information about an existing entity. References `target_entity_id` (matched by name from `existing_entity_names`).
  - **relationship**: A relationship between entities. Includes `relationship_type` and `related_entity_name`.
  - **conflict**: A contradiction between text and existing KB data. Includes `conflict_description`.
  - Confidence scoring: 0.0-1.0, where ≥0.7 is high confidence, 0.4-0.7 is medium, <0.4 is low.
  - Items with confidence <0.3 should not be returned (filter at prompt level).

### REQ-05: KBAgent toolset composition
- **What**: ExtractionAgent composes with KBAgent tools for entity lookup
- **Details**:
  - When `kb_agent` is provided, agent can use `get_entity` and `search_kb` to verify existing entities
  - This helps distinguish new_entity from update_entity cases
  - When `kb_agent` is None, agent relies on `existing_entity_names` list for dedup
  - Same composition pattern as `DraftAgent` and `KBAssistAgent`

### REQ-06: Unit tests
- **What**: Test suite using `TestModel` and `FunctionModel`
- **Details**:
  - Test ExtractionOutput model validation
  - Test ExtractionItem with each item_type
  - Test confidence score boundaries
  - Test agent with and without KBAgent toolset
  - Test empty results (chapter with no entities)
  - Lives in `tests/unit/core/agents/test_extraction_agent.py`
