"""Unit tests for ``EmbeddingHookManager._dispatch_task`` (ADR-080).

``_dispatch_task`` schedules the in-process ``embed_source`` coroutine via
``asyncio.create_task`` (no broker, ADR-080) and holds a strong reference
in the module-level ``_INFLIGHT_TASKS`` GC-guard set so the in-flight
coroutine cannot be garbage-collected; the reference is discarded on
completion via the done-callback.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from structlog.testing import capture_logs

from narrare.kb.embedding_hooks import EmbeddingHookManager


class TestDispatchTask:
    """``_dispatch_task`` schedules the in-process embedding coroutine.

    ADR-080: embedding generation runs via ``asyncio.create_task`` (no broker).
    The dispatch site holds a strong reference in ``_INFLIGHT_TASKS`` to prevent
    GC of the in-flight coroutine, and discards it on completion.
    """

    @pytest.mark.asyncio
    async def test_dispatch_creates_inprocess_task(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """_dispatch_task schedules run_embed_source_inprocess with string args."""
        from narrare.kb import embedding_hooks

        captured: list[tuple[str, str, str]] = []

        async def fake_runner(source_type: str, source_id: str, content: str) -> None:
            captured.append((source_type, source_id, content))

        monkeypatch.setattr(embedding_hooks, "run_embed_source_inprocess", fake_runner)

        manager = EmbeddingHookManager()
        source_id = uuid4()
        await manager._dispatch_task(source_id, "content", trigger="create")

        # A task was scheduled and added to the GC-guard set.
        assert len(embedding_hooks._INFLIGHT_TASKS) == 1
        task = next(iter(embedding_hooks._INFLIGHT_TASKS))
        await task

        assert captured == [("kb_entry", str(source_id), "content")]

    @pytest.mark.asyncio
    async def test_dispatch_passes_trigger_update(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """_dispatch_task forwards the update trigger (no behavioural diff)."""
        from narrare.kb import embedding_hooks

        async def fake_runner(source_type: str, source_id: str, content: str) -> None:
            pass

        monkeypatch.setattr(embedding_hooks, "run_embed_source_inprocess", fake_runner)

        manager = EmbeddingHookManager()
        await manager._dispatch_task(uuid4(), "body", trigger="update")

        assert len(embedding_hooks._INFLIGHT_TASKS) == 1
        await next(iter(embedding_hooks._INFLIGHT_TASKS))

    @pytest.mark.asyncio
    async def test_gc_guard_removes_completed_task(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The GC guard discards the task once it completes (ADR-080)."""
        from narrare.kb import embedding_hooks

        async def fake_runner(source_type: str, source_id: str, content: str) -> None:
            pass

        monkeypatch.setattr(embedding_hooks, "run_embed_source_inprocess", fake_runner)

        manager = EmbeddingHookManager()
        await manager._dispatch_task(uuid4(), "content", trigger="create")

        assert len(embedding_hooks._INFLIGHT_TASKS) == 1
        task = next(iter(embedding_hooks._INFLIGHT_TASKS))
        await task
        # add_done_callback runs on the next loop tick — yield control.
        await asyncio.sleep(0)

        assert len(embedding_hooks._INFLIGHT_TASKS) == 0

    @pytest.mark.asyncio
    async def test_dispatch_does_not_await_runner(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """_dispatch_task is fire-and-forget — the runner has not run yet on return."""
        from narrare.kb import embedding_hooks

        started: list[bool] = []

        async def slow_runner(source_type: str, source_id: str, content: str) -> None:
            started.append(True)
            await asyncio.sleep(0.05)

        monkeypatch.setattr(embedding_hooks, "run_embed_source_inprocess", slow_runner)

        manager = EmbeddingHookManager()
        await manager._dispatch_task(uuid4(), "content", trigger="create")

        # The task is scheduled but we return immediately without awaiting it.
        assert len(embedding_hooks._INFLIGHT_TASKS) == 1
        task = next(iter(embedding_hooks._INFLIGHT_TASKS))
        # Allow it to finish so it does not leak into other tests.
        await task
        assert started == [True]

    @pytest.mark.asyncio
    async def test_failing_runner_logs_background_task_failed(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A failing background task logs via structlog and is retrieved.

        Regression for IMP-1: the done-callback must call ``task.exception()``
        so asyncio does not emit an un-retrieved-exception warning, and the
        failure is surfaced as a structured error event (RULE-11). The GC
        guard must still discard the task.
        """
        from narrare.kb import embedding_hooks

        async def boom_runner(source_type: str, source_id: str, content: str) -> None:
            raise RuntimeError("embed runner boom")

        monkeypatch.setattr(embedding_hooks, "run_embed_source_inprocess", boom_runner)

        with capture_logs() as logs:
            manager = EmbeddingHookManager()
            await manager._dispatch_task(uuid4(), "content", trigger="create")

            assert len(embedding_hooks._INFLIGHT_TASKS) == 1
            task = next(iter(embedding_hooks._INFLIGHT_TASKS))
            # Wait for completion without re-raising (asyncio.wait never raises
            # — it just returns the done set). Then yield once so the
            # add_done_callback fires.
            await asyncio.wait([task])
            await asyncio.sleep(0)

        failures = [r for r in logs if r.get("event") == "background_task_failed"]
        assert len(failures) == 1, f"expected one error log, got {logs}"
        assert failures[0]["log_level"] == "error"
        assert "embed runner boom" in failures[0]["error"]
        # The GC guard still discards the failed task.
        assert len(embedding_hooks._INFLIGHT_TASKS) == 0
