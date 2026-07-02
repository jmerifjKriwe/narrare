"""Tests for settings/token_limits/dependencies — DI factories.

The dependency-injection factories in ``dependencies.py`` are router-layer
wiring (RULE-06). These tests cover the stateless metadata-service factory,
which was previously only exercised indirectly (and not at all in unit tests).
"""

from __future__ import annotations

from narrare.settings.token_limits.dependencies import get_token_limits_metadata_service
from narrare.settings.token_limits.metadata_service import TokenLimitsMetadataService


def test_get_token_limits_metadata_service_returns_stateless_instance() -> None:
    """The metadata-service factory returns a stateless service instance."""
    svc = get_token_limits_metadata_service()
    assert isinstance(svc, TokenLimitsMetadataService)
    # Each call returns a fresh instance (no shared mutable state).
    assert get_token_limits_metadata_service() is not svc
