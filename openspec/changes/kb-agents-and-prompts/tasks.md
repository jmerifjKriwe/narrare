## Phase 1: Core Types & Prompts

### 1.1 KBAssistOutput types
- Create `packages/core/narrare_core/agents/kb_assist_types.py`
- Define `KBAssistOutput` with `mode` discriminator and optional fields per mode
- Follow pattern from `summary_types.py`, `review_types.py`

### 1.2 ExtractionOutput types
- Create `packages/core/narrare_core/agents/extraction_types.py`
- Define `ExtractionOutput`, `ExtractionItem` with item_type discriminator
- Include confidence scoring, source_text quoting, proposed_content

### 1.3 KB prompts — English
- Create `packages/core/narrare_core/prompts/_bundled/kb/en/interview/system.md`
- Create `packages/core/narrare_core/prompts/_bundled/kb/en/suggest/system.md`
- Create `packages/core/narrare_core/prompts/_bundled/kb/en/enhance/system.md`
- Create `packages/core/narrare_core/prompts/_bundled/kb/en/extract/system.md`
- Each includes: CoT directives, negative examples, output format, variable placeholders

### 1.4 Prompt integration
- Register KB prompt categories in PromptComposer or ensure PromptLoader can find them
- Verify variable substitution works for `{{template_structure}}`, `{{existing_answers}}`, etc.

## Phase 2: Agents

### 2.1 KBAssistAgent
- Create `packages/core/narrare_core/agents/kb_assist_agent.py`
- Implement `KBAssistDeps` and `KBAssistAgent` extending `NarrareAgent[KBAssistDeps, KBAssistOutput]`
- Output function handles mode-specific field population
- KBAgent toolset composition (ToolSearch + Toolset)
- Update `agents/__init__.py` exports

### 2.2 ExtractionAgent
- Create `packages/core/narrare_core/agents/extraction_agent.py`
- Implement `ExtractionDeps` and `ExtractionAgent` extending `NarrareAgent[ExtractionDeps, ExtractionOutput]`
- KBAgent toolset composition
- Update `agents/__init__.py` exports

## Phase 3: Tests

### 3.1 KBAssistOutput model tests
- Test `KBAssistOutput` validation for each mode
- Test optional fields populated correctly per mode
- File: `tests/unit/core/agents/test_kb_assist_types.py`

### 3.2 ExtractionOutput model tests
- Test `ExtractionOutput` and `ExtractionItem` validation
- Test each item_type
- Test confidence boundaries
- File: `tests/unit/core/agents/test_extraction_types.py`

### 3.3 KBAssistAgent tests
- Test agent instantiation with/without KBAgent
- Test output function handles streaming (partial output)
- Test mode-specific output using TestModel/FunctionModel
- File: `tests/unit/core/agents/test_kb_assist_agent.py`

### 3.4 ExtractionAgent tests
- Test agent instantiation with/without KBAgent
- Test empty results, single entity, multiple items
- Test confidence filtering
- File: `tests/unit/core/agents/test_extraction_agent.py`

### 3.5 Prompt tests
- Test each prompt file loads
- Test variable substitution
- File: `tests/unit/core/prompts/test_kb_prompts.py`

## Phase 4: Validation

### 4.1 Architecture check
- Run `scripts/check_architecture.py` — must pass clean
- Verify RULE-04 file size limits
- Verify RULE-06 one responsibility per file

### 4.2 Test suite
- Run full test suite — all new + existing tests pass
- Coverage target: ≥90% for new files

### 4.3 Update docs
- Update `docs/_shared/CURRENT_STATE.md` with KB agents status
- Update `docs/features/kb/KB-002-kb-session.md` with agent architecture decisions
- Update `docs/features/kb/KB-007-extraction.md` with agent architecture decisions
