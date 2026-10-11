"""Generation request repository — DB queries only."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import case, func, or_, select, update

from narrare._app.base_repository import BaseRepository
from narrare.writing.models import GenerationRequest

if TYPE_CHECKING:
    import uuid

_ACTIVE_STATUSES = ("pending", "streaming")


class GenerationRepository(BaseRepository):
    """DB queries for generation request tracking."""

    async def create(
        self,
        chapter_id: uuid.UUID,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        mode: str,
        tone: str = "balanced",
    ) -> uuid.UUID:
        """Insert a new generation request with status 'pending'.

        Returns:
            The UUID of the newly created request.
        """
        request = GenerationRequest(
            chapter_id=chapter_id,
            novel_id=novel_id,
            user_id=user_id,
            mode=mode,
            tone=tone,
            status="pending",
        )
        self._session.add(request)
        await self._flush_and_refresh(request)
        return request.id

    async def create_if_no_active(
        self,
        chapter_id: uuid.UUID,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        mode: str,
        tone: str = "balanced",
        scenes: list[dict[str, object]] | None = None,
    ) -> uuid.UUID:
        """Atomically check for active requests and insert a new one.

        Uses ``SELECT ... FOR UPDATE`` to lock any active row, preventing
        the TOCTOU race where two concurrent requests both read no active
        row and both INSERT.  Also protected by the partial unique index
        ``uq_generation_requests_active_chapter`` as a database-level guard.

        Args:
            chapter_id: The chapter the generation is scoped to.
            novel_id: The novel the generation is scoped to.
            user_id: The requesting user.
            mode: Generation mode string.
            tone: Tone string (default ``"balanced"``).
            scenes: Optional structured scene snapshot (PLAN-001 spec
                §8.2) persisted verbatim — the row is the single state
                carrier between POST and stream. ``None`` = legacy
                scene-less request.

        Returns:
            The UUID of the newly created request.

        Raises:
            ConflictError: If an active generation already exists for the chapter.
            IntegrityError: Propagated if the partial unique index is violated
                (secondary defense against races).
        """
        result = await self._session.execute(
            select(GenerationRequest)
            .where(
                GenerationRequest.chapter_id == chapter_id,
                GenerationRequest.status.in_(_ACTIVE_STATUSES),
            )
            .with_for_update()
        )
        active = result.scalar_one_or_none()

        if active is not None:
            from narrare_core.shared.errors import ConflictError

            raise ConflictError(f"Generation already active for chapter {chapter_id}")

        request = GenerationRequest(
            chapter_id=chapter_id,
            novel_id=novel_id,
            user_id=user_id,
            mode=mode,
            tone=tone,
            status="pending",
            scenes=scenes,
        )
        self._session.add(request)
        await self._flush_and_refresh(request)
        return request.id

    async def get_by_id(self, request_id: uuid.UUID) -> GenerationRequest | None:
        """Fetch a generation request by its primary key."""
        result = await self._session.execute(
            select(GenerationRequest).where(GenerationRequest.id == request_id)
        )
        return result.scalar_one_or_none()

    async def update_status(
        self,
        request_id: uuid.UUID,
        status: str,
        **kwargs: Any,
    ) -> None:
        """Update status and optional fields on a generation request.

        Accepted kwargs: tokens_used, word_count, error_message,
        completed_at, started_at, model_id, provider_name.
        """
        values: dict[str, Any] = {"status": status}
        allowed = {
            "tokens_used",
            "word_count",
            "error_message",
            "completed_at",
            "started_at",
            "model_id",
            "provider_name",
        }
        for key, value in kwargs.items():
            if key in allowed:
                values[key] = value
        await self._session.execute(
            update(GenerationRequest).where(GenerationRequest.id == request_id).values(**values)
        )
        await self._flush()

    async def get_active_for_chapter(self, chapter_id: uuid.UUID) -> GenerationRequest | None:
        """Check for pending/streaming requests (concurrent prevention)."""
        result = await self._session.execute(
            select(GenerationRequest).where(
                GenerationRequest.chapter_id == chapter_id,
                GenerationRequest.status.in_(["pending", "streaming"]),
            )
        )
        return result.scalar_one_or_none()

    async def cleanup_stale(
        self,
        max_age_minutes: int = 30,
        pending_age_minutes: int = 5,
    ) -> int:
        """Mark stale streaming and pending requests as failed.

        Streaming requests older than *max_age_minutes* and pending
        requests older than *pending_age_minutes* are marked as failed.
        Pending requests that never started streaming are cleaned up
        with a shorter window since they indicate a pre-stream failure
        (e.g. validation error).

        Args:
            max_age_minutes: Cutoff in minutes for ``streaming`` status.
            pending_age_minutes: Cutoff in minutes for ``pending`` status.

        Returns:
            Number of requests marked as failed.
        """
        now = datetime.now(UTC)
        streaming_cutoff = now - timedelta(minutes=max_age_minutes)
        pending_cutoff = now - timedelta(minutes=pending_age_minutes)

        stale_filter = or_(
            (GenerationRequest.status == "streaming")
            & (GenerationRequest.updated_at < streaming_cutoff),
            (GenerationRequest.status == "pending")
            & (GenerationRequest.updated_at < pending_cutoff),
        )

        # Count first
        count_result = await self._session.execute(
            select(func.count()).select_from(GenerationRequest).where(stale_filter)
        )
        count = count_result.scalar() or 0

        if count > 0:
            await self._session.execute(
                update(GenerationRequest)
                .where(stale_filter)
                .values(
                    status="failed",
                    error_message="Stale request — cleaned up by system",
                    completed_at=datetime.now(UTC),
                )
            )
            await self._flush()

        return count

    async def get_stats_for_novel(self, novel_id: uuid.UUID) -> dict[str, Any]:
        """Aggregate generation statistics for a novel.

        Returns dict with: total_generations, success_rate, avg_tokens,
        avg_word_count, most_used_model.
        """
        result = await self._session.execute(
            select(
                func.count().label("total"),
                func.avg(
                    case(
                        (
                            GenerationRequest.status == "completed",
                            1,
                        ),
                        else_=0,
                    )
                ).label("success_rate"),
                func.avg(GenerationRequest.tokens_used).label("avg_tokens"),
                func.avg(GenerationRequest.word_count).label("avg_word_count"),
            ).where(GenerationRequest.novel_id == novel_id)
        )
        row = result.one()

        # Most used model
        model_result = await self._session.execute(
            select(GenerationRequest.model_id, func.count().label("cnt"))
            .where(
                GenerationRequest.novel_id == novel_id,
                GenerationRequest.model_id.isnot(None),
            )
            .group_by(GenerationRequest.model_id)
            .order_by(func.count().desc())
            .limit(1)
        )
        model_row = model_result.first()

        return {
            "total_generations": int(row.total),
            "success_rate": float(row.success_rate or 0),
            "avg_tokens": float(row.avg_tokens or 0),
            "avg_word_count": float(row.avg_word_count or 0),
            "most_used_model": model_row[0] if model_row else None,
        }
