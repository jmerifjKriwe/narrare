"""
OpenAI provider adapter.

Registered as: "openai"
Models: gpt-*, o1, o3, text-embedding-* family
"""

from __future__ import annotations

from pydantic_ai.models.openai import OpenAIChatModel

from narrare_core.llm._providers.registry import register, register_model


def _make_openai(model_id: str) -> OpenAIChatModel:
    """Create an OpenAI model. API key from OPENAI_API_KEY env var."""
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
