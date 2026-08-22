# apps/api/narrare/notes/embedding_dispatch.py
"""In-process embedding dispatch for notes (ADR-080, NOTES-001 §6a).

Thin mirror of ``narrare.kb.embedding_hooks``: schedules
``run_embed_source_inprocess("note", ...)`` via ``asyncio.create_task``
fire-and-forget and holds a strong reference against GC. The task itself
performs content-hash idempotency (skips unchanged content), so no hook
manager is needed (spec §3).
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import structlog

from narrare.embeddings.tasks import run_embed_source_inprocess

if TYPE_CHECKING:
    from uuid import UUID

logger = structlog.get_logger(__name__)

#: Strong references to in-flight embedding coroutines (ADR-080 GC guard).
_INFLIGHT_TASKS: set[asyncio.Task[None]] = set()


def _on_done(task: asyncio.Task[None]) -> None:
    """Discard the GC-guard reference; log surfaced failures (RULE-11)."""
    _INFLIGHT_TASKS.discard(task)
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.error("note_background_task_failed", error=str(exc), exc_info=exc)


class InProcessNoteEmbeddingDispatch:
    """Dispatches note embeddings in-process; swappable seam (ADR-080)."""

    async def dispatch(self, note_id: UUID, text: str) -> None:
        task = asyncio.create_task(run_embed_source_inprocess("note", str(note_id), text))
        _INFLIGHT_TASKS.add(task)
        task.add_done_callback(_on_done)
        logger.info("note_embedding_task_dispatched", note_id=str(note_id))
