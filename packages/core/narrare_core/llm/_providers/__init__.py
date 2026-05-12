"""
Provider auto-registration.

Importing this package registers all providers in the registry.
The gateway imports this package on startup.
"""

# Import all providers to trigger their register() calls
from narrare_core.llm._providers import (  # noqa: F401
    anthropic,  # pyright: ignore[reportUnusedImport]
    ollama,  # pyright: ignore[reportUnusedImport]
    openai,  # pyright: ignore[reportUnusedImport]
    others,  # pyright: ignore[reportUnusedImport]
    zai,  # pyright: ignore[reportUnusedImport]
)
from narrare_core.llm._providers.registry import (
    available,
    get,
    infer_provider,
    register,
    register_model,
)

__all__ = ["available", "get", "infer_provider", "register", "register_model"]
