"""Google, Groq, and OpenRouter provider adapters."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.groq import GroqModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.providers.groq import GroqProvider
from pydantic_ai.providers.openai import OpenAIProvider

from narrare_core.llm._providers.registry import register, register_model

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

    Args:
        model_id: Google model identifier (e.g. "gemini-2.0-flash").
        api_key: Optional API key — overrides env var when provided.
        base_url: Ignored for Google (uses official API endpoint).

    Returns:
        Configured GoogleModel instance.
    """
    if api_key is not None:
        provider = GoogleProvider(api_key=api_key)
        return GoogleModel(model_id, provider=provider)
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

    Args:
        model_id: Groq model identifier (e.g. "mixtral-8x7b-32768").
        api_key: Optional API key — overrides env var when provided.
        base_url: Ignored for Groq (uses official API endpoint).

    Returns:
        Configured GroqModel instance.
    """
    if api_key is not None:
        provider = GroqProvider(api_key=api_key)
        return GroqModel(model_id, provider=provider)
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

    Args:
        model_id: Model identifier (may include "openrouter/" prefix).
        api_key: Optional API key — overrides env var when provided.
        base_url: Optional base URL — defaults to OpenRouter API.

    Returns:
        Configured OpenAIChatModel via OpenRouter endpoint.
    """
    resolved_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
    resolved_base = base_url or "https://openrouter.ai/api/v1"
    return OpenAIChatModel(
        model_id.removeprefix("openrouter/"),
        provider=OpenAIProvider(base_url=resolved_base, api_key=resolved_key),
    )


register("openrouter", _make_openrouter)
