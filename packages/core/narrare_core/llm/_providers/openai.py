"""
OpenAI provider adapter.

Registered as: "openai"
Models: gpt-*, o1, o3, text-embedding-* family
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from narrare_core.llm._providers.registry import register, register_model

if TYPE_CHECKING:
    from pydantic_ai.models import Model


def _make_openai(
    model_id: str,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
) -> Model:
    """Create an OpenAI model.

    When ``api_key`` or ``base_url`` is provided, creates an explicit
    ``AsyncOpenAI`` client with those credentials. Otherwise falls back
    to ``OPENAI_API_KEY`` env var (for dev/test).

    Args:
        model_id: OpenAI model identifier (e.g. "gpt-4o").
        api_key: Optional API key — overrides env var when provided.
        base_url: Optional base URL — for proxies or compatible APIs.

    Returns:
        Configured OpenAIChatModel instance.
    """
    if api_key is not None or base_url is not None:
        return OpenAIChatModel(
            model_id,
            provider=OpenAIProvider(api_key=api_key, base_url=base_url),
        )
    return OpenAIChatModel(model_id)


register("openai", _make_openai)

# Register known OpenAI model IDs explicitly — avoids prefix-based inference
for _mid in [
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4-turbo",
    "gpt-3.5-turbo",
    "o1-preview",
    "o1-mini",
    "o3-mini",
    "text-embedding-3-small",
]:
    register_model(_mid, "openai")
