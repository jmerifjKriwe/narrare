"""
Provider auto-registration.

Importing this package registers all providers in the registry.
The gateway imports this package on startup.
"""

# Import all providers to trigger their register() calls
from narrare_core.llm._providers import (  # noqa: F401
    anthropic,  # type: ignore[import]
    ollama,  # type: ignore[import]
    openai,  # type: ignore[import]
    others,  # type: ignore[import]
    zai,  # type: ignore[import]
)
from narrare_core.llm._providers.registry import (
    available,
    get,
    infer_provider,
    register,
)

__all__ = ["available", "get", "infer_provider", "register"]
