"""Concrete KBSuggestedProvider backed by the KB repository.

Provides KB-suggested context for the invocation pipeline by querying
KB entries for the given project and formatting the top entities by
usage count as relevance-weighted lines.

This provider is a lightweight, read-only query — it creates a fresh
database session per call to avoid tying the singleton pipeline to a
request-scoped session.

Graceful degradation:
    - Returns ``""`` (empty string) when the project has no KB entries.
    - Returns ``""`` when project_id is ``None`` or not resolvable to a UUID.
    - Returns ``""`` and logs a warning when the DB query raises.

See:
    ADR-038, ADR-039, ADR-045, CONSTRAINTS.md RULE-03/RULE-06/RULE-11.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from narrare.kb.models import KBEntry

logger = structlog.get_logger(__name__)

#: Maximum number of KB entries to include in the suggested context output.
_MAX_SUGGESTED_ENTRIES: int = 5

#: Number of entries to fetch from the DB for in-memory relevance sorting.
_FETCH_SIZE: int = 20


def _resolve_novel_id(project_id: object | None) -> uuid.UUID | None:
    """Convert project_id to a UUID, or return None if not possible.

    Accepts ``uuid.UUID``, ``str``, or any type whose ``str()``
    representation is a valid UUID hex string.

    Args:
        project_id: The project identifier from the invocation context.

    Returns:
        UUID if convertible, ``None`` otherwise.
    """
    if project_id is None:
        return None
    if isinstance(project_id, uuid.UUID):
        return project_id
    if isinstance(project_id, str):
        try:
            return uuid.UUID(project_id)
        except ValueError:
            return None
    try:
        return uuid.UUID(str(project_id))
    except ValueError:
        return None


class KBSuggestedProviderImpl:
    """KBSuggestedProvider that queries the KB for suggested entities.

    Creates a database session per call via the injected session factory.
    Queries KB entries for the project, sorts by usage count descending,
    and returns the top :data:`_MAX_SUGGESTED_ENTRIES` formatted as
    relevance-weighted suggestions.

    Graceful degradation:
        Returns ``""`` if the project has no KB entries, the project_id
        is ``None``/unresolvable, or the DB query raises.

    Args:
        session_factory: Factory that creates async DB sessions (production).
            The provider opens a session, queries, and closes it per call.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def _get_kb_entries(
        self,
        novel_id: UUID,
    ) -> tuple[list[KBEntry], int]:
        """Query KB entries for the given novel.

        Separated into its own method so tests can patch it without
        needing a real database session.

        Args:
            novel_id: The novel/project UUID.

        Returns:
            A tuple of (entries, total_count).
        """
        # Lazy import to keep the module-level dependency graph clean.
        # KBRepository is an API-layer class; importing it eagerly
        # would couple core-level protocols to API-level DB access.
        from narrare.kb.repository import KBRepository

        async with self._session_factory() as session:
            repo = KBRepository(session)
            return await repo.list_entries(
                novel_id=novel_id,
                page=1,
                page_size=_FETCH_SIZE,
            )

    async def get_suggested_context(
        self,
        *,
        user_id: object | None = None,
        project_id: object | None = None,
        intent: str | None = None,
        mode: str | None = None,
    ) -> str:
        """Return KB-suggested context text for the given parameters.

        Queries the top KB entities for the project sorted by usage count,
        formats them as relevance-weighted lines.

        Args:
            user_id: Ignored in this implementation (reserved for future use).
            project_id: The project/novel UUID to query KB entries for.
            intent: Ignored in this implementation (reserved for future use).
            mode: Ignored in this implementation (reserved for future use).

        Returns:
            Formatted KB context text, or ``""`` if no entries found or
            ``project_id`` is not resolvable.
        """
        novel_id = _resolve_novel_id(project_id)
        if novel_id is None:
            logger.debug(
                "kb_suggested_provider_unresolvable_project",
                project_id_type=type(project_id).__name__ if project_id is not None else "None",
            )
            return ""

        try:
            entries, total = await self._get_kb_entries(novel_id)
        except Exception:
            logger.warning(
                "kb_suggested_provider_query_failed",
                novel_id=str(novel_id),
                exc_info=True,
            )
            return ""

        if not entries:
            logger.debug(
                "kb_suggested_provider_no_entries",
                novel_id=str(novel_id),
            )
            return ""

        # Sort by usage_count descending, take top N
        sorted_entries = sorted(
            entries,
            key=lambda e: e.usage_count or 0,
            reverse=True,
        )
        top_entries = sorted_entries[:_MAX_SUGGESTED_ENTRIES]

        max_usage = max(e.usage_count or 0 for e in top_entries)
        if max_usage == 0:
            # All entries have equal (zero) usage — treat relevance as equal
            lines = [f"{e.name} ({e.entity_type}), relevance: 1.00" for e in top_entries]
        else:
            lines = [
                f"{e.name} ({e.entity_type}), relevance: {(e.usage_count or 0) / max_usage:.2f}"
                for e in top_entries
            ]

        result = "\n".join(lines)
        logger.debug(
            "kb_suggested_provider_success",
            novel_id=str(novel_id),
            entry_count=len(top_entries),
            total_entries=total,
            result_length=len(result),
        )
        return result
