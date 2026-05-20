"""
Narrare Model Registry — provides configured Model instances for Agents.

This is the Gateway v2.  Instead of creating ephemeral Agents and calling
``run_sync()``, the registry returns configured ``Model`` instances.
Agents obtain their Model here, then call ``agent.run()`` themselves.

**RULE-01b**: ``from pydantic_ai import Agent`` is restricted in ``core/llm/``.
The convenience ``run()`` method on ``ModelRegistry`` is the only approved
exception — it creates an ephemeral Agent for simple one-shot calls.

See CONSTRAINTS.md RULE-01b and ADR-015.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

import structlog

# narrare: allow-agent reason="ModelRegistry convenience run() creates ephemeral Agent"
from pydantic_ai import Agent

from narrare_core.llm._providers.registry import get as get_provider

if TYPE_CHECKING:
    from pydantic_ai.models import Model
    from pydantic_ai.usage import UsageLimits

    from narrare_core.llm.intents import LLMIntent, ResolvedModelConfig

logger = structlog.get_logger(__name__)

T = TypeVar("T")

# Public API: ModelRegistry (v2) + LLMGateway (legacy re-export for back compat)
__all__ = ["LLMGateway", "ModelRegistry"]


class ModelRegistry:
    """Gateway v2 — provides configured Model instances for Agents.

    Agents obtain their Model here, then call ``agent.run()`` themselves.
    The registry handles:

    * Provider resolution — which factory for a given ``provider_name``
    * Credential injection — ``api_key`` + ``base_url`` for per-user secrets
    * ``UsageLimits`` pre-configuration — prepared for Phase 1 of ADR-015

    Simple use cases (health checks, name generation) can use the
    convenience :meth:`run` method, which creates an ephemeral Agent,
    calls it, and returns the output.  Complex use cases (writing
    pipeline) should use :meth:`get_model` + their own Agent definition
    in :mod:`~narrare_core.agents`.
    """

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
            usage_limits: Prepared for Phase 1 of ADR-015.
                **Currently ignored.**  Will be applied in Phase 1.

        Returns:
            Configured pydantic-ai Model instance ready for use with ``Agent``.

        Raises:
            KeyError: If ``config.provider_name`` is not registered in the
                :mod:`~narrare_core.llm._providers` registry.
        """
        factory = get_provider(config.provider_name)
        return factory(config.model_id, api_key=api_key, base_url=base_url)

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
            usage_limits: Prepared for Phase 1 of ADR-015.
                **Currently ignored.**

        Returns:
            The agent's output — either ``str`` (when ``output_type`` is
            ``None`` or ``str``) or an instance of the specified type ``T``.
        """
        # narrare: allow-agent reason="ModelRegistry convenience run() (ADR-015)"
        model = await self.get_model(config, usage_limits=usage_limits)
        agent = Agent(
            model=model,
            system_prompt=system_prompt or "",
            output_type=output_type or str,
        )
        result = await agent.run(
            prompt, deps=deps
        )  # narrare: allow-agent reason="ModelRegistry convenience run() (ADR-015)"
        return result.output


# Backward compatibility — LLMGateway has moved to _legacy.py
from narrare_core.llm._legacy import LLMGateway  # noqa: E402, I001  # pyright: ignore[reportUnusedImport]
