"""LLM Model Registry and Agent Registry singletons.

Extracted from ``dependencies.py`` for RULE-04 modularisation.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from narrare_core.agents.registry import AgentRegistry
from narrare_core.llm import ModelRegistry

# ---------------------------------------------------------------------------
# LLM Model Registry (singleton)
# ---------------------------------------------------------------------------


@lru_cache
def _get_model_registry_instance() -> ModelRegistry:
    return ModelRegistry()


def get_model_registry() -> ModelRegistry:
    """Provide the shared LLM Model Registry instance."""
    return _get_model_registry_instance()


ModelRegistryDep = Annotated[ModelRegistry, Depends(get_model_registry)]


# ---------------------------------------------------------------------------
# Agent Registry (singleton — module-level, NOT @lru_cache)
# ---------------------------------------------------------------------------

_agent_registry: AgentRegistry | None = None


def get_agent_registry() -> AgentRegistry:
    """Provide the shared AgentRegistry singleton.

    AgentRegistry is mutable (has async state), so ``@lru_cache`` is not
    appropriate.  The module-level singleton pattern ensures a single
    instance across the application lifecycle.
    """
    global _agent_registry
    if _agent_registry is None:
        _agent_registry = AgentRegistry(max_size=50, ttl_seconds=300.0)
    return _agent_registry


AgentRegistryDep = Annotated[AgentRegistry, Depends(get_agent_registry)]
