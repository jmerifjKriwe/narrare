"""
Model configuration types — provider, model, caching, token limits.

Extracted from ``intents.py`` per RULE-04 (file size limit).
See :mod:`narrare_core.llm.intents` for :class:`LLMIntent` and related types.
"""

from __future__ import annotations

from dataclasses import dataclass

from narrare_core.llm.token_profiles import PROFILE_OUTPUT_LIMITS, resolve_output_limit_for_profile

__all__ = ["PROFILE_OUTPUT_LIMITS", "CacheSettings", "ResolvedModelConfig"]


@dataclass(frozen=True, slots=True)
class CacheSettings:
    """Prompt caching configuration for a resolved model.

    Provider-specific behavior:
    - Anthropic: Enables cache_control blocks on system prompt + tools.
    - OpenAI / Z.AI / Groq: Ignored (automatic server-side caching).
    - Google: Triggers explicit cached_contents creation.
    - Ollama: Ignored (no caching support).
    """

    enabled: bool = True
    ttl_seconds: int = 300  # Anthropic minimum: 300 (5min)
    max_cache_points: int = 4  # Anthropic limit: 4


@dataclass(frozen=True, slots=True)
class ResolvedModelConfig:
    """Fully resolved model configuration ready for the gateway.

    Contains everything the gateway needs to make an LLM call:
    which provider, which model, and generation parameters.

    This is the output of ``ModelRoutingResolver.resolve()`` and the
    input to ``ModelRegistry.run()`` / ``ModelRegistry.stream()``.

    Replaces the old ``ModelConfig`` which had no ``provider_name``
    and relied on ``infer_provider()`` heuristics.

    The final output token limit is determined by
    :meth:`resolve_output_limit` — it delegates to the profile system
    if ``token_limit_profile`` is set.
    """

    provider_name: str
    model_id: str
    temperature: float = 0.7
    max_tokens: int = 4096
    streams: bool = False
    token_limit_profile: str | None = None
    cache: CacheSettings | None = None

    def resolve_output_limit(self, profile: str | None = None) -> int:
        """Return the output token limit, optionally overridden by *profile*.

        Resolution order:
        1. If *profile* is a preset key in ``PROFILE_OUTPUT_LIMITS``, return that limit.
        2. If ``self.token_limit_profile`` is a preset key, return its limit.
        3. If the selected profile is ``custom`` or unknown, return ``self.max_tokens``.

        Parameters
        ----------
        profile:
            Optional explicit profile name (takes highest priority).

        Returns
        -------
        int
            The resolved output token limit.
        """
        effective = profile or self.token_limit_profile
        return resolve_output_limit_for_profile(effective, raw_output_limit=self.max_tokens)
