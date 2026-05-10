"""
OpenAI provider adapter.

Registered as: "openai"
Models: gpt-*, o1, o3, text-embedding-* family
"""

from __future__ import annotations

from pydantic_ai.models.openai import OpenAIChatModel

from narrare_core.llm._providers.registry import register


def _make_openai(model_id: str) -> OpenAIChatModel:
    """Create an OpenAI model. API key from OPENAI_API_KEY env var."""
    return OpenAIChatModel(model_id)


register("openai", _make_openai)
