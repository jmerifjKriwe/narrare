"""Provider-specific prompt caching ModelSettings.

Maps CacheSettings to provider-specific pydantic-ai ModelSettings kwargs.
Isolated per RULE-06 (one responsibility per file).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from narrare_core.llm.model_config import CacheSettings


def build_model_settings(
    provider_name: str,
    cache: CacheSettings | None,
) -> dict[str, Any]:
    """Build provider-specific ModelSettings kwargs for prompt caching.

    Returns a dict of kwargs to pass to Agent.run(model_settings=...).

    Provider mapping:
    - anthropic: {"cache_control": True} via AnthropicModelSettings
    - openai / groq / zai / openrouter: {} (automatic, no config needed)
    - google: {} (when pydantic-ai supports it)
    - ollama: {} (no caching)
    """
    if cache is None or not cache.enabled:
        return {}

    match provider_name:
        case "anthropic":
            return {"cache_control": True}
        case "google":
            return {}  # Future: cached_contents API
        case "openai" | "groq" | "zai" | "openrouter":
            return {}  # Automatic server-side caching
        case "ollama":
            return {}  # No caching support
        case _:
            return {}
