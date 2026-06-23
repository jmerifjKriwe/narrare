"""Tests for SessionManager.reattach_session — ADR-052 Phase 2 Core recovery.

Extracted from ``test_session_manager.py`` for RULE-04 (the manager test
file exceeded the 400-line hard limit once reattach tests were added).

Covers:
- Happy path: live session, correct owner -> ``Reattached``.
- Missing session (cache miss) -> ``SessionNotFound``.
- Inactive session (``is_active=False``) -> ``SessionExpired``.
- Wrong user / wrong project -> ``OwnershipMismatch``.
- Pure-data invariant: reattach must NOT mutate ``connection_state``.
- Snapshot surfaces the ADR-052 recovery fields (invocation id, stream
  status, last sequence, active partial prose).
"""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from narrare_core.writing.session_manager import SessionManager
from tests.unit.core.writing.test_session_manager import InMemoryCache, _uuids

# ---------------------------------------------------------------------------
# Fixtures (reuse InMemoryCache from the canonical manager test module)
# ---------------------------------------------------------------------------


@pytest.fixture
def cache() -> InMemoryCache:
    return InMemoryCache()


@pytest.fixture
def manager(cache: InMemoryCache) -> SessionManager:
    return SessionManager(cache=cache)


# ---------------------------------------------------------------------------
# Reattach (ADR-052 Phase 2 Core)
# ---------------------------------------------------------------------------


class TestReattachSession:
    """SessionManager.reattach_session — pure-data recovery validation.

    Per ADR-052 Phase 2 Core: reattach validates ownership + liveness and
    returns a typed ``ReattachOutcome``.  It does NOT mutate the session's
    ``connection_state`` (the backend transport layer owns that transition).
    """

    async def test_reattach_live_session_returns_recovered(self, manager: SessionManager) -> None:
        from narrare_core.writing.requests import Reattached, ReattachOutcome

        chapter_id, project_id, user_id = _uuids()
        session_id = await manager.create_session(chapter_id, project_id, user_id)

        outcome = await manager.reattach_session(session_id, user_id, project_id)

        assert isinstance(outcome, Reattached)
        assert outcome.kind == "recovered"
        assert outcome.session_id == session_id
        assert outcome.project_id == project_id
        assert outcome.user_id == user_id
        # Static type-narrowing check for the discriminated union
        outcome_kind: ReattachOutcome = outcome
        assert outcome_kind.kind in {
            "recovered",
            "not_found",
            "expired",
            "ownership_mismatch",
        }

    async def test_reattach_missing_session_returns_not_found(
        self, manager: SessionManager
    ) -> None:
        from narrare_core.writing.requests import SessionNotFound

        _chapter_id, project_id, user_id = _uuids()
        missing = uuid4()

        outcome = await manager.reattach_session(missing, user_id, project_id)

        assert isinstance(outcome, SessionNotFound)
        assert outcome.kind == "not_found"
        assert outcome.session_id == missing

    async def test_reattach_inactive_session_returns_expired(
        self,
        manager: SessionManager,
        cache: InMemoryCache,
    ) -> None:
        from narrare_core.writing.requests import SessionExpired

        chapter_id, project_id, user_id = _uuids()
        session_id = await manager.create_session(chapter_id, project_id, user_id)

        # Flip is_active=False in the cached JSON (session still present, but ended)
        key = f"writing:session:{session_id}"
        raw = cache._data[key]
        data = json.loads(raw)
        data["is_active"] = False
        cache._data[key] = json.dumps(data)

        outcome = await manager.reattach_session(session_id, user_id, project_id)

        assert isinstance(outcome, SessionExpired)
        assert outcome.kind == "expired"
        assert outcome.session_id == session_id

    async def test_reattach_wrong_user_returns_ownership_mismatch(
        self, manager: SessionManager
    ) -> None:
        from narrare_core.writing.requests import OwnershipMismatch

        chapter_id, project_id, user_id = _uuids()
        session_id = await manager.create_session(chapter_id, project_id, user_id)

        other_user = uuid4()
        outcome = await manager.reattach_session(session_id, other_user, project_id)

        assert isinstance(outcome, OwnershipMismatch)
        assert outcome.kind == "ownership_mismatch"
        assert outcome.session_id == session_id
        assert outcome.user_id == other_user

    async def test_reattach_wrong_project_returns_ownership_mismatch(
        self, manager: SessionManager
    ) -> None:
        from narrare_core.writing.requests import OwnershipMismatch

        chapter_id, project_id, user_id = _uuids()
        session_id = await manager.create_session(chapter_id, project_id, user_id)

        other_project = uuid4()
        outcome = await manager.reattach_session(session_id, user_id, other_project)

        assert isinstance(outcome, OwnershipMismatch)
        assert outcome.kind == "ownership_mismatch"

    async def test_reattach_does_not_mutate_connection_state(
        self,
        manager: SessionManager,
        cache: InMemoryCache,
    ) -> None:
        """Pure-data invariant: reattach must NOT mutate the cached SessionState.

        The backend transport layer owns ``connection_state`` transitions
        (disconnected -> reattaching -> connected).  Core's reattach is a
        read-only validation + snapshot.
        """
        chapter_id, project_id, user_id = _uuids()
        session_id = await manager.create_session(chapter_id, project_id, user_id)

        # Mutate the cached state to a non-default connection_state to make
        # the invariant observable.
        key = f"writing:session:{session_id}"
        data = json.loads(cache._data[key])
        data["connection_state"] = "disconnected"
        cache._data[key] = json.dumps(data)

        await manager.reattach_session(session_id, user_id, project_id)

        # The persisted state must be unchanged (still "disconnected", NOT "reattaching")
        post_state = await manager.get_session(session_id)
        assert post_state is not None
        assert post_state.connection_state.value == "disconnected"

    async def test_reattach_snapshot_reflects_recovery_fields(
        self, manager: SessionManager, cache: InMemoryCache
    ) -> None:
        """The recovered snapshot must surface the ADR-052 recovery fields."""
        from narrare_core.writing._enums import StreamStatus
        from narrare_core.writing.requests import Reattached

        chapter_id, project_id, user_id = _uuids()
        session_id = await manager.create_session(chapter_id, project_id, user_id)
        invocation = uuid4()

        # Inject non-default recovery state into the cache
        key = f"writing:session:{session_id}"
        data = json.loads(cache._data[key])
        data["active_invocation_id"] = str(invocation)
        data["stream_status"] = StreamStatus.STREAMING.value
        data["last_sequence"] = 7
        data["active_partial_prose"] = "in-flight prose"
        cache._data[key] = json.dumps(data)

        outcome = await manager.reattach_session(session_id, user_id, project_id)

        assert isinstance(outcome, Reattached)
        assert outcome.active_invocation_id == invocation
        assert outcome.stream_status is StreamStatus.STREAMING
        assert outcome.last_sequence == 7
        assert outcome.active_partial_prose == "in-flight prose"
