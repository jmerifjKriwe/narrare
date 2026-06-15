"""Runtime output-budget enforcement for pydantic-ai runs.

The resolver converts Narrare output budgets and model ceilings into the
``UsageLimits`` and ``ModelSettings`` values applied at the Core LLM/agent
boundary for both run and stream paths.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai.usage import UsageLimits

from narrare_core.llm.cost_rates import get_model_limits

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from uuid import UUID

    from narrare_core.ai_invocation.budgets import OutputBudgetDecision
    from narrare_core.llm.cost_rates import ModelLimits
    from narrare_core.llm.model_config import ResolvedModelConfig


class ResolvedRunLimits(BaseModel):
    """Provider-safe runtime limits for one AI invocation."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    invocation_id: UUID
    output_budget_profile: str | None = None
    max_output_tokens: int | None = Field(default=None, gt=0)
    provider_max_output_tokens: int | None = Field(default=None, gt=0)
    effective_output_tokens: int | None = Field(default=None, gt=0)
    usage_limits: UsageLimits | None = None
    model_settings: Mapping[str, object] = Field(default_factory=dict)
    source: str


class DefaultRunLimitResolver:
    """Default implementation of the ADR-045 RunLimitResolver contract."""

    def __init__(
        self,
        *,
        model_limits_provider: Callable[[str, str], ModelLimits | None] = get_model_limits,
    ) -> None:
        self._model_limits_provider = model_limits_provider

    def resolve(
        self,
        *,
        config: ResolvedModelConfig,
        budget: OutputBudgetDecision | None,
        invocation_id: UUID,
    ) -> ResolvedRunLimits:
        """Resolve provider-safe usage limits and model settings."""
        requested_tokens = _requested_output_tokens(config, budget)
        profile = _requested_profile(config, budget)
        source = budget.source if budget is not None else "model_config"

        provider_limits = self._model_limits_provider(config.provider_name, config.model_id)
        provider_max = provider_limits.output if provider_limits is not None else None
        effective_tokens = requested_tokens
        if provider_max is not None and requested_tokens > provider_max:
            effective_tokens = provider_max
            source = f"{source}:capped_to_provider_max"
        elif provider_max is None:
            source = f"{source}:provider_max_unknown"

        usage_limits = UsageLimits(output_tokens_limit=effective_tokens)
        return ResolvedRunLimits(
            invocation_id=invocation_id,
            output_budget_profile=profile,
            max_output_tokens=requested_tokens,
            provider_max_output_tokens=provider_max,
            effective_output_tokens=effective_tokens,
            usage_limits=usage_limits,
            model_settings={"max_tokens": effective_tokens},
            source=source,
        )


def _requested_output_tokens(
    config: ResolvedModelConfig,
    budget: OutputBudgetDecision | None,
) -> int:
    if budget is not None:
        return budget.budget.max_tokens
    return config.resolve_output_limit()


def _requested_profile(
    config: ResolvedModelConfig,
    budget: OutputBudgetDecision | None,
) -> str | None:
    if budget is not None:
        return budget.budget.profile
    return config.token_limit_profile


def merge_model_settings(
    base: Mapping[str, object] | None,
    limits: ResolvedRunLimits | None,
) -> dict[str, object] | None:
    """Merge cache/provider settings with run-limit model settings."""
    merged: dict[str, object] = {}
    if base is not None:
        merged.update(base)
    if limits is not None:
        merged.update(limits.model_settings)
    return merged or None


def profile_to_usage_limits(profile: str) -> UsageLimits | None:
    """Convert a named token limit profile to UsageLimits.

    These profiles are stored in user_ai_settings and project_settings
    as the ``token_limit_profile`` column.

    Args:
        profile: One of "quick", "balanced", "long_texts", "comprehensive",
            "conservative", "custom".

    Returns:
        Configured UsageLimits, or None if the profile is unknown.
    """
    profiles: dict[str, dict[str, int]] = {
        "quick": {"request_limit": 10, "total_tokens_limit": 16000},
        "balanced": {"request_limit": 25, "total_tokens_limit": 64000},
        "long_texts": {"request_limit": 25, "total_tokens_limit": 128000},
        "comprehensive": {"request_limit": 25, "total_tokens_limit": 256000},
        "conservative": {"request_limit": 10, "total_tokens_limit": 32000},
        "custom": {"request_limit": 25, "total_tokens_limit": 64000},  # falls back to balanced
    }
    limits = profiles.get(profile)
    if limits is None:
        return None
    return UsageLimits(
        request_limit=limits["request_limit"],
        total_tokens_limit=limits["total_tokens_limit"],
    )


def resolve_runtime_limits(
    resolver: DefaultRunLimitResolver,
    *,
    config: ResolvedModelConfig,
    resolved_limits: ResolvedRunLimits | None,
    output_budget: OutputBudgetDecision | None,
) -> ResolvedRunLimits | None:
    """Resolve ADR-045 limits for run/stream when applicable.

    Returns pre-resolved limits as-is, or resolves from budget/profile
    when applicable. Returns None when no limits are needed.
    """
    if resolved_limits is not None:
        return resolved_limits
    if output_budget is None and not config.token_limit_profile:
        return None
    return resolver.resolve(
        config=config,
        budget=output_budget,
        invocation_id=uuid4(),
    )


def _rebuild_forward_refs() -> None:
    """Resolve Pydantic forward refs for ResolvedRunLimits."""
    from collections.abc import Mapping
    from uuid import UUID

    ResolvedRunLimits.model_rebuild(
        _types_namespace={"Mapping": Mapping, "UUID": UUID},
    )


_rebuild_forward_refs()
