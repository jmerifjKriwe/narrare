"""Unit tests for the notes in-process embedding dispatch (ADR-080, NOTES-001 §6a)."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from uuid import uuid4

from narrare.notes import embedding_dispatch as dispatch_module
from narrare.notes.embedding_dispatch import InProcessNoteEmbeddingDispatch

if TYPE_CHECKING:
    import pytest


async def _drain() -> None:
    """Yield enough event-loop turns for created tasks to complete."""
    for _ in range(3):
        await asyncio.sleep(0)


class TestInProcessNoteEmbeddingDispatch:
    async def test_dispatches_run_embed_source_inprocess_with_note_source(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[tuple[str, str, str]] = []

        async def _fake_run(source_type: str, source_id: str, content: str) -> None:
            calls.append((source_type, source_id, content))

        monkeypatch.setattr(dispatch_module, "run_embed_source_inprocess", _fake_run)
        dispatch = InProcessNoteEmbeddingDispatch()

        note_id = uuid4()
        await dispatch.dispatch(note_id, "title\nbody")
        await _drain()

        assert calls == [("note", str(note_id), "title\nbody")]

    async def test_completes_without_leaking_inflight_references(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def _fake_run(source_type: str, source_id: str, content: str) -> None:
            return None

        monkeypatch.setattr(dispatch_module, "run_embed_source_inprocess", _fake_run)
        dispatch = InProcessNoteEmbeddingDispatch()
        await dispatch.dispatch(uuid4(), "text")
        await _drain()

        # The GC-guard set is part of the unit under test (ADR-080): the
        # done-callback must discard completed tasks so the set never grows.
        assert not dispatch_module._INFLIGHT_TASKS  # pyright: ignore[reportPrivateUsage]

    async def test_task_failure_is_contained_never_raises_into_save_path(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """RULE-11: a failing background task must not raise into the save path.

        ``dispatch()`` returns before the task runs; the done-callback
        retrieves the exception (``filterwarnings = ["error", ...]`` turns an
        un-retrieved task exception into a test error), so reaching the final
        assertion with an empty GC-guard set proves containment + logging.
        """

        async def _failing_run(source_type: str, source_id: str, content: str) -> None:
            msg = "embedding boom"
            raise RuntimeError(msg)

        monkeypatch.setattr(dispatch_module, "run_embed_source_inprocess", _failing_run)
        dispatch = InProcessNoteEmbeddingDispatch()

        await dispatch.dispatch(uuid4(), "text")  # must not raise, now or later
        await _drain()

        assert not dispatch_module._INFLIGHT_TASKS  # pyright: ignore[reportPrivateUsage]
