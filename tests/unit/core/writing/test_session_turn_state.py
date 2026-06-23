"""Tests for SessionTurnStateStore — in-process active-turn partial-prose registry.

Covers (ADR-052, Phase 1 Core):
1. ``register_active_turn`` initializes a fresh turn (sequence=0, empty prose).
2. ``record_chunk`` appends text and increments the sequence; returns the new
   sequence number; is a no-op (returns 0) when no active turn exists.
3. ``finalize_turn`` clears the active turn and returns the preserved prose;
   prefers the supplied ``final_text`` over the accumulated partial.
4. ``cancel_active_turn`` clears the active turn and returns the partial prose.
5. ``get_active_snapshot`` / ``get_active_partial`` read the live state.
"""

from __future__ import annotations

import pytest

from narrare_core.writing._enums import StreamStatus
from narrare_core.writing.session_turn_state import (
    ActiveTurnSnapshot,
    SessionTurnStateStore,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def store() -> SessionTurnStateStore:
    return SessionTurnStateStore()


# ---------------------------------------------------------------------------
# register_active_turn + record_chunk
# ---------------------------------------------------------------------------


class TestRegisterAndRecord:
    """register_active_turn + record_chunk happy-path behaviour."""

    async def test_register_returns_fresh_snapshot(self, store: SessionTurnStateStore) -> None:
        snapshot = await store.register_active_turn("s-1", "inv-1")

        assert isinstance(snapshot, ActiveTurnSnapshot)
        assert snapshot.invocation_id == "inv-1"
        assert snapshot.sequence == 0
        assert snapshot.partial_prose == ""

    async def test_register_overwrites_previous_turn(self, store: SessionTurnStateStore) -> None:
        """Re-registering a session resets sequence and partial prose."""
        await store.register_active_turn("s-1", "inv-1")
        await store.record_chunk("s-1", "stale partial")

        snapshot = await store.register_active_turn("s-1", "inv-2")

        assert snapshot.invocation_id == "inv-2"
        assert snapshot.sequence == 0
        assert snapshot.partial_prose == ""

    async def test_record_chunk_appends_and_increments(self, store: SessionTurnStateStore) -> None:
        await store.register_active_turn("s-1", "inv-1")

        seq1 = await store.record_chunk("s-1", "Hello")
        seq2 = await store.record_chunk("s-1", " world")

        assert seq1 == 1
        assert seq2 == 2

        snapshot = await store.get_active_snapshot("s-1")
        assert snapshot is not None
        assert snapshot.sequence == 2
        assert snapshot.partial_prose == "Hello world"

    async def test_record_chunk_with_no_active_turn_is_noop(
        self, store: SessionTurnStateStore
    ) -> None:
        """Recording a chunk for a session with no active turn returns 0 and stores nothing."""
        seq = await store.record_chunk("ghost", "text")

        assert seq == 0
        assert await store.get_active_snapshot("ghost") is None


# ---------------------------------------------------------------------------
# finalize_turn + cancel_active_turn
# ---------------------------------------------------------------------------


class TestFinalizeAndCancel:
    """finalize_turn and cancel_active_turn clear the turn and return prose."""

    async def test_finalize_returns_preserved_prose_and_clears(
        self, store: SessionTurnStateStore
    ) -> None:
        await store.register_active_turn("s-1", "inv-1")
        await store.record_chunk("s-1", "partial")

        preserved = await store.finalize_turn("s-1", final_text="final prose")

        assert preserved == "final prose"
        # The active turn is cleared
        assert await store.get_active_snapshot("s-1") is None

    async def test_finalize_without_final_text_returns_accumulated_partial(
        self, store: SessionTurnStateStore
    ) -> None:
        await store.register_active_turn("s-1", "inv-1")
        await store.record_chunk("s-1", "accu")
        await store.record_chunk("s-1", "mulated")

        preserved = await store.finalize_turn("s-1")

        assert preserved == "accumulated"

    async def test_finalize_with_no_active_turn_returns_empty(
        self, store: SessionTurnStateStore
    ) -> None:
        preserved = await store.finalize_turn("ghost")
        assert preserved == ""

    async def test_finalize_accepts_status(self, store: SessionTurnStateStore) -> None:
        """finalize_turn accepts a StreamStatus (observability hook); does not raise."""
        await store.register_active_turn("s-1", "inv-1")
        await store.record_chunk("s-1", "x")

        preserved = await store.finalize_turn("s-1", final_text="x", status=StreamStatus.FAILED)

        assert preserved == "x"

    async def test_cancel_returns_partial_prose_and_clears(
        self, store: SessionTurnStateStore
    ) -> None:
        await store.register_active_turn("s-1", "inv-1")
        await store.record_chunk("s-1", "partial")

        preserved = await store.cancel_active_turn("s-1")

        assert preserved == "partial"
        assert await store.get_active_snapshot("s-1") is None

    async def test_cancel_with_no_active_turn_returns_empty(
        self, store: SessionTurnStateStore
    ) -> None:
        preserved = await store.cancel_active_turn("ghost")
        assert preserved == ""


# ---------------------------------------------------------------------------
# get_active_snapshot / get_active_partial
# ---------------------------------------------------------------------------


class TestGetActivePartial:
    """Read-only accessors for the live turn state."""

    async def test_get_active_snapshot_returns_current_state(
        self, store: SessionTurnStateStore
    ) -> None:
        await store.register_active_turn("s-1", "inv-1")
        await store.record_chunk("s-1", "abc")

        snapshot = await store.get_active_snapshot("s-1")

        assert snapshot is not None
        assert snapshot.invocation_id == "inv-1"
        assert snapshot.sequence == 1
        assert snapshot.partial_prose == "abc"

    async def test_get_active_snapshot_returns_none_when_no_turn(
        self, store: SessionTurnStateStore
    ) -> None:
        assert await store.get_active_snapshot("ghost") is None

    async def test_get_active_partial_returns_prose_string(
        self, store: SessionTurnStateStore
    ) -> None:
        await store.register_active_turn("s-1", "inv-1")
        await store.record_chunk("s-1", "partial prose")

        assert await store.get_active_partial("s-1") == "partial prose"

    async def test_get_active_partial_returns_empty_when_no_turn(
        self, store: SessionTurnStateStore
    ) -> None:
        assert await store.get_active_partial("ghost") == ""
