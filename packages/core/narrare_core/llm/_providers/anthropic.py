"""
Anthropic provider adapter.

Registered as: "anthropic"
Models: claude-* family
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic_ai.models.anthropic import AnthropicModel

from narrare_core.llm._providers.registry import register, register_model

if TYPE_CHECKING:
    from pydantic_ai.models import Model


def _make_anthropic(
    model_id: str,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
) -> Model:
    """Create an Anthropic model.

    When ``api_key`` is provided, uses it directly. Otherwise falls
    back to the ``ANTHROPIC_API_KEY`` environment variable (for dev/test).

    Args:
        model_id: Anthropic model identifier (e.g. "claude-sonnet-4-5-20251020").
        api_key: Optional API key — overrides env var when provided.
        base_url: Ignored for Anthropic (uses official API endpoint).

    Returns:
        Configured AnthropicModel instance.
    """
    if api_key is not None or base_url is not None:
        from pydantic_ai.providers.anthropic import AnthropicProvider

        return AnthropicModel(
            model_id,
            provider=AnthropicProvider(api_key=api_key, base_url=base_url),
        )
    return AnthropicModel(model_id)


register("anthropic", _make_anthropic)

# Register known Claude model IDs explicitly — avoids prefix-based inference
for _mid in [
    "claude-sonnet-4-5-20251020",
    "claude-haiku-3-5-20241022",
    "claude-opus-4-20250514",
]:
    register_model(_mid, "anthropic")
