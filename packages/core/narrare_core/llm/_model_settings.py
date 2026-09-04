"""Provider-specific ModelSettings construction for ModelRegistry.

Holds the stateless settings helpers that previously lived on
:class:`~narrare_core.llm.gateway.ModelRegistry`. Extracted to respect
RULE-04 (file size limits): modularise, do not minify.

This is an internal module — it is intentionally **not** re-exported from
:mod:`narrare_core.llm`. The public surface is
:meth:`ModelRegistry.get_cache_settings`, which delegates here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from narrare_core.llm._providers.cache_settings import build_model_settings
from narrare_core.llm.thinking_policy import resolve_thinking_level

if TYPE_CHECKING:
    from pydantic_ai.settings import ModelSettings
    from pydantic_ai.usage import UsageLimits

    from narrare_core.llm.intents import LLMIntent
    from narrare_core.llm.model_config import ResolvedModelConfig


def get_cache_settings(config: ResolvedModelConfig) -> ModelSettings:
    """Build provider-specific ModelSettings for prompt caching.

    Returned as kwargs dict for ``Agent.run(model_settings=...)``.
    """
    return cast("ModelSettings", build_model_settings(config.provider_name, config.cache))


def build_runtime_model_settings(
    config: ResolvedModelConfig,
    usage_limits: UsageLimits | None,
    intent: LLMIntent | None = None,
) -> ModelSettings | None:
    """Build provider model_settings merged with runtime policy settings.

    Cache/provider settings come from :func:`get_cache_settings`. When
    ``usage_limits.output_tokens_limit`` is set, it is forwarded as
    ``model_settings["max_tokens"]`` (ADR-045 contract) so the provider
    enforces the same ceiling applied via ``UsageLimits``. The explicit
    runtime limit takes precedence over any provider-derived value.

    When ``intent`` is provided, a thinking level is resolved via
    :func:`narrare_core.llm.thinking_policy.resolve_thinking_level`
    (universal, intent-aware — replaced the former zai-only thinking
    default). ``intent=None`` omits the key entirely. Providers without
    thinking support drop the key at request time (pydantic-ai
    ``supports_thinking`` profile gate), making the policy
    provider-universal.
    """
    base = get_cache_settings(config)
    settings: dict[str, object] = dict(base) if base else {}
    if usage_limits is not None and usage_limits.output_tokens_limit is not None:
        settings["max_tokens"] = usage_limits.output_tokens_limit
    if intent is not None:
        thinking = resolve_thinking_level(intent)
        if thinking is not None:
            settings["thinking"] = thinking
    return cast("ModelSettings", settings) if settings else None
