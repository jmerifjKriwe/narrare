"""Shared fixtures for adaptive unit tests (ADR-070 Task 4).

Minimal stub fakes for ``AdaptiveContextProvider`` and
``AdaptiveSettingsRepositoryProtocol``. ``get_adaptive_snapshots`` does not
call the provider or settings repo, so these stubs only need to satisfy the
``AdaptiveContextService`` constructor's structural types.

``fake_novel_repo`` (IDOR remediation S11c) is a permissive ownership fake:
these are BEHAVIOR tests (persistence, clamping, mapping), not ownership
tests — the gate always passes. The ownership matrix lives in
``test_adaptive_settings_ownership.py`` with a real owned-map fake.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from narrare.novels.models import Novel
from narrare_core.ai_invocation.adaptive_context import (
    AdaptiveContext,
    AdaptiveSettings,
)
from tests.fakes._shared import CallRecord
from tests.fakes.fake_novel_repo import FakeNovelRepository

if TYPE_CHECKING:
    from uuid import UUID


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


class _PermissiveNovelRepo(FakeNovelRepository):
    """Ownership-permissive novel repository.

    Every (novel, user) pair resolves to an owned novel — for behavior
    tests that must not be blocked by the S11c ownership gate. Extends the
    full ``FakeNovelRepository`` so the structural
    ``NovelRepositoryProtocol`` contract stays satisfied.
    """

    async def get_by_id(self, novel_id: UUID, user_id: UUID) -> Novel | None:
        self.calls.append(
            CallRecord("get_by_id", kwargs={"novel_id": novel_id, "user_id": user_id})
        )
        return Novel(id=novel_id, user_id=user_id)


@pytest.fixture
def fake_novel_repo() -> _PermissiveNovelRepo:
    """Return an ownership-permissive novel repo (behavior tests only)."""
    return _PermissiveNovelRepo()
