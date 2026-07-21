"""Phase 3 tests for AdaptiveContextProviderImpl — DB-backed get_settings().

Extracted from ``test_adaptive_context_provider.py`` for RULE-04 file-size
discipline (Phase 2 + Phase 3 together exceeded the 400-line test cap).

Phase 3 scope (ADR-069 Task 4):
- ``get_settings()`` loads from ``ProjectSettings.adaptive_settings`` JSONB
  via the wired ``AdaptiveSettingsRepository``.
- Phase 2 contract preserved: defaults are returned when no repo is wired,
  when no DB row exists, or when the load raises (RULE-11 graceful
  degradation).

See: ADR-069 Decision 2 / Decision 3, CONSTRAINTS.md RULE-11.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from narrare.adaptive.adaptive_context_provider import (
    AdaptiveContextProviderImpl,
)
from narrare_core.ai_invocation.adaptive_context import (
    AdaptiveSettings,
    AdaptiveWeights,
)


class FakeSettingsRepo:
    """Async fake AdaptiveSettingsRepository for the provider extension."""

    def __init__(self, loaded: AdaptiveSettings | None = None) -> None:
        self._loaded = loaded

    async def load(self, project_id: object) -> AdaptiveSettings | None:
        del project_id
        return self._loaded

    async def save(self, project_id: object, settings: AdaptiveSettings) -> None:
        del project_id, settings


class TestGetSettingsPhase3DB:
    """Phase 3: get_settings() loads from DB when a repo is wired."""

    @pytest.mark.asyncio
    async def test_returns_db_settings_when_repo_wired(self) -> None:
        db_settings = AdaptiveSettings(
            enabled=False,
            weights=AdaptiveWeights(preference=0.3, voice_fidelity=0.5),
        )
        impl = AdaptiveContextProviderImpl(
            preference_provider=None,
            profile_provider=None,
            settings_repo=FakeSettingsRepo(loaded=db_settings),  # type: ignore[arg-type]
        )
        result = await impl.get_settings(user_id=uuid4(), project_id=uuid4())
        assert result.enabled is False
        assert result.weights.preference == 0.3

    @pytest.mark.asyncio
    async def test_returns_defaults_when_repo_returns_none(self) -> None:
        """Phase 2 contract preserved: NULL row → defaults."""
        impl = AdaptiveContextProviderImpl(
            preference_provider=None,
            profile_provider=None,
            settings_repo=FakeSettingsRepo(loaded=None),  # type: ignore[arg-type]
        )
        result = await impl.get_settings(user_id=uuid4(), project_id=uuid4())
        assert result.enabled is True
        assert result.weights.preference == 0.7

    @pytest.mark.asyncio
    async def test_returns_defaults_when_repo_is_none(self) -> None:
        """Phase 2 contract preserved: no repo wired → defaults."""
        impl = AdaptiveContextProviderImpl(
            preference_provider=None,
            profile_provider=None,
            settings_repo=None,
        )
        result = await impl.get_settings(user_id=uuid4(), project_id=uuid4())
        assert result.enabled is True
        assert result.weights.preference == 0.7
