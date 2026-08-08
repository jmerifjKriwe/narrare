"""Embedding generation — standalone runner + in-process entry point.

Per ADR-080, embedding generation runs **in-process** via
``asyncio.create_task`` (no broker, no worker process). This module
provides:

- ``run_embed_source`` — the transport-independent standalone runner that
  owns the ``[30.0, 120.0, 300.0]s`` retry loop and is callable directly.
- ``run_embed_source_inprocess`` — the in-process entry point that builds
  its **own** DB session (via ``get_session_factory()``), calls the
  standalone runner, and commits/rolls back. Dispatched fire-and-forget
  by ``EmbeddingHookManager._dispatch_task``.

Retry strategy: max 3 retries with exponential backoff (30s, 120s, 300s).
Content-hash comparison ensures idempotent processing — if the content
hasn't changed since the last embedding, the task is skipped entirely.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import structlog

from narrare_core.embeddings.hash import compute_content_hash
from narrare_core.llm.embeddings import embed_texts
from narrare_core.shared.errors import EmbeddingError

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.embeddings.contracts import EmbeddingRepositoryProtocol

logger = structlog.get_logger(__name__)

_DEFAULT_RETRY_DELAYS: list[float] = [30.0, 120.0, 300.0]


async def run_embed_source(
    source_type: str,
    source_id: UUID,
    content: str,
    *,
    repo: EmbeddingRepositoryProtocol,
    model: str | None = None,
    dimension: int | None = None,
    retry_delays: list[float] | None = None,
) -> bool:
    """Generate embedding for a source entity with retry and idempotency.

    This is the standalone entry point that can be called directly.
    The TaskIQ decorator wrapper calls this function.

    Steps:
    1. Compute content hash
    2. Compare with stored hash — skip if identical (idempotent)
    3. Generate embedding via ``embed_texts()``
    4. Upsert via repository

    Args:
        source_type: Content type label (e.g. "kb_entry").
        source_id: UUID of the source entity.
        content: Text content to embed.
        repo: Embedding repository for upsert/get operations.
        model: Embedding model override.
        dimension: Embedding dimension override.

    Returns:
        True if embedding was generated, False if skipped (unchanged).
    """
    effective_model = model or "text-embedding-3-small"
    effective_dimension = dimension or 1536
    delays = retry_delays or _DEFAULT_RETRY_DELAYS
    max_retries = len(delays)

    # Step 1: Compute content hash
    content_hash = compute_content_hash(content)

    # Step 2: Check idempotency — skip if hash matches stored
    existing = await repo.get_by_source(source_type, source_id, model=effective_model)
    if existing is not None and existing.content_hash == content_hash:
        logger.info(
            "embed_source_skipped_unchanged",
            source_type=source_type,
            source_id=str(source_id),
        )
        return False

    # Step 3: Generate embedding with retry
    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            vectors = await embed_texts([content], model=effective_model)
            if not vectors:
                raise EmbeddingError("Embedding returned no vectors")

            vector = vectors[0]

            # Step 4: Upsert
            await repo.upsert(
                source_type=source_type,
                source_id=source_id,
                content_hash=content_hash,
                embedding=vector,
                model=effective_model,
                dimension=effective_dimension,
            )
            logger.info(
                "embed_source_completed",
                source_type=source_type,
                source_id=str(source_id),
                model=effective_model,
                attempt=attempt,
            )
            return True

        except Exception as exc:
            last_error = exc
            if attempt < max_retries:
                delay = delays[attempt]
                logger.warning(
                    "embed_source_retry",
                    source_type=source_type,
                    source_id=str(source_id),
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    delay_seconds=delay,
                    error=str(exc),
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    "embed_source_permanently_failed",
                    source_type=source_type,
                    source_id=str(source_id),
                    attempts=attempt + 1,
                    error=str(exc),
                )

    # All retries exhausted — content_hash remains stale, will be retried
    # on next save
    if last_error is not None:
        raise EmbeddingError(
            f"Embedding failed after {max_retries} retries: {last_error}"
        ) from last_error
    return False  # unreachable, but satisfies type checker


# NOTE (ADR-080): the ``run_embed_source_inprocess`` wrapper below is the
# in-process execution seam. It accepts JSON-serialisable arguments (UUID as
# a string) so the dispatch site is a single, swappable seam — re-introducing
# a broker later means swapping ``asyncio.create_task(...)`` back to the
# broker enqueue call at the call site only. The wrapper builds its own DB
# session via ``get_session_factory()`` (never the request session) and
# commits on success / rolls back on failure.


async def run_embed_source_inprocess(
    source_type: str,
    source_id: str,
    content: str,
) -> None:
    """In-process entry point for embedding generation.

    Mirrors :func:`run_embed_source` but accepts JSON-serialisable arguments
    (``source_id`` as a string) so the dispatch seam is swappable. Builds its
    own database session and commits on success / rolls back on failure.

    Fire-and-forget: the dispatch site (``EmbeddingHookManager._dispatch_task``)
    schedules this via ``asyncio.create_task`` and does not await the result;
    the return is therefore ``None``.

    Args:
        source_type: Content type label (e.g. "kb_entry").
        source_id: UUID of the source entity, as a string.
        content: Text content to embed.
    """
    from uuid import UUID

    from narrare._app.database import get_session_factory
    from narrare.embeddings.repository import EmbeddingRepository

    session_factory = get_session_factory()
    async with session_factory() as session:
        repo = EmbeddingRepository(session)
        try:
            await run_embed_source(source_type, UUID(source_id), content, repo=repo)
            await session.commit()
        except Exception:
            await session.rollback()
            raise
