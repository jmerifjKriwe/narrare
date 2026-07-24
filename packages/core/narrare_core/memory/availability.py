"""mem0 availability and provider detection.

Encapsulates mem0 package detection and LLM provider auto-detection
from environment variables.  This module (together with ``mem0_client.py``)
is where mem0 is imported — nowhere else in the application.

RULE-08: mem0 is confined to ``narrare_core/memory/``.
"""

from __future__ import annotations

from dataclasses import dataclass

import structlog

from narrare_core.settings import get_core_settings

logger = structlog.get_logger(__name__)


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
    settings = get_core_settings()
    # Priority: openai first (matches default memory models), then anthropic.
    openai_key = settings.openai_api_key
    if openai_key:
        return ProviderEnvConfig(
            provider="openai", api_key=openai_key, base_url=settings.openai_base_url
        )
    anthropic_key = settings.anthropic_api_key
    if anthropic_key:
        return ProviderEnvConfig(
            provider="anthropic",
            api_key=anthropic_key,
            base_url=settings.anthropic_base_url,
        )
    return None
