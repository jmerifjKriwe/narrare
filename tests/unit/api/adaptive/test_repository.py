"""Tests for AdaptiveSettingsRepository (RULE-14 JSONB persistence).

Verifies load/save round-trip + graceful degradation when no row exists.
Uses FakeSession (in-memory) — no DB I/O.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from narrare.adaptive.repository import AdaptiveSettingsRepository
from narrare_core.ai_invocation.adaptive_context import (
    AdaptiveSettings,
    AdaptiveWeights,
)


class _FakeResult:
    def __init__(self, row: dict[str, Any] | None) -> None:
        self._row = row
        # Mimics SQLAlchemy CursorResult.rowcount for UPDATE statements.
        # 0 means "no row matched" → repository inserts a new ProjectSettings
        # row (exercised by TestAdaptiveSettingsRepositorySave).
        self.rowcount = 0

    def scalar_one_or_none(self) -> dict[str, Any] | None:
        # Real SQLAlchemy scalar_one_or_none() returns the first column's
        # value (not a wrapped row dict). The repo selects
        # ProjectSettings.adaptive_settings, so extract that key from the
        # mocked row dict to correctly simulate the production behaviour.
        if self._row is None:
            return None
        return self._row.get("adaptive_settings")


class _FakeSession:
    def __init__(self, row: dict[str, Any] | None = None) -> None:
        self._row = row
        self.add_calls: list[Any] = []
        self.flush_calls = 0

    async def execute(self, stmt: Any) -> _FakeResult:
        del stmt
        return _FakeResult(self._row)

    def add(self, model: Any) -> None:
        self.add_calls.append(model)

    async def flush(self) -> None:
        self.flush_calls += 1


def _make_settings() -> AdaptiveSettings:
    return AdaptiveSettings(
        enabled=True,
        weights=AdaptiveWeights(preference=0.42, voice_fidelity=0.81),
    )


class TestAdaptiveSettingsRepositoryLoad:
    """load() returns AdaptiveSettings when row exists."""

    @pytest.mark.asyncio
    async def test_load_returns_settings_when_row_exists(self) -> None:
        row = {
            "adaptive_settings": {
                "enabled": False,
                "weights": {
                    "preference": 0.3,
                    "voice_fidelity": 0.5,
                    "style_constraints": 0.7,
                    "avoidance": 0.9,
                },
            }
        }
        repo = AdaptiveSettingsRepository(_FakeSession(row=row))  # type: ignore[arg-type]
        result = await repo.load(project_id=uuid4())
        assert result is not None
        assert result.enabled is False
        assert result.weights.preference == 0.3
        assert result.weights.voice_fidelity == 0.5

    @pytest.mark.asyncio
    async def test_load_returns_none_when_no_row(self) -> None:
        repo = AdaptiveSettingsRepository(_FakeSession(row=None))  # type: ignore[arg-type]
        result = await repo.load(project_id=uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_load_returns_none_when_column_null(self) -> None:
        """Existing rows have NULL adaptive_settings — graceful fallback."""
        row = {"adaptive_settings": None}
        repo = AdaptiveSettingsRepository(_FakeSession(row=row))  # type: ignore[arg-type]
        result = await repo.load(project_id=uuid4())
        assert result is None


class TestAdaptiveSettingsRepositorySave:
    """save() upserts the adaptive_settings JSONB column."""

    @pytest.mark.asyncio
    async def test_save_calls_flush(self) -> None:
        session = _FakeSession(row=None)
        repo = AdaptiveSettingsRepository(session)  # type: ignore[arg-type]
        await repo.save(project_id=uuid4(), settings=_make_settings())
        assert session.flush_calls >= 1
