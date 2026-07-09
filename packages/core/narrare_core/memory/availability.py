"""mem0 availability and provider detection.

Encapsulates mem0 package detection and LLM provider auto-detection
from environment variables.  This module (together with ``mem0_client.py``)
is where mem0 is imported — nowhere else in the application.

RULE-08: mem0 is confined to ``narrare_core/memory/``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import structlog

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


@dataclass(frozen=True, slots=True)
class ProviderEnvConfig:
    """Detected provider config from environment variables."""

    provider: str
    api_key: str
    base_url: str | None = None


def is_mem0_available() -> bool:
    """Check whether the ``mem0`` package is installed.

    Returns ``True`` if ``mem0`` can be imported, ``False`` otherwise.
    """
    try:
        import mem0  # pyright: ignore[reportMissingTypeStubs]  # reason: mem0 has no type stubs

        del mem0
        return True
    except ImportError:
        return False


def detect_provider_from_env() -> ProviderEnvConfig | None:
    """Detect LLM provider from environment variables.

    Priority: openai → anthropic.
    Returns None if no credentials available.
    """
    for prov, key_env, url_env in _PROVIDER_ENV_VARS:
        key = os.environ.get(key_env)
        if key:
            return ProviderEnvConfig(
                provider=prov,
                api_key=key,
                base_url=os.environ.get(url_env),
            )
    return None
