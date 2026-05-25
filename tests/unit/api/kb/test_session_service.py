"""Unit tests for KBSessionService.

Tests session lifecycle: creation, field updates, AI suggestions,
interview questions, enhancement, completion, and abandonment.
Uses fakes for KBCreationSessionStore, KBAssistProtocol, and KBServiceProtocol.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from ._test_fakes import make_service, make_session

# ---------------------------------------------------------------------------
# Tests: create_session
# ---------------------------------------------------------------------------


class TestCreateSession:
    """Test session creation."""

    async def test_creates_session_with_template_fields(self) -> None:
        """create_session generates fields from template for entity type."""
        service, _, _ = make_service()
        novel_id = uuid4()
        user_id = uuid4()

        session = await service.create_session(
            novel_id=novel_id,
            user_id=user_id,
            entity_type="character",
        )

        assert session.novel_id == novel_id
        assert session.user_id == user_id
        assert session.entity_type == "character"
        assert session.status == "active"
        assert len(session.fields) > 0
        # Character template should have at least some fields
        field_keys = [f.field_key for f in session.fields]
        assert "role" in field_keys

    async def test_stores_session_in_store(self) -> None:
        """Created session is persisted in the store."""
        service, store, _ = make_service()

        session = await service.create_session(
            novel_id=uuid4(),
            user_id=uuid4(),
            entity_type="character",
        )

        # Verify the session was stored
        assert await store.get(session.id) is not None


# ---------------------------------------------------------------------------
# Tests: get_session
# ---------------------------------------------------------------------------


class TestGetSession:
    """Test session retrieval."""

    async def test_returns_session_when_found(self) -> None:
        """get_session returns the session if it exists."""
        service, store, _ = make_service()
        session = make_session()
        await store.create(session)

        result = await service.get_session(session.id)
        assert result is not None
        assert result.id == session.id

    async def test_returns_none_when_not_found(self) -> None:
        """get_session returns None for unknown ID."""
        service, _, _ = make_service()

        result = await service.get_session(uuid4())
        assert result is None


# ---------------------------------------------------------------------------
# Tests: answer_field
# ---------------------------------------------------------------------------


class TestAnswerField:
    """Test field answer updates."""

    async def test_updates_field_value(self) -> None:
        """answer_field sets user_value, source, and final_value."""
        service, store, _ = make_service()
        session = make_session()
        await store.create(session)

        updated = await service.answer_field(session.id, "name", "Aria")

        name_field = next(f for f in updated.fields if f.field_key == "name")
        assert name_field.user_value == "Aria"
        assert name_field.source == "user"
        assert name_field.final_value == "Aria"

    async def test_raises_for_unknown_field(self) -> None:
        """answer_field raises ValueError for non-existent field key."""
        service, store, _ = make_service()
        session = make_session()
        await store.create(session)

        with pytest.raises(ValueError, match="Field 'unknown' not found"):
            await service.answer_field(session.id, "unknown", "value")

    async def test_raises_for_inactive_session(self) -> None:
        """answer_field raises ValueError for non-active session."""
        service, store, _ = make_service()
        session = make_session(status="complete")
        await store.create(session)

        with pytest.raises(ValueError, match="has status 'complete'"):
            await service.answer_field(session.id, "name", "Aria")
