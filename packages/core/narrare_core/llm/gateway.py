"""
Narrare LLM Gateway.

THE single entry point for all LLM calls in the system.
No other module may call an LLM provider directly.

See CONSTRAINTS.md RULE-01 and ADR-001.

Usage:
    gateway = LLMGateway(settings)

    # Non-streaming
    result = await gateway.run(
        intent=LLMIntent.WRITE,
        system_prompt=prompt.system,
        user_prompt=prompt.user,
    )

    # Streaming
    async for chunk in gateway.stream(
        intent=LLMIntent.WRITE,
        system_prompt=prompt.system,
        user_prompt=prompt.user,
    ):
        yield chunk.text
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator

import structlog
from pydantic_ai import Agent
from pydantic_ai.models import Model

from narrare_core.llm import _providers  # noqa: F401 — triggers provider registration
from narrare_core.llm._providers.registry import get as get_provider
from narrare_core.llm._providers.registry import infer_provider
from narrare_core.llm.intents import LLMIntent, get_model_config
from narrare_core.llm.metrics import record_failure, record_success
from narrare_core.llm.result import LLMResult, StreamChunk, TokenUsage
from narrare_core.llm.retry import DEFAULT_RETRY, RetryConfig, with_retry
from narrare_core.shared.errors import (
    LLMAuthError,
    LLMContextTooLargeError,
    LLMGatewayError,
    LLMInvalidRequestError,
    LLMRateLimitError,
    LLMServiceUnavailableError,
    LLMTimeoutError,
)

logger = structlog.get_logger(__name__)


class LLMGateway:
    """
    Central gateway for all LLM calls.

    Handles:
    - Provider selection based on model name
    - Intent-based model routing
    - Retry with exponential backoff
    - Cost tracking and telemetry
    - Error classification and wrapping

    This class is instantiated once and injected everywhere via DI.
    Never instantiate this inside a request handler or service method.
    """

    def __init__(self, default_provider: str = "anthropic") -> None:
        """
        Initialise the gateway.

        Args:
            default_provider: Fallback provider when model cannot be inferred.
        """
        self._default_provider = default_provider
        logger.info("llm_gateway_initialized", default_provider=default_provider)

    def _get_model(self, model_id: str) -> Model:
        """Resolve a model ID to a pydantic-ai Model instance."""
        provider_name = infer_provider(model_id)
        factory = get_provider(provider_name)
        return factory(model_id)

    def _make_agent(
        self,
        model: Model,
        system_prompt: str,
    ) -> Agent[None, str]:
        """Create a pydantic-ai Agent for a single call."""
        return Agent(
            model,
            system_prompt=system_prompt,
            result_type=str,
        )

    def _classify_error(self, error: Exception) -> LLMGatewayError:
        """Convert provider-specific exceptions to domain errors."""
        msg = str(error).lower()

        # Auth errors
        if any(k in msg for k in ("api key", "authentication", "unauthorized", "401")):
            return LLMAuthError(str(error))

        # Rate limits
        if any(k in msg for k in ("rate limit", "429", "too many requests", "quota")):
            return LLMRateLimitError(str(error))

        # Context length
        if any(k in msg for k in ("context", "token", "length", "too long", "maximum")):
            return LLMContextTooLargeError(str(error))

        # Timeouts
        if any(k in msg for k in ("timeout", "timed out", "deadline")):
            return LLMTimeoutError(str(error))

        # Service unavailable
        if any(k in msg for k in ("503", "502", "overloaded", "unavailable", "capacity")):
            return LLMServiceUnavailableError(str(error))

        # Invalid request
        if any(k in msg for k in ("invalid", "400", "bad request")):
            return LLMInvalidRequestError(str(error))

        # Unknown — wrap generically
        return LLMGatewayError(f"Unexpected LLM error: {error}")

    async def run(
        self,
        *,
        intent: LLMIntent,
        system_prompt: str,
        user_prompt: str,
        model_override: str | None = None,
        retry_config: RetryConfig = DEFAULT_RETRY,
    ) -> LLMResult:
        """
        Execute a non-streaming LLM call.

        Args:
            intent: The operation intent — drives model selection.
            system_prompt: System role message.
            user_prompt: User role message.
            model_override: Override the default model for this intent.
            retry_config: Retry behaviour configuration.

        Returns:
            LLMResult with generated text and usage statistics.

        Raises:
            LLMGatewayError: On failure after all retries.
        """
        config = get_model_config(intent)
        model_id = model_override or config.model
        model = self._get_model(model_id)
        provider = infer_provider(model_id)

        log = logger.bind(intent=intent.value, model=model_id, provider=provider)
        log.debug("llm_run_start")

        start = time.monotonic()

        async def _call() -> LLMResult:
            try:
                agent = self._make_agent(model, system_prompt)
                result = await agent.run(user_prompt)
                elapsed = time.monotonic() - start

                # pydantic-ai result usage
                usage = result.usage()
                token_usage = TokenUsage(
                    prompt_tokens=usage.request_tokens or 0,
                    completion_tokens=usage.response_tokens or 0,
                    total_tokens=usage.total_tokens or 0,
                )

                record_success(
                    intent=intent.value,
                    model=model_id,
                    provider=provider,
                    usage=token_usage,
                    duration_seconds=elapsed,
                )
                log.info(
                    "llm_run_complete",
                    tokens=token_usage.total_tokens,
                    duration_ms=round(elapsed * 1000),
                )
                return LLMResult(
                    text=result.data,
                    usage=token_usage,
                    model=model_id,
                    intent=intent.value,
                )
            except Exception as e:
                elapsed = time.monotonic() - start
                domain_error = self._classify_error(e)
                record_failure(
                    intent=intent.value,
                    model=model_id,
                    provider=provider,
                    error_type=type(domain_error).__name__,
                    duration_seconds=elapsed,
                )
                raise domain_error from e

        result = await with_retry(_call, retry_config, intent=intent.value)
        return result  # type: ignore[return-value]

    async def stream(
        self,
        *,
        intent: LLMIntent,
        system_prompt: str,
        user_prompt: str,
        model_override: str | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """
        Execute a streaming LLM call.

        Args:
            intent: The operation intent.
            system_prompt: System role message.
            user_prompt: User role message.
            model_override: Override the default model for this intent.

        Yields:
            StreamChunk instances with text fragments.
            The final chunk has is_final=True and usage populated.

        Raises:
            LLMGatewayError: If the stream cannot be started or fails mid-stream.
        """
        config = get_model_config(intent)
        model_id = model_override or config.model
        model = self._get_model(model_id)
        provider = infer_provider(model_id)

        log = logger.bind(intent=intent.value, model=model_id, provider=provider)
        log.debug("llm_stream_start")

        start = time.monotonic()

        try:
            agent = self._make_agent(model, system_prompt)
            async with agent.run_stream(user_prompt) as stream_result:
                async for text in stream_result.stream_text(delta=True):
                    yield StreamChunk(text=text)

                # Final chunk with usage
                elapsed = time.monotonic() - start
                usage = stream_result.usage()
                token_usage = TokenUsage(
                    prompt_tokens=usage.request_tokens or 0,
                    completion_tokens=usage.response_tokens or 0,
                    total_tokens=usage.total_tokens or 0,
                )
                record_success(
                    intent=intent.value,
                    model=model_id,
                    provider=provider,
                    usage=token_usage,
                    duration_seconds=elapsed,
                )
                log.info(
                    "llm_stream_complete",
                    tokens=token_usage.total_tokens,
                    duration_ms=round(elapsed * 1000),
                )
                yield StreamChunk(text="", is_final=True, usage=token_usage)

        except Exception as e:
            elapsed = time.monotonic() - start
            domain_error = self._classify_error(e)
            record_failure(
                intent=intent.value,
                model=model_id,
                provider=provider,
                error_type=type(domain_error).__name__,
                duration_seconds=elapsed,
            )
            raise domain_error from e
