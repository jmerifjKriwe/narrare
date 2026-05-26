"""
Ollama provider adapter (local models).

Registered as: "ollama"
Models: any model served by Ollama (llama3, mistral, etc.)
URL from OLLAMA_BASE_URL env var (default: http://localhost:11434)

Note: No explicit model IDs registered here because Ollama model IDs
are user-defined. Prefix-based inference ("ollama/" prefix) handles routing.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from narrare_core.llm._providers.registry import register

if TYPE_CHECKING:
    from pydantic_ai.models import Model


def _make_ollama(
    model_id: str,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
) -> Model:
    """Create an Ollama model via its OpenAI-compatible endpoint.

    When ``base_url`` is provided, uses it directly. Otherwise falls
    back to the ``OLLAMA_BASE_URL`` environment variable.

    Args:
        model_id: Model identifier (may include "ollama/" prefix).
        api_key: Ignored for Ollama (uses dummy key).
        base_url: Optional base URL — overrides OLLAMA_BASE_URL env var.

    Returns:
        Configured OpenAIChatModel pointing at Ollama endpoint.
    """
    resolved_base = base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    # Ollama's OpenAI-compatible endpoint
    return OpenAIChatModel(
        model_id.removeprefix("ollama/"),
        provider=OpenAIProvider(
            base_url=f"{resolved_base.rstrip('/')}/v1",
            api_key="ollama",  # Ollama ignores the key but pydantic-ai requires one
        ),
    )


register("ollama", _make_ollama)
