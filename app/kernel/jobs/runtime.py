"""The lane's place in the process: one asyncio task, started by the API lifespan.

These two functions are the interface the spec keeps swappable (D10): the
lifespan calls them and does not care what loops behind them — this drain loop
today, something else later. Stopping is graceful by construction: no
cancellation, so a handler mid-flight always gets to record its outcome.
"""

import asyncio
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from logging import getLogger
from time import monotonic
from typing import TYPE_CHECKING

from sqlalchemy import update

from app.kernel.db.session import Session
from app.kernel.jobs.models import QUEUED, RUNNING, Job
from app.kernel.jobs.worker import JobHandler, Worker

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

IDLE_SLEEP = 0.5  # seconds between empty polls — off the database's back when idle
ERROR_BACKOFF = 1.0  # seconds before re-probing a failed database, not a tight loop
STALE_AFTER = 30.0  # seconds without a heartbeat before a running row reads as dead
SWEEP_EVERY = 10.0  # seconds between the lane's sweeps for stale running rows


def _stale_before() -> datetime:
    """The freshness deadline: a running row not written to since this
    instant is a dead process's leftover, not a live handler's claim."""
    return datetime.now(UTC) - timedelta(seconds=STALE_AFTER)


async def reset_stuck_running(session_factory: async_sessionmaker[AsyncSession]) -> int:
    """Requeue the rows a dead process left ``running``; returns how many.

    A process killed mid-handler leaves its row in running forever: the claim
    committed, so no other worker's queued-scan sees it, and the lock died with
    the connection. Stale rows — nothing written for STALE_AFTER, so the
    heartbeat a live claim keeps moving has gone silent — go back in line.
    The retry_count keeps its history — the reset itself increments nothing; a
    row that already failed once before the crash fails permanently on its next
    failure, because that failure is its second attempt.

    The stale bound is what lets a second process start safely beside a live
    one: a fresh running row (a handler mid-flight, its heartbeat moving) is
    not touched, so the reset cannot steal it. One lane per database remains
    the supported deployment, but the reset is no longer the thing that
    breaks first when it is violated.
    """
    async with session_factory() as session:
        requeued = (
            (
                await session.execute(
                    update(Job)
                    .where(Job.status == RUNNING, Job.updated_at < _stale_before())
                    .values(status=QUEUED)
                    .returning(Job.id)
                )
            )
            .scalars()
            .all()
        )
        await session.commit()
        return len(requeued)


async def start_worker(app: FastAPI, handlers: dict[str, JobHandler]) -> None:
    """Start the lane on the app: recover stale rows, then loop claim→execute."""
    await reset_stuck_running(Session)
    worker = Worker(Session, handlers)
    stopping = asyncio.Event()
    app.state.jobs_stopping = stopping
    app.state.jobs_task = asyncio.create_task(_lane(worker, Session, stopping))


async def stop_worker(app: FastAPI) -> None:
    """Stop the lane gracefully and wait for it: the current run_once finishes.

    Setting the event is the whole signal — the lane checks it between jobs,
    never mid-handler, so no outcome is left unrecorded and no row is abandoned
    in running by a polite shutdown (a killed process is what the stale sweep
    is for).
    """
    task: asyncio.Task[None] | None = getattr(app.state, "jobs_task", None)
    if task is None:
        return
    stopping: asyncio.Event | None = getattr(app.state, "jobs_stopping", None)
    if stopping is not None:
        stopping.set()
    await task


async def _lane(
    worker: Worker, session_factory: async_sessionmaker[AsyncSession], stopping: asyncio.Event
) -> None:
    """Drain the queue until told to stop, sleeping briefly when idle.

    A claimed row may not be the last one, so a busy lane never sleeps; an
    idle lane wakes on the stop signal immediately and re-polls at IDLE_SLEEP
    otherwise. Every SWEEP_EVERY the lane also sweeps for stale running rows —
    a process that died elsewhere leaves them behind, and with the lane
    already running, nothing else would ever bring them back.

    Handler errors are the row's problem — the Worker records them; what the
    Worker cannot survive is its own I/O dying (a database restart under a live
    lane, a dropped connection). Those the lane absorbs: it logs at failure
    time and backs off before the next claim, because a dead task would leave
    every queued job sitting forever with nothing anywhere saying why.
    CancelledError is not Exception and is not caught: shutdown is shutdown.
    """
    swept = monotonic()
    while not stopping.is_set():
        try:
            if monotonic() - swept >= SWEEP_EVERY:
                await reset_stuck_running(session_factory)
                swept = monotonic()
            claimed = await worker.run_once()
        except Exception:
            getLogger("narrare").exception("the jobs lane hit an infrastructure failure")
            with suppress(TimeoutError):
                await asyncio.wait_for(stopping.wait(), ERROR_BACKOFF)
            continue
        if claimed:
            continue  # a claimed row may not be the last queued one
        with suppress(TimeoutError):
            await asyncio.wait_for(stopping.wait(), IDLE_SLEEP)
