---
id: SET-005
title: "Configurable Token Limits"
status: in-progress
phase: 1
area: settings
mvp: false

ui_tooltip: "Review token settings; CR-08 phases are enforced."
ui_help_short: |
  View and edit token-limit settings. CR-08 phases are enforced; ADR-051 remains open.
ui_help_long: |
  SET-005 gives Narrare a storage/API/UI cascade for output-limit profiles,
  context-budget percentages, and system timeout visibility. Defaults and saved
  overrides live in one place instead of being scattered through code or env files.

  CR-08 P0-P4 now prove the main runtime paths, profile vocabulary, UI/API/Core
  parity, model-limit calibration, model suitability warnings, governed defaults,
  and future audit-template enforcement. SET-005 remains in-progress only because
  ADR-051 is still Proposed and must be accepted or superseded before final
  stable/resolved language is truthful.

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
percentages, and timeout-related configuration. CR-08 P0-P4 now have
implementation/enforcement evidence for the runtime-effect paths, operator defaults,
long-tail governed defaults, and future audit-template gate. SET-005 remains
`in-progress` because ADR-051 is still Proposed.

> **CR-08 status note (2026-06-20):** SET-005's storage/API/UI cascade exists (✅),
> and CR-08 P0-P4 have phase-scoped implementation/enforcement evidence for
> output-limit enforcement, tier-budget consumption, token-profile parity/FIND-013,
> model-limit calibration, model suitability warnings/blocks, operator/default
> governance, long-tail governed defaults, truthful status taxonomy, and the future
> audit-template matrix gate. Do not claim full SET-005 stability until ADR-051 is
> accepted or superseded. Remediation is specified in
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
6. Changes save through the Settings cascade. CR-08 P0-P4 controls/defaults have phase-specific implementation/enforcement evidence; final stable language still waits for ADR-051 acceptance or supersession.
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

### Core Changes

Core owns the runtime token contracts and model-boundary enforcement used by P0/P1.
Settings-to-runtime adoption remains phase-scoped: CR-AUFG-08-01/02/03/04/05/06/07/08/09/10/11/12/13/14
have implementation/enforcement evidence, while ADR-051 remains Proposed.

**`packages/core/narrare_core/writing/budget.py`:**
- `TokenBudgetManager` constructor accepts optional `tier_overrides` dict
- `_BASE_PERCENTAGES` and `_FIRST_CHAPTER_PERCENTAGES` become overridable
- API: `TokenBudgetManager(total_budget=6000, tier_overrides={"immediate": 0.40})`

**`packages/core/narrare_core/llm/intents.py`:**
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
| `token_limits/models.py` | `UserTokenLimits` + `ProjectTokenLimits` SQLAlchemy models |
| `token_limits/schemas.py` | Pydantic request/response schemas |
| `token_limits/contracts.py` | `TokenLimitsServiceProtocol`, `TokenLimitsRepositoryProtocol` |
| `token_limits/repository.py` | CRUD for token limits overrides |
| `token_limits/service.py` | Cascade resolution logic + merge with env/code defaults |
| `token_limits/router.py` | REST endpoints under `/api/v1/settings/token-limits` |

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

See the [Data Migration & Deprecation Plan](../../architecture/implementation-plans/SET-005-data-migration-plan.md) for detailed implementation steps and migration strategy.

SET-005 storage/API/UI foundation delivered (legacy SET-005 work; not full CR-08
runtime-effect closure):
- `token_limits/` module: contracts, models, schemas, repository, service, router
- Data migration from old columns → new tables (non-destructive, idempotent)
- Three-layer resolution cascade
- Writing deps integration (`get_writing_service`, `get_extend_service`, `get_rewrite_service`, `get_summary_service`)
- WS handler integration
- Dual-write in `UserAiSettingsService` + `ProjectAiSettingsService`
- Profile name fix: `"long"` → `"long_texts"`
- Model limits validation via `get_model_limits()`
- Frontend profile read/write via `TokenLimitsApi`

CR-08 P1 delivered (2026-06-20; not full CR-08 closure):
- Core token profile vocabulary: `quick`, `balanced`, `long_texts`, `comprehensive`, `custom`
- `conservative` removed from the public contract; legacy persisted values normalize to `balanced`
- `custom` uses raw `output_limit`; known provider ceilings still cap at runtime
- Backend metadata exposes profile/cap/calibration/suitability information
- Frontend supports custom limits above 16k and renders calibration/suitability warnings
- Platform cross-layer contract tests and configuration matrix evidence gate protect parity

CR-08 P2/P3/P4 delivered (2026-06-20; still not full CR-08 lifecycle closure):
- P2 operator/default governance covers inline suggest cap, consistency caps,
  setup fallback/Ollama defaults, system/background model defaults, and operator
  defaults; evidence is recorded in the Configuration Adoption Matrix.
- P3 governed-defaults manifest classifies embedding search defaults, name dedup
  caps, and SSE/connect/retry defaults with rationale, review triggers, override
  paths, discovery paths, and concrete test paths.
- P4 status taxonomy and audit-template hardening distinguish phase-complete
  implementation/enforcement from ADR-051 final resolution. Future structured
  material P0/P1 configuration/effect findings fail the matrix gate if not
  classified.

Historical consistency integration delivered (legacy SET-005 work; separate from the
CR-AUFG-08-02 P0 evidence for `tier_percentages` → `WritingContextAssembler`):
- Consistency module integration: `checker_service.py` resolves limits via `TokenLimitsService`
- `prompt_builder.py` accepts `max_chapter_tokens` parameter instead of hardcoded `MAX_CONSISTENCY_CONTEXT_TOKENS`
- `checker_helpers.py` accepts `max_kb_entries` parameter instead of hardcoded `MAX_KB_ENTRIES`
- `consistency/deps.py` factory wires TokenLimitsService injection
- New fields: `max_chapter_tokens: int = 2000`, `max_kb_entries: int = 100`

Remaining CR-08 lifecycle blocker is tracked in
[`CR-08 Remediation — Configuration/Effect Drift`](../remediation/cr-08-configuration-effect-drift.md).
P0-P4 are implemented/enforced; ADR-051 remains Proposed until accepted or superseded.

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
| 2026-06-20 | CR-08 P0-P4 implementation/enforcement evidence recorded for token limit enforcement, tier percentages, profile parity/FIND-013, model calibration, suitability warnings/blocks, operator/default governance, long-tail governed defaults, and audit-template matrix hardening; ADR-051 decision remains open | In Progress |
