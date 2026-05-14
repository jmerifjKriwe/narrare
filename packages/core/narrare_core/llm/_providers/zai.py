"""
Z.AI provider adapter.

Registered as: "zai"
Models: glm-* family via Z.AI OpenAI-compatible endpoints

Z.AI exposes two endpoints:
- General API: https://api.z.ai/api/paas/v4
- Coding API:  https://api.z.ai/api/coding/paas/v4

See: docs/agents/architecture/questions/Q-005-resolved.md
ADR: ADR-006 (tech stack)
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from narrare_core.llm._providers.registry import register, register_model

if TYPE_CHECKING:
    from pydantic_ai.models import Model

_ZAI_GENERAL_URL = "https://api.z.ai/api/paas/v4"
_ZAI_CODING_URL = "https://api.z.ai/api/coding/paas/v4"


def _make_zai(
    model_id: str,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
) -> Model:
    """
    Create a Z.AI model using the General API endpoint.

    When ``api_key`` is provided, uses it directly. Otherwise falls back
    to the ``ZAI_API_KEY`` environment variable.

    # narrare: allow-direct-llm  reason="Z.AI requires custom base_url — OpenAI-compatible"

    Args:
        model_id: Z.AI model identifier (e.g. "glm-z1-32b").
        api_key: Optional API key — overrides env var when provided.
        base_url: Optional base URL — defaults to Z.AI General API.

    Returns:
        Configured OpenAIChatModel via Z.AI endpoint.
    """
    resolved_key = api_key or os.environ.get("ZAI_API_KEY", "")
    resolved_base = base_url or _ZAI_GENERAL_URL
    return OpenAIChatModel(
        model_id,
        provider=OpenAIProvider(base_url=resolved_base, api_key=resolved_key),
    )


def make_zai_coding(
    model_id: str,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
) -> Model:
    """
    Create a Z.AI model using the Coding API endpoint.

    Used for code-generation intents. Not registered by default —
    call explicitly when needed.

    # narrare: allow-direct-llm  reason="Z.AI coding endpoint requires custom base_url"

    Args:
        model_id: Z.AI model identifier.
        api_key: Optional API key — overrides env var when provided.
        base_url: Optional base URL — defaults to Z.AI Coding API.

    Returns:
        Configured OpenAIChatModel via Z.AI Coding endpoint.
    """
    resolved_key = api_key or os.environ.get("ZAI_API_KEY", "")
    resolved_base = base_url or _ZAI_CODING_URL
    return OpenAIChatModel(
        model_id,
        provider=OpenAIProvider(base_url=resolved_base, api_key=resolved_key),
    )


register("zai", _make_zai)

# Register known Z.AI model IDs explicitly — avoids prefix-based inference
for _mid in [
    "glm-z1-32b",
    "glm-4-flash",
    "glm-4-plus",
    "chatglm-4",
]:
    register_model(_mid, "zai")
