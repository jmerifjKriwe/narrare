"""The jobs table: durable work a request enqueues, the lane finishes.

Jobs are kernel-internal machinery, not shared domain vocabulary, so the table
lives here rather than in contracts. No capability touches it directly — a
request enqueues through :func:`enqueue`, a handler registered in the
capability's ``jobs.py`` does the work (spec §9 D10). The enqueue rides the
caller's own transaction, so a rolled-back request leaves no job behind (D14).
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002
from sqlalchemy.orm import Mapped, mapped_column

from app.kernel.db.base import UserOwned

# The lane's whole state machine, spelled once: a row moves queued → running at
# claim, then to done or failed; a failure may return it to queued once.
QUEUED = "queued"
RUNNING = "running"
DONE = "done"
FAILED = "failed"


class Job(UserOwned):
    """One unit of background work, owned by the user whose request enqueued it."""

    __tablename__ = "jobs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    # What a capability registered: "extract-entities" and friends.
    kind: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(16), default=QUEUED)
    # 0-100, the handler's to report as it goes; NULL until it first does.
    progress: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    payload: Mapped[dict[str, object]] = mapped_column(JSON)
    result: Mapped[dict[str, object] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


async def enqueue(
    session: AsyncSession, user_id: UUID, kind: str, payload: dict[str, object]
) -> Job:
    """Add a job on the caller's session; it becomes durable when the caller commits.

    No commit here, on purpose: the enqueue rides the request's own transaction,
    so a rollback takes the job with it — enqueueing is not a side effect that
    outlives the request that asked for it (D14).
    """
    job = Job(user_id=user_id, kind=kind, payload=payload)
    session.add(job)
    await session.flush()  # the id exists before the caller commits
    return job
