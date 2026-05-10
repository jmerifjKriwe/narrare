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

from pydantic_ai.models.openai import OpenAIChatModel

from narrare_core.llm._providers.registry import register

_ZAI_GENERAL_URL = "https://api.z.ai/api/paas/v4"
_ZAI_CODING_URL = "https://api.z.ai/api/coding/paas/v4"


def _make_zai(model_id: str) -> OpenAIChatModel:
    """
    Create a Z.AI model using the General API endpoint.

    API key from ZAI_API_KEY environment variable.

    # narrare: allow-direct-llm  reason="Z.AI requires custom base_url — OpenAI-compatible"
    """
    api_key = os.environ.get("ZAI_API_KEY", "")
    return OpenAIChatModel(  # type: ignore[call-arg]
        model_id,
        base_url=_ZAI_GENERAL_URL,
        api_key=api_key,
    )


def make_zai_coding(model_id: str) -> OpenAIChatModel:
    """
    Create a Z.AI model using the Coding API endpoint.

    Used for code-generation intents. Not registered by default —
    call explicitly when needed.

    # narrare: allow-direct-llm  reason="Z.AI coding endpoint requires custom base_url"
    """
    api_key = os.environ.get("ZAI_API_KEY", "")
    return OpenAIChatModel(  # type: ignore[call-arg]
        model_id,
        base_url=_ZAI_CODING_URL,
        api_key=api_key,
    )


register("zai", _make_zai)
