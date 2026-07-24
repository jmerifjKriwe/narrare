"""Google, Groq, and OpenRouter provider adapters."""

from __future__ import annotations

from typing import TYPE_CHECKING

from google.genai import Client as GoogleClient
from google.genai import types as google_types
from groq import AsyncGroq
from openai import AsyncOpenAI
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.groq import GroqModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.providers.groq import GroqProvider
from pydantic_ai.providers.openai import OpenAIProvider

from narrare_core.llm._providers.registry import register, register_model
from narrare_core.llm._transport_retry import get_transport_max_retries
from narrare_core.settings import get_core_settings

if TYPE_CHECKING:
    from pydantic_ai.models import Model


# --- Google ---


def _make_google(
    model_id: str,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
) -> Model:
    """Gemini models via Google AI.

    When ``api_key`` is provided, passes it explicitly to the provider
    so each request uses its own credentials (thread-safe). Otherwise
    falls back to the ``GOOGLE_API_KEY`` / ``GEMINI_API_KEY`` environment
    variable.

    Transport retry (transient errors) is governed at the provider layer via
    :func:`get_transport_max_retries` (ADR-060). Google's SDK retries via
    ``HttpOptions(retry_options=HttpRetryOptions(attempts=N))`` rather than an
    SDK ``max_retries`` knob; the governed value is applied in Google's
    provider-native ``attempts`` units.

    Args:
        model_id: Google model identifier (e.g. "gemini-2.0-flash").
        api_key: Optional API key — overrides env var when provided.
        base_url: Ignored for Google (uses official API endpoint).

    Returns:
        Configured GoogleModel instance.
    """
    attempts = get_transport_max_retries()
    settings = get_core_settings()
    resolved_key = (
        api_key if api_key is not None else (settings.google_api_key or settings.gemini_api_key)
    )
    if resolved_key is not None:
        client = GoogleClient(
            api_key=resolved_key,
            http_options=google_types.HttpOptions(
                retry_options=google_types.HttpRetryOptions(attempts=attempts),
            ),
        )
        return GoogleModel(model_id, provider=GoogleProvider(client=client))
    # No resolvable credential: defer to pydantic-ai (Google's Client raises
    # without a key; this path makes no real calls).
    return GoogleModel(model_id)


register("google", _make_google)

for _mid in [
    "gemini-2.0-flash",
    "gemini-1.5-pro",
    "gemini-1.5-flash",
]:
    register_model(_mid, "google")


# --- Groq ---


def _make_groq(
    model_id: str,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
) -> Model:
    """Fast inference via Groq.

    When ``api_key`` is provided, passes it explicitly to the provider
    so each request uses its own credentials (thread-safe). Otherwise
    falls back to the ``GROQ_API_KEY`` environment variable.

    Transport retry (transient 429/5xx/timeout) is governed at the provider
    layer via :func:`get_transport_max_retries` (ADR-060) and applied to the
    SDK client's ``max_retries`` — uniformly for ``run()`` and ``stream()``.

    Args:
        model_id: Groq model identifier (e.g. "mixtral-8x7b-32768").
        api_key: Optional API key — overrides env var when provided.
        base_url: Ignored for Groq (uses official API endpoint).

    Returns:
        Configured GroqModel instance.
    """
    max_retries = get_transport_max_retries()
    resolved_key = api_key if api_key is not None else get_core_settings().groq_api_key
    if resolved_key is not None:
        # base_url intentionally ignored for Groq (official endpoint only).
        client = AsyncGroq(api_key=resolved_key, max_retries=max_retries)
        return GroqModel(model_id, provider=GroqProvider(groq_client=client))
    # No resolvable credential: defer to pydantic-ai (Groq's client raises
    # without a key; this path makes no real calls).
    return GroqModel(model_id)


register("groq", _make_groq)

for _mid in [
    "mixtral-8x7b-32768",
    "llama-3.3-70b-versatile",
]:
    register_model(_mid, "groq")


# --- OpenRouter ---


def _make_openrouter(
    model_id: str,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
) -> Model:
    """OpenRouter — access to many models via one API.

    When ``api_key`` is provided, uses it directly. Otherwise falls back
    to the ``OPENROUTER_API_KEY`` environment variable.

    Transport retry (transient 429/5xx/timeout) is governed at the provider
    layer via :func:`get_transport_max_retries` (ADR-060) and applied to the
    SDK client's ``max_retries`` — uniformly for ``run()`` and ``stream()``.

    Args:
        model_id: Model identifier (may include "openrouter/" prefix).
        api_key: Optional API key — overrides env var when provided.
        base_url: Optional base URL — defaults to OpenRouter API.

    Returns:
        Configured OpenAIChatModel via OpenRouter endpoint.
    """
    max_retries = get_transport_max_retries()
    resolved_key = api_key or (get_core_settings().openrouter_api_key or "")
    resolved_base = base_url or "https://openrouter.ai/api/v1"
    if resolved_key:
        client = AsyncOpenAI(api_key=resolved_key, base_url=resolved_base, max_retries=max_retries)
        return OpenAIChatModel(
            model_id.removeprefix("openrouter/"),
            provider=OpenAIProvider(openai_client=client),
        )
    # No resolvable key (empty string would make the SDK raise at construction):
    # defer to pydantic-ai, preserving the prior lazy behaviour. This path
    # cannot make real calls, so transport retry is not applicable.
    return OpenAIChatModel(
        model_id.removeprefix("openrouter/"),
        provider=OpenAIProvider(api_key=resolved_key, base_url=resolved_base),
    )


register("openrouter", _make_openrouter)
