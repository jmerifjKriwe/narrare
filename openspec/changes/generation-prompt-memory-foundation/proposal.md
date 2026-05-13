## Why

Narrare has no generation features yet — every AI interaction is limited to writing, KB, and analysis. GEN-001 (Name Generator) is the first generation feature, but implementing it reveals that the underlying infrastructure is incomplete: there are no generation intents, no bundled prompt templates for generation, no prompt override UI, no culture/genre injection system, and no memory layer to learn from user feedback. Building GEN-001 properly means building the foundation for all 20+ generation and AI-assisted features that follow. This is not an MVP — it is foundational architecture that must be done right once.

## What Changes

- **New LLM Intents**: Add `GENERATE`, `NAME_GENERATE`, `TITLE_GENERATE` to `LLMIntent` enum with dedicated model routing entries
- **Prompt System Extensions**: Add generation category to prompt composer, support culture/genre injection via injectable prompt sections (base prompt + culture definition files), and extend PromptContext with memory-related fields (`user_preferences`, `avoidance_patterns`)
- **Bundled Prompt Content**: Create prompt templates for name generation (3 languages) and culture definition files (fantasy, modern, scifi — expandable) under `_bundled/generation/`
- **Memory Layer (mem0)**: Implement the full memory subsystem using mem0 `AsyncMemory` with pgvector backend, including feedback event collection, semantic preference extraction, and prompt injection — with graceful degradation via `NullMemoryClient`
- **Prompt Management Service**: Port `PromptManagementService` from `_scratch` with CRUD operations (list, get, save, reset), cascade resolution info, update detection (bundled version tracking), and diff comparison for override management
- **Prompt Override UI**: Settings panel for browsing, editing, and resetting prompts across all categories, with update notifications when Narrare ships new bundled prompt versions
- **Generation API**: New `generation/` API module with `NameGeneratorService`, contracts, router, and schemas
- **Feedback Collection API**: New `memory/` API module with feedback recording, preference retrieval, and preference reset endpoints
- **mem0 Dependency**: Add `mem0ai` to `packages/core/pyproject.toml`, configured to reuse the user's LLM provider credentials with a cost-efficient default model
- **Documented RULE-01 Exception**: mem0's internal LLM calls for memory extraction use the user's configured provider but bypass the gateway — documented analogously to `core/llm/embeddings.py`

## Capabilities

### New Capabilities
- `generation-intents`: LLM intent definitions and model routing for generation operations (GENERATE, NAME_GENERATE, TITLE_GENERATE)
- `prompt-culture-injection`: Three-layer prompt system (base prompt + culture definitions + overrides) with injectable culture sections via `{{culture_guidelines}}`
- `bundled-generation-prompts`: Bundled prompt templates for name generation and culture definitions under `_bundled/generation/`
- `memory-layer`: Full memory subsystem using mem0 AsyncMemory with pgvector, feedback event collection, preference extraction, and prompt injection
- `prompt-management`: CRUD service for prompt overrides with cascade resolution, version tracking, update detection, and diff comparison
- `prompt-override-ui`: Frontend settings panel for prompt browsing, editing, resetting, and update notifications
- `name-generator-api`: Backend API for GEN-001 name generation with intent routing, culture support, and KB deduplication
- `feedback-api`: Backend API for recording user feedback (accept/reject/modify) and retrieving preference profiles

### Modified Capabilities
- *(none — no existing specs have requirement-level changes)*

## Impact

**Core (`packages/core/narrare_core/`):**
- `llm/intents.py` — new enum values + routing entries
- `prompts/composer.py` — generation category mapping, culture injection, preference injection
- `prompts/registry.py` — culture definition resolution
- `prompts/context.py` — new memory/preference fields
- `prompts/_bundled/` — new generation prompts + culture definitions
- `memory/` — full new module (protocols, models, services, mem0 client)
- `pyproject.toml` — mem0ai dependency

**API (`apps/api/narrare/`):**
- `generation/` — new module (contracts, service, router, schemas)
- `prompts/` — new module (contracts, service, router, schemas)
- `memory/` — new module (contracts, service, router, schemas, repository, models)
- Alembic migration — `feedback_events` table, `user_prompt_templates` table

**Frontend (`packages/web/`):**
- New name generator UI component (modal/panel)
- New prompt settings tab (list, edit, diff, reset, update badges)
- Feedback UI integration (accept/reject/modify on AI suggestions)

**Documentation (`docs/`):**
- INFRA-002 update (status → in-progress)
- INFRA-005 update (status → in-progress, mem0 integration)
- PROMPT-001 + PROMPT-002 completion
- GEN-001 update (status → in-progress, technical details)
- CONSTRAINTS.md — documented RULE-01 exception for mem0
- TECH_STACK.md — mem0 configuration details

**Dependencies:**
- `mem0ai` — new dependency in `packages/core/`
- `psycopg2-binary` — for mem0 pgvector backend (if not already present)
