---
id: SET-005
title: "Configurable Token Limits"
status: stable
phase: 1
area: settings
mvp: false

ui_tooltip: "Review and tune token-limit settings; changes take effect at the model boundary."
ui_help_short: |
  View and edit token-limit settings. Changes flow through the resolution cascade
  and take effect at the model/context boundary.
ui_help_long: |
  SET-005 gives Narrare a storage/API/UI cascade for output-limit profiles,
  context-budget percentages, and system timeout visibility. Defaults and saved
  overrides live in one place instead of being scattered through code or env files.

  CR-08 (resolved under ADR-051, accepted 2026-06-20) proved the main runtime
  paths, profile vocabulary, UI/API/Core parity, model-limit calibration, model
  suitability warnings, governed defaults, and future audit-template enforcement.
  Every user/project-facing setting now has a source → resolver → runtime consumer
  → enforcement test chain recorded in the Configuration Adoption Matrix.

  The Settings tab shows three groups:
  - **Output Limits** — Stored per-call generation limit profiles and values
    (quick/balanced/long_texts/comprehensive presets, or custom raw token values)
  - **Context Budget** — How the total token budget is distributed across
    context tiers (immediate chapter, recent history, KB entities, pinned items)
  - **System Timeouts** — WebSocket idle timeout, API request timeout, retry config
ui_available_in: [settings]
---

# [SET-005] — Configurable Token Limits

## What it does

Provides a Settings surface and persistence/API cascade for token limits, budget
percentages, and timeout-related configuration. CR-08 (P0–P4) is resolved under
ADR-051 (accepted 2026-06-20): runtime-effect paths, operator defaults, long-tail
governed defaults, and the future audit-template gate all have implementation,
enforcement, and cross-layer evidence. SET-005 is `stable`.

> **CR-08 status note (2026-06-20):** SET-005's storage/API/UI cascade exists (✅),
> and CR-08 P0-P4 have phase-scoped implementation/enforcement evidence for
> output-limit enforcement, tier-budget consumption, token-profile parity/FIND-013,
> model-limit calibration, model suitability warnings/blocks, operator/default
> governance, long-tail governed defaults, truthful status taxonomy, and the future
> audit-template matrix gate. ADR-051 was accepted 2026-06-20, satisfying the final
> lifecycle criterion for SET-005 stability. Remediation is specified in
> [`docs/features/remediation/cr-08-configuration-effect-drift.md`](../remediation/cr-08-configuration-effect-drift.md).

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
3. **Output Limits** shows a table of features (Draft, Summary, Suggest, Continue, Consistency, etc.) each with a dropdown: *quick* / *balanced* / *long_texts* / *comprehensive* — or a *custom* raw token input for precise control
4. **Context Budget** shows the 5-tier pie chart (immediate/recent/kb_referenced/kb_suggested/pinned) with percentage sliders that automatically adjust to total 100%
5. **System** shows WebSocket timeout (seconds), retry count, API timeout
6. Changes save through the Settings cascade and take effect at the model/context boundary (proven by CR-08 enforcement evidence under ADR-051).
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

**Model Data Source:** Model-limit suggestions use [models.dev](https://models.dev) data where available. See [Model Data Reference](../../reference/model-data.md) for details on how model specifications are fetched, cached, and refreshed. CR-AUFG-08-07/11 are implemented with calibration metadata and suitability-warning/block evidence.

### Context Budget Keys (ADR-082 / C5, 2026-08-15)

Input-context token budgets joined the cascade (previously hardcoded
constants bypassing it — CR-08 P0):

| Key | Default | Bounds | Meaning |
|---|---|---|---|
| `context_total_budget` | 32,000 | ≥ 1,024 | Total input-context ceiling for writing **and** analysis (one knob) |
| `series_history_budget` | 16,000 | ≥ 1,024 | Series-history block ceiling **within** the total (guarded carve-out: effective = `min(configured, 50% × effective_total)`) |

Operator env: `NARRARE_CONTEXT_TOTAL_BUDGET` / `NARRARE_SERIES_HISTORY_BUDGET`
(`apps/api/narrare/_app/settings_model.py`). Defaults single-sourced from
`narrare_core.context.budget` (no backend/Core drift possible).

Model-boundary capping (ADR-082 Decision 3/4): `DefaultContextBudgetResolver`
(`packages/core/narrare_core/context/budget_resolver.py`) caps every input
budget against the configured model's context window:
`effective = min(configured, window − reserve)` with
`reserve = min(4,000 + effective_output_limit, window // 4)`. Unknown window
(offline, no cache) → uncapped passthrough, tagged
`cascade:window_unknown` (RULE-11 — never blocks generation). The resolver
only ever caps **down** (min() principle — scaling up requires explicit user
configuration).

**CR-08 P0 closure note (2026-08-15):** this closes the remaining P0 item
"model-boundary/tier-budget adoption" — all four previously hardcoded
constants (writing 6,000→32,000; analysis 6,000→32,000; series-history
512→16,000 ×2) now flow through the cascade and adopt the model boundary,
completing what `run_limits.py` did for the output side (input-side
capping). No UI in C5 (expert-invisible; the existing token-limits PATCH
API is the configuration surface).

### Core Changes

Core owns the runtime token contracts and model-boundary enforcement used by P0/P1.
Settings-to-runtime adoption is proven end-to-end: CR-AUFG-08-01/02/03/04/05/06/07/08/09/10/11/12/13/14
have implementation/enforcement evidence, and ADR-051 is accepted (2026-06-20).

**`packages/core/narrare_core/writing/budget.py`:**
- `TokenBudgetManager` constructor accepts optional `tier_overrides` dict
- `_BASE_PERCENTAGES` and `_FIRST_CHAPTER_PERCENTAGES` become overridable
- API: `TokenBudgetManager(total_budget=6000, tier_overrides={"immediate": 0.40})`

**`packages/core/narrare_core/llm/intents/__init__.py`** (intent types) / **`packages/core/narrare_core/llm/model_config.py`** (`ResolvedModelConfig`):
- `ResolvedModelConfig` gains `resolve_output_limit(profile: str) -> int` method
- Maps token_limit_profile (`quick`/`balanced`/`long_texts`/`comprehensive`/`custom`) to preset or raw token values
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
| `apps/api/narrare/settings/token_limits/models.py` | `UserTokenLimits` + `ProjectTokenLimits` SQLAlchemy models |
| `apps/api/narrare/settings/token_limits/schemas.py` | Pydantic request/response schemas |
| `apps/api/narrare/settings/token_limits/contracts.py` | `TokenLimitsServiceProtocol`, `TokenLimitsRepositoryProtocol` |
| `apps/api/narrare/settings/token_limits/repository.py` | CRUD for token limits overrides |
| `apps/api/narrare/settings/token_limits/service.py` | Cascade resolution logic + merge with env/code defaults |
| `apps/api/narrare/settings/token_limits/router.py` | REST endpoints under `/api/v1/settings/token-limits` |

### Backend Resolver Integration

Several writing dependency factories resolve settings through `TokenLimitsService`
instead of raw `resolve_output_limit()`. CR-AUFG-08-01 now has model-boundary
enforcement evidence at `run()`/`stream()`/agent boundaries; future changes must keep
that source → resolver → runtime consumer chain intact.

- `apps/api/narrare/writing/deps.py`: `get_writing_service()`, `get_extend_service()`, `get_rewrite_service()` resolve limits via `TokenLimitsService.get_resolved_limits()`
- `apps/api/narrare/writing/summary_deps.py`: `get_summary_service()` uses `TokenLimitsService` instead of `resolve_output_limit()`
- `apps/api/narrare/writing/router_sessions.py`: Resolves `output_limit` + `ws_timeout` dynamically via `TokenLimitsService.get_resolved_limits()` — no more hardcoded 2000
- `apps/api/narrare/writing/ws_handler.py`: Reads `settings.ws_idle_timeout_seconds`

### Dual-Write Mode

The old columns (`user_ai_settings.token_limit_overrides`, `project_ai_settings.token_limit_profile`) still exist but are deprecated. Both `UserAiSettingsService` and `ProjectAiSettingsService` write to both old columns and the new `TokenLimitsService` tables. Writes through the old path emit a deprecation warning.

### Frontend

- `packages/web/components/studio/settings/ContextBudget.tsx` — Token budget distribution across 5 context tiers with auto-summing percentage sliders
- `packages/web/components/studio/settings/SystemTimeouts.tsx` — WebSocket idle timeout, API request timeout, retry configuration
- `packages/web/components/studio/settings/DefaultModelSection.tsx` — Model selection with token limit display from `get_model_limits()`
- All components under `packages/web/components/studio/settings/`
- Profile selector in `packages/web/components/studio/settings/AiTab.tsx` reads/writes via `TokenLimitsApi`
- Save-on-change with debounce
- "Reset to defaults" button per section

### mem0 Integration

- `apps/api/narrare/memory/dependencies.py` (new): Creates `create_memory_client()` with settings
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

See the [Data Migration & Deprecation Plan](../../architecture/implementation-plans/SET-005-data-migration-plan.md) for detailed implementation steps and migration strategy.

SET-005 storage/API/UI foundation delivered (legacy SET-005 work; preceded the
CR-08 runtime-effect closure that followed):
- `token_limits/` module: contracts, models, schemas, repository, service, router
- Data migration from old columns → new tables (non-destructive, idempotent)
- Three-layer resolution cascade
- Writing deps integration (`get_writing_service`, `get_extend_service`, `get_rewrite_service`, `get_summary_service`)
- WS handler integration
- Dual-write in `UserAiSettingsService` + `ProjectAiSettingsService`
- Profile name fix: `"long"` → `"long_texts"`
- Model limits validation via `get_model_limits()`
- Frontend profile read/write via `TokenLimitsApi`

CR-08 P1 delivered (2026-06-20):
- Core token profile vocabulary: `quick`, `balanced`, `long_texts`, `comprehensive`, `custom`
- `conservative` removed from the public contract; legacy persisted values normalize to `balanced`
- `custom` uses raw `output_limit`; known provider ceilings still cap at runtime
- Backend metadata exposes profile/cap/calibration/suitability information
- Frontend supports custom limits above 16k and renders calibration/suitability warnings
- Platform cross-layer contract tests and configuration matrix evidence gate protect parity

CR-08 P2/P3/P4 delivered (2026-06-20):
- P2 operator/default governance covers inline suggest cap, consistency caps,
  setup fallback/Ollama defaults, system/background model defaults, and operator
  defaults; evidence is recorded in the Configuration Adoption Matrix.
- P3 governed-defaults manifest classifies embedding search defaults, name dedup
  caps, and SSE/connect/retry defaults with rationale, review triggers, override
  paths, discovery paths, and concrete test paths.
- P4 status taxonomy and audit-template hardening record phase-complete
  implementation/enforcement alongside the accepted ADR-051 lifecycle resolution.
  Future structured material P0/P1 configuration/effect findings fail the matrix
  gate if not classified.

Historical consistency integration delivered (legacy SET-005 work; separate from the
CR-AUFG-08-02 P0 evidence for `tier_percentages` → `WritingContextAssembler`):
- Consistency module integration: `apps/api/narrare/consistency/checker_service.py` resolves limits via `TokenLimitsService`
- `apps/api/narrare/consistency/prompt_builder.py` accepts `max_chapter_tokens` parameter instead of hardcoded `MAX_CONSISTENCY_CONTEXT_TOKENS`
- `apps/api/narrare/consistency/checker_helpers.py` accepts `max_kb_entries` parameter instead of hardcoded `MAX_KB_ENTRIES`
- `apps/api/narrare/consistency/deps.py` factory wires TokenLimitsService injection
- New fields: `max_chapter_tokens: int = 2000`, `max_kb_entries: int = 100`

CR-08 lifecycle is resolved — see
[`CR-08 Remediation — Configuration/Effect Drift`](../remediation/cr-08-configuration-effect-drift.md).
P0-P4 are implemented/enforced; ADR-051 was accepted 2026-06-20, removing the final
lifecycle blocker for SET-005 stability.

## Related Features

- [SET-001](SET-001-user-settings.md) — User settings base
- [SET-003](SET-003-model-config.md) — Per-task Model Configuration (token_limit_profile)
- [CR-08 audit](../../../_audit/results/content-review/cr-08-hardcoded-values.md) — Audit that motivated this feature
- [INFRA-005](../infra/INFRA-005-memory-layer.md) — Memory Layer (mem0 embedding model config)

## Status & History

| Date | Change | Status |
|---|---|---|
| 2026-05-24 | Created from CR-08 audit findings | In Progress |
| 2026-05-26 | Storage/API/UI foundation implemented as legacy SET-005 work | In Progress |
| 2026-06-08 | Historical consistency integration implemented as legacy SET-005 work; not current CR-AUFG-08-02 closure | In Progress |
| 2026-06-18 | CR-08 reclassified runtime-effect adoption gaps; status remains in-progress until false controls are closed | In Progress |
| 2026-06-20 | CR-08 P0-P4 implementation/enforcement evidence recorded for token limit enforcement, tier percentages, profile parity/FIND-013, model calibration, suitability warnings/blocks, operator/default governance, long-tail governed defaults, and audit-template matrix hardening; ADR-051 accepted same date (RULE-18b elevated to CONSTRAINTS.md); CR-08 AUFG set resolved; SET-005 promoted to `stable` (cascade + runtime adoption + UI/API/Core parity + tests verified in the Configuration Adoption Matrix) | Stable |
| 2026-08-15 | CR-08 P0 closed (ADR-082/C5): `context_total_budget` (32k) + `series_history_budget` (16k) cascade keys, model-boundary input capping via `DefaultContextBudgetResolver`, all four hardcoded input budgets lifted | Stable |
