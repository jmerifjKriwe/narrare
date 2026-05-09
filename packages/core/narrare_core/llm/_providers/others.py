"""Google, Groq, and OpenRouter provider adapters."""

from __future__ import annotations

import os

from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.groq import GroqModel
from pydantic_ai.models.openai import OpenAIModel

from narrare_core.llm._providers.registry import register


# --- Google ---

def _make_google(model_id: str) -> GoogleModel:
    """Gemini models via Google AI. API key from GOOGLE_API_KEY."""
    return GoogleModel(model_id)


register("google", _make_google)


# --- Groq ---

def _make_groq(model_id: str) -> GroqModel:
    """Fast inference via Groq. API key from GROQ_API_KEY."""
    return GroqModel(model_id)


register("groq", _make_groq)


# --- OpenRouter ---

def _make_openrouter(model_id: str) -> OpenAIModel:
    """
    OpenRouter — access to many models via one API.
    API key from OPENROUTER_API_KEY.

    # narrare: allow-direct-llm  reason="OpenRouter requires custom base_url"
    """
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    return OpenAIModel(
        model_id.removeprefix("openrouter/"),
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )


register("openrouter", _make_openrouter)
