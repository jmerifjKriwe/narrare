<!-- Context: narrare-dev/guides/agent-creation | Priority: high | Source: docs/development/how-to-add-an-agent.md | Updated: 2026-06-12 -->

# How to Add a New Agent

> Complete reference: `docs/development/how-to-add-an-agent.md`

## Overview: 7 Steps

1. **Types** → `packages/core/narrare_core/agents/{name}_types.py`
2. **Agent** → `packages/core/narrare_core/agents/{name}_agent.py`
3. **Prompt** → `packages/core/narrare_core/prompts/_bundled/{category}/{lang}/{mode}/` (optional)
4. **Registry** → `packages/core/narrare_core/agents/__init__.py`
5. **Service** → `apps/api/narrare/{domain}/{name}_service.py`
6. **Router + DI** → `apps/api/narrare/{domain}/{name}_router.py` + `{name}_deps.py`
7. **Tests** → Agent-level + Service-level + Integration

## NarrareAgent Generic Pattern

All agents follow this base class: `NarrareAgent[DepsT, OutputT]`

```python
class {Name}Agent(NarrareAgent[{Name}Deps, {Name}Output]):
    def __init__(self, model: Any) -> None:
        super().__init__(
            model=model,
            deps_type={Name}Deps,
            output_type=[self._process_output, {Name}Output],
            system_prompt="You are a... ",
        )

    async def _process_output(self, ctx, result="", confidence=1.0):
        if ctx.partial_output:
            return {Name}Output()
        return {Name}Output(result=result, confidence=confidence)

    async def run(self, prompt: str, deps: {Name}Deps, **kwargs) -> {Name}Output:
        result = await self._agent.run(prompt, deps=deps, **kwargs)
        return result.output
```

**Key patterns:**
- `output_type=[self._process_output, {Name}Output]` — LLM calls `_process_output` with named params, which builds the typed output
- `ctx.partial_output` → return minimal output during streaming
- `run()` delegates to `self._agent.run()` and extracts `.output`
- **Automatic Capabilities**: `NarrareAgent.__init__` injects `NarrareObservability`, `NarrareUniversalRules`, and `NarrareMeta` — every agent always has universal rules and meta-prompt identity (ADR-026). No `with_meta()` needed.

## ADR-026 Compliance — Required for Every Agent

Every agent created via `NarrareAgent` automatically receives these Capabilities:

| Capability | Injects | Source |
|-----------|---------|--------|
| `NarrareObservability` | Logging, spans, metrics | auto |
| `NarrareUniversalRules` | Fiction guidelines, conflict resolution, injection defense | `_bundled/universal/` |
| `NarrareMeta` | Narrare identity, role flexibility, conversation guardrails | `_bundled/meta/` |

**No manual meta-prompt loading needed.** Do NOT use `MetaPromptLoader`, `with_meta()`, or manual meta-prepending — these are removed/obsolete (ADR-026 Phase 3).

**Prompt content rules (RULE-02a):**
- **Guaranteed content** (universal rules, identity): Capability — cannot be forgotten
- **Customizable content** (task, output format, mode): PromptComposer cascade + template variables
- **Dynamic data** (KB entities, preferences): Variable substitution via `PromptContext`
- **Dynamic instructions** (per-run behavioral adjustments): `@agent.instructions` (future use)

When adding a new agent, simply inherit `NarrareAgent` — Capabilities are automatic.

## Step 1: Define Types

File: `agents/{name}_types.py`

```python
class {Name}Output(BaseModel):
    result: str = Field(description="Main result text")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
```

Simple outputs can live in the agent file. Complex ones get their own `_types.py`.

## Step 2: Create Agent

File: `agents/{name}_agent.py` — uses NarrareAgent pattern above.

Deps class holds context: language, genre, project_id, etc.

## Step 3: Prompt (optional)

Simple agents: `system_prompt` string in constructor.
Complex agents: prompt file in `prompts/_bundled/{category}/{lang}/{mode}/system.md`, loaded via PromptComposer.

## Step 4: Register in `__init__.py`

```python
from narrare_core.agents.{name}_agent import {Name}Agent, {Name}Deps
from narrare_core.agents.{name}_types import {Name}Output
```

Add to `__all__`.

## Step 5: Backend Service

File: `apps/api/narrare/{domain}/{name}_service.py`

- Constructor takes `ModelRegistry` + `ResolvedModelConfig` via DI
- Gets model from registry, creates agent, runs it
- Optional: `{name}_contracts.py` with ServiceProtocol for testability

## Step 6: Router + DI

Router: thin delegation — `service.process(request.input_text)` → response.
DI: `Depends()` for registry, config, and other services.

## Step 7: Tests

| Level | Tool | Location |
|-------|------|----------|
| Agent | `TestModel(custom_output_text=...)` | `tests/unit/core/agents/` |
| Service | Mocked dependencies | `tests/unit/api/{domain}/` |
| Integration | HTTP with TestModel via DI override | `tests/integration/` |

## Checklist

- [ ] Type file (`*_types.py`)
- [ ] Agent file (`*_agent.py`) with NarrareAgent pattern
- [ ] Prompt (if complex)
- [ ] Registry export (`agents/__init__.py`)
- [ ] Service (backend)
- [ ] Router + DI
- [ ] Contract (optional but recommended)
- [ ] Agent tests (TestModel)
- [ ] Service tests
- [ ] Integration tests
- [ ] i18n keys (if UI)
- [ ] Feature documentation

**Related**: `narrare-dev/guides/prompt-quality`, `narrare-dev/lookup/tech-stack`
