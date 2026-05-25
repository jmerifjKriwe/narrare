"""Shared fakes and helpers for KB session service tests.

Provides in-memory fakes for KBCreationSessionStore, KBAssistProtocol,
and KBServiceProtocol, plus factory helpers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from narrare.kb.assist_contracts import (
    KBAssistEnhancementResponse,
    KBAssistQuestionResponse,
    KBAssistSuggestionResponse,
)
from narrare.kb.session_models import KBCreationField, KBCreationSession
from narrare.kb.session_service import KBSessionService


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


@dataclass
class FakeKBService:
    """Fake KBServiceProtocol — stores created entries with generated UUID.

    Can be configured to raise on create for error-path testing.
    """

    fail_on_create: bool = False
    created_entries: list[dict[str, object]] | None = None

    async def create(
        self,
        novel_id: UUID,
        user_id: UUID,
        data: object,
    ) -> object:
        """Fake create — returns an object with .id."""
        if self.fail_on_create:
            msg = "KB service create failed"
            raise RuntimeError(msg)

        if self.created_entries is not None:
            self.created_entries.append(
                {
                    "novel_id": novel_id,
                    "user_id": user_id,
                    "data": data,
                }
            )

        return _FakeEntry(id=uuid4())


@dataclass
class _FakeEntry:
    """Minimal fake KB entry returned by FakeKBService."""

    id: UUID


def make_service(
    assist: FakeAssistService | None = None,
    kb_service: FakeKBService | None = None,
) -> tuple[KBSessionService, FakeSessionStore, FakeAssistService]:
    """Create a KBSessionService with fake dependencies."""
    store = FakeSessionStore()
    fake_assist = assist or FakeAssistService()
    fake_kb = kb_service
    service = KBSessionService(
        session_store=store,  # type: ignore[arg-type]
        assist_service=fake_assist,  # type: ignore[arg-type]
        kb_service=fake_kb,  # type: ignore[arg-type]
    )
    return service, store, fake_assist


def make_session(
    entity_type: str = "character",
    status: str = "active",
    fields: list[KBCreationField] | None = None,
    name: str | None = None,
) -> KBCreationSession:
    """Create a test session.

    When name is None (default), the session gets no name field.
    Pass a string to test completion flow.
    """
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
        name=name,
        status=status,  # type: ignore[arg-type]
        fields=fields,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
