"""Tests for WritingSessionControlService (ADR-052 Phase 1 + 2).

Covers:
- ``stop_generation`` with an active turn returns ``stopped`` + partial.
- ``stop_generation`` without an active turn returns ``no_active_turn``.
- ``reattach_session`` live session returns ``recovered``.
- ``reattach_session`` missing session returns ``not_found``.
- ``reattach_session`` wrong user returns ``ownership_mismatch``.
- ``reattach_session`` inactive session returns ``expired``.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING
from uuid import uuid4

from narrare.writing._ws_cache import InMemorySessionCache
from narrare.writing.ws_active_turn_registry import ActiveTurnRegistry
from narrare.writing.ws_session_control_service import WritingSessionControlService
from narrare_core.writing._enums import StreamStatus
from narrare_core.writing.session_manager import SessionManager
from narrare_core.writing.session_turn_state import SessionTurnStateStore

if TYPE_CHECKING:
    from collections.abc import Mapping
    from uuid import UUID


class _RecordingSink:
    """Transport sink test double for reattach rebinding assertions."""

    def __init__(self) -> None:
        self.sent: list[dict[str, object]] = []

    async def send_json(self, data: Mapping[str, object]) -> None:
        self.sent.append(dict(data))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_service() -> tuple[
    WritingSessionControlService,
    SessionManager,
    SessionTurnStateStore,
    ActiveTurnRegistry,
    InMemorySessionCache,
]:
    cache = InMemorySessionCache()
    session_manager = SessionManager(cache=cache)
    turn_state = SessionTurnStateStore()
    registry = ActiveTurnRegistry()
    service = WritingSessionControlService(
        session_manager=session_manager,
        turn_state=turn_state,
        registry=registry,
    )
    return service, session_manager, turn_state, registry, cache


async def _seed_session(
    session_manager: SessionManager,
) -> tuple[UUID, UUID, UUID]:
    """Create a session and return (session_id, project_id, user_id)."""
    chapter_id = uuid4()
    project_id = uuid4()
    user_id = uuid4()
    session_id = await session_manager.create_session(
        chapter_id=chapter_id,
        project_id=project_id,
        user_id=user_id,
    )
    return session_id, project_id, user_id


# ---------------------------------------------------------------------------
# stop_generation
# ---------------------------------------------------------------------------


class TestStopGeneration:
    """WritingSessionControlService.stop_generation."""

    async def test_stop_with_active_turn_returns_stopped_and_partial(self) -> None:
        service, session_manager, turn_state, registry, _ = _make_service()
        session_id, _, _ = await _seed_session(session_manager)
        invocation_id = uuid4()

        # Register an active turn in both the turn-state store and the registry
        await turn_state.register_active_turn(
            str(session_id),
            str(invocation_id),
        )
        await turn_state.record_chunk(str(session_id), "partial ")
        await turn_state.record_chunk(str(session_id), "output")

        async def _sleep_forever() -> str | None:
            await asyncio.sleep(100)
            return None

        task = asyncio.ensure_future(_sleep_forever())
        await asyncio.sleep(0)
        registry.register(
            str(session_id),
            str(invocation_id),
            task=task,
            sink=registry.get_sink(str(session_id)),
        )

        result = await service.stop_generation(session_id, invocation_id)

        assert result["status"] == "stopped"
        assert result["partial_prose"] == "partial output"
        assert result["invocation_id"] == str(invocation_id)
        assert result["sequence"] == 2

        # Task was cancelled
        with contextlib.suppress(asyncio.CancelledError, TimeoutError):
            await asyncio.wait_for(task, timeout=2.0)
        assert task.cancelled() or task.done()

        # Turn state is cleared
        snapshot = await turn_state.get_active_snapshot(str(session_id))
        assert snapshot is None

    async def test_stop_without_active_turn_returns_no_active_turn(self) -> None:
        service, session_manager, *_ = _make_service()
        session_id, _, _ = await _seed_session(session_manager)
        invocation_id = uuid4()

        result = await service.stop_generation(session_id, invocation_id)

        assert result["status"] == "no_active_turn"
        assert result["partial_prose"] == ""
        assert result["invocation_id"] == str(invocation_id)
        assert result["sequence"] == 0


# ---------------------------------------------------------------------------
# reattach_session
# ---------------------------------------------------------------------------


class TestReattachSession:
    """WritingSessionControlService.reattach_session."""

    async def test_reattach_live_session_returns_recovered(self) -> None:
        service, session_manager, *_ = _make_service()
        session_id, project_id, user_id = await _seed_session(session_manager)

        result = await service.reattach_session(session_id, user_id, project_id)

        assert result["kind"] == "recovered"
        assert result["session_id"] == str(session_id)

    async def test_reattach_missing_session_returns_not_found(self) -> None:
        service, *_ = _make_service()

        result = await service.reattach_session(uuid4(), uuid4(), uuid4())

        assert result["kind"] == "not_found"

    async def test_reattach_wrong_user_returns_ownership_mismatch(self) -> None:
        service, session_manager, *_ = _make_service()
        session_id, project_id, _ = await _seed_session(session_manager)

        wrong_user = uuid4()
        result = await service.reattach_session(session_id, wrong_user, project_id)

        assert result["kind"] == "ownership_mismatch"

    async def test_reattach_inactive_session_returns_expired(self) -> None:
        service, session_manager, _, _, cache = _make_service()
        session_id, project_id, user_id = await _seed_session(session_manager)

        # Force-expire by setting is_active=False in the cached state
        # (end_session would delete the entry entirely → not_found;
        #  expired requires the entry to exist but be inactive)
        key = session_manager._cache_key(session_id)
        raw = await cache.get(key)
        assert raw is not None
        import json

        data = json.loads(raw)
        data["is_active"] = False
        await cache.set(key, json.dumps(data))

        result = await service.reattach_session(session_id, user_id, project_id)

        assert result["kind"] == "expired"

    async def test_reattach_wrong_project_returns_ownership_mismatch(self) -> None:
        service, session_manager, *_ = _make_service()
        session_id, _, user_id = await _seed_session(session_manager)

        wrong_project = uuid4()
        result = await service.reattach_session(session_id, user_id, wrong_project)

        assert result["kind"] == "ownership_mismatch"

    async def test_reattach_recovered_includes_snapshot_fields(self) -> None:
        """A recovered session includes recovery snapshot fields."""
        service, session_manager, *_ = _make_service()
        session_id, project_id, user_id = await _seed_session(session_manager)

        result = await service.reattach_session(session_id, user_id, project_id)

        assert result["kind"] == "recovered"
        assert "last_sequence" in result
        assert "active_partial_prose" in result
        assert "stream_status" in result

    async def test_reattach_rebinds_active_turn_sink(self) -> None:
        """A recovered live turn is rebound to the new transport sink."""
        service, session_manager, turn_state, registry, _ = _make_service()
        session_id, project_id, user_id = await _seed_session(session_manager)
        invocation_id = uuid4()
        old_sink = _RecordingSink()
        new_sink = _RecordingSink()

        await turn_state.register_active_turn(str(session_id), str(invocation_id))
        await turn_state.record_chunk(str(session_id), "live partial")

        async def _sleep_forever() -> str | None:
            await asyncio.sleep(100)
            return None

        task = asyncio.ensure_future(_sleep_forever())
        await asyncio.sleep(0)
        try:
            registry.register(
                str(session_id),
                str(invocation_id),
                task=task,
                sink=old_sink,
            )

            result = await service.reattach_session(
                session_id,
                user_id,
                project_id,
                new_sink=new_sink,
            )

            assert result["kind"] == "recovered"
            assert registry.get_sink(str(session_id)) is new_sink
            assert result.get("active_partial_prose") == "live partial"
            assert result.get("active_invocation_id") == str(invocation_id)
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def test_reattach_reconciles_streaming_without_live_handle_to_stopped(self) -> None:
        """Cold-start recovery marks stale streaming state as stopped."""
        service, session_manager, *_ = _make_service()
        session_id, project_id, user_id = await _seed_session(session_manager)
        state = await session_manager._load(session_id)
        assert state is not None
        state.stream_status = StreamStatus.STREAMING
        state.active_invocation_id = uuid4()
        state.active_partial_prose = "cached partial"
        await session_manager._persist(state)

        result = await service.reattach_session(
            session_id,
            user_id,
            project_id,
            new_sink=_RecordingSink(),
        )

        assert result["kind"] == "recovered"
        assert result.get("stream_status") == "stopped"
        assert result.get("active_partial_prose") == "cached partial"
