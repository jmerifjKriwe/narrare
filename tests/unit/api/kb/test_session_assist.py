"""Unit tests for KBSessionService — AI-assisted operations.

Tests request_suggestion, request_interview_question, request_enhancement.
Uses fakes from test_session_service via conftest import.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

from narrare.kb.assist_contracts import (
    KBAssistEnhancementResponse,
    KBAssistQuestionResponse,
    KBAssistSuggestionResponse,
)
from narrare.kb.session_models import KBCreationField, KBCreationSession
from narrare.kb.session_service import KBSessionService

from ._test_fakes import FakeNovelRepo

if TYPE_CHECKING:
    from narrare.novels.contracts import NovelRepositoryProtocol

# ---------------------------------------------------------------------------
# Fakes (duplicated from test_session_service for isolation)
# ---------------------------------------------------------------------------


class _FakeStore:
    """Minimal in-memory fake for KBCreationSessionStore."""

    def __init__(self) -> None:
        self._store: dict[UUID, KBCreationSession] = {}

    async def create(self, s: KBCreationSession) -> KBCreationSession:
        self._store[s.id] = s
        return s

    async def get(self, sid: UUID) -> KBCreationSession | None:
        return self._store.get(sid)

    async def update(self, s: KBCreationSession) -> KBCreationSession:
        self._store[s.id] = s
        return s

    async def delete(self, sid: UUID) -> None:
        self._store.pop(sid, None)


class _FakeAssist:
    """Minimal fake KBAssistProtocol for tests."""

    def __init__(self) -> None:
        self.last_suggestion_args: dict[str, object] | None = None
        self.last_question_args: dict[str, object] | None = None
        self.last_enhancement_args: dict[str, object] | None = None

    async def get_suggestion(self, **kwargs: object) -> KBAssistSuggestionResponse:
        self.last_suggestion_args = kwargs
        return KBAssistSuggestionResponse(
            field_key=str(kwargs.get("field_key", "name")),
            suggestion="A fitting name",
            reasoning="It matches the genre",
        )

    async def get_interview_question(self, **kwargs: object) -> KBAssistQuestionResponse:
        self.last_question_args = kwargs
        return KBAssistQuestionResponse(
            field_key="name",
            question="What is the character's name?",
            reasoning="Name is fundamental",
        )

    async def get_enhancement(self, **kwargs: object) -> KBAssistEnhancementResponse:
        self.last_enhancement_args = kwargs
        return KBAssistEnhancementResponse(
            draft_entry={"name": "Elena", "role": "protagonist"},
            progress=0.6,
            reasoning="Based on genre conventions",
        )


def _make_session(**kwargs: object) -> KBCreationSession:
    """Create a minimal test session."""
    session = KBCreationSession(
        id=uuid4(),
        novel_id=uuid4(),
        user_id=uuid4(),
        entity_type="character",
        fields=[
            KBCreationField(field_key="name", label="Name", required=True),
            KBCreationField(field_key="role", label="Role"),
        ],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    if kwargs:
        session = session.model_copy(update=kwargs)  # type: ignore[arg-type]
    return session


def _make_service() -> tuple[KBSessionService, _FakeStore, _FakeAssist]:
    """Create a KBSessionService with fakes for testing."""
    store = _FakeStore()
    assist = _FakeAssist()
    service = KBSessionService(
        session_store=store,  # type: ignore[arg-type]
        assist_service=assist,
        novel_repo=cast("NovelRepositoryProtocol", FakeNovelRepo()),
    )
    return service, store, assist


# ---------------------------------------------------------------------------
# Tests: request_suggestion
# ---------------------------------------------------------------------------


class TestRequestSuggestion:
    """Test AI suggestion requests."""

    async def test_calls_assist_service(self) -> None:
        """request_suggestion delegates to KBAssistProtocol."""
        service, store, fake_assist = _make_service()
        session = _make_session()
        await store.create(session)

        updated, suggestion = await service.request_suggestion(
            session.id, session.novel_id, session.user_id, "name"
        )

        assert fake_assist.last_suggestion_args is not None
        assert fake_assist.last_suggestion_args["field_key"] == "name"
        assert suggestion["field_key"] == "name"
        assert "suggestion" in suggestion
        assert updated.id == session.id

    async def test_updates_field_with_suggestion(self) -> None:
        """request_suggestion stores ai_suggested_value on the field."""
        service, store, _ = _make_service()
        session = _make_session()
        await store.create(session)

        updated, _ = await service.request_suggestion(
            session.id, session.novel_id, session.user_id, "name"
        )

        name_field = next(f for f in updated.fields if f.field_key == "name")
        assert name_field.ai_suggested_value is not None
        assert name_field.ai_reasoning is not None


class TestRequestInterviewQuestion:
    """Test interview question requests."""

    async def test_calls_assist_service(self) -> None:
        """request_interview_question delegates to KBAssistProtocol."""
        service, store, fake_assist = _make_service()
        session = _make_session()
        await store.create(session)

        _updated, question = await service.request_interview_question(
            session.id, session.novel_id, session.user_id
        )

        assert fake_assist.last_question_args is not None
        assert "entity_type" in fake_assist.last_question_args
        assert question["field_key"] == "name"
        assert "question" in question

    async def test_passes_existing_fields(self) -> None:
        """interview question includes already-answered fields."""
        service, store, fake_assist = _make_service()
        session = _make_session()
        await store.create(session)
        await service.answer_field(session.id, session.novel_id, session.user_id, "name", "Elena")

        await service.request_interview_question(session.id, session.novel_id, session.user_id)

        assert fake_assist.last_question_args is not None


class TestRequestEnhancement:
    """Test enhancement requests."""

    async def test_calls_assist_service(self) -> None:
        """request_enhancement delegates to KBAssistProtocol."""
        service, store, fake_assist = _make_service()
        session = _make_session()
        await store.create(session)

        _updated, enhancement = await service.request_enhancement(
            session.id, session.novel_id, session.user_id
        )

        assert fake_assist.last_enhancement_args is not None
        assert "draft_entry" in enhancement
        assert enhancement["progress"] == 0.6

    async def test_updates_fields_from_draft(self) -> None:
        """request_enhancement updates fields from draft_entry."""
        service, store, _ = _make_service()
        session = _make_session()
        await store.create(session)

        updated, _ = await service.request_enhancement(
            session.id, session.novel_id, session.user_id
        )

        name_field = next(f for f in updated.fields if f.field_key == "name")
        assert name_field.ai_suggested_value is not None

    async def test_does_not_override_user_values(self) -> None:
        """Enhancement does not replace user-provided values."""
        service, store, _ = _make_service()
        session = _make_session()
        await store.create(session)
        await service.answer_field(
            session.id, session.novel_id, session.user_id, "name", "UserChosenName"
        )

        updated, _ = await service.request_enhancement(
            session.id, session.novel_id, session.user_id
        )

        name_field = next(f for f in updated.fields if f.field_key == "name")
        assert name_field.user_value == "UserChosenName"
        assert name_field.final_value == "UserChosenName"
