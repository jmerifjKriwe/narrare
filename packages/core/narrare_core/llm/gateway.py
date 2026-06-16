"""
Narrare Model Registry — provides configured Model instances for Agents.

This is the Gateway v2.  Instead of creating ephemeral Agents and calling
``run_sync()``, the registry returns configured ``Model`` instances.
Agents obtain their Model here, then call ``agent.run()`` themselves.

**RULE-01b**: ``from pydantic_ai import Agent`` is restricted in ``core/llm/``.
The convenience ``run()`` and ``stream()`` methods on ``ModelRegistry`` are
the only approved exceptions — they create ephemeral Agents for simple calls.

See CONSTRAINTS.md RULE-01b and ADR-015.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, TypeVar

import structlog

# narrare: allow-agent reason="ModelRegistry convenience run()/stream() creates ephemeral Agent"
from pydantic_ai import Agent
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.usage import UsageLimits

from narrare_core.llm._model_settings import (
    build_runtime_model_settings,
)
from narrare_core.llm._model_settings import (
    get_cache_settings as _get_cache_settings,
)
from narrare_core.llm._providers.registry import get as get_provider
from narrare_core.llm.result import StreamChunk, TokenUsage

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from pydantic_ai.models import Model
    from pydantic_ai.settings import ModelSettings

    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.intents import LLMIntent

logger = structlog.get_logger(__name__)

T = TypeVar("T")

# Public API
__all__ = ["ModelRegistry"]


class ModelRegistry:
    """Gateway v2 — provides configured Model instances for Agents.

    Agents obtain their Model here, then call ``agent.run()`` themselves.
    The registry handles:

    * Provider resolution — which factory for a given ``provider_name``
    * Credential injection — ``api_key`` + ``base_url`` for per-user secrets
    * ``UsageLimits`` pre-configuration — prepared for Phase 1 of ADR-015

    Simple use cases (health checks, name generation) can use the
    convenience :meth:`run` and :meth:`stream` methods, which create
    ephemeral Agents.  Complex use cases (writing pipeline) should use
    :meth:`get_model` + their own Agent definition in
    :mod:`~narrare_core.agents`.
    """

    @staticmethod
    def _profile_to_limits(profile: str) -> UsageLimits | None:
        """Convert a named token limit profile to UsageLimits.

        These profiles are stored in user_ai_settings and project_settings
        as the ``token_limit_profile`` column.

        Args:
            profile: One of "quick", "balanced", "long_texts", "conservative", "custom".

        Returns:
            Configured UsageLimits, or None if the profile is unknown.
        """
        profiles: dict[str, dict[str, int]] = {
            "quick": {"request_limit": 10, "total_tokens_limit": 16000},
            "balanced": {"request_limit": 25, "total_tokens_limit": 64000},
            "long_texts": {"request_limit": 25, "total_tokens_limit": 128000},
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

    async def get_model(
        self,
        config: ResolvedModelConfig,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        usage_limits: UsageLimits | None = None,
    ) -> Model:
        """Return a configured Model instance with credentials.

        Args:
            config: Fully resolved model configuration
                (provider, model, parameters).
            api_key: Optional API key — overrides the environment variable
                when provided.  ``None`` lets the factory fall back to the
                default env var (for dev/test).
            base_url: Optional base URL — overrides the provider default.
            usage_limits: If provided, usage limits are passed through to
                the model's Agent at run time.

        Returns:
            Configured pydantic-ai Model instance ready for use with ``Agent``.

        Raises:
            KeyError: If ``config.provider_name`` is not registered in the
                :mod:`~narrare_core.llm._providers` registry.
        """
        # Auto-convert token_limit_profile to UsageLimits if not explicitly set
        if usage_limits is None:
            profile = getattr(config, "token_limit_profile", None) or ""
            if profile:
                usage_limits = self._profile_to_limits(profile)

        factory = get_provider(config.provider_name)
        return factory(config.model_id, api_key=api_key, base_url=base_url)

    def get_cache_settings(self, config: ResolvedModelConfig) -> ModelSettings:
        """Build provider-specific ModelSettings for prompt caching.

        Delegates to
        :func:`narrare_core.llm._model_settings.get_cache_settings`.
        Returned as kwargs dict for ``Agent.run(model_settings=...)``.
        """
        return _get_cache_settings(config)

    async def run(
        self,
        intent: LLMIntent,
        prompt: str,
        config: ResolvedModelConfig,
        *,
        system_prompt: str | None = None,
        output_type: type[T] | None = None,
        deps: Any = None,
        usage_limits: UsageLimits | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> T:
        """Convenience: create ephemeral Agent, run it, return the output.

        Use this for simple one-shot LLM calls that do not need tools,
        capabilities, or special output processing — for example health
        checks, name generation, or title generation.

        Complex use cases (writing pipeline, multi-agent orchestration)
        should use :meth:`get_model` + their own Agent definition in
        :mod:`~narrare_core.agents` instead.

        Args:
            intent: The operation intent (used for logging).
            prompt: The user message / prompt text.
            config: Fully resolved model configuration.
            system_prompt: Optional system prompt.  Defaults to empty string.
            output_type: Optional structured output type.
                Defaults to ``str`` (plain text).
            deps: Optional dependencies for the Agent.
            usage_limits: Passed to ``agent.run(usage_limits=...)`` to
                enforce token and request limits.
            api_key: Optional API key — overrides the environment variable.
            base_url: Optional base URL — overrides the provider default.

        Returns:
            The agent's output — either ``str`` (when ``output_type`` is
            ``None`` or ``str``) or an instance of the specified type ``T``.
        """
        start = time.monotonic()
        model = await self.get_model(
            config, api_key=api_key, base_url=base_url, usage_limits=usage_limits
        )
        agent = Agent(  # narrare: allow-agent reason="ModelRegistry convenience run() (ADR-015)"
            model=model,
            system_prompt=system_prompt or "",
            output_type=output_type or str,
        )
        try:
            model_settings = build_runtime_model_settings(config, usage_limits)
            # narrare: allow-agent reason="ModelRegistry run() passes model_settings (ADR-016)"
            result = await agent.run(
                prompt,
                deps=deps,
                usage_limits=usage_limits,
                model_settings=model_settings,
            )

            # Populate TokenUsage with provider/model for cost estimation
            _usage = result.usage
            token_usage = TokenUsage(
                prompt_tokens=_usage.input_tokens or 0,
                completion_tokens=_usage.output_tokens or 0,
                total_tokens=_usage.total_tokens or 0,
                provider=config.provider_name,
                model=config.model_id,
            )

            elapsed = time.monotonic() - start
            logger.info(
                "model_registry_run_complete",
                intent=intent.value,
                model=config.model_id,
                provider=config.provider_name,
                tokens=token_usage.total_tokens,
                duration_ms=round(elapsed * 1000),
                cost_estimate=token_usage.cost_estimate_usd,
            )

            return result.output
        except UsageLimitExceeded:
            # Phase 1: Wird in Phase 1.3 als user-visible error klassifiziert
            raise

    async def stream(
        self,
        *,
        intent: LLMIntent,
        system_prompt: str,
        user_prompt: str,
        config: ResolvedModelConfig,
        api_key: str | None = None,
        base_url: str | None = None,
        usage_limits: UsageLimits | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Convenience: create ephemeral Agent, stream text output.

        Use this for streaming LLM calls that need text deltas — for
        example interactive writing sessions or draft generation.

        Args:
            intent: The operation intent (used for logging).
            system_prompt: System role message.
            user_prompt: User role message.
            config: Fully resolved model configuration.
            api_key: Optional API key — overrides the environment variable.
            base_url: Optional base URL — overrides the provider default.

        Yields:
            StreamChunk instances with text fragments.  The final chunk
            has ``is_final=True`` and populated ``usage``.
        """
        model = await self.get_model(config, api_key=api_key, base_url=base_url)
        # narrare: allow-agent reason="ModelRegistry convenience stream() (ADR-015)"
        agent = Agent(
            model=model,
            system_prompt=system_prompt,
            output_type=str,
        )

        start = time.monotonic()

        # narrare: allow-agent reason="ModelRegistry convenience stream() (ADR-015)"
        model_settings = build_runtime_model_settings(config, usage_limits)
        async with agent.run_stream(
            user_prompt, model_settings=model_settings, usage_limits=usage_limits
        ) as stream_result:
            async for text in stream_result.stream_text(delta=True):
                yield StreamChunk(text=text)

            elapsed = time.monotonic() - start
            usage = stream_result.usage
            token_usage = TokenUsage(
                prompt_tokens=usage.input_tokens or 0,
                completion_tokens=usage.output_tokens or 0,
                total_tokens=usage.total_tokens or 0,
                provider=config.provider_name,
                model=config.model_id,
            )
            logger.info(
                "model_registry_stream_complete",
                intent=intent.value,
                model=config.model_id,
                provider=config.provider_name,
                tokens=token_usage.total_tokens,
                duration_ms=round(elapsed * 1000),
                cost_estimate=token_usage.cost_estimate_usd,
            )
            yield StreamChunk(text="", is_final=True, usage=token_usage)
