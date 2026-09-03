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

if TYPE_CHECKING:
    from pydantic_ai.settings import ModelSettings, ThinkingLevel
    from pydantic_ai.usage import UsageLimits

    from narrare_core.llm.model_config import ResolvedModelConfig

_ZAI_THINKING_LEVEL: ThinkingLevel = "low"
"""Default thinking effort for Z.AI models.

GLM models (notably glm-5.3-flash) think extensively by default — measured
~50k reasoning tokens on a 6.3k-token extraction prompt (~7 min), while
``reasoning_effort: "low"`` completes the same task in ~22s / 872 completion
tokens (verified via direct API probe). pydantic-ai's unified ``thinking``
setting maps to ``reasoning_effort`` for OpenAI-compatible endpoints; the
Z.AI provider profile declares ``supports_thinking=True`` so the setting
resolves (see :data:`narrare_core.llm._providers.zai._ZAI_MODEL_PROFILE`).
"""


def get_cache_settings(config: ResolvedModelConfig) -> ModelSettings:
    """Build provider-specific ModelSettings for prompt caching.

    Returned as kwargs dict for ``Agent.run(model_settings=...)``.
    """
    return cast("ModelSettings", build_model_settings(config.provider_name, config.cache))


def build_runtime_model_settings(
    config: ResolvedModelConfig,
    usage_limits: UsageLimits | None,
) -> ModelSettings | None:
    """Build provider model_settings merged with the output-token limit.

    Cache/provider settings come from :func:`get_cache_settings`. When
    ``usage_limits.output_tokens_limit`` is set, it is forwarded as
    ``model_settings["max_tokens"]`` (ADR-045 contract) so the provider
    enforces the same ceiling applied via ``UsageLimits``. The explicit
    runtime limit takes precedence over any provider-derived value.

    Z.AI configs additionally receive a ``thinking`` default
    (:data:`_ZAI_THINKING_LEVEL`) — GLM models think extensively by default,
    which stalls extraction-class runs; this single point covers every
    ``run()``/``stream()`` path routed through the gateway.
    """
    base = get_cache_settings(config)
    settings: dict[str, object] = dict(base) if base else {}
    if usage_limits is not None and usage_limits.output_tokens_limit is not None:
        settings["max_tokens"] = usage_limits.output_tokens_limit
    if config.provider_name == "zai":
        settings["thinking"] = _ZAI_THINKING_LEVEL
    return cast("ModelSettings", settings) if settings else None
