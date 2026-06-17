"""
Contracts for the LLM subsystem.

Every LLM call goes through the gateway — CONSTRAINTS.md RULE-01b.
Contract-first design — CONSTRAINTS.md RULE-03.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from pydantic_ai.usage import UsageLimits

    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.intents import LLMIntent
    from narrare_core.llm.model_listing import ModelCatalogEntry
    from narrare_core.llm.result import StreamChunk


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


@runtime_checkable
class ModelCatalogProtocol(Protocol):
    """Contract for listing available models from a provider's catalog API.

    Separate from ``ModelRegistryProtocol`` (which handles LLM inference).
    Catalog queries are read-only GET requests to provider REST APIs —
    they do not invoke LLM inference.

    RULE-08 compliance: provider catalog APIs are external integrations
    abstracted behind this protocol.

    See Also
    --------
    CONSTRAINTS.md RULE-08 — External integrations are abstracted.
    CONSTRAINTS.md RULE-03 — Contracts before implementation.
    """

    async def list_models(
        self,
        provider: str,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> list[ModelCatalogEntry]:
        """List available models for a given provider.

        Parameters
        ----------
        provider:
            Provider name (e.g. ``"anthropic"``, ``"openai"``, ``"ollama"``).
            Passed as a plain string — core has no dependency on apps/.
        api_key:
            Provider API key.  Required for cloud providers.  ``None`` for Ollama.
        base_url:
            Optional base URL override (e.g. Ollama URL, custom endpoint).

        Returns
        -------
        list[ModelCatalogEntry]
            Available models from the provider's catalog.

        Raises
        ------
        ModelCatalogError
            If the provider API is unreachable or returns an error.
        """
        ...
