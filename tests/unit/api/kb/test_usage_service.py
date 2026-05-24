"""Unit tests for ContextUsageService.

Tests accept/dismiss tracking and usage counter updates using
a fake session that captures SQL executions.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

from narrare.kb.usage_service import ContextUsageService

# ---------------------------------------------------------------------------
# Fake session — captures execute calls for assertions
# ---------------------------------------------------------------------------


class FakeResult:
    """Fake query result for get_usage_stats and session.execute."""

    def __init__(self, rows: list[tuple[str, int]] | None = None) -> None:
        self._rows = rows or []

    def fetchall(self) -> list[tuple[str, int]]:
        return self._rows


class FakeSession:
    """Minimal async session that records execute calls."""

    def __init__(self) -> None:
        self.executed: list[tuple[str, dict[str, object]]] = []
        self._flush = AsyncMock()

    async def execute(
        self, statement: object, params: dict[str, object] | None = None
    ) -> FakeResult:
        """Record the SQL statement and params."""
        sql_text = getattr(statement, "text", str(statement))
        self.executed.append((sql_text, params or {}))
        return FakeResult([])

    async def flush(self) -> None:
        await self._flush()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRecordAccept:
    """Accept increments usage_count and updates last_referenced_at."""

    async def test_accept_inserts_event_and_updates_counters(self) -> None:
        """record_accept inserts an event and updates kb_entries."""
        session = FakeSession()
        service = ContextUsageService(session)  # type: ignore[arg-type]  # type: ignore[arg-type]

        novel_id = uuid.uuid4()
        entry_id = uuid.uuid4()
        chapter_id = uuid.uuid4()

        await service.record_accept(novel_id, entry_id, chapter_id, "proactive")

        # Should have two execute calls: INSERT event + UPDATE kb_entries
        assert len(session.executed) == 2

        event_sql, event_params = session.executed[0]
        assert "INSERT INTO context_usage_events" in event_sql
        assert "'accepted'" in event_sql
        assert event_params["entry_id"] == str(entry_id)
        assert event_params["source"] == "proactive"

        update_sql, update_params = session.executed[1]
        assert "UPDATE kb_entries" in update_sql
        assert "usage_count = usage_count + 1" in update_sql
        assert "last_referenced_at = now()" in update_sql
        assert update_params["entry_id"] == str(entry_id)

    async def test_accept_without_chapter_id(self) -> None:
        """record_accept works with chapter_id=None."""
        session = FakeSession()
        service = ContextUsageService(session)  # type: ignore[arg-type]

        await service.record_accept(uuid.uuid4(), uuid.uuid4(), None, "search")

        event_params = session.executed[0][1]
        assert event_params["chapter_id"] is None

    async def test_double_accept_increments_twice(self) -> None:
        """Two accepts result in two counter updates."""
        session = FakeSession()
        service = ContextUsageService(session)  # type: ignore[arg-type]

        entry_id = uuid.uuid4()

        await service.record_accept(uuid.uuid4(), entry_id, None, "proactive")
        await service.record_accept(uuid.uuid4(), entry_id, None, "proactive")

        # 4 execute calls: 2 inserts + 2 updates
        assert len(session.executed) == 4

        update_calls = [sql for sql, _ in session.executed if "UPDATE kb_entries" in sql]
        assert len(update_calls) == 2


class TestRecordDismiss:
    """Dismiss does not update usage_count."""

    async def test_dismiss_inserts_event_only(self) -> None:
        """record_dismiss inserts an event but does NOT update kb_entries."""
        session = FakeSession()
        service = ContextUsageService(session)  # type: ignore[arg-type]

        novel_id = uuid.uuid4()
        entry_id = uuid.uuid4()

        await service.record_dismiss(novel_id, entry_id, None, "proactive")

        # Only one execute call: INSERT event (no UPDATE)
        assert len(session.executed) == 1

        event_sql, event_params = session.executed[0]
        assert "INSERT INTO context_usage_events" in event_sql
        assert "'dismissed'" in event_sql
        assert event_params["entry_id"] == str(entry_id)

    async def test_dismiss_does_not_update_usage_count(self) -> None:
        """Verify no UPDATE kb_entries on dismiss."""
        session = FakeSession()
        service = ContextUsageService(session)  # type: ignore[arg-type]

        await service.record_dismiss(uuid.uuid4(), uuid.uuid4(), None, "search")

        update_calls = [sql for sql, _ in session.executed if "UPDATE kb_entries" in sql]
        assert len(update_calls) == 0


class TestGetUsageStats:
    """Usage stats returned correctly."""

    async def test_stats_returns_accept_and_dismiss_counts(self) -> None:
        """get_usage_stats returns correct accept/dismiss counts."""
        session = FakeSession()
        service = ContextUsageService(session)  # type: ignore[arg-type]

        entry_id = uuid.uuid4()

        # Mock the execute to return usage stats
        fake_result = FakeResult(
            [
                ("accepted", 5),
                ("dismissed", 3),
            ]
        )

        async def mock_execute(
            statement: object, params: dict[str, object] | None = None
        ) -> FakeResult:
            return fake_result

        session.execute = mock_execute  # type: ignore[assignment]

        stats = await service.get_usage_stats(entry_id)

        assert stats == {"accepted": 5, "dismissed": 3}

    async def test_stats_returns_zeros_when_no_events(self) -> None:
        """get_usage_stats returns zeros for entries with no events."""
        session = FakeSession()
        service = ContextUsageService(session)  # type: ignore[arg-type]

        fake_result = FakeResult([])

        async def mock_execute(
            statement: object, params: dict[str, object] | None = None
        ) -> FakeResult:
            return fake_result

        session.execute = mock_execute  # type: ignore[assignment]

        stats = await service.get_usage_stats(uuid.uuid4())

        assert stats == {"accepted": 0, "dismissed": 0}

    async def test_stats_only_counts_known_actions(self) -> None:
        """get_usage_stats ignores unknown action types."""
        session = FakeSession()
        service = ContextUsageService(session)  # type: ignore[arg-type]

        # pinned is in the DB but not in our stats dict
        fake_result = FakeResult(
            [
                ("accepted", 2),
                ("pinned", 1),
            ]
        )

        async def mock_execute(
            statement: object, params: dict[str, object] | None = None
        ) -> FakeResult:
            return fake_result

        session.execute = mock_execute  # type: ignore[assignment]

        stats = await service.get_usage_stats(uuid.uuid4())

        assert stats == {"accepted": 2, "dismissed": 0}
