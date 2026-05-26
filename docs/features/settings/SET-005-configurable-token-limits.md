---
id: SET-005
title: "Configurable Token Limits"
status: stable
phase: 1
area: settings
mvp: true

ui_tooltip: "Customize token budgets and output limits for every AI feature."
ui_help_short: |
  Just like you can customize prompts, you can now adjust every token
  limit in Narrare — output lengths per feature, context budget tiers,
  and timeouts — all from the Settings UI without editing code.
ui_help_long: |
  Every AI feature in Narrare uses token limits and budgets that determine
  how much the AI writes, how much context it sees, and when it times out.

  With this feature, you can tune every single one of these values from
  the Settings UI — no config files, no environment variables, no code changes.
  Narrare provides sensible defaults, but power users and self-hosters can
  override anything.

  There are three groups of settings:
  - **Output Limits** — How many tokens each feature can generate per call
    (quick/balanced/long profiles, or raw token values)
  - **Context Budget** — How the total token budget is distributed across
    context tiers (immediate chapter, recent history, KB entities, pinned items)
  - **System Timeouts** — WebSocket idle timeout, API request timeout, retry config
ui_available_in: [settings]
---

# [SET-005] — Configurable Token Limits

## What it does

Lets users (and operators) view and adjust every token limit, budget
percentage, and timeout in Narrare through a dedicated Settings tab —
without editing code, env vars, or YAML files.

## Why it exists

The CR-08 audit revealed 10+ hardcoded values across the codebase that
different users need to tune differently:

- A novelist writing 10k-word chapters needs higher output limits
- A plotter sketching outlines needs tighter budgets
- A self-hoster on a budget needs conservative retry/timeout configs
- A power-user exploring the AI's creative range wants to push limits

Without UI configurability, every tune-up requires a developer. This feature
makes Narrare adaptable by its users.

## How it works (User perspective)

1. The user opens **Settings → Token Limits**
2. They see three collapsible sections: **Output Limits**, **Context Budget**, **System**
3. **Output Limits** shows a table of features (Draft, Summary, Suggest, Continue, Consistency, etc.) each with a dropdown: *quick* / *balanced* / *long* — or a raw token input for precise control
4. **Context Budget** shows the 5-tier pie chart (immediate/recent/kb_referenced/kb_suggested/pinned) with percentage sliders that automatically adjust to total 100%
5. **System** shows WebSocket timeout (seconds), retry count, API timeout
6. Every change saves immediately and takes effect on the next AI call
7. A **"Reset to defaults"** button restores all factory values

## How it works (Technical)

The feature uses the **Operator-Config → Core-Defaults** pattern from CR-08:

### Three-Layer Resolution (via `TokenLimitsService.get_resolved_limits()`)

```
User override (DB: user_token_limits table)
  ↓
Project override (DB: project_token_limits table)
  ↓
Operator env var (config.py / .env)
  ↓
Code default (hardcoded in core/)
```

**Model Data Source:** All token limit suggestions (max context, max output per model) are derived from [models.dev](https://models.dev) data. See [Model Data Reference](../../reference/model-data.md) for details on how model specifications are fetched, cached, and refreshed.

### Core Changes

**`packages/core/narrare_core/writing/budget.py`:**
- `TokenBudgetManager` constructor accepts optional `token_budget_overrides` dict
- `_BASE_PERCENTAGES` and `_FIRST_CHAPTER_PERCENTAGES` become overridable
- API: `TokenBudgetManager(total_budget=6000, tier_overrides={"immediate": 0.40})`

**`packages/core/narrare_core/llm/intents.py`:**
- `ResolvedModelConfig` gains `resolve_output_limit(profile: str) -> int` method
- Maps token_limit_profile ("quick"/"balanced"/"long") to token values
- Env var override supported via optional `settings` parameter

### API Changes

**`apps/api/narrare/_app/config.py`:**
New settings fields (Operator-Config layer — env vars):

```python
# --- Token Limits (Operator-Config) ---
default_output_limit: int = 4096  # default max_tokens
ws_idle_timeout_seconds: int = 1800
budget_tier_percentages: str = ""  # optional JSON: '{"immediate":30,"recent":20,...}'
```

**`apps/api/narrare/settings/` — New module:**

| File | Purpose |
|------|---------|
| `token_limits/models.py` | `UserTokenLimits` + `ProjectTokenLimits` SQLAlchemy models |
| `token_limits/schemas.py` | Pydantic request/response schemas |
| `token_limits/contracts.py` | `TokenLimitsServiceProtocol`, `TokenLimitsRepositoryProtocol` |
| `token_limits/repository.py` | CRUD for token limits overrides |
| `token_limits/service.py` | Cascade resolution logic + merge with env/code defaults |
| `token_limits/router.py` | REST endpoints under `/api/v1/settings/token-limits` |

### Backend Deps-Integration

All writing deps now use `TokenLimitsService` instead of raw `resolve_output_limit()`:

- `apps/api/narrare/writing/deps.py`: `get_writing_service()`, `get_extend_service()`, `get_rewrite_service()` resolve limits via `TokenLimitsService.get_resolved_limits()`
- `apps/api/narrare/writing/summary_deps.py`: `get_summary_service()` uses `TokenLimitsService` instead of `resolve_output_limit()`
- `apps/api/narrare/writing/router_sessions.py`: Resolves `output_limit` + `ws_timeout` dynamically via `TokenLimitsService.get_resolved_limits()` — no more hardcoded 2000
- `apps/api/narrare/writing/ws_handler.py`: Reads `settings.ws_idle_timeout_seconds`

### Dual-Write Mode

The old columns (`user_ai_settings.token_limit_overrides`, `project_ai_settings.token_limit_profile`) still exist but are deprecated. Both `UserAiSettingsService` and `ProjectAiSettingsService` write to both old columns and the new `TokenLimitsService` tables. Writes through the old path emit a deprecation warning.

### Frontend

- `ContextBudget.tsx` — Token budget distribution across 5 context tiers with auto-summing percentage sliders
- `SystemTimeouts.tsx` — WebSocket idle timeout, API request timeout, retry configuration
- `DefaultModelSection.tsx` — Model selection with token limit display from `get_model_limits()`
- All components under `components/settings/`
- Profile selector in `AiTab.tsx` reads/writes via `TokenLimitsApi`
- Save-on-change with debounce
- "Reset to defaults" button per section

### mem0 Integration

- `apps/api/narrare/writing/memory_deps.py` (new): Creates `create_memory_client()` with settings
- Reads `config.memory_llm_model` and `config.memory_embedding_model`
- Memory router starts using real client instead of `NullMemoryClient()`

## Constraints & Edge Cases

- **Validation**: Percentages in context budget must sum to 100%; enforced client- and server-side
- **Safe defaults**: Code defaults always exist as fallback — invalid env var values fall through to code default
- **Migration**: New DB tables need Alembic migration
- **Atomicity**: Partial save of budget percentages is not possible — all 5 values are saved/validated together
- **Scope**: Sysadmin/env-var settings (retry, timeouts) are *read-only* in the UI — only visible, not editable by end users
- **Feature interaction**: `token_limit_profile` from SET-003 (per-task model config) maps to the Output Limits profiles — the profile name selects the row in the table

## Implementation

See the [Data Migration & Deprecation Plan](../architecture/implementation-plans/SET-005-data-migration-plan.md) for detailed implementation steps and migration strategy.

Phase 1 (SET-005) delivered:
- `token_limits/` module: contracts, models, schemas, repository, service, router
- Data migration from old columns → new tables (non-destructive, idempotent)
- Three-layer resolution cascade
- Writing deps integration (`get_writing_service`, `get_extend_service`, `get_rewrite_service`, `get_summary_service`)
- WS handler integration
- Dual-write in `UserAiSettingsService` + `ProjectAiSettingsService`
- Profile name fix: `"long"` → `"long_texts"`
- Model limits validation via `get_model_limits()`
- Frontend profile read/write via `TokenLimitsApi`

## Related Features

- [SET-001](SET-001-user-settings.md) — User settings base
- [SET-003](SET-003-model-config.md) — Per-task Model Configuration (token_limit_profile)
- [CR-08 audit](../../_audit/results/content-review/cr-08-hardcoded-values.md) — Audit that motivated this feature
- [INFRA-005](../../../docs/features/infra/INFRA-005-memory-layer.md) — Memory Layer (mem0 embedding model config)

## Status & History

- `2026-05-24` — Created from CR-08 audit findings
| 2026-05-26 | Phase 1 implemented | Stable |
