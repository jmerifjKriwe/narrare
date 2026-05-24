## Why

KB-002 (Assisted Creation) and KB-007 (Entity Extraction) both need specialized LLM agents. The existing `KBAgent` is a tool-provider only (no `output_type`, never runs independently). We need two new agents: one that guides assisted entity creation with multiple interaction modes (interview, suggest, enhance), and one that extracts entities from chapter text with structured output. Both reuse KBAgent's tools (search_kb, get_entity, get_related_entities) via Toolset integration. The prompts for these agents are critical — they must produce template-aware output that integrates with the existing KB template system.

## What Changes

- **New `KBAssistAgent`** in `core/agents/` — NarrareAgent subclass with Union output type supporting 4 modes: question, suggestion, draft, complete. Reuses KBAgent's toolset for world context queries.
- **New `ExtractionAgent`** in `core/agents/` — NarrareAgent subclass that reads chapter text and produces structured `ExtractionResult[]` output (new entities, updates, relationships, conflicts).
- **New output type modules**: `kb_assist_types.py` and `extraction_types.py` with Pydantic models for structured LLM output.
- **New bundled prompts** in `_bundled/kb/{en,de,fr}/`: interview, suggest, enhance, extract system prompts + first-message prompts.
- **New `KBCreationContextAssembly`** in `core/context/` — assembles template structure + world context (via ProactiveContextService when available, fallback to KBAgent tools) + previous session answers into a prompt context.
- **Modified `KBAgent`** — no changes to KBAgent itself (it stays a tool-provider). New agents compose with it via Toolset capability.

## Capabilities

### New Capabilities
- `kb-assist-agent`: LLM agent for assisted KB entity creation with interview, suggest, enhance, and auto-generate modes. Union output type for mode-aware responses. Template-aware output that maps to KB template field structure.
- `extraction-agent`: LLM agent for extracting entities, facts, and relationships from chapter text. Structured output with confidence scoring, dedup detection, and conflict identification.
- `kb-prompts`: Bundled prompt system for KB operations (interview, suggest, enhance, extract) in en/de/fr with CoT reasoning and structured output enforcement.

### Modified Capabilities
- (none — existing agents are not modified)

## Impact

- **Core agents**: Two new agents + output types in `packages/core/narrare_core/agents/`
- **Core context**: New `KBCreationContextAssembly` in `packages/core/narrare_core/context/`
- **Core prompts**: New prompt directory `_bundled/kb/` with 12+ prompt files (4 modes × 3 languages)
- **Dependencies**: Both agents depend on existing KBAgent (toolset composition), KBQueryService, and core template schemas. ExtractionAgent additionally depends on INFRA-004 embeddings (for dedup similarity) — soft dependency, can start with name-based dedup.
- **No API layer changes** in this change — API endpoints and frontend come in subsequent changes (KB-002, KB-007 implementation).
