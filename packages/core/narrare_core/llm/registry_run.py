"""
Ephemeral-Agent convenience layer for the ModelRegistry — RULE-04 split.

``run()`` and ``stream()`` (plus their ephemeral-Agent wiring) moved verbatim
from ``gateway.py`` (stats002 cost-tracking plan, Task 4a) so the registry
core stays within its RULE-04 hard limit.  Mixed into
:class:`narrare_core.llm.gateway.ModelRegistry` — the public API is
unchanged; callers still use ``registry.run(...)`` / ``registry.stream(...)``.

**RULE-01b**: ``from pydantic_ai import Agent`` is restricted in ``core/llm/``.
The ephemeral Agents created here are the only approved exceptions — they
exist for simple one-shot calls that need no tools or capabilities.

See CONSTRAINTS.md RULE-01b, RULE-04 and ADR-015.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, TypeVar

import structlog

# narrare: allow-agent reason="ModelRegistry convenience run()/stream() creates ephemeral Agent"
from pydantic_ai import Agent
from pydantic_ai.exceptions import UsageLimitExceeded

from narrare_core.llm._model_settings import build_runtime_model_settings
from narrare_core.llm.result import StreamChunk, TokenUsage
from narrare_core.llm.usage_events import emit_registry_usage_event

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Coroutine

    from pydantic_ai.models import Model
    from pydantic_ai.usage import UsageLimits

    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.intents import LLMIntent

logger = structlog.get_logger(__name__)

T = TypeVar("T")

__all__ = ["RegistryRunMixin"]


class RegistryRunMixin:
    """``run()``/``stream()`` convenience methods for :class:`ModelRegistry`.

    RULE-04 extraction (stats002 plan, Task 4a): both methods moved verbatim
    from ``gateway.py``.  ``ModelRegistry`` mixes this in, so the public API
    (``registry.run(...)`` / ``registry.stream(...)``) is unchanged.

    Host classes must provide an async
    ``get_model(config, *, api_key, base_url, usage_limits)`` method (see
    :meth:`narrare_core.llm.gateway.ModelRegistry.get_model`).
    """

    if TYPE_CHECKING:
        # Host-provided (ModelRegistry in gateway.py); declared so the
        # get_model call sites below are strictly type-checked.
        get_model: Callable[..., Coroutine[Any, Any, Model]]

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
            intent: The operation intent (drives the thinking policy and
                logging).
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
            model_settings = build_runtime_model_settings(config, usage_limits, intent=intent)
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
            await emit_registry_usage_event(
                intent=intent, config=config, usage=_usage, duration_seconds=elapsed
            )
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
            # Phase 1: will be classified as a user-visible error in Phase 1.3
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
            intent: The operation intent (drives the thinking policy and
                logging).
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
        model_settings = build_runtime_model_settings(config, usage_limits, intent=intent)
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
            await emit_registry_usage_event(
                intent=intent, config=config, usage=usage, duration_seconds=elapsed
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
