# FIND-001 – Output token limits are configured but not reliably enforced

Status: resolved
Source: CR-03 Feature-Adoption audit, 2026-06-12
Priority: 🔴 High

Resolved: 2026-06-19 via ADR-045 runtime adoption enforcement.

## Summary

The original audit found that Narrare had intent-specific output profiles (`quick`,
`balanced`, `long_texts`, `comprehensive`) and user/project token-limit settings, but
the audited model-call path did not reliably apply those limits to `agent.run()` /
`agent.run_stream()`.

**Resolution summary (2026-06-19):** ADR-045 added run-limit enforcement infrastructure
and coverage at the LLM runtime boundary. `ResolvedRunLimits` and
`DefaultRunLimitResolver` convert output-budget decisions into provider-safe runtime
limits, and ModelRegistry run/stream tests cover applying those limits. Adoption now
reports `PASS 0.97` with all 29 modes runtime-verified + adopted.

## Original Evidence

- `ResolvedModelConfig.resolve_output_limit()` maps profiles/settings to numeric output limits (profile calibration itself is resolved; see historical FIND-004).
- `IntentOutputBudgetResolverImpl` records output-budget decisions for invocation evidence.
- `packages/core/narrare_core/llm/gateway.py:119-126` derives `usage_limits` in `ModelRegistry.get_model()`, but the method returns only `factory(...)`; the derived limits are not attached to the returned model or returned to callers.
- `packages/core/narrare_core/llm/gateway.py:178-194` passes `usage_limits` to `agent.run()` only from the explicit method argument, not from the config-derived limits computed inside `get_model()`.
- `packages/core/narrare_core/llm/gateway.py:249-262` creates the streaming agent and calls `agent.run_stream(user_prompt, model_settings=...)` without `usage_limits` or an output-token setting.
- `packages/core/narrare_core/writing/_invocation_adapter.py:125-149` prepares/finalizes invocation budget evidence, but builds the prompt through the original `PromptContext`; this reinforces that evidence and enforcement must be bound at the actual model-call boundary.

## Original Root Cause

The token-limit architecture split configuration/evidence from enforcement. Profiles and budgets are resolved in settings/AI-invocation layers, but the LLM gateway boundary does not consistently translate the resolved decision into pydantic-ai run settings or provider-specific max-output settings.

## Original User Impact

- CR-03 adoption can claim budget resolution while model calls may still run without the intended output cap.
- Long-form modes can still be silently truncated by provider defaults or grow beyond intended budgets depending on provider behavior.
- UI/self-host token settings may give users a false sense of control.
- Runtime and audit evidence can diverge: the system can prove that a profile was selected without proving that the provider invocation honored it.

## Sustainable Recommendation

Enforce resolved output limits at the LLM gateway/agent boundary. The accepted fix should:

1. Resolve the final output limit from intent/profile/user/project settings.
2. Pass it to the actual pydantic-ai/model invocation through the correct `ModelSettings` or provider setting.
3. Add regression tests proving `run()` and `stream()` apply the limit.
4. Keep evidence tied to the same invocation that reaches the model.

## Resolution Evidence

- ADR-045 accepted and implemented.
- `ResolvedRunLimits` / `DefaultRunLimitResolver` cover the enforcement contract.
- ModelRegistry run and stream usage-limit tests cover the runtime boundary.
- Adoption gate now requires correlated runtime evidence for PASS and reports all 29
  modes runtime-verified + adopted.

## Related CR Task

- `CR-AUFG-03-01`
- `CR-AUFG-03-06`
- `CR-AUFG-03-07`

## Related Findings

- Historical `FIND-004` remains resolved; it covered profile calibration. This finding covers runtime enforcement.
