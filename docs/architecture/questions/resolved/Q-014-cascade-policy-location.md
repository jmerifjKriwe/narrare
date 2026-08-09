# Q-014 — Should the Model-Routing Cascade Logic Live in Core or API?

> **Status:** ✅ Resolved
> **Resolved:** 2026-07-04
> **Resolution:** The cascade logic stays in `apps/api/`. The current design
>                (Protocol in `core/llm/model_routing.py`, DB-backed
>                implementation in `apps/api/narrare/settings/model_routing_resolver.py`)
>                is architecturally correct per RULE-07.
> **ADR created:** None needed — confirmed existing architecture, no change.

---

## Context

The `ModelRoutingResolver` Protocol is defined in `packages/core/narrare_core/llm/model_routing.py`.
The implementation `ModelRoutingResolverImpl` lives in
`apps/api/narrare/settings/model_routing_resolver.py` and contains the cascade
priority logic:

```
project_intent → project_category → user_intent → user_category → user_default → ConfigurationError
```

The question was whether this cascade logic should be moved to `core/` so it's
closer to the Protocol definition.

## Analysis

The cascade logic depends on three database repositories:

- `ProjectAiSettingsRepository`
- `UserAiSettingsRepository`
- `UserProvidersRepository`

These repositories use SQLAlchemy `AsyncSession` and are tied to the API layer.
Moving the cascade logic to `core/` would require either:

### Option A: Inject repository Protocols into core

- Define `ProjectAiSettingsRepositoryProtocol` etc. in core
- Core cascade calls these protocols
- API provides the implementations

**Problem:** The cascade logic is fundamentally DB-query orchestration (check
project settings → if not found, check user settings → if not found, use
default). Moving it to core would mean core orchestrates DB access, which
blurs the core/API boundary. The repositories themselves (query logic) would
still live in API, creating a split where core "manages" DB interactions.

### Option B: Move cascade + ORM models to core

- Move cascade logic AND the repository interfaces to core

**Problem:** Violates RULE-07 (core/ never imports from apps/) and RULE-08
(external integrations in dedicated adapters only). Core would need SQLAlchemy
as a dependency.

### Current design (selected):

- `core/llm/model_routing.py` defines the **contract** (Protocol + result types)
- `apps/api/settings/model_routing_resolver.py` defines the **implementation**
  (cascade logic + DB queries)
- API services call the resolver, pass the result to the gateway

This is clean separation: Protocol in core, implementation in API.

## Resolution

**No change.** The cascade logic stays in `apps/api/`. The current architecture
is correct:

1. `core/` defines *what* a resolver does (the Protocol)
2. `apps/api/` defines *how* it does it (DB-backed cascade)
3. RULE-07 is respected: `core/` has zero imports from `apps/`
4. If another consumer (e.g. CLI, MCP) needs model routing, it provides its own
   `ModelRoutingResolver` implementation — no cascade code needs to move.

## Related

- `packages/core/narrare_core/llm/model_routing.py` — Protocol definition
- `apps/api/narrare/settings/model_routing_resolver.py` — Implementation
- `docs/_shared/CONSTRAINTS.md` § RULE-07 — Dependency direction
