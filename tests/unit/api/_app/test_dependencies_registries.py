"""Unit tests for ``narrare._app.dependencies_registries`` — agent registry.

Covers the ``get_agent_registry()`` creation path (lines 49-51) which is
not exercised by existing tests.
"""

from __future__ import annotations

import narrare._app.dependencies_registries as registries_mod
from narrare._app.dependencies_registries import get_agent_registry, get_model_registry


class TestGetAgentRegistry:
    def test_creates_registry_when_none(self) -> None:
        """When _agent_registry is None, a new AgentRegistry is created."""
        original = registries_mod._agent_registry
        registries_mod._agent_registry = None
        try:
            registry = get_agent_registry()
            assert registry is not None
            assert registries_mod._agent_registry is registry
        finally:
            registries_mod._agent_registry = original

    def test_returns_existing_registry(self) -> None:
        """When _agent_registry exists, returns it without creating new."""
        original = registries_mod._agent_registry
        try:
            # Ensure registry is created
            first = get_agent_registry()
            # Second call returns same instance
            second = get_agent_registry()
            assert first is second
        finally:
            registries_mod._agent_registry = original


class TestGetModelRegistry:
    def test_returns_registry_instance(self) -> None:
        registry = get_model_registry()
        assert registry is not None
