# KB Prompts — Specification

## Requirements

### REQ-01: Prompt directory structure
- **What**: Bundled prompt files for KB agent operations
- **Details**:
  - Directory: `packages/core/narrare_core/prompts/_bundled/kb/`
  - Structure:
    ```
    kb/
    ├── en/
    │   ├── interview/system.md
    │   ├── suggest/system.md
    │   ├── enhance/system.md
    │   └── extract/system.md
    ├── de/
    │   └── (Phase 2 — after en is validated)
    └── fr/
        └── (Phase 2 — after en is validated)
    ```
  - Only English prompts in this change. German and French follow after validation.

### REQ-02: Interview prompt (kb/interview)
- **What**: System prompt for KBAssistAgent in interview mode
- **Details**:
  - Instructs the agent to ask one focused question at a time about a specific template field
  - Uses world context (provided via deps) to make questions relevant
  - Includes CoT reasoning directives: "Think about which field needs the most information next"
  - Negative examples: "Do NOT ask about fields the user has already answered"
  - Structured output enforcement: "Always set mode='question', field_key to the target field, and question to your question"
  - Variables: `{{template_structure}}`, `{{existing_answers}}`, `{{world_context}}`

### REQ-03: Suggest prompt (kb/suggest)
- **What**: System prompt for KBAssistAgent in suggestion mode
- **Details**:
  - Instructs the agent to suggest a value for a specific field based on context
  - References world context to make informed suggestions
  - Includes CoT reasoning: "Explain why this suggestion fits the story world"
  - Negative examples: "Do NOT suggest values that contradict existing KB data"
  - Structured output enforcement: "Always set mode='suggestion', field_key, and suggestion"
  - Variables: same as interview plus `{{target_field}}`, `{{target_field_description}}`

### REQ-04: Enhance prompt (kb/enhance)
- **What**: System prompt for KBAssistAgent in enhance/draft mode
- **Details**:
  - Instructs the agent to generate or expand entity entries using template structure
  - Uses world context for consistency
  - Includes CoT reasoning: "Consider which fields are most important for this entity type"
  - Negative examples: "Do NOT leave required template fields empty"
  - Structured output enforcement: "Always set mode='draft' or 'complete', draft_entry/final_entry as a dict matching the template structure"
  - Variables: `{{template_structure}}`, `{{existing_answers}}`, `{{world_context}}`, `{{entity_type}}`

### REQ-05: Extract prompt (kb/extract)
- **What**: System prompt for ExtractionAgent
- **Details**:
  - Instructs the agent to extract entities, relationships, and conflicts from chapter text
  - References existing entity names for dedup detection
  - Includes CoT reasoning: "For each entity, consider whether it's new or an update to an existing one"
  - Negative examples: "Do NOT extract entities that are only mentioned in passing with no meaningful information"
  - Confidence calibration instructions: "Score ≥0.7 for explicit facts, 0.4-0.7 for implied facts, <0.4 for speculation — do not return items <0.3"
  - Structured output enforcement: "Return an ExtractionOutput with a list of ExtractionItem entries"
  - Variables: `{{chapter_title}}`, `{{existing_entity_names}}`, `{{genre}}`

### REQ-06: Prompt loading integration
- **What**: Integration with existing PromptComposer
- **Details**:
  - Register new prompt categories in `PromptComposer` intent mapping:
    - `kb_interview` → category="kb", mode="interview"
    - `kb_suggest` → category="kb", mode="suggest"
    - `kb_enhance` → category="kb", mode="enhance"
    - `kb_extract` → category="kb", mode="extract"
  - Or: agents load prompts directly via `PromptLoader` (same as existing agents)
  - Follow whichever pattern is established by `ChapterSummaryAgent` / `DraftAgent`

### REQ-07: Unit tests for prompts
- **What**: Test that prompts load and contain expected variables
- **Details**:
  - Test each prompt file loads without error
  - Test variable substitution produces valid prompts
  - Test prompts contain key instructions (CoT, negative examples, output format)
  - Lives in `tests/unit/core/prompts/test_kb_prompts.py`
