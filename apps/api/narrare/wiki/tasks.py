"""Background tasks for wiki summary generation (ADR-080 — in-process).

Standalone ``run_wiki_*`` functions are invoked **directly** by
``WikiEventListener`` (``wiki/listeners.py``). There is no broker: the
listener awaits the runner in-process. The ``run_wiki_*`` functions are
transport-independent — they accept a zero-arg ``wiki_service_factory``
so the caller controls session/service construction.

Retry strategy: max 3 retries with exponential backoff (30s, 120s, 300s).
Freshness check ensures idempotent processing.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from narrare.wiki.service import APIWikiService

logger = structlog.get_logger(__name__)

SYSTEM_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")
_DEFAULT_RETRY_DELAYS: list[float] = [30.0, 120.0, 300.0]
_GenerateFn = Callable[[uuid.UUID, uuid.UUID], Awaitable[Any]]


async def run_wiki_generate_entity(
    entity_id: uuid.UUID,
    novel_id: uuid.UUID,
    *,
    wiki_service_factory: Callable[[], APIWikiService],
) -> bool:
    """Generate entity wiki summary with retry and idempotency.

    Returns True if generated, False if skipped (already fresh) or failed.
    """
    svc = wiki_service_factory()

    # Idempotency: skip if summary is already fresh.
    existing = await svc.get_summary_raw(entity_id, novel_id)
    if existing is not None and existing.status == "fresh":
        logger.info("wiki_entity_skipped_fresh", entity_id=str(entity_id))
        return False

    async def _gen(eid: uuid.UUID, nid: uuid.UUID) -> Any:
        return await svc.generate_entity_summary(eid, nid, SYSTEM_USER_ID)

    return await _retry_generate(_gen, entity_id, novel_id, context="wiki_entity")


async def run_wiki_generate_chapter(
    chapter_id: uuid.UUID,
    novel_id: uuid.UUID,
    *,
    wiki_service_factory: Callable[[], APIWikiService],
) -> bool:
    """Generate chapter wiki summary with retry and idempotency.

    Returns True if generated, False if skipped or failed.
    """
    svc = wiki_service_factory()

    existing = await svc.get_chapter_summary_raw(chapter_id)
    if existing is not None and existing.status == "fresh":
        logger.info("wiki_chapter_skipped_fresh", chapter_id=str(chapter_id))
        return False

    async def _gen(cid: uuid.UUID, nid: uuid.UUID) -> Any:
        return await svc.generate_chapter_summary(cid, nid, SYSTEM_USER_ID)  # type: ignore[attr-defined]  # reason: APIWikiService inherits method, type checker can't resolve through TYPE_CHECKING import chain

    return await _retry_generate(_gen, chapter_id, novel_id, context="wiki_chapter")


async def run_wiki_mark_all_stale(
    novel_id: uuid.UUID,
    prompt_version: str,
    *,
    wiki_service_factory: Callable[[], APIWikiService],
) -> int:
    """Mark all wiki summaries stale after a prompt change. No retry (DB only)."""
    svc = wiki_service_factory()
    try:
        count = await svc.mark_all_stale(novel_id, SYSTEM_USER_ID, prompt_version)
        logger.info("wiki_marked_stale", novel_id=str(novel_id), count=count)
        return count
    except Exception:
        logger.exception("wiki_mark_stale_failed", novel_id=str(novel_id))
        return 0


async def run_wiki_refresh_summary(
    entity_id: uuid.UUID,
    novel_id: uuid.UUID,
    *,
    wiki_service_factory: Callable[[], APIWikiService],
) -> bool:
    """Force-refresh a single entity wiki summary with retry."""
    svc = wiki_service_factory()

    async def _refresh(eid: uuid.UUID, nid: uuid.UUID) -> Any:
        return await svc.refresh_summary(eid, nid, SYSTEM_USER_ID, force=True)

    return await _retry_generate(_refresh, entity_id, novel_id, context="wiki_refresh")


async def _retry_generate(
    generate_fn: _GenerateFn,
    target_id: uuid.UUID,
    novel_id: uuid.UUID,
    *,
    context: str,
    retry_delays: list[float] | None = None,
) -> bool:
    """Execute ``generate_fn(target_id, novel_id)`` with exponential-backoff retry."""
    delays = retry_delays or _DEFAULT_RETRY_DELAYS
    max_retries = len(delays)
    for attempt in range(max_retries + 1):
        try:
            result = await generate_fn(target_id, novel_id)
            if result is not None:
                logger.info(f"{context}_completed", target_id=str(target_id), attempt=attempt)
                return True
            # Graceful None — retry unless exhausted.
            if attempt < max_retries:
                delay = delays[attempt]
                logger.warning(
                    f"{context}_retry_no_result",
                    target_id=str(target_id),
                    attempt=attempt + 1,
                    delay_seconds=delay,
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    f"{context}_permanently_failed", target_id=str(target_id), attempts=attempt + 1
                )
        except Exception as exc:
            if attempt < max_retries:
                delay = delays[attempt]
                logger.warning(
                    f"{context}_retry_exception",
                    target_id=str(target_id),
                    attempt=attempt + 1,
                    delay_seconds=delay,
                    error=str(exc),
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    f"{context}_permanently_failed", target_id=str(target_id), error=str(exc)
                )
    return False
