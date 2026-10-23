"""The worker: claims queued rows one at a time and runs them to an outcome.

A job row enqueued in a request's transaction is this class's business and no
one else's. Handlers receive their own session and own their transaction — what
a handler commits is durable whatever happens to the job row afterwards. A
handler that raises never propagates: the row pays for it, not the lane.
"""

from collections.abc import Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.kernel.jobs.models import DONE, FAILED, QUEUED, RUNNING, Job

# What a capability registers: its own session, the claimed row, a result dict.
type JobHandler = Callable[[AsyncSession, Job], Awaitable[dict[str, object]]]

MAX_ATTEMPTS = 2  # the first run and the one re-run a failure earns


class Worker:
    """The durable lane's engine: claim one row, run its handler, record the outcome.

    The session factory is a dependency, not an import: a fresh factory is a
    fresh "process" in the restart tests, and D10 can swap what loops behind
    the runtime without this class knowing.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        handlers: dict[str, JobHandler],
    ) -> None:
        self._session_factory = session_factory
        self._handlers = handlers

    async def run_once(self) -> bool:
        """Claim and run at most one queued job.

        True when a row was claimed and run (to done *or* failed — both count
        as work done); False when the queue was idle.
        """
        async with self._session_factory() as session:
            job = (
                await session.execute(
                    select(Job)
                    .where(Job.status == QUEUED)
                    # Oldest first: the lane is FIFO, and a requeued failure
                    # keeps its original created_at.
                    .order_by(Job.created_at)
                    .limit(1)
                    # The heart of the claim: two workers may run this SELECT
                    # at once, and FOR UPDATE SKIP LOCKED makes the row one has
                    # locked invisible to the other instead of a wait — so a
                    # queued row is claimed by exactly one worker, never two,
                    # never a queue of waiters idle-blocking on each other.
                    .with_for_update(skip_locked=True)
                )
            ).scalar_one_or_none()
            if job is None:
                return False
            job.status = RUNNING
            await session.commit()
            # The claim is durable now. The row lock died with the commit, but
            # it is no longer needed: no other worker's WHERE status = 'queued'
            # can ever see this row again until it is requeued — and it can
            # only be requeued through this same claimed state.
        await self._finish(job)
        return True

    async def _finish(self, job: Job) -> None:
        """Run the handler and record done, or the failure path with its retry."""
        handler = self._handlers.get(job.kind)
        if handler is None:
            # An assembly miss — a kind no capability registered a handler for —
            # is not a payload failure: retrying cannot make a handler appear.
            await self._write(job, status=FAILED, error=f"no handler for kind {job.kind!r}")
            return
        try:
            async with self._session_factory() as session:
                result = await handler(session, job)
        except Exception as failure:
            # The lane never dies with a job: the failure becomes the row's
            # state. Both attempts spent → failed; otherwise back in line for
            # the one re-run, with the error kept for the record.
            attempts = job.retry_count + 1
            await self._write(
                job,
                status=QUEUED if attempts < MAX_ATTEMPTS else FAILED,
                error=str(failure),
                retry_count=attempts,
            )
        else:
            # Success erases the earlier failure's error: the last word on a
            # done row is its result, not a mistake it survived.
            await self._write(job, status=DONE, error=None, result=result)

    async def _write(
        self,
        job: Job,
        *,
        status: str,
        error: str | None,
        result: dict[str, object] | None = None,
        retry_count: int | None = None,
    ) -> None:
        """Record the outcome on a fresh session — the claim's closed long ago.

        ``None`` retry_count means "leave the counter"; a stuck-running row
        that is requeued keeps its history, and only a real failure moves it.
        """
        async with self._session_factory() as session:
            row = await session.get(Job, job.id)
            if row is None:
                # A handler that deleted its own job made the outcome moot.
                return
            row.status = status
            row.error = error
            row.result = result
            if retry_count is not None:
                row.retry_count = retry_count
            await session.commit()
