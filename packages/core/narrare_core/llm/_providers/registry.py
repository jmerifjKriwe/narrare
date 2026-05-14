"""
LLM provider registry.

Maps provider names to pydantic-ai model factory functions.
The gateway uses this registry — no provider-specific code anywhere else.

To add a new provider:
1. Create packages/core/narrare_core/llm/_providers/<name>.py
2. Register it with register("name", factory)
3. Optionally register known model IDs with register_model()

Factory functions accept optional ``api_key`` and ``base_url`` kwargs.
When provided, these override environment variable defaults, enabling
per-user credentials from the database.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pydantic_ai.models import Model


@runtime_checkable
class ProviderFactory(Protocol):
    """Protocol for provider factory functions.

    Factory functions create a ``pydantic-ai Model`` instance for a
    given model ID. They accept optional credentials that override
    environment variable defaults — this enables per-user API keys
    stored in the database.

    When ``api_key`` and ``base_url`` are both ``None``, the factory
    falls back to environment variables for backward compatibility
    with dev/test environments.
    """

    def __call__(
        self,
        model_id: str,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> Model:
        """Create a pydantic-ai Model instance for the given model ID.

        Args:
            model_id: Model identifier (e.g. "claude-sonnet-4-5-20251020").
            api_key: Optional API key — overrides env var when provided.
            base_url: Optional base URL — overrides provider default.

        Returns:
            Configured pydantic-ai Model instance.
        """
        ...


_REGISTRY: dict[str, ProviderFactory] = {}

# Explicit model → provider mapping. Checked before prefix matching.
_MODEL_PROVIDER_MAP: dict[str, str] = {}

# Ordered prefix → provider mapping. Most specific prefixes first.
# Order matters: "chatglm" before "glm", "ollama/" before "llama", etc.
_PROVIDER_PREFIXES: list[tuple[str, str]] = [
    ("claude", "anthropic"),
    ("gpt-", "openai"),
    ("o1-", "openai"),
    ("o3-", "openai"),
    ("text-", "openai"),
    ("chatglm", "zai"),
    ("glm", "zai"),
    ("gemini", "google"),
    ("ollama/", "ollama"),
    ("openrouter/", "openrouter"),
    ("mixtral", "groq"),
    ("llama", "ollama"),
]


def register(name: str, factory: ProviderFactory) -> None:
    """Register a provider factory by name."""
    _REGISTRY[name] = factory


def register_model(model_id: str, provider_name: str) -> None:
    """Register an explicit model → provider mapping.

    Registered model IDs are matched exactly (case-insensitive) before
    prefix-based inference. Use this for known model IDs to avoid
    relying on heuristics.
    """
    _MODEL_PROVIDER_MAP[model_id.lower()] = provider_name


def get(name: str) -> ProviderFactory:
    """
    Get a provider factory by name.

    The returned factory accepts optional ``api_key`` and ``base_url``
    keyword arguments for per-request credential pass-through.

    Args:
        name: Provider name (e.g. "anthropic", "openai", "zai").

    Returns:
        Factory function that creates a pydantic-ai Model.
        Call with ``(model_id, api_key=..., base_url=...)`` to pass
        explicit credentials, or just ``(model_id)`` for env var fallback.

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

    .. deprecated::
        ``infer_provider`` is retained as a dev/debugging utility only.
        The runtime model routing path uses explicit ``provider_name``
        from ``ResolvedModelConfig`` — never inference.

    Resolution order:
    1. Explicit model → provider mapping (via register_model)
    2. Prefix-based matching against _PROVIDER_PREFIXES
    3. Default fallback to "openai" (openai-compatible)

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

    # 1. Check explicit mapping first
    if lower in _MODEL_PROVIDER_MAP:
        return _MODEL_PROVIDER_MAP[lower]

    # 2. Fall back to prefix matching
    for prefix, provider in _PROVIDER_PREFIXES:
        if lower.startswith(prefix):
            return provider

    # 3. Default fallback — try openai-compatible
    return "openai"
