## Context

Narrare's KB features need two specialized LLM agents. The existing `KBAgent` (in `core/agents/kb_agent.py`) is a tool-provider that exposes `search_kb`, `get_entity`, and `get_related_entities` via a `FunctionToolset` for composition into other agents. It has `output_type=None` and never runs independently — it exists solely to provide KB search capabilities to agents like DraftAgent.

The two new agents follow the established NarrareAgent pattern (ADR-015) with pydantic-ai: each has a `Deps` class for injected dependencies, a structured output type, and system prompts from the bundled prompt system. Both compose with KBAgent via Toolset capability injection.

Existing agent patterns to follow:
- `ChapterSummaryAgent` — simple agent with structured `SummaryOutput`
- `DraftAgent` — agent with KBAgent toolset composition
- `ReviewAgent` — agent with rich deps and structured output
- `WritingGraph` — multi-step orchestration of multiple agents

## Goals / Non-Goals

**Goals:**
- `KBAssistAgent` that supports 4 interaction modes (question, suggestion, draft, complete) via a single Union output type
- `ExtractionAgent` that reads chapter text and produces structured `ExtractionResult[]` with confidence scoring
- Bundled prompts for all 4 KB assist modes + extraction in en/de/fr
- `KBCreationContextAssembly` that assembles template structure + world context + previous answers
- Unit tests for both agents using `TestModel` / `FunctionModel` (no real LLM calls)
- Promptfoo eval baselines for KB prompts

**Non-Goals:**
- API endpoints or frontend for KB-002/KB-007 (those are separate changes)
- Session management or REST/SSE endpoints (separate change)
- Embedding-based dedup in ExtractionAgent (soft dependency — start with name-based)
- ProactiveContextService integration (not yet built — KBCreationContextAssembly will use KBAgent tools as fallback)

## Decisions

### D1: Two separate agents, not one

**Decision:** `KBAssistAgent` and `ExtractionAgent` are separate NarrareAgent subclasses.

**Rationale:** Different input/output types, different system prompts, different tools. KBAssistAgent works with templates and Q&A; ExtractionAgent works with chapter text and structured extraction. Merging them would require a complex Union output that's harder to validate and test.

### D2: KBAssistAgent uses Union output type

**Decision:** Single output model with discriminator field:

```python
class KBAssistOutput(BaseModel):
    mode: Literal["question", "suggestion", "draft", "complete"]
    # Mode-specific fields (all optional, validated by mode)
    question: str | None = None
    field_key: str | None = None
    suggestion: str | None = None
    reasoning: str | None = None
    context_used: list[str] | None = None
    draft_entry: dict[str, Any] | None = None
    final_entry: dict[str, Any] | None = None
    progress: float | None = None  # 0.0-1.0
```

**Alternatives considered:**
- Separate output types per mode with `Union[QuestionOutput, SuggestionOutput, ...]`: pydantic-ai doesn't support discriminated unions well as `output_type`. Single model with optional fields is more practical.
- Always return full draft_entry: Wasteful for single-field suggestions.

**Rationale:** Single model simplifies pydantic-ai integration. The `mode` field tells the caller what kind of response it is. Optional fields are populated based on mode.

### D3: ExtractionAgent produces structured list output

**Decision:**

```python
class ExtractionOutput(BaseModel):
    results: list[ExtractionItem]

class ExtractionItem(BaseModel):
    item_type: Literal["new_entity", "update_entity", "relationship", "conflict"]
    entity_type: str | None = None  # character, location, etc.
    name: str
    confidence: float  # 0.0-1.0
    source_text: str  # quote from chapter
    proposed_content: dict[str, Any] | None = None
    target_entity_id: UUID | None = None  # for updates
    conflict_description: str | None = None
```

**Rationale:** List output lets the agent extract multiple entities from one chapter pass. Each item has a type discriminator for different handling in the review UI.

### D4: Prompts use PromptComposer, not f-strings

**Decision:** All KB prompts go through `PromptComposer` following RULE-02. Prompts live in `_bundled/kb/{lang}/{mode}/system.md`. First-message prompts for interview mode live alongside as `first_message.md`.

### D5: KBCreationContextAssembly uses KBAgent tools as primary context source

**Decision:** `KBCreationContextAssembly` assembles context from:
1. Template structure (from `core/kb/schemas/` registry)
2. Previous session answers (passed in from API layer)
3. World context via KBAgent tools (search_kb for related entities)
4. Project metadata (genre, language)

When ProactiveContextService is available (after KB-005), it will replace the KBAgent-tools-based world context with embedding-ranked suggestions. The assembly interface stays the same.

### D6: Agent prompts follow CR-01 quality standards

**Decision:** All prompts include:
- Chain-of-Thought reasoning directives
- Negative examples (what NOT to do)
- Structured output format enforcement
- World context integration (use provided KB data)
- Template-aware output (map to template field structure)

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| Union output type may confuse the LLM | Use clear `mode` instructions in system prompt. Test with FunctionModel to verify mode selection. |
| Extraction quality depends on prompt engineering | Start with strong CoT prompts. Add promptfoo eval baselines. Iterate based on real results. |
| Template structure changes may break agent output | Agent receives template structure as part of context, not hardcoded. Template changes are reflected automatically. |
| 12+ prompt files (4 modes × 3 langs) is a lot to maintain | Start with en only. Add de/fr translations after en is validated. Follow existing translation pattern from writing prompts. |
| KBAgent tools may not provide enough world context | Acceptable for now. ProactiveContextService (KB-005) will improve this. KBAgent search is the baseline. |
