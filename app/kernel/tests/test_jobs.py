"""The jobs lane against the real database: enqueue, claim, retry, restart.

D10 (spec §9): a row enqueued in a request's own transaction is completed by
a worker that claims it with ``FOR UPDATE SKIP LOCKED``. These tests pin the
lane's three promises — exclusive claims, exactly one re-run after a failure,
restart recovery — plus the enqueue seam the first capability boards (Task 3).
"""

import asyncio
from typing import cast
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.kernel.db.session import Session
from app.kernel.db.testsupport import seed_user, url_for
from app.kernel.jobs import Job, enqueue
from app.kernel.jobs.models import DONE, FAILED, QUEUED, RUNNING
from app.kernel.jobs.runtime import (
    _lane,  # pyright: ignore[reportPrivateUsage]  the loop itself is the unit under test
    reset_stuck_running,
    start_worker,
    stop_worker,
)
from app.kernel.jobs.worker import Worker

pytestmark = pytest.mark.usefixtures("schema", "empty_tables")

OWNER = uuid4()


@pytest.fixture
async def a_user(empty_tables: None) -> None:
    """The users row a user-owned jobs row needs: the key reaches users."""
    await seed_user(OWNER)


async def _job(job_id: UUID) -> Job:
    """Fetch the row fresh: each look sees the database, not a cached session."""
    async with Session() as session:
        job = await session.get(Job, job_id)
    assert job is not None
    return job


async def _enqueue(kind: str, payload: dict[str, object] | None = None) -> Job:
    """Enqueue and commit, the way a request transaction would."""
    async with Session() as session:
        job = await enqueue(session, OWNER, kind, payload or {})
        await session.commit()
    return job


async def _count() -> int:
    async with Session() as session:
        return int(await session.scalar(text("SELECT count(*) FROM jobs")) or 0)


async def test_enqueue_persists_a_queued_job(a_user: None) -> None:
    job = await _enqueue("extract-entities", {"chapter_id": "c1"})

    row = await _job(job.id)
    assert row.status == QUEUED
    assert row.kind == "extract-entities"
    assert row.payload == {"chapter_id": "c1"}
    assert row.retry_count == 0
    assert row.result is None
    assert row.error is None
    assert row.user_id == OWNER


async def test_an_uncommitted_enqueue_leaves_nothing_behind(a_user: None) -> None:
    async with Session() as session:
        await enqueue(session, OWNER, "extract-entities", {})
        await session.rollback()

    assert await _count() == 0


async def test_two_concurrent_claims_exactly_one_wins(a_user: None) -> None:
    job = await _enqueue("kind")
    calls: list[UUID] = []

    async def handler(_: AsyncSession, claimed: Job) -> dict[str, object]:
        calls.append(claimed.id)
        return {"ran": True}

    first = Worker(Session, {"kind": handler})
    second = Worker(Session, {"kind": handler})
    results = await asyncio.gather(first.run_once(), second.run_once())

    assert sorted(results) == [False, True]  # one claim, the other saw idle
    assert calls == [job.id]  # the handler ran exactly once
    assert (await _job(job.id)).status == DONE


async def test_a_failing_handler_earns_one_rerun_then_fails(a_user: None) -> None:
    job = await _enqueue("kind")
    calls: list[str] = []

    async def exploding(_: AsyncSession, claimed: Job) -> dict[str, object]:
        calls.append("ran")
        raise ValueError("extraction exploded")

    worker = Worker(Session, {"kind": exploding})

    assert await worker.run_once() is True  # ran, and failed
    first = await _job(job.id)
    assert first.status == QUEUED  # back in line for its one re-run
    assert first.retry_count == 1
    assert first.error is not None
    assert "extraction exploded" in first.error

    assert await worker.run_once() is True  # the re-run
    second = await _job(job.id)
    assert second.status == FAILED  # terminal now
    assert second.retry_count == 2
    assert second.error is not None
    assert "extraction exploded" in second.error

    assert await worker.run_once() is False  # idle: there is no third run
    assert len(calls) == 2


async def test_a_retry_that_succeeds_clears_the_earlier_error(a_user: None) -> None:
    job = await _enqueue("kind")
    attempts: list[str] = []

    async def flaky(_: AsyncSession, claimed: Job) -> dict[str, object]:
        attempts.append("ran")
        if len(attempts) == 1:
            raise RuntimeError("first try fails")
        return {"entities": 3}

    worker = Worker(Session, {"kind": flaky})
    assert await worker.run_once() is True
    assert await worker.run_once() is True

    done = await _job(job.id)
    assert done.status == DONE
    assert done.result == {"entities": 3}
    assert done.error is None  # the success erases the earlier failure
    assert done.retry_count == 1


async def test_a_done_job_carries_its_result(a_user: None) -> None:
    job = await _enqueue("kind")

    async def handler(work: AsyncSession, claimed: Job) -> dict[str, object]:
        # The handler owns its session: what it commits here is durable.
        return {"answer": 42}

    assert await Worker(Session, {"kind": handler}).run_once() is True
    done = await _job(job.id)
    assert done.status == DONE
    assert done.result == {"answer": 42}


async def test_a_job_whose_kind_has_no_handler_fails_without_retry(a_user: None) -> None:
    job = await _enqueue("orphan")

    assert await Worker(Session, {}).run_once() is True

    row = await _job(job.id)
    assert row.status == FAILED
    assert row.error is not None
    assert "no handler" in row.error
    assert row.retry_count == 0  # an assembly miss is not a payload failure


async def test_a_restarted_process_completes_an_enqueued_job(a_user: None) -> None:
    job = await _enqueue("kind", {"text": "Kapitel eins"})

    async def handler(_: AsyncSession, claimed: Job) -> dict[str, object]:
        return {"saw": claimed.payload["text"]}

    # A fresh engine and factory stand in for a restarted process: no shared
    # memory with the enqueuing one, only the row in the database.
    engine = create_async_engine(url_for("narrare_v2_test"))
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        assert await Worker(factory, {"kind": handler}).run_once() is True
    finally:
        await engine.dispose()

    done = await _job(job.id)
    assert done.status == DONE
    assert done.result == {"saw": "Kapitel eins"}


async def test_rows_stuck_running_by_a_dead_process_are_requeued(a_user: None) -> None:
    async with Session() as session:
        job = await enqueue(session, OWNER, "kind", {})
        job.status = RUNNING  # what a killed process leaves behind
        await session.commit()

    assert await reset_stuck_running(Session) == 1

    row = await _job(job.id)
    assert row.status == QUEUED
    assert row.retry_count == 0  # the counter is untouched; a new failure retires it

    async def handler(_: AsyncSession, claimed: Job) -> dict[str, object]:
        return {"ran": True}

    assert await Worker(Session, {"kind": handler}).run_once() is True
    assert (await _job(job.id)).status == DONE  # the requeued row is claimable again


async def test_the_runtime_lane_drains_jobs_and_stops_cleanly(a_user: None) -> None:
    flaky = await _enqueue("flaky")  # oldest first: the lane is FIFO
    good = await _enqueue("good")
    attempts: list[str] = []

    async def flaky_handler(_: AsyncSession, claimed: Job) -> dict[str, object]:
        attempts.append(claimed.kind)
        raise RuntimeError("first try explodes")

    async def good_handler(_: AsyncSession, claimed: Job) -> dict[str, object]:
        attempts.append(claimed.kind)
        return {"ran": True}

    app = FastAPI()
    await start_worker(app, {"flaky": flaky_handler, "good": good_handler})
    task: asyncio.Task[None] | None = getattr(app.state, "jobs_task", None)
    assert task is not None
    try:
        for _ in range(200):  # 10 s ceiling on a lane that wakes twice a second
            if (await _job(flaky.id)).status == FAILED and (await _job(good.id)).status == DONE:
                break
            await asyncio.sleep(0.05)
        else:
            pytest.fail("the lane did not finish both jobs within 10 s")
    finally:
        await stop_worker(app)

    assert attempts == ["flaky", "flaky", "good"]  # FIFO, one re-run, then the next
    assert task.done()  # graceful: the lane finished and exited


async def test_the_lane_survives_a_transient_infrastructure_failure(a_user: None) -> None:
    job = await _enqueue("kind")

    async def handler(_: AsyncSession, claimed: Job) -> dict[str, object]:
        return {"ran": True}

    class FlakyFactory:
        """The first claim meets a dead database; the lane must outlive it.

        Not a handler failure — the connection I/O itself dies before any
        session exists, which is exactly the gap handler isolation leaves.
        """

        def __init__(self) -> None:
            self.blipped = False

        def __call__(self) -> AsyncSession:
            if not self.blipped:
                self.blipped = True
                raise ConnectionError("the database went away")
            return Session()

    # One deliberate type fib: the wrapper has to behave like the maker, not be it.
    flaky = cast("async_sessionmaker[AsyncSession]", FlakyFactory())
    stopping = asyncio.Event()
    task = asyncio.create_task(_lane(Worker(flaky, {"kind": handler}), stopping))
    try:
        for _ in range(200):  # 10 s ceiling on a lane that backs off a second
            if (await _job(job.id)).status == DONE:
                break
            await asyncio.sleep(0.05)
        else:
            pytest.fail("the lane never completed the job after the blip")
        assert not task.done()  # the failure did not end the task
    finally:
        stopping.set()
        await task  # and it still stops cleanly
