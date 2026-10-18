"""System-plane session lifecycle for the wiki service.

Mixin for APIWikiService that finalizes units of work owned by
system-plane callers (background tasks, event listeners).  Request-plane
sessions commit in ``get_async_session`` teardown; factory-built system
sessions have no such teardown, so their owners must commit and release
explicitly (RULE-04 split from service.py — one responsibility per file).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


class WikiSessionLifecycle:
    """Mixin providing commit/close for system-plane units of work.

    Subclasses must set ``self._session`` (an AsyncSession) before
    calling these methods.
    """

    _session: AsyncSession

    async def commit(self) -> None:
        """Commit the session's pending writes (system-plane units of work).

        Request-plane sessions commit in ``get_async_session`` teardown;
        system-plane services (the WikiEventListener factory) own their
        session and must finalize writes explicitly — an uncommitted
        system session is rolled back when garbage-collected, silently
        discarding persisted summaries (2026-10-18 E2E finding: chapter
        summaries never became durable).
        """
        await self._session.commit()

    async def close(self) -> None:
        """Release the session, rolling back any active transaction.

        Teardown path for system-plane units of work — safe after
        ``commit`` (a committed session holds no active transaction).
        A release failure is logged, not raised (RULE-11): teardown
        must not mask the unit of work's own outcome.
        """
        try:
            await self._session.rollback()
            await self._session.close()
        except Exception:
            logger.exception("wiki_service_session_release_failed")
