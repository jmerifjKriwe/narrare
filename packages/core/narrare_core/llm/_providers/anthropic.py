"""
Anthropic provider adapter.

Registered as: "anthropic"
Models: claude-* family
"""

from __future__ import annotations

from pydantic_ai.models.anthropic import AnthropicModel

from narrare_core.llm._providers.registry import register, register_model


def _make_anthropic(model_id: str) -> AnthropicModel:
    """Create an Anthropic model. API key from ANTHROPIC_API_KEY env var."""
    return AnthropicModel(model_id)


register("anthropic", _make_anthropic)

# Register known Claude model IDs explicitly — avoids prefix-based inference
for _mid in [
    "claude-sonnet-4-5-20251020",
    "claude-haiku-3-5-20241022",
    "claude-opus-4-20250514",
]:
    register_model(_mid, "anthropic")
