# ADR-026 — Capability-Based Prompt Injection Pattern

> **Status:** ✅ Accepted
> **Date:** 2026-06-01
> **Deciders:** Architecture Specialist
> **Supersedes:** Partially supersedes ADR-019 (system-prompt consistency)
> **Related:** ADR-002 (unified prompt system), ADR-015 (agents as first-class citizens), ADR-016 (prompt caching)

---

## Context

Narrare's prompt system currently uses a monolithic approach: `PromptComposer.build()` assembles a single `system_prompt` string by prepending the meta-prompt (identity, fiction guidelines, conflict resolution, injection defense) to the feature-specific template. This creates two problems:

1. **Universal rules must be manually included in every template.** The meta-prompt contains content that must ALWAYS be present (fiction content guidelines, conflict resolution, content security/injection defense). Currently, this content is embedded in the meta-prompt template files (`_bundled/meta/{lang}/system.md`) and prepended by PromptComposer. If an agent is instantiated without PromptComposer (e.g., via `NarrareAgent.with_meta()` or direct `__init__`), these universal rules can be missed. FIND-015, FIND-018, and FIND-020 were all caused by this manual-copying requirement.

2. **Customizable and guaranteed content are conflated.** The meta-prompt mixes user-customizable content (role description, tone, genre) with architecturally guaranteed content (fiction guidelines, conflict resolution, injection defense). This makes templates longer than necessary and prevents language optimization (EN-only templates with cascade overrides).

pydantic-ai provides `AbstractCapability.get_instructions()` and `@agent.instructions` as composable prompt injection mechanisms. Capabilities are attached to the agent at construction time and cannot be "forgotten" — they are architecturally guaranteed. This is the correct mechanism for content that must always be present.

---

## Decision Drivers

- **Architectural guarantee** — Universal rules must be impossible to omit, not merely "remembered"
- **RULE-02 compliance** — All prompt content must have a clear, governed source
- **Template simplicity** — Templates should contain only user-customizable content
- **Language optimization** — EN-only templates with cascade overrides should be possible
- **pydantic-ai alignment** — Use the framework's native composition mechanisms instead of building parallel infrastructure
- **Backward compatibility** — Existing PromptComposer paths must continue to work during migration
- **Separation of concerns** — Guaranteed content, customizable content, and dynamic content have different lifecycle requirements

---

## Options Considered

### Option A — Status Quo: PromptComposer-only (rejected)

Keep all prompt content in PromptComposer, including universal rules. Fix FIND-015/018/020 by ensuring every agent path goes through PromptComposer.

**Pros:**
- Single source of truth for all prompts
- No new abstractions needed
- RULE-02 remains simple

**Cons:**
- Does not solve the root cause: universal rules can still be forgotten if PromptComposer is bypassed
- Templates remain bloated with content that is never customized
- Language optimization blocked (4 language variants of meta-prompt must be kept in sync)
- `with_meta()` is a workaround, not a guarantee — a developer can still create a bare agent
- Conflates three distinct concerns (guaranteed, customizable, dynamic) into one mechanism

### Option B — Capabilities for guaranteed content, Templates for customizable content, @agent.instructions for dynamic content (chosen)

Adopt a hybrid approach with three distinct injection mechanisms, each aligned to its content type:

| Content Type | Mechanism | Source | Lifecycle |
|---|---|---|---|
| **Guaranteed** (fiction guidelines, conflict resolution, injection defense) | `AbstractCapability.get_instructions()` | `core/prompts/_bundled/` (canonical) | Static per agent, always present |
| **Customizable** (role, task, output format, mode-specific instructions) | PromptComposer cascade | `core/prompts/_bundled/` + user overrides | Per intent, user-configurable |
| **Dynamic** (KB data, style profiles, voice profiles) | `@agent.instructions` or `Capability.for_run()` | Deps (runtime) | Per invocation, data-driven |

**Pros:**
- Universal rules are architecturally guaranteed (cannot be forgotten)
- Templates become shorter and focused on customizable content
- Language optimization becomes possible (EN-only templates with cascade overrides)
- Each mechanism is aligned to its content type's lifecycle
- Follows pydantic-ai's native composition model
- NarrareObservability already establishes the Capability pattern

**Cons:**
- Three mechanisms instead of one — requires documentation
- RULE-02 needs amendment to distinguish content types
- Migration must be phased to avoid breaking existing paths
- Capabilities add a small token overhead (capability instructions are always included)

### Option C — Capabilities for everything (rejected)

Move all prompt content into Capabilities, including templates.

**Pros:**
- Single mechanism for all prompt injection
- Maximum composability

**Cons:**
- Violates RULE-02: Capabilities would need to implement cascade resolution logic
- Templates are user-customizable — Capabilities are not the right mechanism for user overrides
- Would require Capabilities to duplicate PromptComposer's cascade logic
- Breaks the separation between "what the user can customize" and "what the system guarantees"

---

## Decision

**We choose Option B — Hybrid approach with three distinct injection mechanisms.**

### Capability Definitions

#### 1. `NarrareUniversalRules` (Phase 1)

A `AbstractCapability` subclass that injects fiction content guidelines, conflict resolution rules, and content security/injection defense instructions. These rules are always present for every Narrare agent — they are non-negotiable and non-customizable.

```python
class NarrareUniversalRules(AbstractCapability):
    """Injects universal rules that must always be present.

    - Fiction content guidelines
    - Conflict resolution (outline vs KB)
    - Content security / injection defense
    """

    async def get_instructions(self) -> str:
        # Load from core/prompts/_bundled/universal_rules/{language}/system.md
        # Fallback to EN if language not available
        ...
```

**Source:** `core/prompts/_bundled/universal_rules/{language}/system.md`
**Location:** `core/agents/capabilities/universal_rules.py`
**Attached:** Automatically by `NarrareAgent.__init__` (alongside `NarrareObservability`)

#### 2. `NarrareMeta` (Phase 3)

A `AbstractCapability` subclass that injects the meta-prompt identity (who Narrare is, role flexibility). This replaces the current meta-prompt prepending in PromptComposer.

```python
class NarrareMeta(AbstractCapability):
    """Injects the Narrare meta-prompt identity.

    - Who Narrare is
    - Role flexibility
    - Writing language
    """

    async def for_run(self, ctx: RunContext[PromptDeps]) -> NarrareMeta:
        # Extract language, genre, etc. from deps via getattr()
        ...

    async def get_instructions(self) -> str:
        # Load from core/prompts/_bundled/meta/{language}/system.md
        ...
```

**Source:** `core/prompts/_bundled/meta/{language}/system.md` (existing, trimmed)
**Location:** `core/agents/capabilities/meta.py`

#### 3. KB Context via `@agent.instructions` (Phase 4)

Dynamic, per-invocation content (KB data, style profiles) is injected via `@agent.instructions` or `Capability.for_run()`. This is data, not instructions — though it may contain formatting.

```python
# In agent definition:
@agent.instructions
async def kb_context(ctx: RunContext[WritingDeps]) -> str:
    """Inject KB context for this specific invocation."""
    assembler = ctx.deps.context_assembler
    if assembler is None:
        return ""
    return await assembler.build_context(ctx.deps)
```

### Template Changes

After migration, templates become shorter. They contain only:
- Role description (customizable per intent)
- Task instructions (customizable per intent)
- Output format specification (customizable per intent)
- Mode-specific instructions (customizable per intent)

Universal rules, meta-prompt identity, and injection defense are removed from templates and handled by Capabilities.

---

## Rationale

The root cause of FIND-015/018/020 is that universal rules had to be manually included in every template. This is an architectural problem, not a documentation problem — no amount of "remember to include the meta-prompt" will prevent a future developer from creating an agent that misses it.

Capabilities solve this at the architecture level: they are attached to the agent at construction time and cannot be omitted. `NarrareAgent.__init__` already injects `NarrareObservability` for every agent — adding `NarrareUniversalRules` follows the same pattern and provides the same architectural guarantee.

The three-mechanism approach aligns each content type to its natural lifecycle:
- **Guaranteed content** has a static lifecycle (same for every invocation) → Capability
- **Customizable content** has a per-intent lifecycle (different per intent, user-configurable) → PromptComposer cascade
- **Dynamic content** has a per-invocation lifecycle (different every time) → `@agent.instructions` / `for_run()`

This is not "three ways to do the same thing" — it is three mechanisms for three distinct concerns. Conflating them (Option A) caused the original bugs. Over-consolidating them (Option C) would violate RULE-02.

---

## Consequences

**Positive:**
- Universal rules are architecturally guaranteed — impossible to forget
- Templates become shorter and focused on customizable content
- Language optimization becomes possible (EN-only templates with cascade overrides)
- `with_meta()` removed entirely — Capabilities replace it (Phases 1–3)
- PromptComposer's role becomes clearer: it handles customizable content only
- ADR-019's two-path problem is resolved — Capabilities are always present regardless of path
- Follows pydantic-ai's native composition model (no parallel infrastructure)

**Negative / Tradeoffs:**
- Three injection mechanisms require developer education
- RULE-02 needs amendment to distinguish content types
- Migration must be phased (cannot break existing PromptComposer paths)
- Capabilities add a small token overhead (instructions are always included in the system prompt)
- `NarrareUniversalRules` must load from `core/prompts/_bundled/` — this creates a dependency from `core/agents/capabilities/` to `core/prompts/`, but it is a read-only dependency that respects RULE-02 (no prompt assembly in capabilities)

**Constraints introduced / updated:**
- RULE-02 is amended to RULE-02a: distinguishes user-customizable, architecturally guaranteed, and dynamic prompt content
- `check_architecture.py` should verify that no `get_instructions()` in `core/agents/capabilities/` assembles prompts via f-string or concatenation — it must load from `core/prompts/` or return static strings
- ADR-019 is fully superseded: `with_meta()` has been removed, all prompt identity/rules are now via Capabilities

---

## Migration Plan

The migration is phased to ensure each step is atomic and backward-compatible.

| Phase | Content | Risk | Depends On | Status |
|-------|---------|------|------------|--------|
| 1 | `NarrareUniversalRules` Capability + template cleanup | Low — additive, no existing paths change | ADR-026 approval | ✅ Complete |
| 2 | PromptGuard reorientation | Low — PromptGuard validates Capability output | Phase 1 | ✅ Complete |
| 3 | `NarrareMeta` Capability | Medium — meta-prompt moves from PromptComposer to Capability | Phase 1 | ✅ Complete |
| 4 | KB-Context as `@agent.instructions` | Medium — changes how KB data is injected | Phase 3 | Pending |
| 5 | Language optimization (EN-only templates) | Low — removes language variants from templates | Phase 3 | Pending |
| 6 | TemplateStr evaluation (optional) | Low — template syntax modernization | Phase 5 | Pending |

### Phase 1: NarrareUniversalRules + Template Cleanup (Atomic)

1. Create `NarrareUniversalRules` Capability in `core/agents/capabilities/universal_rules.py`
2. Extract universal rules from `_bundled/meta/{lang}/system.md` into `_bundled/universal_rules/{lang}/system.md`
3. Add `NarrareUniversalRules()` to `NarrareAgent.__init__` capability list (alongside `NarrareObservability`)
4. Remove universal rules sections from meta-prompt templates (keep identity + role flexibility)
5. Update `PromptComposer.build()` to NOT prepend universal rules (they come from Capability now)
6. Verify: all existing tests pass, universal rules are present in all agent outputs

### Phase 2: PromptGuard Reorientation

1. Update PromptGuard to validate Capability-injected content
2. Add tests that verify `NarrareUniversalRules` output is present in every agent's system prompt
3. Add architecture check: `NarrareUniversalRules` is in every `NarrareAgent` subclass's capability list

### Phase 3: NarrareMeta Capability

1. Create `NarrareMeta` Capability in `core/agents/capabilities/meta.py`
2. Move meta-prompt identity from PromptComposer to `NarrareMeta`
3. Update `NarrareAgent.with_meta()` to use `NarrareMeta` Capability instead of manual prepending
4. Simplify PromptComposer: it now only handles customizable content

### Phase 4: KB-Context as @agent.instructions

1. Move KB context injection from PromptComposer to `@agent.instructions`
2. Create `NarrareKBContext` Capability or use `@agent.instructions` directly
3. Update `WritingDeps` and other Deps types to implement `PromptDeps` protocol

### Phase 5: Language Optimization

1. Make templates EN-only with cascade overrides for other languages
2. Remove language variants from feature-specific templates
3. Keep language variants only for meta-prompt and universal rules (where language matters)

### Phase 6: TemplateStr Evaluation (Optional)

1. Evaluate switching from `{{variable}}` to `{variable}` (Python format strings) in templates
2. Requires ADR if pursued

### Completed Phases (1–3)

Phases 1–3 were implemented in commit `45b7395`. Key outcomes:

- `NarrareUniversalRules` Capability injects fiction guidelines, conflict resolution, injection defense from `_bundled/universal/`
- `NarrareMeta` Capability injects identity, role flexibility, guardrails from `_bundled/meta/`
- Both auto-injected by `NarrareAgent.__init__` — architecturally guaranteed for every agent
- `with_meta()` REMOVED completely — no longer needed
- `PromptComposer` simplified: no `meta_loader`, no `include_meta`, no meta-prepending. Handles only customizable content
- RULE-02a established: three content categories (Guaranteed / Customizable / Dynamic)

---

## Implementation Notes

### Files to Create

| File | Purpose |
|------|---------|
| `core/agents/capabilities/universal_rules.py` | `NarrareUniversalRules` Capability |
| `core/agents/capabilities/meta.py` | `NarrareMeta` Capability (Phase 3) |
| `core/agents/capabilities/contracts.py` | `PromptDeps` and `PromptContextDeps` protocols |
| `core/prompts/_bundled/universal_rules/en/system.md` | Universal rules (EN) |
| `core/prompts/_bundled/universal_rules/de/system.md` | Universal rules (DE) |
| `core/prompts/_bundled/universal_rules/fr/system.md` | Universal rules (FR) |

### Files to Modify

| File | Change |
|------|--------|
| `core/agents/base.py` | Add `NarrareUniversalRules()` to capability list |
| `core/agents/capabilities/__init__.py` | Export new Capabilities |
| `core/prompts/composer.py` | Remove universal rules prepending (Phase 1), remove meta prepending (Phase 3) |
| `core/prompts/meta.py` | Simplify after universal rules extraction |
| `core/prompts/_bundled/meta/{lang}/system.md` | Remove universal rules sections |
| `docs/_shared/CONSTRAINTS.md` | Amend RULE-02 |

### Key Pattern: Capability Loading from core/prompts/

Capabilities that inject prompt content MUST load from `core/prompts/` (typically `_bundled/`). They MUST NOT assemble prompts via f-string or concatenation. This preserves RULE-02's intent while allowing Capabilities to be the injection mechanism for guaranteed content.

```python
# CORRECT: Load from canonical source
class NarrareUniversalRules(AbstractCapability):
    async def get_instructions(self) -> str:
        loader = UniversalRulesLoader()  # uses core/prompts/ cascade
        return await loader.load(language=self._language)

# FORBIDDEN: Assemble via f-string
class NarrareUniversalRules(AbstractCapability):
    async def get_instructions(self) -> str:
        return f"You are a fiction assistant. Always follow these rules: {rules}..."
```

### Key Pattern: Deps Access via getattr()

Capabilities access Deps fields via `getattr()` with fallbacks, following the pattern established by `NarrareObservability`:

```python
async def for_run(self, ctx: RunContext[Any]) -> NarrareMeta:
    deps = ctx.deps
    language = getattr(deps, "language", "en") if deps else "en"
    genre = getattr(deps, "genre", None) if deps else None
    ...
```

This avoids requiring all Deps types to implement a full protocol, while still providing type-safe contracts for Capabilities that need them (`PromptDeps`, `PromptContextDeps`).

---

## Review Trigger

- [ ] After Phase 1 completion: Verify universal rules are present in all agent outputs
- [ ] After Phase 3 completion: Verify meta-prompt identity is present regardless of PromptComposer usage
- [ ] When pydantic-ai v2 is released: Verify `AbstractCapability.get_instructions()` contract is unchanged
- [ ] After 3 months: Audit whether any production code bypasses Capability injection
- [ ] When adding a new agent: Verify it inherits `NarrareUniversalRules` via `NarrareAgent.__init__`
