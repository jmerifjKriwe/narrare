"""Existing-KB-entries access for extraction — dedup + world context (RULE-04 split).

Extracted from ``extraction_service.py`` when that file hit the 300-line
hard limit (IDOR remediation S10): the service keeps the orchestration
(chapter load, prompt composition, agent run), this module owns the
"what does the novel's KB already contain" lookup — a single fetch whose
result feeds both the dedup name list and the curated world context.

The graceful variant degrades to an empty list when the KB repo is
unavailable (RULE-11) so extraction can proceed without dedup data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.kb.contracts import KBRepositoryProtocol
    from narrare.kb.models import KBEntry

logger = structlog.get_logger(__name__)


async def list_existing_entries(
    kb_repo: KBRepositoryProtocol,
    novel_id: UUID,
    user_id: UUID,
) -> list[KBEntry]:
    """Fetch existing KB entries for the novel (dedup + world context).

    Args:
        kb_repo: KB entry repository — the data source.
        novel_id: The novel whose KB entries to fetch.
        user_id: Requesting user (ownership is enforced by the caller's
            novel gate before this helper runs).

    Returns:
        All KB entries of the novel (single page of 1000).

    Raises:
        Exception: Repository errors propagate — error-tolerant callers
            should use :func:`list_existing_entries_graceful`.
    """
    entries, _ = await kb_repo.list_entries(
        novel_id=novel_id,
        entity_type=None,
        tags=None,
        page=1,
        page_size=1000,
    )
    return list(entries)


async def list_existing_entries_graceful(
    kb_repo: KBRepositoryProtocol,
    novel_id: UUID,
    user_id: UUID,
) -> list[KBEntry]:
    """Fetch existing KB entries with graceful degradation (RULE-11).

    If the KB repo is unavailable (DB connection lost, timeout, etc.),
    returns an empty list so extraction can proceed without dedup data
    or world context. Logs a warning so the failure is visible.

    Args:
        kb_repo: KB entry repository — the data source.
        novel_id: The novel whose KB entries to fetch.
        user_id: Requesting user (ownership is enforced by the caller's
            novel gate before this helper runs).

    Returns:
        All KB entries of the novel, or ``[]`` on repository failure.
    """
    try:
        return await list_existing_entries(kb_repo, novel_id, user_id)
    except Exception as exc:
        logger.warning(
            "kb_repo_unavailable_using_empty_dedup",
            novel_id=str(novel_id),
            error=str(exc),
        )
        return []
