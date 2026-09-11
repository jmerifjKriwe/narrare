"""Shared fakes and helpers for KB session service tests.

Provides in-memory fakes for KBCreationSessionStore, KBAssistProtocol,
and KBServiceProtocol, plus factory helpers. The KB improve/worldbuilding
fakes live in ``_test_fakes_improve_worldbuilding.py`` (RULE-04 split).
"""

from __future__ import annotations

from dataclasses import dataclass
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

if TYPE_CHECKING:
    from narrare.kb.assist_contracts import KBAssistProtocol
    from narrare.kb.contracts import KBServiceProtocol
    from narrare.kb.session_store import KBCreationSessionStore
    from narrare.novels.contracts import NovelRepositoryProtocol


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


class FakeNovelRepo:
    """Fake NovelRepositoryProtocol for the create-time ownership gate.

    Permissive by default (owns everything) so non-ownership tests keep
    working; pass an explicit ``ownership`` map ``{novel_id: user_id}``
    to model real ownership (used by the S7 ownership matrix).
    """

    def __init__(self, ownership: dict[UUID, UUID] | None = None) -> None:
        self._ownership = ownership
        self.get_by_id_calls: list[tuple[UUID, UUID]] = []

    async def get_by_id(self, novel_id: UUID, user_id: UUID) -> object | None:
        self.get_by_id_calls.append((novel_id, user_id))
        if self._ownership is None or self._ownership.get(novel_id) == user_id:
            return object()  # the gate only checks existence
        return None


class CountingSessionStore(FakeSessionStore):
    """FakeSessionStore that records every mutation for side-effect asserts."""

    def __init__(self) -> None:
        super().__init__()
        self.create_calls: list[UUID] = []
        self.update_calls: list[UUID] = []
        self.delete_calls: list[UUID] = []

    async def create(self, session: KBCreationSession) -> KBCreationSession:
        self.create_calls.append(session.id)
        return await super().create(session)

    async def update(self, session: KBCreationSession) -> KBCreationSession:
        self.update_calls.append(session.id)
        return await super().update(session)

    async def delete(self, session_id: UUID) -> None:
        self.delete_calls.append(session_id)
        await super().delete(session_id)


class CountingAssistService(FakeAssistService):
    """FakeAssistService that counts AI invocations.

    Overrides carry the parent's explicit keyword-only signatures (no
    ``**kwargs`` indirection) so the fake stays structurally assignable
    to ``KBAssistProtocol`` without suppressions (RULE-23).
    """

    def __init__(self) -> None:
        super().__init__()
        self.ai_calls: int = 0

    async def get_suggestion(
        self,
        *,
        novel_id: UUID,
        entity_type: str,
        field_key: str,
        existing_fields: dict[str, str],
    ) -> KBAssistSuggestionResponse:
        self.ai_calls += 1
        return await super().get_suggestion(
            novel_id=novel_id,
            entity_type=entity_type,
            field_key=field_key,
            existing_fields=existing_fields,
        )

    async def get_interview_question(
        self,
        *,
        novel_id: UUID,
        entity_type: str,
        existing_fields: dict[str, str],
    ) -> KBAssistQuestionResponse:
        self.ai_calls += 1
        return await super().get_interview_question(
            novel_id=novel_id,
            entity_type=entity_type,
            existing_fields=existing_fields,
        )

    async def get_enhancement(
        self,
        *,
        novel_id: UUID,
        entity_type: str,
        existing_fields: dict[str, str],
    ) -> KBAssistEnhancementResponse:
        self.ai_calls += 1
        return await super().get_enhancement(
            novel_id=novel_id,
            entity_type=entity_type,
            existing_fields=existing_fields,
        )


def make_owned_session(
    novel_id: UUID, user_id: UUID, name: str | None = "Aria"
) -> KBCreationSession:
    """A session owned by ``user_id`` under ``novel_id`` (the victim's resource)."""
    return make_session(name=name).model_copy(update={"novel_id": novel_id, "user_id": user_id})


def make_ownership_service(
    ownership: dict[UUID, UUID],
) -> tuple[
    KBSessionService, CountingSessionStore, CountingAssistService, FakeKBService, FakeNovelRepo
]:
    """Build a KBSessionService over counting fakes + a novel ownership map."""
    store = CountingSessionStore()
    assist = CountingAssistService()
    kb = FakeKBService(created_entries=[])
    novel_repo = FakeNovelRepo(ownership)
    service = KBSessionService(
        session_store=cast("KBCreationSessionStore", store),
        assist_service=cast("KBAssistProtocol", assist),
        novel_repo=cast("NovelRepositoryProtocol", novel_repo),
        kb_service=cast("KBServiceProtocol", kb),
    )
    return service, store, assist, kb, novel_repo


def make_service(
    assist: FakeAssistService | None = None,
    kb_service: FakeKBService | None = None,
    novel_repo: FakeNovelRepo | None = None,
) -> tuple[KBSessionService, FakeSessionStore, FakeAssistService]:
    """Create a KBSessionService with fake dependencies."""
    store = FakeSessionStore()
    fake_assist = assist or FakeAssistService()
    fake_kb = kb_service
    service = KBSessionService(
        session_store=store,  # type: ignore[arg-type]
        assist_service=fake_assist,  # type: ignore[arg-type]
        novel_repo=cast("NovelRepositoryProtocol", novel_repo or FakeNovelRepo()),
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
