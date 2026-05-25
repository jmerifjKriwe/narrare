"""Unit tests for KBSessionService.

Tests session lifecycle: creation, field updates, AI suggestions,
interview questions, enhancement, completion, and abandonment.
Uses fakes for KBCreationSessionStore and KBAssistProtocol.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from narrare.kb.assist_contracts import (
    KBAssistEnhancementResponse,
    KBAssistQuestionResponse,
    KBAssistSuggestionResponse,
)
from narrare.kb.session_models import KBCreationField, KBCreationSession
from narrare.kb.session_service import KBSessionService

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeSessionStore:
    """In-memory fake for KBCreationSessionStore."""

    def __init__(self) -> None:
        self._store: dict[UUID, KBCreationSession] = {}

    async def create(self, session: KBCreationSession) -> KBCreationSession:
        self._store[session.id] = session
        return session

    async def get(self, session_id: UUID) -> KBCreationSession | None:
        return self._store.get(session_id)

    async def update(self, session: KBCreationSession) -> KBCreationSession:
        self._store[session.id] = session
        return session

    async def delete(self, session_id: UUID) -> None:
        self._store.pop(session_id, None)


class FakeAssistService:
    """Fake KBAssistProtocol for tests."""

    def __init__(
        self,
        suggestion: KBAssistSuggestionResponse | None = None,
        question: KBAssistQuestionResponse | None = None,
        enhancement: KBAssistEnhancementResponse | None = None,
    ) -> None:
        self._suggestion = suggestion
        self._question = question
        self._enhancement = enhancement
        self.last_suggestion_args: dict[str, object] | None = None
        self.last_question_args: dict[str, object] | None = None
        self.last_enhancement_args: dict[str, object] | None = None

    async def get_suggestion(
        self,
        *,
        novel_id: UUID,
        entity_type: str,
        field_key: str,
        existing_fields: dict[str, str],
    ) -> KBAssistSuggestionResponse:
        self.last_suggestion_args = {
            "novel_id": novel_id,
            "entity_type": entity_type,
            "field_key": field_key,
            "existing_fields": existing_fields,
        }
        if self._suggestion is not None:
            return self._suggestion
        return KBAssistSuggestionResponse(
            field_key=field_key,
            suggestion="A brave warrior",
            reasoning="Based on story context",
            context_used=["world_derived"],
        )

    async def get_interview_question(
        self,
        *,
        novel_id: UUID,
        entity_type: str,
        existing_fields: dict[str, str],
    ) -> KBAssistQuestionResponse:
        self.last_question_args = {
            "novel_id": novel_id,
            "entity_type": entity_type,
            "existing_fields": existing_fields,
        }
        if self._question is not None:
            return self._question
        return KBAssistQuestionResponse(
            field_key="name",
            question="What is the character's name?",
            reasoning="Name is the most fundamental attribute",
        )

    async def get_enhancement(
        self,
        *,
        novel_id: UUID,
        entity_type: str,
        existing_fields: dict[str, str],
    ) -> KBAssistEnhancementResponse:
        self.last_enhancement_args = {
            "novel_id": novel_id,
            "entity_type": entity_type,
            "existing_fields": existing_fields,
        }
        if self._enhancement is not None:
            return self._enhancement
        return KBAssistEnhancementResponse(
            draft_entry={"name": "Aria", "role": "protagonist"},
            progress=0.6,
            reasoning="Generated from existing context",
            context_used=["world_derived"],
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service(
    assist: FakeAssistService | None = None,
) -> tuple[KBSessionService, FakeSessionStore, FakeAssistService]:
    """Create a KBSessionService with fake dependencies."""
    store = FakeSessionStore()
    fake_assist = assist or FakeAssistService()
    service = KBSessionService(session_store=store, assist_service=fake_assist)  # type: ignore[arg-type]
    return service, store, fake_assist


def _make_session(
    entity_type: str = "character",
    status: str = "active",
    fields: list[KBCreationField] | None = None,
) -> KBCreationSession:
    """Create a test session."""
    if fields is None:
        fields = [
            KBCreationField(field_key="name", label="Name", required=True),
            KBCreationField(field_key="role", label="Role"),
        ]
    return KBCreationSession(
        id=uuid4(),
        novel_id=uuid4(),
        user_id=uuid4(),
        entity_type=entity_type,
        status=status,  # type: ignore[arg-type]
        fields=fields,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Tests: create_session
# ---------------------------------------------------------------------------


class TestCreateSession:
    """Test session creation."""

    async def test_creates_session_with_template_fields(self) -> None:
        """create_session generates fields from template for entity type."""
        service, _, _ = _make_service()
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
        service, store, _ = _make_service()

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
        service, store, _ = _make_service()
        session = _make_session()
        await store.create(session)

        result = await service.get_session(session.id)
        assert result is not None
        assert result.id == session.id

    async def test_returns_none_when_not_found(self) -> None:
        """get_session returns None for unknown ID."""
        service, _, _ = _make_service()

        result = await service.get_session(uuid4())
        assert result is None


# ---------------------------------------------------------------------------
# Tests: answer_field
# ---------------------------------------------------------------------------


class TestAnswerField:
    """Test field answer updates."""

    async def test_updates_field_value(self) -> None:
        """answer_field sets user_value, source, and final_value."""
        service, store, _ = _make_service()
        session = _make_session()
        await store.create(session)

        updated = await service.answer_field(session.id, "name", "Aria")

        name_field = next(f for f in updated.fields if f.field_key == "name")
        assert name_field.user_value == "Aria"
        assert name_field.source == "user"
        assert name_field.final_value == "Aria"

    async def test_raises_for_unknown_field(self) -> None:
        """answer_field raises ValueError for non-existent field key."""
        service, store, _ = _make_service()
        session = _make_session()
        await store.create(session)

        with pytest.raises(ValueError, match="Field 'unknown' not found"):
            await service.answer_field(session.id, "unknown", "value")

    async def test_raises_for_inactive_session(self) -> None:
        """answer_field raises ValueError for non-active session."""
        service, store, _ = _make_service()
        session = _make_session(status="complete")
        await store.create(session)

        with pytest.raises(ValueError, match="has status 'complete'"):
            await service.answer_field(session.id, "name", "Aria")


# ---------------------------------------------------------------------------
