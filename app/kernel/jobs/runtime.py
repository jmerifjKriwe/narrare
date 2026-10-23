"""The lane's place in the process: one asyncio task, started by the API lifespan.

These two functions are the interface the spec keeps swappable (D10): the
lifespan calls them and does not care what loops behind them — this drain loop
today, something else later. Stopping is graceful by construction: no
cancellation, so a handler mid-flight always gets to record its outcome.
"""

import asyncio
from contextlib import suppress
from typing import TYPE_CHECKING

from sqlalchemy import update

from app.kernel.db.session import Session
from app.kernel.jobs.models import QUEUED, RUNNING, Job
from app.kernel.jobs.worker import JobHandler, Worker

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

IDLE_SLEEP = 0.5  # seconds between empty polls — off the database's back when idle


async def reset_stuck_running(session_factory: async_sessionmaker[AsyncSession]) -> int:
    """Requeue the rows a dead process left ``running``; returns how many.

    A process killed mid-handler leaves its row in running forever: the claim
    committed, so no other worker's queued-scan sees it, and the lock died with
    the connection. At worker start every such row goes back in line instead.
    The retry_count keeps its history — the reset itself increments nothing; a
    row that already failed once before the crash fails permanently on its next
    failure, because that failure is its second attempt.
    """
    async with session_factory() as session:
        requeued = (
            (
                await session.execute(
                    update(Job).where(Job.status == RUNNING).values(status=QUEUED).returning(Job.id)
                )
            )
            .scalars()
            .all()
        )
        await session.commit()
        return len(requeued)


async def start_worker(app: FastAPI, handlers: dict[str, JobHandler]) -> None:
    """Start the lane on the app: recover stuck rows, then loop claim→execute."""
    await reset_stuck_running(Session)
    worker = Worker(Session, handlers)
    stopping = asyncio.Event()
    app.state.jobs_stopping = stopping
    app.state.jobs_task = asyncio.create_task(_lane(worker, stopping))


async def stop_worker(app: FastAPI) -> None:
    """Stop the lane gracefully and wait for it: the current run_once finishes.

    Setting the event is the whole signal — the lane checks it between jobs,
    never mid-handler, so no outcome is left unrecorded and no row is abandoned
    in running by a polite shutdown (a killed process is what the startup reset
    is for).
    """
    task: asyncio.Task[None] | None = getattr(app.state, "jobs_task", None)
    if task is None:
        return
    stopping: asyncio.Event | None = getattr(app.state, "jobs_stopping", None)
    if stopping is not None:
        stopping.set()
    await task


async def _lane(worker: Worker, stopping: asyncio.Event) -> None:
    """Drain the queue until told to stop, sleeping briefly when idle.

    A claimed row may not be the last one, so a busy lane never sleeps; an
    idle lane wakes on the stop signal immediately and re-polls at IDLE_SLEEP
    otherwise.
    """
    while not stopping.is_set():
        if await worker.run_once():
            continue
        with suppress(TimeoutError):
            await asyncio.wait_for(stopping.wait(), IDLE_SLEEP)
