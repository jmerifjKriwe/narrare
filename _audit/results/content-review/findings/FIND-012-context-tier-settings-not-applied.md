# FIND-012 — Context tier settings are exposed but not applied at runtime

Priority: 🔴 High
Status: identified / open
Source: CR-08 Hardcoded Values & Configurability audit, 2026-06-12

## Finding

Narrare exposes writing context tier percentages as configurable settings, but production writing context assembly still uses hardcoded/default tier allocations. This creates a false-control risk: users can adjust context budget sliders, yet generated writing context can continue to use the bundled defaults.

## Evidence

- `TokenLimitOverrides.tier_percentages` defines configurable tier percentages for `immediate`, `recent`, `kb_referenced`, `kb_suggested`, and `pinned` (`apps/api/narrare/settings/token_limits/contracts.py:36-44`).
- The token-limits API returns `tier_percentages` and accepts updates through `UpdateTokenLimitsRequest` (`apps/api/narrare/settings/token_limits/router.py:73-80`; `apps/api/narrare/settings/token_limits/schemas.py:21-29`, `47`).
- The Settings UI renders sliders for the same tiers and writes updates through `handleTierPercentagesChange()` (`packages/web/components/studio/settings/AiTab.tsx:151-164`; `packages/web/components/studio/settings/ContextBudget.tsx:69-157`; `packages/web/components/studio/settings/useAiTabData.ts:103-109`).
- `TokenBudgetManager` can accept `tier_overrides` (`packages/core/narrare_core/context/budget.py:101-119`), but `WritingContextAssembler.__init__()` only accepts `total_budget` and `token_counter`, then constructs `TokenBudgetManager(total_budget)` without overrides (`packages/core/narrare_core/writing/context_assembler.py:69-77`).
- Production writing factories instantiate `WritingContextAssembler()` without resolved token-limit settings (`apps/api/narrare/writing/deps_pipeline.py:40-47`; `apps/api/narrare/writing/router_sessions.py:95-103`).
- `WritingPipeline.stream()` calls `self._context_assembler.assemble(...)` without any tier override argument (`packages/core/narrare_core/writing/pipeline.py:135-152`).

## Root Cause

The settings/UI layer and the context assembly layer evolved separately. The token-limit cascade stores and displays tier percentages, while the production assembler constructor does not expose or receive those resolved percentages. The underlying `TokenBudgetManager` is capable of applying overrides, but the dependency factories do not bridge the resolved settings into that manager.

## User Impact

- Authors may believe they have increased/decreased KB, recent-chapter, or pinned context priority when the LLM receives the default distribution.
- Context Inspector metadata can appear governed by settings while the actual allocation remains fixed.
- CR-03/CR-08 adoption evidence overstates token-budget configurability for input context.

## Sustainable Recommendation

Wire the existing cascade through the existing abstraction:

1. Extend `WritingContextAssembler` to accept validated tier overrides and pass them to `TokenBudgetManager`.
2. Resolve `TokenLimitOverrides` in writing dependency factories and pass `tier_percentages` into the assembler/pipeline.
3. Keep defaults in code as fallback only; user/project/operator layers should override them through `TokenLimitsService`.
4. Add regression tests proving a changed `kb_suggested`/`immediate` percentage changes generated tier budgets and context metadata.

## Related CR Tasks

- `CR-AUFG-08-02`
