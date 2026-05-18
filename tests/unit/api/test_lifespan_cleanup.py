"""Unit tests for lifespan stale-generation cleanup helpers.

Tests the startup and periodic cleanup logic in isolation, using
mocked sessions and repositories.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from narrare._app.lifespan import _periodic_cleanup_loop, _run_stale_cleanup

# ---------------------------------------------------------------------------
# _run_stale_cleanup
# ---------------------------------------------------------------------------


class TestRunStaleCleanup:
    async def test_returns_count_from_repository(self) -> None:
        """_run_stale_cleanup() returns the count from cleanup_stale()."""
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()

        mock_factory = Mock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_repo = AsyncMock()
        mock_repo.cleanup_stale.return_value = 4

        with (
            patch("narrare._app.database._async_session_factory", mock_factory),
            patch("narrare.writing.repository.GenerationRepository", return_value=mock_repo),
        ):
            result = await _run_stale_cleanup()

        assert result == 4
        mock_repo.cleanup_stale.assert_awaited_once()
        mock_session.commit.assert_awaited_once()

    async def test_rollback_on_exception(self) -> None:
        """_run_stale_cleanup() rolls back and re-raises on failure."""
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()

        mock_factory = Mock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_repo = AsyncMock()
        mock_repo.cleanup_stale.side_effect = RuntimeError("db error")

        with (
            patch("narrare._app.database._async_session_factory", mock_factory),
            patch("narrare.writing.repository.GenerationRepository", return_value=mock_repo),
            pytest.raises(RuntimeError, match="db error"),
        ):
            await _run_stale_cleanup()

        mock_session.rollback.assert_awaited_once()
        mock_session.commit.assert_not_awaited()


# ---------------------------------------------------------------------------
# _periodic_cleanup_loop
# ---------------------------------------------------------------------------


class TestPeriodicCleanupLoop:
    async def test_loop_runs_cleanup_and_sleeps(self) -> None:
        """_periodic_cleanup_loop() calls _run_stale_cleanup() after sleep."""
        call_count = 0

        async def fake_cleanup() -> int:
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise asyncio.CancelledError()
            return 3

        with (
            patch("narrare._app.lifespan.asyncio.sleep", new_callable=AsyncMock),
            patch(
                "narrare._app.lifespan._run_stale_cleanup",
                side_effect=fake_cleanup,
            ),
            pytest.raises(asyncio.CancelledError),
        ):
            await _periodic_cleanup_loop()

        assert call_count == 2

    async def test_loop_continues_after_cleanup_error(self) -> None:
        """_periodic_cleanup_loop() does not stop on individual failures."""
        results: list[int] = []

        async def fake_cleanup() -> int:
            results.append(1)
            if len(results) == 1:
                raise RuntimeError("transient")
            raise asyncio.CancelledError()

        with (
            patch("narrare._app.lifespan.asyncio.sleep", new_callable=AsyncMock),
            patch(
                "narrare._app.lifespan._run_stale_cleanup",
                side_effect=fake_cleanup,
            ),
            pytest.raises(asyncio.CancelledError),
        ):
            await _periodic_cleanup_loop()

        # First call errored but loop continued to second call
        assert len(results) == 2
