## Context

Narrare is at the transition from Phase 4 (Frontend Foundation) to Phase 5 (Integration & Polish). The core infrastructure exists — LLM Gateway, Prompt System (Registry + Composer + Variable Engine), and a basic set of LLM Intents for writing, KB, and analysis operations. However, no generation features exist yet, the prompt override system is not user-facing, and the memory layer is an empty stub (`memory/__init__.py`).

GEN-001 (Name Generator) is the first generation feature, but implementing it requires foundational work across multiple systems. The old codebase in `_scratch/` has mature implementations of `PromptManagementService`, bundled prompts for names/generation/writing, culture-specific prompts, and a variable metadata registry — all of which should be ported rather than rewritten.

The tech stack already includes mem0 (`>=1.0`) with pgvector backend documented in `TECH_STACK.md`, but mem0ai is not yet in any `pyproject.toml` and the memory module is empty.

Key constraints from existing architecture:
- RULE-01: All LLM calls through `core/llm/gateway.py` (mem0 will be a documented exception)
- RULE-02: Prompts built only in `core/prompts/` (generation prompts follow this)
- RULE-03: Contract (Protocol) before implementation (all new modules need contracts first)
- RULE-04: Modularize instead of compress — enforce hard limits
- ADR-002: Unified Prompt System (already implemented, needs extension)

## Goals / Non-Goals

**Goals:**
- Establish generation intent infrastructure that scales to 20+ generator features without refactoring
- Build a three-layer prompt culture system (base prompt + culture definitions + overrides) that avoids O(cultures × languages) file explosion
- Implement the full memory layer with mem0 AsyncMemory + pgvector, including feedback collection, preference extraction, and prompt injection — with graceful degradation
- Port and modernize `PromptManagementService` from `_scratch` for full prompt CRUD with update detection and diff comparison
- Create the first generation feature (GEN-001 Name Generator) as proof that the architecture works end-to-end
- Make mem0's LLM provider configurable by the user, reusing their existing provider credentials with a cost-efficient default model
- Ensure every new module follows Protocol-first development (ADR-003)

**Non-Goals:**
- Full Context Assembly Pipeline (INFRA-003) — only the generation-relevant context (existing names for dedup) is in scope
- Complex NLP-based preference extraction — mem0 handles extraction, we handle the integration
- mem0 graph store (Neo4j/Memgraph) — pgvector vector store only for now
- Multi-draft generation, batch embedding, or other background task patterns (TaskIQ integration for memory processing is deferred)
- Style adaptation analysis (LEARN-002) — only the preference injection into prompts
- Model configuration per intent UI (SET-003) — model routing is code-only for now
- Additional generation features beyond GEN-001 (plot generator, dialogue generator, etc.)

## Decisions

### D1: Intent granularity — dedicated intents per generator type

**Decision:** Add three new intents: `GENERATE`, `NAME_GENERATE`, `TITLE_GENERATE`.

**Rationale:** Each generator type has different model requirements (name gen = fast/structured/low temperature, title gen = creative/short). The overhead of adding an intent is minimal (enum value + routing entry), but the benefit of fine-grained model routing is significant. Future generators that need different parameters get their own intent; those that don't use the generic `GENERATE`.

**Alternatives considered:**
- Single `GENERATE` intent with mode differentiation → rejected: all generators would share model/temperature/max_tokens
- Intent per feature (40+ intents) → rejected: premature, add as needed

### D2: Culture system — three-layer injection, not per-culture prompt files

**Decision:** Base prompt template (one per feature/language) with `{{culture_guidelines}}` placeholder, injectable culture definition files (one per culture/language), and standard cascade overrides on the base prompt only.

**Rationale:** Cultures/genres can grow unbounded (fantasy, medieval, stone age, scifi, dark scifi, WWII, enlightenment, ...). Having one `system.md` per culture per language means O(cultures × languages) files with massive duplication. The three-layer approach separates concerns: the base prompt defines structure/output format, culture definitions define domain-specific rules, and overrides let users customize independently.

```
_bundled/generation/en/names/system.md           ← base prompt with {{culture_guidelines}}
_bundled/generation/cultures/en/fantasy.md        ← culture definition
_bundled/generation/cultures/en/modern.md         ← culture definition
_bundled/generation/cultures/en/scifi.md          ← culture definition
```

**Alternatives considered:**
- One `system.md` per culture (old `_scratch` approach) → rejected: file explosion, maintenance burden
- Culture as a variable only (`{{culture}}` = "fantasy") → rejected: too little control, no phonetic rules or examples
- Culture as DB entities (KB-006 worldbuilding) → future option, not now

### D3: Memory layer — mem0 AsyncMemory + own feedback_events table

**Decision:** Dual storage: immutable `feedback_events` table (our PostgreSQL) for raw audit trail + mem0 `AsyncMemory` with pgvector backend for semantic preference extraction. Our `FeedbackService` writes to both; our `PreferenceService` queries mem0 for prompt injection.

**Rationale:** mem0 extracts semantic memories ("user dislikes apostrophe-heavy names") from interaction text. But we need the raw events for auditing, statistics, and event-sourced rebuilds. The two stores serve different purposes: events = auditable facts, mem0 = derived preferences. mem0 can be rebuilt from events at any time.

**Alternatives considered:**
- mem0 only (no feedback_events) → rejected: no audit trail, no statistics, no rebuild capability
- Custom memory service (no mem0) → rejected: reinventing semantic extraction, mem0 already in TECH_STACK
- mem0 hosted platform (MemoryClient) → rejected: self-hosted AsyncMemory gives us full control

### D4: mem0 LLM provider — reuse user's configured provider with separate model

**Decision:** mem0 reads the user's provider + API key from Narrare's settings infrastructure (same as SETUP-004). The model defaults to a cost-efficient option per provider (e.g., Claude Haiku for Anthropic, GPT-4.1-nano for OpenAI, Llama3 for Ollama). User can override the memory model in Settings.

**Rationale:** Users shouldn't configure providers twice. Memory extraction is infrastructure, not content generation — it needs a fast/cheap model, not the user's primary model. Configuring the same provider ensures credentials and connectivity work.

**RULE-01 exception:** mem0's internal LLM calls bypass the gateway. Justified because: provider/model is user-controlled via our settings, the purpose is infrastructure (not content), and gateway overhead (intent routing, rate limiting) doesn't apply. Documented analogously to `core/llm/embeddings.py`.

### D5: PromptContext extension — first-class memory fields, feature-specific via extra

**Decision:** Add `user_preferences: str`, `avoidance_patterns: str`, and `style_constraints: str` as first-class fields to `PromptContext`. Generation-specific variables (name_type, culture, count, gender, etc.) go through `extra: dict[str, Any]`.

**Rationale:** Memory fields are cross-cutting — almost every feature needs them. Generation variables are feature-specific and will change as new generators are added. The `extra` dict avoids breaking the API when new variables are needed.

**Alternatives considered:**
- Sub-contexts (`GenerationContext` dataclass) → rejected: over-engineering for current scope, `as_variables()` flattening handles it
- All generation fields as first-class → rejected: PromptContext becomes unwieldy, API breaks with each new generator

### D6: Prompt override update detection — version tracking in frontmatter

**Decision:** Each bundled prompt has `prompt_version` in YAML frontmatter. When a user creates an override, the bundled version at creation time is saved as `override_of_version` in the override's frontmatter. On app start / project open, the system compares stored version with current bundled version to detect updates.

**Rationale:** Minimal implementation that enables the full update notification + diff UX. No separate tracking table needed. The version is informational (no automatic migration) but enables "Your override is based on v1.0.0, but v1.1.0 is now available" UX.

### D7: Graceful degradation — NullMemoryClient pattern

**Decision:** If mem0 is unavailable at startup, the system creates a `NullMemoryClient` that logs warnings and returns empty results. Feedback events are still written to PostgreSQL. The system functions without memory features.

**Rationale:** TECH_STACK.md mandates: "Never a hard dependency at request time." mem0's pgvector connection might fail, the library might not be installed, or the user might disable it. The rest of Narrare must work.

## Risks / Trade-offs

**[mem0 adds an external dependency with its own LLM calls]** → Mitigation: mem0 is already in TECH_STACK.md as a chosen dependency. Graceful degradation via NullMemoryClient means the system works without it. Provider/model is user-configurable. Cost tracking is separate.

**[Culture injection adds complexity to PromptComposer]** → Mitigation: The injection is a simple string substitution (`{{culture_guidelines}}`), triggered only when `context.extra["culture"]` is set. Features that don't use cultures are unaffected.

**[feedback_events table grows unbounded]** → Mitigation: Add TTL/cleanup policy in a future iteration. For now, events are small (a few hundred bytes each) and PostgreSQL handles millions of rows.

**[mem0 creates its own tables in our PostgreSQL database]** → Mitigation: mem0 manages its own schema. We document the table names and ensure no conflicts with our namespace. Connection uses the same Postgres instance but mem0 owns its tables.

**[Large scope — 8 capabilities in one change]** → Mitigation: The capabilities are strongly coupled (memory feeds prompts, prompts feed generation, UI needs all backends). Splitting would create incomplete, unusable increments. The layer ordering (Core → API → Frontend) provides natural checkpoints.

## Open Questions

- **Embedding provider for mem0**: Should mem0 use the same embedding provider as `core/llm/embeddings.py` (OpenAI text-embedding-3-small) or be independently configurable? Proposal: same provider, not independently configurable for now.
- **Culture definition location**: Should culture definitions live under `_bundled/generation/cultures/` or at a shared level `_bundled/cultures/`? Proposal: under generation for now, move to shared level when KB-006 (Worldbuilding) needs them.
- **Async feedback processing**: Should mem0.add() be called synchronously during feedback recording, or asynchronously via TaskIQ? Proposal: synchronous for now (mem0 calls are fast), TaskIQ background processing as optimization later.
