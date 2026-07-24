"""Shared fixtures for adaptive unit tests (ADR-070 Task 4).

Minimal stub fakes for ``AdaptiveContextProvider`` and
``AdaptiveSettingsRepositoryProtocol``. ``get_adaptive_snapshots`` does not
call the provider or settings repo, so these stubs only need to satisfy the
``AdaptiveContextService`` constructor's structural types.
"""

from __future__ import annotations

import pytest

from narrare_core.ai_invocation.adaptive_context import (
    AdaptiveContext,
    AdaptiveSettings,
)


class _StubAdaptiveProvider:
    """Minimal AdaptiveContextProvider stub (functional, never asserted)."""

    async def get_context(
        self,
        user_id: object,
        project_id: object,
    ) -> AdaptiveContext:
        return AdaptiveContext(user_id=user_id, project_id=project_id)  # type: ignore[arg-type]

    async def get_settings(
        self,
        user_id: object,
        project_id: object,
    ) -> AdaptiveSettings:
        return AdaptiveSettings()


class _StubSettingsRepo:
    """Minimal AdaptiveSettingsRepository stub (functional, never asserted)."""

    async def load(self, project_id: object) -> AdaptiveSettings | None:
        del project_id
        return None

    async def save(self, project_id: object, settings: AdaptiveSettings) -> None:
        del project_id, settings


@pytest.fixture
def fake_provider() -> _StubAdaptiveProvider:
    """Return a stub AdaptiveContextProvider (ADR-070 Task 4)."""
    return _StubAdaptiveProvider()


@pytest.fixture
def fake_settings_repo() -> _StubSettingsRepo:
    """Return a stub AdaptiveSettingsRepository (ADR-070 Task 4)."""
    return _StubSettingsRepo()
