"""
Ollama provider adapter (local models).

Registered as: "ollama"
Models: any model served by Ollama (llama3, mistral, etc.)
URL from OLLAMA_BASE_URL env var (default: http://localhost:11434)
"""

from __future__ import annotations

import os

from pydantic_ai.models.openai import OpenAIModel

from narrare_core.llm._providers.registry import register


def _make_ollama(model_id: str) -> OpenAIModel:
    """
    Create an Ollama model via its OpenAI-compatible endpoint.

    # narrare: allow-direct-llm  reason="Ollama requires custom base_url"
    """
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    # Ollama's OpenAI-compatible endpoint
    return OpenAIModel(
        model_id.removeprefix("ollama/"),
        base_url=f"{base_url.rstrip('/')}/v1",
        api_key="ollama",  # Ollama ignores the key but pydantic-ai requires one
    )


register("ollama", _make_ollama)
