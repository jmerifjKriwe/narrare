"""Unit tests for wiki/tasks.py — system-plane session lifecycle (commit+close).

System-plane sessions have NO request-teardown commit — without an
explicit ``commit()`` the persisted summary rolls back when the session
is garbage-collected (2026-10-18 E2E finding: chapter summaries logged
"persisted" yet never became durable, and ``wiki_chapter_summaries``
stayed empty).  Split from test_wiki_tasks.py (RULE-04 file limit).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

from narrare.wiki.models import WikiSummary
from narrare.wiki.service import APIWikiService
from narrare.wiki.tasks import (
    run_wiki_generate_chapter,
    run_wiki_generate_entity,
    run_wiki_mark_all_stale,
)

if TYPE_CHECKING:
    from collections.abc import Callable

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_service(**overrides: object) -> MagicMock:
    """Create a mock APIWikiService with pre-configured async methods."""
    service = MagicMock(spec=APIWikiService)
    service.get_summary_raw = AsyncMock(return_value=None)
    service.get_chapter_summary_raw = AsyncMock(return_value=None)
    service.generate_entity_summary = AsyncMock(return_value=MagicMock(spec=object))
    service.generate_chapter_summary = AsyncMock(return_value=MagicMock(spec=object))
    service.refresh_summary = AsyncMock(return_value=MagicMock(spec=object))
    service.mark_all_stale = AsyncMock(return_value=0)
    # System-plane session lifecycle (tasks finalize their unit of work).
    service.commit = AsyncMock()
    service.close = AsyncMock()
    for key, value in overrides.items():
        setattr(service, key, value)
    return service


def _make_factory(service: MagicMock) -> Callable[[], MagicMock]:
    return lambda: service


# ---------------------------------------------------------------------------
# Tests: system-plane session lifecycle (commit + close)
# ---------------------------------------------------------------------------


class TestTaskSessionLifecycle:
    """run_wiki_* tasks finalize their factory-built service's session.

    System-plane sessions have NO request-teardown commit — without an
    explicit ``commit()`` the persisted summary rolls back when the
    session is garbage-collected (2026-10-18 E2E finding: chapter
    summaries logged "persisted" yet never became durable, and
    ``wiki_chapter_summaries`` stayed empty).
    """

    async def test_chapter_generate_commits_and_closes(self) -> None:
        """A generated chapter summary is committed (durability) and closed."""
        svc = _make_mock_service()
        chapter_id, novel_id = uuid.uuid4(), uuid.uuid4()

        result = await run_wiki_generate_chapter(
            chapter_id, novel_id, wiki_service_factory=_make_factory(svc)
        )

        assert result is True
        svc.commit.assert_awaited_once()
        svc.close.assert_awaited_once()

    async def test_entity_generate_commits_and_closes(self) -> None:
        """A generated entity summary is committed and the session closed."""
        svc = _make_mock_service()

        result = await run_wiki_generate_entity(
            uuid.uuid4(), uuid.uuid4(), wiki_service_factory=_make_factory(svc)
        )

        assert result is True
        svc.commit.assert_awaited_once()
        svc.close.assert_awaited_once()

    async def test_skip_fresh_closes_without_commit(self) -> None:
        """The idempotent skip wrote nothing — close runs, commit does not."""
        existing = MagicMock(spec=WikiSummary)
        existing.status = "fresh"
        svc = _make_mock_service(get_summary_raw=AsyncMock(return_value=existing))

        result = await run_wiki_generate_entity(
            uuid.uuid4(), uuid.uuid4(), wiki_service_factory=_make_factory(svc)
        )

        assert result is False
        svc.commit.assert_not_awaited()
        svc.close.assert_awaited_once()

    async def test_close_runs_after_permanent_failure(self) -> None:
        """Retry exhaustion still releases the session (no leak on failure)."""
        svc = _make_mock_service(generate_chapter_summary=AsyncMock(return_value=None))

        with patch("narrare.wiki.tasks.asyncio.sleep", new_callable=AsyncMock):
            result = await run_wiki_generate_chapter(
                uuid.uuid4(), uuid.uuid4(), wiki_service_factory=_make_factory(svc)
            )

        assert result is False
        svc.close.assert_awaited_once()

    async def test_mark_all_stale_commits_and_closes(self) -> None:
        """The DB-only staleness update is committed, then released."""
        svc = _make_mock_service(mark_all_stale=AsyncMock(return_value=2))

        result = await run_wiki_mark_all_stale(
            uuid.uuid4(), "2.0.0", wiki_service_factory=_make_factory(svc)
        )

        assert result == 2
        svc.commit.assert_awaited_once()
        svc.close.assert_awaited_once()

    async def test_mark_all_stale_closes_on_exception(self) -> None:
        """A failing staleness update still releases the session."""
        svc = _make_mock_service(mark_all_stale=AsyncMock(side_effect=RuntimeError("DB down")))

        result = await run_wiki_mark_all_stale(
            uuid.uuid4(), "2.0.0", wiki_service_factory=_make_factory(svc)
        )

        assert result == 0
        svc.commit.assert_not_awaited()
        svc.close.assert_awaited_once()
