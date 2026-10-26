"""The jobs lane against the real database: enqueue, claim, retry, restart.

D10 (spec §9): a row enqueued in a request's own transaction is completed by
a worker that claims it with ``FOR UPDATE SKIP LOCKED``. These tests pin the
lane's three promises — exclusive claims, exactly one re-run after a failure,
restart recovery — plus the enqueue seam the first capability boards (Task 3).
"""

import asyncio
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.kernel.db.session import Session
from app.kernel.db.testsupport import seed_user, url_for
from app.kernel.jobs import Job, enqueue
from app.kernel.jobs import runtime as jobs_runtime
from app.kernel.jobs import worker as jobs_worker
from app.kernel.jobs.models import DONE, FAILED, QUEUED, RUNNING
from app.kernel.jobs.runtime import (
    _lane,  # pyright: ignore[reportPrivateUsage]  the loop itself is the unit under test
    reset_stuck_running,
    start_worker,
    stop_worker,
)
from app.kernel.jobs.worker import ProgressReport, Worker

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


async def _age_past_stale(job_id: UUID) -> None:
    """Push a row's updated_at beyond STALE_AFTER, the state of a claim a
    dead process left behind long enough for the stale bound to see it."""
    stale = datetime.now(UTC) - timedelta(seconds=jobs_runtime.STALE_AFTER + 30)
    async with Session() as session:
        await session.execute(update(Job).where(Job.id == job_id).values(updated_at=stale))
        await session.commit()


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
    # What this pins is claim exclusivity — one claimant per job, the other
    # sees an idle lane — not skip-vs-wait semantics: a worker that waited on
    # the row lock instead of skipping it would lose the same race and also
    # return False, so which FOR UPDATE mode earned this outcome is not what
    # these asserts decide.
    job = await _enqueue("kind")
    calls: list[UUID] = []

    async def handler(_: AsyncSession, claimed: Job, report: ProgressReport) -> dict[str, object]:
        calls.append(claimed.id)
        return {"ran": True}

    first = Worker(Session, {"kind": handler})
    second = Worker(Session, {"kind": handler})
    results = await asyncio.gather(first.run_once(), second.run_once())

    assert sorted(results) == [False, True]  # one claim, the other saw idle
    assert calls == [job.id]  # the handler ran exactly once
    assert (await _job(job.id)).status == DONE


async def test_a_claim_skips_a_row_another_transaction_locks(a_user: None) -> None:
    # The other half of the claim, the one the race above cannot decide: a
    # row locked by a live transaction must be SKIPPED, not waited on. The
    # holder below owns the row lock without committing; a claim that waited
    # for it (plain FOR UPDATE) would block, and the wait_for would time out
    # — only skip_locked=True returns idle, promptly. That is the mode spec
    # §9 D10 names, pinned here against a silent regression to waiting.
    job = await _enqueue("kind")

    async def handler(_: AsyncSession, claimed: Job, report: ProgressReport) -> dict[str, object]:
        return {"ran": True}

    worker = Worker(Session, {"kind": handler})
    async with Session() as holder:
        await holder.execute(select(Job).where(Job.id == job.id).with_for_update())
        claimed = await asyncio.wait_for(worker.run_once(), timeout=2.0)
        assert claimed is False  # skipped the locked row: an idle lane, now
        await holder.rollback()

    # The lock released, the same row is claimable again.
    assert await worker.run_once() is True
    assert (await _job(job.id)).status == DONE


async def test_a_failing_handler_earns_one_rerun_then_fails(a_user: None) -> None:
    job = await _enqueue("kind")
    calls: list[str] = []

    async def exploding(_: AsyncSession, claimed: Job, report: ProgressReport) -> dict[str, object]:
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


async def test_report_persists_progress_and_survives_a_later_raise(a_user: None) -> None:
    # A handler that reports twice, then raises: the row keeps the last
    # reported progress and gains the error — the lane's honesty about
    # failure, not the handler's.
    async def handler(_: AsyncSession, claimed: Job, report: ProgressReport) -> dict[str, object]:
        await report(25)
        await report(50)
        raise RuntimeError("boom")

    job = await _enqueue("kind")
    worker = Worker(Session, {"kind": handler})
    assert await worker.run_once() is True  # ran, failed, back in line

    # The requeue's own outcome write must not take the progress with it:
    # the number is the lane's honest record of how far the run reached,
    # and the re-run below reports it all over again.
    requeued = await _job(job.id)
    assert requeued.status == QUEUED
    assert requeued.progress == 50

    assert await worker.run_once() is True  # the re-run's failure is terminal

    job_row = await _job(job.id)
    assert job_row.progress == 50
    assert job_row.status == FAILED
    assert job_row.error is not None
    assert "boom" in job_row.error


async def test_a_retry_that_succeeds_clears_the_earlier_error(a_user: None) -> None:
    job = await _enqueue("kind")
    attempts: list[str] = []

    async def flaky(_: AsyncSession, claimed: Job, report: ProgressReport) -> dict[str, object]:
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

    async def handler(
        work: AsyncSession, claimed: Job, report: ProgressReport
    ) -> dict[str, object]:
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

    async def handler(_: AsyncSession, claimed: Job, report: ProgressReport) -> dict[str, object]:
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


async def test_a_row_stranded_by_a_dead_outcome_write_recovers_without_a_restart(
    a_user: None,
) -> None:
    # I4: the claim committed, the handler ran, and then the outcome write
    # died with the database — the row is stranded in running, invisible to
    # every queued-scan. The worker that stranded it must return it to the
    # line itself; a process restart must not be the only way back.
    job = await _enqueue("kind")
    ran: list[str] = []

    async def handler(_: AsyncSession, claimed: Job, report: ProgressReport) -> dict[str, object]:
        ran.append("ran")
        return {"ran": True}

    class ThirdOpenDies:
        """Claim (1st open) and handler (2nd) succeed; the outcome write
        (3rd) meets a dead database — the exact seam the finding names."""

        def __init__(self) -> None:
            self.opens = 0

        def __call__(self) -> AsyncSession:
            self.opens += 1
            if self.opens == 3:
                raise ConnectionError("the database went away mid-write")
            return Session()

    factory = cast("async_sessionmaker[AsyncSession]", ThirdOpenDies())
    worker = Worker(factory, {"kind": handler})

    with pytest.raises(ConnectionError):
        await worker.run_once()  # claimed, ran, the outcome write died
    assert (await _job(job.id)).status == RUNNING  # the strand, on the record

    # The next run returns the stranded row to the line and completes it.
    assert await worker.run_once() is True
    row = await _job(job.id)
    assert row.status == DONE
    assert row.retry_count == 0  # an infrastructure casualty is not an attempt
    assert len(ran) == 2  # at-least-once: the handler ran again


async def test_a_stranded_row_still_recovers_when_the_first_retry_dies_too(a_user: None) -> None:
    # The database can stay dead past the first recovery attempt: the row
    # stays remembered, and the recovery is retried until it lands.
    job = await _enqueue("kind")

    async def handler(_: AsyncSession, claimed: Job, report: ProgressReport) -> dict[str, object]:
        return {"ran": True}

    class ThirdAndFourthOpenDie:
        """The outcome write (3rd open) and the first recovery attempt
        (4th) both meet a dead database; the 5th open is alive again."""

        def __init__(self) -> None:
            self.opens = 0

        def __call__(self) -> AsyncSession:
            self.opens += 1
            if self.opens in (3, 4):
                raise ConnectionError("the database is still gone")
            return Session()

    factory = cast("async_sessionmaker[AsyncSession]", ThirdAndFourthOpenDie())
    worker = Worker(factory, {"kind": handler})

    with pytest.raises(ConnectionError):
        await worker.run_once()
    assert (await _job(job.id)).status == RUNNING

    with pytest.raises(ConnectionError):  # the recovery attempt dies too
        await worker.run_once()
    assert (await _job(job.id)).status == RUNNING  # still stranded, still remembered

    assert await worker.run_once() is True  # the retry lands
    assert (await _job(job.id)).status == DONE


async def test_a_live_claims_row_stays_fresh_while_its_handler_runs(
    a_user: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The freshness proof behind the stale bound: a handler that runs long
    # keeps its claim's updated_at moving, so no reset can mistake the row
    # for a dead process's leftover and steal it mid-flight.
    monkeypatch.setattr(jobs_worker, "HEARTBEAT_EVERY", 0.1)

    job = await _enqueue("kind")
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow_handler(
        _: AsyncSession, claimed: Job, report: ProgressReport
    ) -> dict[str, object]:
        started.set()
        await release.wait()
        return {"ran": True}

    task = asyncio.create_task(Worker(Session, {"kind": slow_handler}).run_once())
    try:
        await asyncio.wait_for(started.wait(), timeout=5)
        await asyncio.sleep(0.05)  # let the claim's own write settle
        before = (await _job(job.id)).updated_at
        await asyncio.sleep(0.4)  # a few heartbeat ticks while the handler waits
        after = (await _job(job.id)).updated_at
        assert after is not None and before is not None
        assert after > before  # the heartbeat moved the claim's freshness
    finally:
        release.set()
        assert await task  # the handler finished, the outcome was written
    assert (await _job(job.id)).status == DONE


async def test_rows_stuck_running_by_a_dead_process_are_requeued(a_user: None) -> None:
    async with Session() as session:
        job = await enqueue(session, OWNER, "kind", {})
        job.status = RUNNING  # what a killed process leaves behind
        await session.commit()
    await _age_past_stale(job.id)

    assert await reset_stuck_running(Session) == 1

    row = await _job(job.id)
    assert row.status == QUEUED
    assert row.retry_count == 0  # the counter is untouched; a new failure retires it

    async def handler(_: AsyncSession, claimed: Job, report: ProgressReport) -> dict[str, object]:
        return {"ran": True}

    assert await Worker(Session, {"kind": handler}).run_once() is True
    assert (await _job(job.id)).status == DONE  # the requeued row is claimable again


async def test_a_fresh_running_row_is_not_stolen_by_a_reset(a_user: None) -> None:
    # A row claimed moments ago may well have a live handler behind it: the
    # reset must leave fresh running rows alone — only stale ones are dead
    # processes' leftovers. This is the theft the stale bound exists to stop;
    # the heartbeat test above is what keeps a long handler on the fresh
    # side of it.
    async with Session() as session:
        job = await enqueue(session, OWNER, "kind", {})
        job.status = RUNNING  # a live claim, written this instant
        await session.commit()

    assert await reset_stuck_running(Session) == 0

    assert (await _job(job.id)).status == RUNNING  # untouched, not requeued


async def test_start_worker_recovers_stale_rows_at_startup(
    a_user: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The wiring pin: start_worker resets stale rows before the loop begins.
    # The sweep is muzzled here (SWEEP_EVERY pushed past every deadline), so
    # only the eager startup reset can bring this row back — deleting the
    # call in start_worker leaves it stuck running until the test's ceiling
    # runs out.
    async with Session() as session:
        job = await enqueue(session, OWNER, "kind", {})
        job.status = RUNNING  # a dead process's leftover
        await session.commit()
    await _age_past_stale(job.id)

    async def handler(_: AsyncSession, claimed: Job, report: ProgressReport) -> dict[str, object]:
        return {"ran": True}

    monkeypatch.setattr(jobs_runtime, "SWEEP_EVERY", 3600.0)
    app = FastAPI()
    await start_worker(app, {"kind": handler})
    try:
        for _ in range(200):  # 10 s ceiling on a lane that wakes twice a second
            if (await _job(job.id)).status == DONE:
                break
            await asyncio.sleep(0.05)
        else:
            pytest.fail("the startup reset never brought the stale row back")
    finally:
        await stop_worker(app)


async def test_the_lane_sweeps_stale_running_rows_while_it_runs(
    a_user: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A row can go stale while a lane is already running — a process that
    # died elsewhere, or a claim that aged out during an outage. The lane's
    # own periodic sweep returns it to the line; nothing else will.
    monkeypatch.setattr(jobs_runtime, "SWEEP_EVERY", 0.2)

    async def handler(_: AsyncSession, claimed: Job, report: ProgressReport) -> dict[str, object]:
        return {"ran": True}

    app = FastAPI()
    await start_worker(app, {"kind": handler})
    try:
        # The row goes stale AFTER the lane started, so the startup reset
        # cannot be what recovers it.
        async with Session() as session:
            job = await enqueue(session, OWNER, "kind", {})
            job.status = RUNNING
            await session.commit()
        await _age_past_stale(job.id)

        for _ in range(200):  # 10 s ceiling
            if (await _job(job.id)).status == DONE:
                break
            await asyncio.sleep(0.05)
        else:
            pytest.fail("the lane never swept the stale row back into the line")
    finally:
        await stop_worker(app)


async def test_the_runtime_lane_drains_jobs_and_stops_cleanly(a_user: None) -> None:
    flaky = await _enqueue("flaky")  # oldest first: the lane is FIFO
    good = await _enqueue("good")
    attempts: list[str] = []

    async def flaky_handler(
        _: AsyncSession, claimed: Job, report: ProgressReport
    ) -> dict[str, object]:
        attempts.append(claimed.kind)
        raise RuntimeError("first try explodes")

    async def good_handler(
        _: AsyncSession, claimed: Job, report: ProgressReport
    ) -> dict[str, object]:
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


async def test_stop_worker_bounds_a_handler_that_outlives_the_grace(
    a_user: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A provider stream that never answers must not hang shutdown: the lane
    # gets a bounded grace to record an outcome, then the handler is
    # abandoned in running — the stale sweep, pinned above, is its recovery.
    monkeypatch.setattr(jobs_runtime, "SHUTDOWN_GRACE", 0.1)

    job = await _enqueue("kind")
    stuck = asyncio.Event()

    async def stuck_handler(
        _: AsyncSession, claimed: Job, report: ProgressReport
    ) -> dict[str, object]:
        await stuck.wait()  # a provider that never returns
        return {"ran": True}

    app = FastAPI()
    await start_worker(app, {"kind": stuck_handler})
    try:
        # Let the lane claim the row and enter the handler.
        for _ in range(100):
            if (await _job(job.id)).status == RUNNING:
                break
            await asyncio.sleep(0.02)
        else:
            pytest.fail("the lane never claimed the job")

        # stop_worker must return despite the stuck handler.
        await asyncio.wait_for(stop_worker(app), timeout=5)
    finally:
        stuck.set()  # release the handler so nothing outlives the test

    # The abandoned claim stays running until the stale sweep recovers it.
    assert (await _job(job.id)).status == RUNNING
    await _age_past_stale(job.id)
    assert await reset_stuck_running(Session) == 1
    assert (await _job(job.id)).status == QUEUED


async def test_stop_worker_bounds_its_cancel_wait_when_a_handler_defies_it(
    a_user: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A handler can swallow or delay the CancelledError — a finally that
    # awaits, a provider wrapper that catches BaseException. The cancel wait
    # itself must be bounded too, or the shutdown hangs through the back
    # door. The abandoned row is the stale sweep's, as always.
    monkeypatch.setattr(jobs_runtime, "SHUTDOWN_GRACE", 0.1)
    monkeypatch.setattr(jobs_runtime, "CANCEL_GRACE", 0.1)

    job = await _enqueue("kind")
    stuck = asyncio.Event()

    async def stubborn_handler(
        _: AsyncSession, claimed: Job, report: ProgressReport
    ) -> dict[str, object]:
        try:
            await stuck.wait()
        except asyncio.CancelledError:
            # Outlive the cancel grace on purpose: without a bound on the
            # post-cancel wait, this sleep is the shutdown hang.
            await asyncio.sleep(3600)
            raise
        return {"ran": True}

    app = FastAPI()
    await start_worker(app, {"kind": stubborn_handler})
    task: asyncio.Task[None] | None = getattr(app.state, "jobs_task", None)
    assert task is not None
    try:
        for _ in range(100):
            if (await _job(job.id)).status == RUNNING:
                break
            await asyncio.sleep(0.02)
        else:
            pytest.fail("the lane never claimed the job")

        # The handler defies cancellation; the stop must still return. The
        # awaited stop is bounded by the harness so a regression fails the
        # case instead of hanging it, but the real assertion is the clock:
        # with both graces at 0.1 s, anything near the harness bound means
        # the post-cancel wait was unbounded again.
        started = asyncio.get_running_loop().time()
        await asyncio.wait_for(stop_worker(app), timeout=5)
        assert asyncio.get_running_loop().time() - started < 2.0
    finally:
        # The abandoned task is still sleeping; end it for the test teardown.
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    # The claim was abandoned in running; the stale sweep recovers it.
    assert (await _job(job.id)).status == RUNNING
    await _age_past_stale(job.id)
    assert await reset_stuck_running(Session) == 1
    assert (await _job(job.id)).status == QUEUED


async def test_the_lane_survives_a_transient_infrastructure_failure(a_user: None) -> None:
    job = await _enqueue("kind")

    async def handler(_: AsyncSession, claimed: Job, report: ProgressReport) -> dict[str, object]:
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
    task = asyncio.create_task(_lane(Worker(flaky, {"kind": handler}), flaky, stopping))
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
