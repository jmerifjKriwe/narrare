"""
Contracts for the LLM Gateway subsystem.

Every LLM call goes through the gateway — CONSTRAINTS.md RULE-01.
Contract-first design — CONSTRAINTS.md RULE-03.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from narrare_core.llm.intents import LLMIntent, ResolvedModelConfig
    from narrare_core.llm.result import LLMResult, StreamChunk
    from narrare_core.llm.retry import RetryConfig


@runtime_checkable
class LLMGatewayProtocol(Protocol):
    """Contract for the LLM Gateway — single entry point for all LLM calls.

    All LLM interactions in the system must flow through an object that
    satisfies this protocol.  The concrete implementation
    (:class:`~narrare_core.llm.gateway.LLMGateway`) handles provider
    selection, retry logic, observability, and error classification.

    See Also
    --------
    CONSTRAINTS.md RULE-01 — LLM calls go through the Gateway.
    CONSTRAINTS.md RULE-03 — Contracts before implementation.
    ADR-001 — Centralised LLM Gateway decision.
    """

    async def run(
        self,
        *,
        intent: LLMIntent,
        system_prompt: str,
        user_prompt: str,
        config: ResolvedModelConfig,
        api_key: str | None = ...,
        base_url: str | None = ...,
        retry_config: RetryConfig = ...,
    ) -> LLMResult:
        """Execute a non-streaming LLM call.

        Parameters
        ----------
        intent:
            The operation intent — drives model selection and metrics.
        system_prompt:
            System role message.
        user_prompt:
            User role message.
        config:
            Fully resolved model configuration (provider + model + params).
        api_key:
            Decrypted API key from user settings.  ``None`` lets the
            provider fall back to environment variables (dev/test).
        base_url:
            Custom base URL for OpenAI-compatible providers.
        retry_config:
            Retry behaviour configuration.

        Returns
        -------
        LLMResult
            Generated text with usage statistics.

        Raises
        ------
        LLMGatewayError
            On failure after all retries.
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
            Decrypted API key from user settings.
        base_url:
            Custom base URL for OpenAI-compatible providers.

        Yields
        ------
        StreamChunk
            Text fragments during generation.  The final chunk has
            ``is_final=True`` and populated ``usage``.

        Raises
        ------
        LLMGatewayError
            If the stream cannot be started or fails mid-stream.
        """
        ...
