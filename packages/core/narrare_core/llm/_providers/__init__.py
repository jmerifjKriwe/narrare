"""
Provider auto-registration.

Importing this package registers all providers in the registry.
The gateway imports this package on startup.
"""

# Import all providers to trigger their register() calls
from narrare_core.llm._providers import (  # noqa: F401
    anthropic,
    openai,
    zai,
    ollama,
    others,
)

from narrare_core.llm._providers.registry import (
    get,
    available,
    infer_provider,
    register,
)

__all__ = ["get", "available", "infer_provider", "register"]
