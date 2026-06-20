# CR-05: Finding Index — Current Status

> **Last updated:** 2026-06-20
> **Audit:** Content Review CR-05 consolidation after CR-01 through CR-04 rerun
> **Lifecycle:** status words follow `docs/development/finding-lifecycle.md` — `resolved` requires Design + Implementation + Enforcement evidence.
> **Note:** All CR-05 formal findings are now resolved and their individual `FIND-*.md` files have been deleted. This index is the historical record. Active CR-08 tracking lives in `docs/features/remediation/cr-08-configuration-effect-drift.md` (P2/P3/P4 + candidate ADR-051 remain open there).

## Open / active findings

None. All CR-05 formal findings are resolved (see table below).

## Resolved / historical findings

Verified against current code on 2026-06-20; finding files deleted because the described problem no longer exists. Do not reopen from stale wording unless new code evidence contradicts the resolution.

| Finding | Resolution evidence |
|---|---|
| FIND-001: Output token limits not reliably enforced | ✅ Resolved via ADR-045 — `ResolvedRunLimits`, `DefaultRunLimitResolver`, `build_runtime_model_settings()` apply output-token ceilings at the run/stream boundary; tests in `tests/unit/core/llm/test_run_limits.py`. |
| FIND-003: mem0 preference DI not wired | ✅ Resolved — `_get_preference_service_instance()` creates `PreferenceService` when mem0 + provider credentials are available and injects it into `PromptComposer` (`apps/api/narrare/_app/dependencies_prompts.py`). |
| FIND-004: Output token profiles under-calibrated | ✅ Resolved — `PROFILE_OUTPUT_LIMITS` (quick/balanced/long_texts/comprehensive) and `_INTENT_PROFILE_DEFAULTS` cover every routeable non-`EMBED` intent. |
| FIND-007: Project writing profile not consistently defined | ✅ Resolved — `core/project/profile.py::ProjectWritingProfile` with `to_prompt_variables()`; consumed by profiles/assembly, writing/context_assembler, prompts/context. |
| FIND-009: Timeline/graph consistency context incomplete | ✅ Resolved via ADR-044 (Staged Consistency Pipeline: `TimelineEventEnvelope`, `ExtractedFact`, `FactExtractorAgent`, enriched deps, SSE stage endpoint, Pydantic Evals) and ADR-050 (cross-feature KB envelope + ref lifecycle for all consumers). |
| FIND-010: Chat prompt surface drift | ✅ Resolved via ADR-049 — route table + manifest both map CHAT to `writing/chat`; orphan `_bundled/chat/` duplicate removed; PROMPT-IDENTITY/ROOT-MODE/PATH-DERIVABILITY/FRONTMATTER-MATCH/ORPHAN-TEMPLATE gates are CI-blocking. |
| FIND-011: Timeline analysis bypasses governed template | ✅ Resolved via ADR-049 — `timeline_analysis_service.py` migrated to `PromptComposer.build(LLMIntent.PLAN, mode="timeline")`; `_bundled/planning/en/timeline/system.md` is the runtime surface; INLINE-FEATURE-PROMPT gate enforces no regression. |
| FIND-012: Context tier settings exposed but not applied | ✅ Resolved via CR-08 P0 (2026-06-20) — `WritingContextAssembler.__init__` accepts `tier_overrides`; `deps_pipeline.create_pipeline()` forwards them; all four writing factories (`deps_writing.py`, `deps_extend.py`, `deps_rewrite.py`, `deps_coauthor.py`) pass `tier_overrides=limits.tier_percentages`; core tier-override enforcement in `tests/unit/core/writing/test_budget.py`. |
| FIND-013: Token settings UI/API/Core contract drift | ✅ Resolved via CR-08 P1 (2026-06-20) — canonical vocabulary in `core/llm/token_profiles.py`; Backend derives schemas from Core, rejects new `conservative`, normalizes legacy; Frontend `web/lib/token-profiles.ts` removes `conservative` and labels 16k as UX-recommended; enforcement tests `test_cr08_p1_token_profile_contract.py`, `test_cr08_p1_cross_layer_contract.py`, `test_cr08_p1_token_limit_metadata.py`, `test_token_profiles.py`. (CR-08 P2/P3/P4 + ADR-051 acceptance remain open — tracked in the CR-08 remediation spec, not here.) |

## Related tracking (not CR-05 findings)

- **CR-08 configuration-effect drift:** `docs/features/remediation/cr-08-configuration-effect-drift.md` — P0+P1 implementation-evidence complete; P2/P3/P4 open; candidate ADR-051 Proposed (not yet accepted).
- **CR-07 UX findings:** the `cr-07-*.md` files in this directory are CR-07 UX-audit findings (separate audit set); CR-07 is closed per `docs/_shared/CURRENT_STATE.md` (CR-07 UX Closure v2).

## Legacy CR-01/CR-02 task-only items

- CR-01 template-quality tasks: `CR-AUFG-01-01` through `CR-AUFG-01-06`.
- CR-02 chat prompt-injection drift: consolidated into (now-resolved) FIND-010.
- CR-02 worldbuilding phase2 / temporal-consistency prompt loader / `writing_graph_prompts.py` fallback: CR task backlog items unless a later review promotes them to formal finding files.
