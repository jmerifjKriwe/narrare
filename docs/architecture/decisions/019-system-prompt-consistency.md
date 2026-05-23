# ADR-019 — System-Prompt Consistency for pydantic-ai Agents

> **Status:** ✅ Accepted
> **Date:** 2026-05-23
> **Deciders:** Architecture Agent, Narrare Dev Coordinator
> **Supersedes:** —
> **Related:** ADR-002 (Unified Prompt System), ADR-015 (Agents as First-Class Citizens)

---

## Context

The introduction of pydantic-ai Agents as first-class citizens (ADR-015) created a parallel prompt path that bypassed the unified prompt system (ADR-002):

- **Path A — PromptComposer:** Writing pipeline → PromptComposer → meta-prompt prepended → ComposedPrompt → passed to agent via `system_prompt` parameter
- **Path B — Direct Agent:** Agent instantiated without `system_prompt` → hardcoded persona → no meta-prompt

This caused **persona fragmentation**. A user using "Continue" (Path A) experienced the collaborative Narrare persona with full identity context, while using "Review" via direct agent instantiation (Path B) got an isolated "professional writing critic" persona that knew nothing about Narrare's identity, the project, or the writer's preferences.

Additionally, the meta-prompt lacked operational guardrails for:
- **Fiction content** — LLMs sometimes refuse to generate conflict, violence, or complex relationship content that is normal in fiction
- **Off-topic handling** — No guidance for redirecting users who ask non-writing questions
- **User error tolerance** — No instructions for handling typos or unclear requests gracefully
- **Avoidance constraints** — No mechanism for user-defined content filtering

---

## Decision Drivers

- **Persona consistency** — Every agent interaction must reflect the same Narrare identity
- **RULE-02 compliance** — All prompts must go through the unified prompt system (ADR-002)
- **Fiction-appropriate behavior** — Creative writing content must not trigger unnecessary LLM refusals
- **Guardrail coverage** — Off-topic, error tolerance, and avoidance patterns must be handled uniformly
- **Backward compatibility** — Existing tests and direct-instantiation paths must not break
- **Minimal coupling** — Agents should not need to know about prompt loading internals

---

## Options Considered

### Option A — Mandatory PromptComposer for all agent instantiation

Every agent creation goes through PromptComposer. Remove direct `__init__` access.

**Pros:**
- Single source of truth for all prompts
- Impossible to create an agent without meta-prompt

**Cons:**
- Breaks test ergonomics — unit tests need PromptComposer setup for every agent
- Overkill for agents that don't need a meta-prompt (utility agents)
- Couples agent lifecycle to prompt infrastructure

### Option B — `NarrareAgent.with_meta()` factory + PromptComposer (chosen)

Agents accept `system_prompt: str | None = None` in `__init__`. A `with_meta()` classmethod loads the meta-prompt via `MetaPromptLoader` and prepends it. Production paths (PromptComposer) already include the meta-prompt; `with_meta()` serves as a safety net for direct-use scenarios.

**Pros:**
- Test paths keep direct `__init__` without meta-prompt (acceptable for unit tests)
- Production paths use PromptComposer (meta-prompt guaranteed)
- Safety net for future direct-use scenarios
- No coupling between agent lifecycle and prompt infrastructure

**Cons:**
- Two paths to create an agent — requires documentation to prevent confusion
- A developer could still bypass `with_meta()` and create a bare agent

### Option C — Meta-prompt injection at run time

Inject the meta-prompt into every `agent.run()` call, regardless of how the agent was created.

**Pros:**
- Impossible to miss the meta-prompt

**Cons:**
- Overhead on every run call (meta-prompt loading)
- Breaks pydantic-ai's `system_prompt` contract
- Makes prompt debugging harder (system prompt changes at runtime)

---

## Decision

**We choose Option B — `NarrareAgent.with_meta()` factory + PromptComposer.**

All agent subclasses accept `system_prompt: str | None = None` via `__init__`. The `NarrareAgent.with_meta()` classmethod loads the meta-prompt via `MetaPromptLoader` and prepends it to the agent-specific system prompt. Production paths (WritingGraph, SummaryService, AnalysisService) use PromptComposer, which already includes meta-prompt prepending — making `with_meta()` a safety net for fallbacks, tests that need full persona, and future direct-use scenarios.

---

## Rationale

The two-path approach mirrors how pydantic-ai itself handles system prompts: you can pass `system_prompt` at construction time or defer it. The key insight is that **production code always uses PromptComposer** (Path A), which guarantees the meta-prompt is included. Path B (`with_meta()`) exists for scenarios where PromptComposer is not available or would be overkill.

This is acceptable because:
1. The architecture check (`scripts/check_architecture.py`) can enforce that services use PromptComposer
2. Tests using direct `__init__` are testing agent behavior, not persona — meta-prompt would be noise
3. `with_meta()` provides a documented, type-safe escape hatch

The guardrails addition (fiction content guidelines, conversation guardrails, `{{avoidance_patterns}}`) addresses real production issues observed during CR-02 testing: LLMs refusing fiction-appropriate content and users experiencing inconsistent behavior across interaction modes.

---

## Consequences

**Positive:**
- All production agents receive the Narrare identity, either via PromptComposer or via `with_meta()`
- Meta-prompt provides consistent guardrails across all interaction modes
- Fiction writing no longer triggers unexpected LLM refusals
- `{{avoidance_patterns}}` enables user-specific content filtering
- Test ergonomics preserved — unit tests use direct `__init__` without meta-prompt overhead
- `with_meta()` is a documented, type-safe escape hatch for edge cases

**Negative / Tradeoffs:**
- Two creation paths require developer awareness — documentation must clarify when to use which
- A developer could bypass `with_meta()` and create a bare agent (mitigated by architecture checks)
- Meta-prompt files (en, de, fr, lite) must be kept in sync — 4 variants to maintain

**Constraints introduced:**
- Production services MUST use PromptComposer for agent system prompts (RULE-02)
- `with_meta()` is for fallback/test scenarios only — not a replacement for PromptComposer
- Meta-prompt guardrails (fiction content, conversation, avoidance) are mandatory in all 4 variants

---

## Implementation Notes

### Files changed

| File | Change |
|------|--------|
| `core/agents/base.py` | Added `NarrareAgent.with_meta()` classmethod factory |
| `core/agents/base.py` | Added `system_prompt: str \| None = None` parameter to `__init__` |
| `core/prompts/_bundled/meta/en/system.md` | Added Fiction Content Guidelines, Conversation Guardrails, `{{avoidance_patterns}}` |
| `core/prompts/_bundled/meta/de/system.md` | Same guardrails in German |
| `core/prompts/_bundled/meta/fr/system.md` | Same guardrails in French |
| `core/prompts/_bundled/meta/en/system.lite.md` | Same guardrails in lite variant |
| `core/agents/writing_graph_prompts.py` | Extracted prompt building for WritingGraph (CR-01) |

### Key pattern

```python
# Production path (PromptComposer handles meta-prompt):
composer = PromptComposer(registry)
prompt = await composer.build(LLMIntent.WRITE, ctx)
agent = DraftAgent(model=model, system_prompt=prompt.system, ...)

# Fallback / test path (with_meta prepends meta-prompt):
agent = await DraftAgent.with_meta(
    model=model,
    meta_loader=loader,
    meta_variables={"project_title": "...", "language": "en", ...},
    system_prompt="Agent-specific instructions",
)

# Unit test path (no meta-prompt — testing agent behavior):
agent = DraftAgent(model=TestModel(), system_prompt=None)
```

### Meta-prompt guardrail structure

All 4 meta-prompt variants now contain:

1. **Fiction Content Guidelines** — Treat fiction content (conflict, violence, complex relationships) as normal narrative appropriate to the genre. Generate faithfully without moral judgment of characters.
2. **Conversation Guardrails** — Off-topic redirection with gentle refocus, typo tolerance with intent inference, empathetic-but-focused emotional response handling.
3. **`{{avoidance_patterns}}`** — Respects user-defined content constraints (variable substituted at load time).

---

## Review Trigger

- [ ] When a new meta-prompt variant is added — ensure all guardrails are included
- [ ] When a new agent is created — verify it uses PromptComposer or documents why `with_meta()` is needed
- [ ] When pydantic-ai v2 is released — verify `system_prompt` parameter contract is unchanged
- [ ] After 3 months — audit whether any production code bypasses PromptComposer for agent creation
