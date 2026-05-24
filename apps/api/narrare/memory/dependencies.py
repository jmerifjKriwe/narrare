"""Memory module dependencies — factory functions for DI.

Provides ``get_memory_client()`` which creates a mem0 client using
application-level config values for the memory model and embedding model.
This wires ``settings.memory_llm_model`` and ``settings.memory_embedding_model``
into ``create_memory_client()`` so the hardcoded ``_PROVIDER_DEFAULT_MODELS``
can be overridden via configuration.

Usage in router::

    @router.post("/feedback")
    async def record_feedback(
        request: FeedbackRequest,
        mem0_client: Any = Depends(get_memory_client),
    ):
        ...
"""

from __future__ import annotations

import os
from typing import Annotated, Any

import structlog
from fastapi import Depends

from narrare._app.config import Settings, get_settings
from narrare_core.memory.mem0_client import NullMemoryClient, create_memory_client

logger = structlog.get_logger(__name__)

# Priority-ordered list of (provider_name, env_var_key, env_var_base_url)
# Used to detect the active LLM provider from environment variables.
_PROVIDER_ENV_VARS: list[tuple[str, str, str]] = [
    ("openai", "OPENAI_API_KEY", "OPENAI_BASE_URL"),
    ("anthropic", "ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL"),
]
"""LLM provider detection order.

OpenAI is checked first because the default ``memory_llm_model``
(``gpt-4o-mini``) and ``memory_embedding_model`` (``text-embedding-3-small``)
are both OpenAI models.
"""


async def get_memory_client(
    settings: Settings = Depends(get_settings),  # noqa: B008 — FastAPI DI pattern
) -> Any:
    """Create a mem0 AsyncMemory client with config overrides.

    Passes ``settings.memory_llm_model`` and ``settings.memory_embedding_model``
    to ``create_memory_client()``, overriding the hardcoded provider defaults
    from ``_PROVIDER_DEFAULT_MODELS``.

    Detects the LLM provider and API key from environment variables.
    Falls back to ``NullMemoryClient`` when no credentials are available or
    when client creation fails — Tier 4 of the embedding cascade.

    Returns
    -------
    Any
        A ``mem0.AsyncMemory`` instance, or ``NullMemoryClient`` as fallback.
        The ``Any`` return type matches ``create_memory_client()`` because
        mem0 may not be installed.
    """
    # Detect LLM provider from available credentials
    provider: str | None = None
    api_key: str | None = None
    base_url: str | None = None

    for prov, key_env, url_env in _PROVIDER_ENV_VARS:
        key = os.environ.get(key_env)
        if key:
            provider = prov
            api_key = key
            base_url = os.environ.get(url_env)
            break

    if not provider or not api_key:
        logger.info(
            "mem0_no_credentials",
            message="No LLM provider credentials found — using NullMemoryClient",
        )
        return NullMemoryClient()

    try:
        client = await create_memory_client(
            provider=provider,
            api_key=api_key,
            base_url=base_url,
            memory_model=settings.memory_llm_model,
            embedding_model=settings.memory_embedding_model,
        )
        logger.info(
            "mem0_client_created_from_deps",
            provider=provider,
            memory_model=settings.memory_llm_model,
            embedding_model=settings.memory_embedding_model,
        )
        return client
    except Exception:
        logger.exception(
            "mem0_client_factory_failed",
            provider=provider,
        )
        return NullMemoryClient()


MemoryClientDep = Annotated[Any, Depends(get_memory_client)]
"""Type alias for FastAPI dependency injection of a mem0 client.

Usage::

    async def my_endpoint(
        mem0_client: MemoryClientDep,
    ):
        ...

Always resolves to either a ``mem0.AsyncMemory`` instance or
``NullMemoryClient`` — never ``None``.
"""
