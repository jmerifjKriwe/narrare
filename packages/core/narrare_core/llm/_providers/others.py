"""Google, Groq, and OpenRouter provider adapters."""

from __future__ import annotations

import os

from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.groq import GroqModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from narrare_core.llm._providers.registry import register, register_model

# --- Google ---


def _make_google(model_id: str) -> GoogleModel:
    """Gemini models via Google AI. API key from GOOGLE_API_KEY."""
    return GoogleModel(model_id)


register("google", _make_google)

for _mid in [
    "gemini-2.0-flash",
    "gemini-1.5-pro",
    "gemini-1.5-flash",
]:
    register_model(_mid, "google")


# --- Groq ---


def _make_groq(model_id: str) -> GroqModel:
    """Fast inference via Groq. API key from GROQ_API_KEY."""
    return GroqModel(model_id)


register("groq", _make_groq)

for _mid in [
    "mixtral-8x7b-32768",
    "llama-3.3-70b-versatile",
]:
    register_model(_mid, "groq")


# --- OpenRouter ---


def _make_openrouter(model_id: str) -> OpenAIChatModel:
    """
    OpenRouter — access to many models via one API.
    API key from OPENROUTER_API_KEY.

    # narrare: allow-direct-llm  reason="OpenRouter requires custom base_url"
    """
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    return OpenAIChatModel(
        model_id.removeprefix("openrouter/"),
        provider=OpenAIProvider(base_url="https://openrouter.ai/api/v1", api_key=api_key),
    )


register("openrouter", _make_openrouter)
