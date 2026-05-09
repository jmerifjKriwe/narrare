"""
LLM provider registry.

Maps provider names to pydantic-ai model factory functions.
The gateway uses this registry — no provider-specific code anywhere else.

To add a new provider:
1. Create apps/api/narrare_core/llm/_providers/<name>.py
2. Register it here
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic_ai.models import Model


@runtime_checkable
class ProviderFactory(Protocol):
    """Protocol for provider factory functions."""

    def __call__(self, model_id: str) -> Model:
        """Create a pydantic-ai Model instance for the given model ID."""
        ...


_REGISTRY: dict[str, ProviderFactory] = {}


def register(name: str, factory: ProviderFactory) -> None:
    """Register a provider factory by name."""
    _REGISTRY[name] = factory


def get(name: str) -> ProviderFactory:
    """
    Get a provider factory by name.

    Args:
        name: Provider name (e.g. "anthropic", "openai", "zai").

    Returns:
        Factory function that creates a pydantic-ai Model.

    Raises:
        KeyError: If provider is not registered.
    """
    if name not in _REGISTRY:
        available = ", ".join(sorted(_REGISTRY.keys()))
        raise KeyError(
            f"Unknown provider '{name}'. Available: {available}. "
            "Register new providers in llm/_providers/registry.py."
        )
    return _REGISTRY[name]


def available() -> list[str]:
    """Return list of registered provider names."""
    return sorted(_REGISTRY.keys())


def infer_provider(model_id: str) -> str:
    """
    Infer provider name from a model ID string.

    Args:
        model_id: Model identifier string.

    Returns:
        Provider name.

    Examples:
        "claude-sonnet-4-5-20251020" → "anthropic"
        "gpt-4o" → "openai"
        "glm-z1-32b" → "zai"
        "ollama/llama3" → "ollama"
        "openrouter/..." → "openrouter"
    """
    lower = model_id.lower()

    if lower.startswith("claude"):
        return "anthropic"
    if lower.startswith(("gpt-", "o1", "o3", "text-")):
        return "openai"
    if lower.startswith("glm") or lower.startswith("chatglm"):
        return "zai"
    if lower.startswith("gemini"):
        return "google"
    if lower.startswith("ollama/") or "/" not in lower and lower.startswith("llama"):
        return "ollama"
    if lower.startswith("openrouter/"):
        return "openrouter"
    if lower.startswith("mixtral") or lower.startswith("llama") and "/" not in lower:
        return "groq"

    # Default fallback — try openai-compatible
    return "openai"
