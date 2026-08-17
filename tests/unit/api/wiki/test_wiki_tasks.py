"""Unit tests for wiki/tasks.py — retry logic, idempotency, mark-all-stale.

Tests the standalone run_wiki_* functions using a mock APIWikiService.
Verifies retry behavior, idempotency checks, and graceful failure handling.

Also covers the Q-016 global staleness path end-to-end at unit level:
the run_wiki_mark_all_stale_global wrapper (mock service) plus the
unscoped WikiRepository.mark_all_stale_global UPDATE it drives (mock
AsyncSession — SQL semantics are proven in tests/integration/api/wiki).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from narrare.wiki.models import WikiSummary
from narrare.wiki.repository import WikiRepository
from narrare.wiki.service import APIWikiService
from narrare.wiki.tasks import (
    SYSTEM_USER_ID,
    run_wiki_generate_chapter,
    run_wiki_generate_entity,
    run_wiki_mark_all_stale,
    run_wiki_mark_all_stale_global,
    run_wiki_refresh_summary,
)

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
    for key, value in overrides.items():
        setattr(service, key, value)
    return service


def _make_factory(service: MagicMock) -> MagicMock:
    """Return a zero-arg factory that produces the given service."""
    factory = MagicMock(spec=Callable, return_value=service)
    return factory


def _make_update_session(rowcount: int = 0) -> AsyncMock:
    """Mocked AsyncSession whose execute() result carries ``rowcount``.

    Same pattern as ``tests/unit/api/test_evidence_repository.py``:
    UPDATE-only repository methods have no result mapping, so the
    compiled statement and the rowcount passthrough are the observable
    outputs.
    """
    session = AsyncMock(spec=AsyncSession)
    result = MagicMock(spec=["rowcount"])
    result.rowcount = rowcount
    session.execute = AsyncMock(return_value=result)
    return session


# ---------------------------------------------------------------------------
# Tests: run_wiki_generate_entity
# ---------------------------------------------------------------------------


class TestRunWikiGenerateEntity:
    """run_wiki_generate_entity — happy path, idempotency, retry."""

    async def test_generates_entity_summary(self) -> None:
        """Returns True when generation succeeds."""
        svc = _make_mock_service()
        entity_id = uuid.uuid4()
        novel_id = uuid.uuid4()

        result = await run_wiki_generate_entity(
            entity_id, novel_id, wiki_service_factory=_make_factory(svc)
        )

        assert result is True
        svc.generate_entity_summary.assert_called_once_with(entity_id, novel_id, SYSTEM_USER_ID)

    async def test_skips_when_summary_is_fresh(self) -> None:
        """Returns False when an existing summary has status 'fresh'."""
        existing = MagicMock(spec=WikiSummary)
        existing.status = "fresh"
        svc = _make_mock_service(get_summary_raw=AsyncMock(return_value=existing))

        result = await run_wiki_generate_entity(
            uuid.uuid4(), uuid.uuid4(), wiki_service_factory=_make_factory(svc)
        )

        assert result is False
        svc.generate_entity_summary.assert_not_called()

    async def test_generates_when_summary_is_stale(self) -> None:
        """Proceeds with generation when existing summary is stale."""
        existing = MagicMock(spec=WikiSummary)
        existing.status = "stale"
        svc = _make_mock_service(get_summary_raw=AsyncMock(return_value=existing))

        result = await run_wiki_generate_entity(
            uuid.uuid4(), uuid.uuid4(), wiki_service_factory=_make_factory(svc)
        )

        assert result is True
        svc.generate_entity_summary.assert_called_once()

    async def test_returns_false_on_permanent_failure(self) -> None:
        """Returns False after all retries are exhausted."""
        svc = _make_mock_service(generate_entity_summary=AsyncMock(return_value=None))

        with patch("narrare.wiki.tasks.asyncio.sleep", new_callable=AsyncMock):
            result = await run_wiki_generate_entity(
                uuid.uuid4(), uuid.uuid4(), wiki_service_factory=_make_factory(svc)
            )

        assert result is False
        # Called once per attempt (initial + retries)
        assert svc.generate_entity_summary.call_count == 4  # max_retries(3) + 1


# ---------------------------------------------------------------------------
# Tests: run_wiki_generate_chapter
# ---------------------------------------------------------------------------


class TestRunWikiGenerateChapter:
    """run_wiki_generate_chapter — happy path, idempotency."""

    async def test_generates_chapter_summary(self) -> None:
        """Returns True when chapter generation succeeds."""
        svc = _make_mock_service()
        chapter_id = uuid.uuid4()
        novel_id = uuid.uuid4()

        result = await run_wiki_generate_chapter(
            chapter_id, novel_id, wiki_service_factory=_make_factory(svc)
        )

        assert result is True
        svc.generate_chapter_summary.assert_called_once_with(chapter_id, novel_id, SYSTEM_USER_ID)

    async def test_skips_when_chapter_summary_is_fresh(self) -> None:
        """Returns False when an existing chapter summary has status 'fresh'."""
        existing = MagicMock(spec=WikiSummary)
        existing.status = "fresh"
        svc = _make_mock_service(get_chapter_summary_raw=AsyncMock(return_value=existing))

        result = await run_wiki_generate_chapter(
            uuid.uuid4(), uuid.uuid4(), wiki_service_factory=_make_factory(svc)
        )

        assert result is False
        svc.generate_chapter_summary.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: run_wiki_mark_all_stale
# ---------------------------------------------------------------------------


class TestRunWikiMarkAllStale:
    """run_wiki_mark_all_stale — happy path, error handling."""

    async def test_marks_stale_and_returns_count(self) -> None:
        """Returns the count from mark_all_stale."""
        svc = _make_mock_service(mark_all_stale=AsyncMock(return_value=5))
        novel_id = uuid.uuid4()

        count = await run_wiki_mark_all_stale(
            novel_id, "2.0.0", wiki_service_factory=_make_factory(svc)
        )

        assert count == 5
        svc.mark_all_stale.assert_called_once_with(novel_id, SYSTEM_USER_ID, "2.0.0")

    async def test_returns_zero_on_exception(self) -> None:
        """Returns 0 when mark_all_stale raises (graceful failure)."""
        svc = _make_mock_service(mark_all_stale=AsyncMock(side_effect=RuntimeError("DB error")))

        count = await run_wiki_mark_all_stale(
            uuid.uuid4(), "1.0.0", wiki_service_factory=_make_factory(svc)
        )

        assert count == 0


# ---------------------------------------------------------------------------
# Tests: run_wiki_mark_all_stale_global (Q-016)
# ---------------------------------------------------------------------------


class TestRunWikiMarkAllStaleGlobal:
    """run_wiki_mark_all_stale_global — happy path, error handling (Q-016)."""

    async def test_marks_all_stale_and_returns_count(self) -> None:
        """Returns the count from mark_all_stale_global."""
        svc = _make_mock_service(mark_all_stale_global=AsyncMock(return_value=7))

        count = await run_wiki_mark_all_stale_global(
            "2.0.0", wiki_service_factory=_make_factory(svc)
        )

        assert count == 7
        svc.mark_all_stale_global.assert_awaited_once_with()

    async def test_returns_zero_on_exception(self) -> None:
        """Returns 0 when mark_all_stale_global raises (graceful failure)."""
        svc = _make_mock_service(
            mark_all_stale_global=AsyncMock(side_effect=RuntimeError("DB error"))
        )

        count = await run_wiki_mark_all_stale_global(
            "1.0.0", wiki_service_factory=_make_factory(svc)
        )

        assert count == 0


# ---------------------------------------------------------------------------
# Tests: WikiRepository.mark_all_stale_global (Q-016)
# ---------------------------------------------------------------------------


class TestWikiRepositoryMarkAllStaleGlobal:
    """WikiRepository.mark_all_stale_global — the global UPDATE behind Q-016.

    The unscoped breadth is the contract: the UPDATE must carry NO
    novel/version filter — that is what distinguishes the global
    prompt-override path (Q-016) from the per-novel, version-gated
    ``mark_all_stale``. With the session faked, the compiled statement
    is the only observable output.
    """

    async def test_executes_unscoped_update_and_returns_rowcount(self) -> None:
        """Global UPDATE sets status='stale' with no WHERE; rowcount passes through."""
        session = _make_update_session(rowcount=41)
        repo = WikiRepository(session=session)

        count = await repo.mark_all_stale_global()

        assert count == 41
        session.execute.assert_awaited_once()
        stmt = session.execute.call_args[0][0]
        assert stmt.__visit_name__ == "update"
        compiled = stmt.compile()
        assert "UPDATE wiki_summaries" in str(compiled)
        assert compiled.params["status"] == "stale"
        assert "WHERE" not in str(compiled)  # Q-016: global, no novel scoping
        session.flush.assert_awaited_once()


# ---------------------------------------------------------------------------
# Tests: run_wiki_refresh_summary
# ---------------------------------------------------------------------------


class TestRunWikiRefreshSummary:
    """run_wiki_refresh_summary — happy path, retry."""

    async def test_refreshes_summary(self) -> None:
        """Returns True when refresh succeeds."""
        svc = _make_mock_service()
        entity_id = uuid.uuid4()
        novel_id = uuid.uuid4()

        result = await run_wiki_refresh_summary(
            entity_id, novel_id, wiki_service_factory=_make_factory(svc)
        )

        assert result is True
        svc.refresh_summary.assert_called_once_with(entity_id, novel_id, SYSTEM_USER_ID, force=True)

    async def test_returns_false_on_permanent_failure(self) -> None:
        """Returns False after all retries exhausted on None returns."""
        svc = _make_mock_service(refresh_summary=AsyncMock(return_value=None))

        with patch("narrare.wiki.tasks.asyncio.sleep", new_callable=AsyncMock):
            result = await run_wiki_refresh_summary(
                uuid.uuid4(), uuid.uuid4(), wiki_service_factory=_make_factory(svc)
            )

        assert result is False


# ---------------------------------------------------------------------------
# Tests: _retry_generate internals
# ---------------------------------------------------------------------------


class TestRetryGenerate:
    """Internal _retry_generate behavior — exception retry, sleep delays."""

    async def test_retries_on_exception_then_succeeds(self) -> None:
        """Succeeds after initial exception on second attempt."""
        call_count = 0

        async def flaky_fn(tid: uuid.UUID, nid: uuid.UUID) -> object:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                msg = "Transient failure"
                raise RuntimeError(msg)
            return MagicMock(spec=object)

        from narrare.wiki.tasks import _retry_generate

        with patch("narrare.wiki.tasks.asyncio.sleep", new_callable=AsyncMock):
            result = await _retry_generate(flaky_fn, uuid.uuid4(), uuid.uuid4(), context="test")

        assert result is True
        assert call_count == 2

    async def test_returns_false_after_all_retries_exhausted(self) -> None:
        """Returns False after exception-based retries are exhausted."""

        async def always_fail(tid: uuid.UUID, nid: uuid.UUID) -> None:
            msg = "Permanent failure"
            raise RuntimeError(msg)

        from narrare.wiki.tasks import _retry_generate

        with patch("narrare.wiki.tasks.asyncio.sleep", new_callable=AsyncMock):
            result = await _retry_generate(always_fail, uuid.uuid4(), uuid.uuid4(), context="test")

        assert result is False

    async def test_retry_sleeps_match_default_retry_delays_constant(self) -> None:
        """The actual sleep delays equal the imported _DEFAULT_RETRY_DELAYS constant.

        This ties the governed default (asserted in
        test_cr08_p2_operator_defaults.py against the manifest value) to
        the runtime behaviour. If someone unwires _DEFAULT_RETRY_DELAYS
        from _retry_generate and hardcodes different delays, this test
        fails — even though the constant still has the 'right' value.
        """
        from narrare.wiki.tasks import _DEFAULT_RETRY_DELAYS, _retry_generate

        async def always_fail(tid: uuid.UUID, nid: uuid.UUID) -> None:
            msg = "Permanent failure"
            raise RuntimeError(msg)

        with patch("narrare.wiki.tasks.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await _retry_generate(always_fail, uuid.uuid4(), uuid.uuid4(), context="test")

        sleep_calls = [call.args[0] for call in mock_sleep.call_args_list]
        assert sleep_calls == _DEFAULT_RETRY_DELAYS, (
            f"_retry_generate slept for {sleep_calls} but _DEFAULT_RETRY_DELAYS "
            f"is {_DEFAULT_RETRY_DELAYS}. The constant must be wired into the "
            "retry loop — do not hardcode separate delays."
        )
