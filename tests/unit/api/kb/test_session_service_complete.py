"""Unit tests for KBSessionService — complete_session flow.

Tests the session completion flow: KB entry creation, error handling,
status validation, and edge cases.
Uses fakes for KBCreationSessionStore, KBAssistProtocol, and KBServiceProtocol.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from narrare.kb.schemas import KBEntryCreate
from narrare_core.shared.errors import NotFoundError

from ._test_fakes import FakeKBService, make_service, make_session

# ---------------------------------------------------------------------------
# Tests: complete_session
# ---------------------------------------------------------------------------


class TestCompleteSession:
    """Test session completion with KB entry creation."""

    async def test_happy_path_creates_entry_and_marks_complete(self) -> None:
        """complete_session creates KB entry and marks session complete."""
        fake_kb = FakeKBService()
        service, store, _ = make_service(kb_service=fake_kb)
        session = make_session(name="Aria")
        await store.create(session)

        result_session, entry_id = await service.complete_session(
            session.id, session.novel_id, session.user_id
        )

        assert result_session.status == "complete"
        assert isinstance(entry_id, UUID)
        # Session should still have its fields
        assert len(result_session.fields) == 2

    async def test_happy_path_returns_entry_id(self) -> None:
        """complete_session returns a valid UUID for the created entry."""
        fake_kb = FakeKBService()
        service, store, _ = make_service(kb_service=fake_kb)
        session = make_session(name="Aria")
        await store.create(session)

        _, entry_id = await service.complete_session(session.id, session.novel_id, session.user_id)

        assert isinstance(entry_id, UUID)
        assert str(entry_id) != "00000000-0000-0000-0000-000000000000"

    async def test_passes_entry_data_to_kb_service(self) -> None:
        """complete_session passes mapped entry data to kb_service.create."""
        created: list[dict[str, object]] = []
        fake_kb = FakeKBService(created_entries=created)
        service, store, _ = make_service(kb_service=fake_kb)
        session = make_session(name="Aria")
        await store.create(session)

        await service.complete_session(session.id, session.novel_id, session.user_id)

        assert len(created) == 1
        call_data = created[0]
        assert call_data["novel_id"] == session.novel_id
        assert call_data["user_id"] == session.user_id

    async def test_error_keeps_session_active(self) -> None:
        """If KB service fails, session stays in its original state."""
        fake_kb = FakeKBService(fail_on_create=True)
        service, store, _ = make_service(kb_service=fake_kb)
        session = make_session(name="Aria")
        await store.create(session)

        with pytest.raises(RuntimeError, match="KB service create failed"):
            await service.complete_session(session.id, session.novel_id, session.user_id)

        # Session should still be active
        stored = await store.get(session.id)
        assert stored is not None
        assert stored.status == "active"

    async def test_raises_for_session_not_found(self) -> None:
        """Unknown session ID raises NotFoundError (IDOR S7: 404 shape)."""
        fake_kb = FakeKBService()
        service, _, _ = make_service(kb_service=fake_kb)

        with pytest.raises(NotFoundError, match="not found"):
            await service.complete_session(uuid4(), uuid4(), uuid4())

    async def test_raises_for_invalid_status(self) -> None:
        """Session in 'abandoned' status raises ValueError."""
        fake_kb = FakeKBService()
        service, store, _ = make_service(kb_service=fake_kb)
        session = make_session(name="Aria", status="abandoned")
        await store.create(session)

        with pytest.raises(ValueError, match="has status 'abandoned'"):
            await service.complete_session(session.id, session.novel_id, session.user_id)

    async def test_raises_for_completed_session(self) -> None:
        """Already completed session raises ValueError."""
        fake_kb = FakeKBService()
        service, store, _ = make_service(kb_service=fake_kb)
        session = make_session(name="Aria", status="complete")
        await store.create(session)

        with pytest.raises(ValueError, match="has status 'complete'"):
            await service.complete_session(session.id, session.novel_id, session.user_id)

    async def test_raises_for_session_without_name(self) -> None:
        """Session without name raises ValueError (from mapper)."""
        fake_kb = FakeKBService()
        service, store, _ = make_service(kb_service=fake_kb)
        session = make_session(name=None)
        await store.create(session)

        with pytest.raises(ValueError, match="Session must have a name"):
            await service.complete_session(session.id, session.novel_id, session.user_id)

    async def test_body_name_fills_missing_session_name(self) -> None:
        """F9-1: name argument fills a missing session name before mapping."""
        created: list[dict[str, object]] = []
        fake_kb = FakeKBService(created_entries=created)
        service, store, _ = make_service(kb_service=fake_kb)
        session = make_session(name=None)
        await store.create(session)

        result_session, _entry_id = await service.complete_session(
            session.id, session.novel_id, session.user_id, name="Aria"
        )

        assert result_session.status == "complete"
        assert result_session.name == "Aria"
        entry_data = created[0]["data"]
        assert isinstance(entry_data, KBEntryCreate)
        assert entry_data.name == "Aria"

    async def test_name_argument_is_ignored_when_none(self) -> None:
        """name=None (absent body) keeps current behavior — mapper guard fires."""
        fake_kb = FakeKBService()
        service, store, _ = make_service(kb_service=fake_kb)
        session = make_session(name=None)
        await store.create(session)

        with pytest.raises(ValueError, match="Session must have a name"):
            await service.complete_session(session.id, session.novel_id, session.user_id, name=None)

    async def test_raises_without_kb_service(self) -> None:
        """Session service without kb_service raises ValueError."""
        service, store, _ = make_service(kb_service=None)
        session = make_session(name="Aria")
        await store.create(session)

        with pytest.raises(ValueError, match="KB service not configured"):
            await service.complete_session(session.id, session.novel_id, session.user_id)

    async def test_works_with_review_status(self) -> None:
        """Session in 'review' status can be completed."""
        fake_kb = FakeKBService()
        service, store, _ = make_service(kb_service=fake_kb)
        session = make_session(name="Aria", status="review")
        await store.create(session)

        result_session, entry_id = await service.complete_session(
            session.id, session.novel_id, session.user_id
        )

        assert result_session.status == "complete"
        assert isinstance(entry_id, UUID)
