"""The worker: claims queued rows one at a time and runs them to an outcome.

A job row enqueued in a request's transaction is this class's business and no
one else's. Handlers receive their own session and own their transaction — what
a handler commits is durable whatever happens to the job row afterwards. A
handler that raises never propagates: the row pays for it, not the lane.
Progress is the lane's, not the handler's: a handler reports it through a
callback, and the lane persists each report on its own session — the handler's
terminal commit stays untouched, and reported progress survives a handler
that raises right after reporting it.
"""

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import suppress
from datetime import UTC, datetime
from logging import getLogger

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.kernel.jobs.models import DONE, FAILED, QUEUED, RUNNING, Job

# What a handler reports as it goes: 0-100 on the claimed row, persisted by
# the lane, never the handler.
type ProgressReport = Callable[[int], Awaitable[None]]

# What a capability registers: its own session, the claimed row, the progress
# reporter, a result dict.
#
# The lane is at-least-once, not exactly-once: a handler that fails after
# committing part of its work earns a re-run (MAX_ATTEMPTS), and a process
# dying between a handler's commit and its outcome write is requeued whole by
# the stale sweep — the same handler may run twice for one job. A handler
# must therefore be idempotent, or commit once at its end: extract_entities
# (knowledge) is the reference — provider call and rows ride one terminal
# commit, progress is reported through the lane's callback, so a raise or a
# re-run leaves nothing half-written.
type JobHandler = Callable[[AsyncSession, Job, ProgressReport], Awaitable[dict[str, object]]]

MAX_ATTEMPTS = 2  # the first run and the one re-run a failure earns

HEARTBEAT_EVERY = 2.0  # seconds between freshness writes on a live claim


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
        """Use the session factory for job I/O and map job kinds to their handlers."""
        self._session_factory = session_factory
        self._handlers = handlers
        # Claims whose outcome write died: the row is stranded in running,
        # invisible to every queued-scan, and only this worker knows it put
        # it there. Kept in memory so the next run can return it to the line
        # without waiting for a process restart — a dead process is what the
        # stale sweep is for, a dead write is what this list is for.
        self._stranded: list[Job] = []

    async def run_once(self) -> bool:
        """Claim and run at most one queued job — after returning any row a
        dead outcome write stranded, so the line it belongs in is whole
        again before a new claim is made.

        Return True when a row was claimed, including one requeued after a
        handler failure or failed for a missing handler; False when no unlocked
        queued row was available. Handler exceptions become job state; errors
        in recovery, claiming, or outcome writes propagate. An outcome write
        failure leaves the claim remembered for requeueing on the next call.
        Cancellation propagates.
        """
        await self._return_stranded()
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
        try:
            await self._finish(job)
        except Exception:
            # The handler's outcome could not be recorded — the write, not
            # the handler, is what died. The row is stranded in running;
            # remember it, and let the failure reach the lane's backoff. The
            # next run requeues the row and re-runs the handler: at-least-once.
            self._stranded.append(job)
            raise
        return True

    async def _return_stranded(self) -> None:
        """Requeue the rows this worker's outcome writes abandoned.

        Guarded on ``running``: a row that moved on without us (the stale
        sweep requeued it, a handler deleted it) is no longer ours to move.
        A failure here keeps the row listed — the next run retries it.
        """
        while self._stranded:
            job = self._stranded[0]
            async with self._session_factory() as session:
                await session.execute(
                    update(Job).where(Job.id == job.id, Job.status == RUNNING).values(status=QUEUED)
                )
                await session.commit()
            self._stranded.pop(0)

    async def _finish(self, job: Job) -> None:
        """Run the handler and record done, or the failure path with its retry."""
        handler = self._handlers.get(job.kind)
        if handler is None:
            # An assembly miss — a kind no capability registered a handler for —
            # is not a payload failure: retrying cannot make a handler appear.
            await self._write(job, status=FAILED, error=f"no handler for kind {job.kind!r}")
            return
        # The claim's freshness proof: while the handler runs, the row's
        # updated_at keeps moving, so the stale bound in reset_stuck_running
        # can never mistake a live claim for a dead process's leftover —
        # however long the handler takes.
        heartbeat = asyncio.create_task(self._heartbeat(job))

        # One report per run, bound to this claim: each call is the lane's own
        # short transaction on the claimed row, never the handler's session.
        async def report(value: int) -> None:
            await self._report_progress(job, value)

        try:
            try:
                async with self._session_factory() as session:
                    result = await handler(session, job, report)
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
        finally:
            heartbeat.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat

    async def _heartbeat(self, job: Job) -> None:
        """Keep a live claim's updated_at moving while its handler runs.

        A write that dies ends the heartbeat quietly: the claim can no
        longer prove its freshness, the row ages past the stale bound, and
        the sweep treats it as dead — which, with the database gone, is the
        honest verdict. The lane's own recovery paths take it from there.
        """
        while True:
            try:
                await asyncio.sleep(HEARTBEAT_EVERY)
                async with self._session_factory() as session:
                    await session.execute(
                        update(Job)
                        .where(Job.id == job.id, Job.status == RUNNING)
                        .values(updated_at=datetime.now(UTC))
                    )
                    await session.commit()
            except asyncio.CancelledError:
                raise
            except Exception:
                getLogger("narrare").warning(
                    "the claim heartbeat died; job %s will age past the stale bound", job.id
                )
                return

    async def _report_progress(self, job: Job, value: int) -> None:
        """Persist one progress report on the lane's own short transaction.

        The handler's session is never touched, so its terminal commit stays
        the only commit the work rides: a failed job still writes no audit
        row (D3), while the progress it reported before failing stays on the
        row — the lane's honesty about how far a run reached. A write that
        dies propagates into the handler's failure path, like any lane error.

        The write is gated on the claim still being the live one: a row the
        stale sweep returned to the queue keeps no percentage from a run
        nobody is running. A re-claimed row is beyond this guard — a dead
        run's callback may land one late advisory value on the new run's
        counter — and that residue is accepted: progress is advisory, and a
        claim token is more machinery than the column is worth.
        """
        async with self._session_factory() as session:
            await session.execute(
                update(Job).where(Job.id == job.id, Job.status == RUNNING).values(progress=value)
            )
            await session.commit()

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
