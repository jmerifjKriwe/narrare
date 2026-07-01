"""
OpenAI provider adapter.

Registered as: "openai"
Models: gpt-*, o1, o3, text-embedding-* family
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from narrare_core.llm._providers.registry import register, register_model
from narrare_core.llm._transport_retry import get_transport_max_retries

if TYPE_CHECKING:
    from pydantic_ai.models import Model


def _make_openai(
    model_id: str,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
) -> Model:
    """Create an OpenAI model.

    Transport retry (transient 429/5xx/timeout) is governed at the provider
    layer via :func:`get_transport_max_retries` (ADR-060) and applied to the
    SDK client's ``max_retries`` — uniformly for ``run()`` and ``stream()``.

    Credential resolution (so retry applies on every call-bearing path,
    including the local-first operator-env path):

    * ``api_key`` arg (per-user credential from the DB) takes precedence;
    * otherwise the ``OPENAI_API_KEY`` environment variable is resolved.

    When a credential is resolvable, an explicit ``AsyncOpenAI`` client is
    constructed so the governed ``max_retries`` takes effect. When no
    credential is resolvable, construction is deferred to pydantic-ai (lazy
    env resolution) — this path cannot make real calls, so transport retry is
    not applicable, and deferral preserves the existing dev/test behaviour.

    Args:
        model_id: OpenAI model identifier (e.g. "gpt-4o").
        api_key: Optional API key — overrides env var when provided.
        base_url: Optional base URL — for proxies or compatible APIs.

    Returns:
        Configured OpenAIChatModel instance.
    """
    max_retries = get_transport_max_retries()
    resolved_key = api_key if api_key is not None else os.environ.get("OPENAI_API_KEY")
    if resolved_key is not None:
        client = AsyncOpenAI(api_key=resolved_key, base_url=base_url, max_retries=max_retries)
        return OpenAIChatModel(model_id, provider=OpenAIProvider(openai_client=client))
    # No resolvable credential: defer to pydantic-ai (cannot build a client
    # without a key; this path makes no real calls).
    if base_url is not None:
        return OpenAIChatModel(model_id, provider=OpenAIProvider(api_key=None, base_url=base_url))
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
