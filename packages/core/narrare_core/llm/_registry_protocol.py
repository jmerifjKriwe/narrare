"""
Contract for the ModelRegistry — the single entry point for all LLM calls.

RULE-04 split from ``contracts.py`` (which had grown past the 200-line
hard limit for ``contracts.py`` files).  ``contracts.py`` remains the
public re-export surface; import from there (or from
:mod:`narrare_core.llm`) — not from this internal module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from pydantic_ai.usage import UsageLimits

    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm._prepared_call import PreparedModelCall
    from narrare_core.llm.intents import LLMIntent
    from narrare_core.llm.result import StreamChunk

__all__ = ["ModelRegistryProtocol"]


@runtime_checkable
class ModelRegistryProtocol(Protocol):
    """Contract for the ModelRegistry — single entry point for all LLM calls.

    All LLM interactions in the system must flow through an object that
    satisfies this protocol.  The concrete implementation
    (:class:`~narrare_core.llm.gateway.ModelRegistry`) handles provider
    resolution, credential injection, and convenience run/stream methods.

    See Also
    --------
    CONSTRAINTS.md RULE-01b — LLM calls go through the Gateway.
    CONSTRAINTS.md RULE-03 — Contracts before implementation.
    ADR-015 — Model Registry migration.
    """

    async def run(
        self,
        intent: LLMIntent,
        prompt: str,
        config: ResolvedModelConfig,
        *,
        system_prompt: str | None = ...,
        usage_limits: UsageLimits | None = ...,
        api_key: str | None = ...,
        base_url: str | None = ...,
    ) -> str:
        """Execute a non-streaming LLM call.

        Parameters
        ----------
        intent:
            The operation intent — drives model selection and metrics.
        prompt:
            The user message / prompt text.
        config:
            Fully resolved model configuration (provider + model + params).
        system_prompt:
            Optional system prompt.  Defaults to empty string.
        usage_limits:
            Optional usage limits for the Agent.

        Returns
        -------
        str
            Generated text output.
        """
        ...

    async def stream(
        self,
        *,
        intent: LLMIntent,
        system_prompt: str,
        user_prompt: str,
        config: ResolvedModelConfig,
        api_key: str | None = ...,
        base_url: str | None = ...,
        usage_limits: UsageLimits | None = ...,
    ) -> AsyncIterator[StreamChunk]:
        """Execute a streaming LLM call.

        Parameters
        ----------
        intent:
            The operation intent.
        system_prompt:
            System role message.
        user_prompt:
            User role message.
        config:
            Fully resolved model configuration.
        api_key:
            Optional API key from user settings.
        base_url:
            Optional base URL for OpenAI-compatible providers.

        Yields
        ------
        StreamChunk
            Text fragments during generation.  The final chunk has
            ``is_final=True`` and populated ``usage``.
        """
        ...

    async def prepare(
        self,
        config: ResolvedModelConfig,
        *,
        intent: LLMIntent | None = ...,
        usage_limits: UsageLimits | None = ...,
        api_key: str | None = ...,
        base_url: str | None = ...,
    ) -> PreparedModelCall:
        """Single assembly point: model + settings + limits as one triple.

        Agent call sites use this instead of ``get_model()`` + separate
        settings assembly, so a Model can never be obtained without its
        matching ``model_settings`` (intent-aware thinking policy, cache
        settings, ADR-045 output cap) and ``usage_limits``.

        Parameters
        ----------
        config:
            Fully resolved model configuration (provider + model + params).
        intent:
            Optional operation intent — drives the thinking policy.
        usage_limits:
            Optional usage limits.  Their ``output_tokens_limit`` is
            mirrored into ``model_settings["max_tokens"]`` and the limits
            themselves are returned for ``Agent.run(usage_limits=...)``.
        api_key:
            Optional API key from user settings.
        base_url:
            Optional base URL for OpenAI-compatible providers.

        Returns
        -------
        PreparedModelCall
            The coherent ``(model, model_settings, usage_limits)`` triple.
        """
        ...
