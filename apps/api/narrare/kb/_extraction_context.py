"""Extraction context helpers — existing KB entry fetch for dedup/world context.

Extracted from ``extraction_service.py`` for RULE-04 compliance (hard
300-line service limit). Owns the existing-entries data path used for dedup
names and curated world context; the LLM orchestration stays in the service.

See:
    :class:`narrare.kb.extraction_service.ExtractionService`
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.kb.contracts import KBRepositoryProtocol
    from narrare.kb.models import KBEntry

logger = structlog.get_logger(__name__)


async def fetch_existing_entries(
    kb_repo: KBRepositoryProtocol,
    novel_id: UUID,
    user_id: UUID,
) -> list[KBEntry]:
    """Fetch existing KB entries for the novel (dedup + world context).

    Repository errors propagate — error-tolerant callers should use
    :func:`fetch_existing_entries_graceful`.
    """
    entries, _ = await kb_repo.list_entries(
        novel_id=novel_id,
        entity_type=None,
        tags=None,
        page=1,
        page_size=1000,
    )
    return list(entries)


async def fetch_existing_entries_graceful(
    kb_repo: KBRepositoryProtocol,
    novel_id: UUID,
    user_id: UUID,
) -> list[KBEntry]:
    """Fetch existing KB entries with graceful degradation (RULE-11).

    If the KB repo is unavailable (DB connection lost, timeout, etc.),
    returns an empty list so extraction can proceed without dedup data
    or world context. Logs a warning so the failure is visible.
    """
    try:
        return await fetch_existing_entries(kb_repo, novel_id, user_id)
    except Exception as exc:
        logger.warning(
            "kb_repo_unavailable_using_empty_dedup",
            novel_id=str(novel_id),
            error=str(exc),
        )
        return []
