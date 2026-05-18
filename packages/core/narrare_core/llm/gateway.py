"""
Narrare LLM Gateway — THE single entry point for all LLM calls.
No other module may call an LLM provider directly.
See CONSTRAINTS.md RULE-01 and ADR-001.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import structlog
from pydantic_ai import Agent

from narrare_core.llm import _providers  # noqa: F401  # pyright: ignore[reportUnusedImport]
from narrare_core.llm._providers.registry import get as get_provider
from narrare_core.llm.gateway_errors import classify_error
from narrare_core.llm.metrics import record_failure, record_success
from narrare_core.llm.observability import LLMObservability
from narrare_core.llm.result import LLMResult, StreamChunk, TokenUsage
from narrare_core.llm.retry import DEFAULT_RETRY, RetryConfig, with_retry

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from pydantic_ai.models import Model

    from narrare_core.llm.intents import LLMIntent, ResolvedModelConfig
    from narrare_core.shared.errors import LLMGatewayError

logger = structlog.get_logger(__name__)


class LLMGateway:
    """
    Central gateway for all LLM calls.

    Handles:
    - Provider selection based on explicit provider_name (from ResolvedModelConfig)
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
                Only used when no ``ResolvedModelConfig`` is provided.
        """
        self._default_provider = default_provider
        self._obs: LLMObservability = LLMObservability()
        logger.info("llm_gateway_initialized", default_provider=default_provider)

    def _get_model_with_credentials(
        self,
        provider_name: str,
        model_id: str,
        *,
        api_key: str | None,
        base_url: str | None,
    ) -> Model:
        """Resolve provider and create model instance with explicit credentials.

        Uses the provider registry to get the factory, then passes credentials
        through. No env-var inference - credentials come from the caller.

        Args:
            provider_name: Explicit provider name (e.g. "anthropic", "openrouter").
            model_id: Model identifier as known to that provider.
            api_key: Decrypted API key from user settings, or None.
            base_url: Custom base URL, or None (use provider default).

        Returns:
            Configured pydantic-ai Model instance.
        """
        factory = get_provider(provider_name)
        return factory(model_id, api_key=api_key, base_url=base_url)

    def _make_agent(self, model: Model, system_prompt: str) -> Agent[None, str]:
        """Create a pydantic-ai Agent for a single call."""
        return Agent(
            model,
            system_prompt=system_prompt,
            output_type=str,
        )

    def _classify_error(self, error: Exception) -> LLMGatewayError:
        """Convert provider exceptions to domain errors.

        Delegates to :func:`gateway_errors.classify_error`.
        Kept as method for backward compatibility with existing tests.
        """
        return classify_error(error)

    async def run(
        self,
        *,
        intent: LLMIntent,
        system_prompt: str,
        user_prompt: str,
        config: ResolvedModelConfig,
        api_key: str | None = None,
        base_url: str | None = None,
        retry_config: RetryConfig = DEFAULT_RETRY,
    ) -> LLMResult:
        """Execute a non-streaming LLM call.

        Args:
            intent: The operation intent - drives model selection.
            system_prompt: System role message.
            user_prompt: User role message.
            config: Resolved model configuration (provider + model + params).
                Must be provided by the caller via ``ModelRoutingResolver``.
            api_key: Decrypted API key from user settings. When ``None``,
                the provider factory falls back to env vars (dev/test).
            base_url: Custom base URL for OpenAI-compatible providers.
            retry_config: Retry behaviour configuration.

        Returns:
            LLMResult with generated text and usage statistics.

        Raises:
            LLMGatewayError: On failure after all retries.
        """
        provider_name = config.provider_name
        model_id = config.model_id
        model = self._get_model_with_credentials(
            provider_name,
            model_id,
            api_key=api_key,
            base_url=base_url,
        )

        log = logger.bind(intent=intent.value, model=model_id, provider=provider_name)
        log.debug("llm_run_start")

        start = time.monotonic()
        obs_trace = self._obs.start_trace(
            intent, model_id, provider_name, system_prompt, user_prompt
        )

        async def _call() -> LLMResult:
            try:
                agent = self._make_agent(model, system_prompt)
                result = await agent.run(user_prompt)
                elapsed = time.monotonic() - start

                usage = result.usage
                token_usage = TokenUsage(
                    prompt_tokens=usage.input_tokens or 0,
                    completion_tokens=usage.output_tokens or 0,
                    total_tokens=usage.total_tokens or 0,
                )

                record_success(
                    intent=intent.value,
                    model=model_id,
                    provider=provider_name,
                    usage=token_usage,
                    duration_seconds=elapsed,
                )
                log.info(
                    "llm_run_complete",
                    tokens=token_usage.total_tokens,
                    duration_ms=round(elapsed * 1000),
                )
                result_text = result.output
                self._obs.finish_trace(obs_trace, result_text, token_usage, round(elapsed * 1000))
                return LLMResult(
                    text=result_text,
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
                    provider=provider_name,
                    error_type=type(domain_error).__name__,
                    duration_seconds=elapsed,
                )
                self._obs.record_error(obs_trace, str(domain_error), type(domain_error).__name__)
                raise domain_error from e

        result = await with_retry(_call, retry_config, intent=intent.value)
        return result

    async def stream(
        self,
        *,
        intent: LLMIntent,
        system_prompt: str,
        user_prompt: str,
        config: ResolvedModelConfig,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Execute a streaming LLM call.

        Args:
            intent: The operation intent.
            system_prompt: System role message.
            user_prompt: User role message.
            config: Resolved model configuration (provider + model + params).
                Must be provided by the caller via ``ModelRoutingResolver``.
            api_key: Decrypted API key from user settings. When ``None``,
                the provider factory falls back to env vars (dev/test).
            base_url: Custom base URL for OpenAI-compatible providers.

        Yields:
            StreamChunk instances with text fragments.
            The final chunk has is_final=True and usage populated.

        Raises:
            LLMGatewayError: If the stream cannot be started or fails mid-stream.
        """
        provider_name = config.provider_name
        model_id = config.model_id
        model = self._get_model_with_credentials(
            provider_name,
            model_id,
            api_key=api_key,
            base_url=base_url,
        )

        log = logger.bind(intent=intent.value, model=model_id, provider=provider_name)
        log.debug("llm_stream_start")

        start = time.monotonic()
        obs_trace = self._obs.start_trace(
            intent, model_id, provider_name, system_prompt, user_prompt
        )

        try:
            agent = self._make_agent(model, system_prompt)
            async with agent.run_stream(user_prompt) as stream_result:
                async for text in stream_result.stream_text(delta=True):
                    yield StreamChunk(text=text)

                elapsed = time.monotonic() - start
                usage = stream_result.usage
                token_usage = TokenUsage(
                    prompt_tokens=usage.input_tokens or 0,
                    completion_tokens=usage.output_tokens or 0,
                    total_tokens=usage.total_tokens or 0,
                )
                record_success(
                    intent=intent.value,
                    model=model_id,
                    provider=provider_name,
                    usage=token_usage,
                    duration_seconds=elapsed,
                )
                log.info(
                    "llm_stream_complete",
                    tokens=token_usage.total_tokens,
                    duration_ms=round(elapsed * 1000),
                )
                self._obs.finish_trace(obs_trace, "", token_usage, round(elapsed * 1000))
                yield StreamChunk(text="", is_final=True, usage=token_usage)

        except Exception as e:
            elapsed = time.monotonic() - start
            domain_error = self._classify_error(e)
            record_failure(
                intent=intent.value,
                model=model_id,
                provider=provider_name,
                error_type=type(domain_error).__name__,
                duration_seconds=elapsed,
            )
            self._obs.record_error(obs_trace, str(domain_error), type(domain_error).__name__)
            raise domain_error from e
